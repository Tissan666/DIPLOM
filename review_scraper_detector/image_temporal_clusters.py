"""Temporal customer-photo cluster signals for coordinated review campaigns."""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass

import pandas as pd

from .image_signals import _fingerprint_image_url, normalize_image_urls


DEFAULT_TEMPORAL_WINDOW_HOURS = 48.0
TEMPORAL_CLUSTER_FLAG_THRESHOLD = 0.55


@dataclass(frozen=True)
class _TemporalPhotoCluster:
    fingerprint: str
    row_positions: tuple[int, ...]
    author_count: int
    span_hours: float
    score: float
    start_time: pd.Timestamp
    end_time: pd.Timestamp


def build_image_temporal_cluster_signals(
    review_df: pd.DataFrame,
    window_hours: float | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Flag reused customer photos that appear across authors inside a short time window."""
    frame = review_df.copy()
    configured_window_hours = _resolve_window_hours(window_hours)
    row_count = len(frame)
    if "image_urls" not in frame.columns:
        frame["image_urls"] = [[] for _ in range(row_count)]

    fingerprints_by_row: list[list[str]] = []
    rows_by_fingerprint: dict[str, set[int]] = defaultdict(set)
    for row_position, value in enumerate(frame["image_urls"].tolist()):
        fingerprints = _fingerprints_for_images(value)
        fingerprints_by_row.append(fingerprints)
        for fingerprint in fingerprints:
            rows_by_fingerprint[fingerprint].add(row_position)

    timestamps = [_extract_timestamp(row) for _, row in frame.reset_index(drop=True).iterrows()]
    author_keys = [_author_key(row.get("author", "")) for _, row in frame.reset_index(drop=True).iterrows()]
    best_by_row = [_empty_row_signal(configured_window_hours) for _ in range(row_count)]
    clusters: list[_TemporalPhotoCluster] = []

    for fingerprint, row_positions in rows_by_fingerprint.items():
        if len(row_positions) < 2:
            continue
        cluster = _best_temporal_cluster_for_fingerprint(
            fingerprint=fingerprint,
            row_positions=sorted(row_positions),
            timestamps=timestamps,
            author_keys=author_keys,
            window_hours=configured_window_hours,
        )
        if cluster is None:
            continue
        clusters.append(cluster)
        for row_position in cluster.row_positions:
            if cluster.score <= float(best_by_row[row_position]["image_temporal_cluster_score"]):
                continue
            best_by_row[row_position] = {
                "image_temporal_cluster_score": float(cluster.score),
                "image_temporal_cluster_flag": int(cluster.score >= TEMPORAL_CLUSTER_FLAG_THRESHOLD),
                "image_temporal_cluster_size": int(len(cluster.row_positions)),
                "image_temporal_cluster_author_count": int(cluster.author_count),
                "image_temporal_cluster_window_hours": float(configured_window_hours),
                "image_temporal_cluster_fingerprint": cluster.fingerprint[:12],
                "image_temporal_cluster_reasons": _build_temporal_cluster_reasons(cluster),
            }

    signal_columns = best_by_row[0].keys() if best_by_row else _empty_row_signal(configured_window_hours).keys()
    for column in signal_columns:
        frame[column] = [row_signal[column] for row_signal in best_by_row]

    photo_reviews = _count_photo_reviews(frame)
    flagged_reviews = int(sum(int(row["image_temporal_cluster_flag"]) for row in best_by_row))
    flagged_clusters = [cluster for cluster in clusters if cluster.score >= TEMPORAL_CLUSTER_FLAG_THRESHOLD]
    flagged_ratio = float(flagged_reviews / photo_reviews) if photo_reviews else 0.0
    largest_cluster = int(max((len(cluster.row_positions) for cluster in flagged_clusters), default=0))

    summary = {
        "photo_temporal_cluster_reviews": flagged_reviews,
        "photo_temporal_cluster_ratio": flagged_ratio,
        "photo_temporal_cluster_count": len(flagged_clusters),
        "largest_photo_temporal_cluster": largest_cluster,
        "photo_temporal_cluster_risk": _temporal_cluster_risk(flagged_ratio, largest_cluster),
        "photo_temporal_cluster_window_hours": float(configured_window_hours),
        "photo_temporal_clusters": [
            {
                "fingerprint": cluster.fingerprint[:12],
                "review_count": int(len(cluster.row_positions)),
                "author_count": int(cluster.author_count),
                "span_hours": round(float(cluster.span_hours), 2),
                "score": round(float(cluster.score), 3),
                "review_indices": [int(position + 1) for position in cluster.row_positions],
                "start_time": cluster.start_time.isoformat(),
                "end_time": cluster.end_time.isoformat(),
            }
            for cluster in sorted(flagged_clusters, key=lambda item: item.score, reverse=True)[:5]
        ],
    }
    return frame, summary


def _resolve_window_hours(window_hours: float | None) -> float:
    if window_hours is not None:
        return max(float(window_hours), 1.0)
    raw_value = os.getenv("REVIEW_IMAGE_CLUSTER_WINDOW_HOURS", "").strip()
    if not raw_value:
        return DEFAULT_TEMPORAL_WINDOW_HOURS
    try:
        return max(float(raw_value), 1.0)
    except ValueError:
        return DEFAULT_TEMPORAL_WINDOW_HOURS


def _fingerprints_for_images(value: object) -> list[str]:
    fingerprints: list[str] = []
    seen: set[str] = set()
    for url in normalize_image_urls(value):
        fingerprint = _fingerprint_image_url(url)
        if not fingerprint or fingerprint in seen:
            continue
        seen.add(fingerprint)
        fingerprints.append(fingerprint)
    return fingerprints


def _extract_timestamp(row: pd.Series) -> pd.Timestamp | None:
    for column in ("date", "created_at", "timestamp", "review_date", "published_at"):
        value = row.get(column, "")
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        parsed = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(parsed):
            continue
        return parsed
    return None


def _author_key(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return " ".join(str(value).strip().lower().split())


def _best_temporal_cluster_for_fingerprint(
    fingerprint: str,
    row_positions: list[int],
    timestamps: list[pd.Timestamp | None],
    author_keys: list[str],
    window_hours: float,
) -> _TemporalPhotoCluster | None:
    entries = [
        (row_position, timestamps[row_position], author_keys[row_position])
        for row_position in row_positions
        if timestamps[row_position] is not None
    ]
    if len(entries) < 2:
        return None
    entries.sort(key=lambda item: item[1])

    best_cluster: _TemporalPhotoCluster | None = None
    for start_index, (_, start_time, _) in enumerate(entries):
        cluster_positions: list[int] = []
        cluster_authors: set[str] = set()
        end_time = start_time
        for row_position, current_time, author_key in entries[start_index:]:
            if current_time is None or start_time is None:
                continue
            span_hours = max((current_time - start_time).total_seconds() / 3600, 0.0)
            if span_hours > window_hours:
                break
            cluster_positions.append(row_position)
            if author_key:
                cluster_authors.add(author_key)
            end_time = current_time

            unique_positions = tuple(sorted(set(cluster_positions)))
            author_count = len(cluster_authors)
            if len(unique_positions) < 2 or author_count < 2:
                continue
            score = _score_temporal_cluster(
                review_count=len(unique_positions),
                author_count=author_count,
                span_hours=span_hours,
                window_hours=window_hours,
            )
            if best_cluster is None or score > best_cluster.score:
                best_cluster = _TemporalPhotoCluster(
                    fingerprint=fingerprint,
                    row_positions=unique_positions,
                    author_count=author_count,
                    span_hours=span_hours,
                    score=score,
                    start_time=start_time,
                    end_time=end_time,
                )
    return best_cluster


def _score_temporal_cluster(review_count: int, author_count: int, span_hours: float, window_hours: float) -> float:
    if review_count < 2 or author_count < 2:
        return 0.0
    size_component = min(review_count / 4, 1.0)
    author_component = min(author_count / 3, 1.0)
    time_component = 1.0 - min(max(span_hours / max(window_hours, 1.0), 0.0), 1.0)
    return float(min(max(0.34 * size_component + 0.38 * author_component + 0.28 * time_component, 0.0), 1.0))


def _build_temporal_cluster_reasons(cluster: _TemporalPhotoCluster) -> list[str]:
    review_count = len(cluster.row_positions)
    span_hours = round(cluster.span_hours, 1)
    if review_count >= 4:
        return [
            f"The same customer photo appears across {review_count} reviews by {cluster.author_count} authors within {span_hours} hours."
        ]
    return [
        f"The same customer photo appears across different authors within a short {span_hours}-hour window."
    ]


def _empty_row_signal(window_hours: float) -> dict:
    return {
        "image_temporal_cluster_score": 0.0,
        "image_temporal_cluster_flag": 0,
        "image_temporal_cluster_size": 0,
        "image_temporal_cluster_author_count": 0,
        "image_temporal_cluster_window_hours": float(window_hours),
        "image_temporal_cluster_fingerprint": "",
        "image_temporal_cluster_reasons": [],
    }


def _count_photo_reviews(frame: pd.DataFrame) -> int:
    if "image_count" in frame.columns:
        return int(sum(_safe_int(count) > 0 for count in frame["image_count"].tolist()))
    return int(sum(len(normalize_image_urls(value)) > 0 for value in frame["image_urls"].tolist()))


def _temporal_cluster_risk(flagged_ratio: float, largest_cluster: int) -> str:
    if flagged_ratio <= 0 or largest_cluster <= 1:
        return "none"
    if flagged_ratio >= 0.30 or largest_cluster >= 5:
        return "high"
    if flagged_ratio >= 0.16 or largest_cluster >= 3:
        return "medium"
    return "low"


def _safe_int(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, float) and pd.isna(value):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
