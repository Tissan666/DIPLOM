"""Customer image forensics signals for review-level fraud analysis."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from urllib.parse import parse_qsl, urlparse, urlunparse

import pandas as pd

IMAGE_QUERY_NOISE_KEYS = {
    "cache",
    "cb",
    "crop",
    "dpr",
    "fit",
    "fm",
    "format",
    "h",
    "height",
    "ixlib",
    "q",
    "quality",
    "resize",
    "s",
    "size",
    "timestamp",
    "ts",
    "w",
    "width",
}


def normalize_image_urls(value: object) -> list[str]:
    """Normalize API/HTML image payloads into a compact list of URL strings."""
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    if isinstance(value, (list, tuple, set)):
        return _dedupe_urls(str(item).strip() for item in value if item is not None)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return _dedupe_urls(str(item).strip() for item in parsed if item is not None)
        separators = ["\n", "|", ","]
        parts = [stripped]
        for separator in separators:
            if separator in stripped:
                parts = stripped.split(separator)
                break
        return _dedupe_urls(part.strip() for part in parts)
    return []


def build_image_duplicate_signals(review_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Attach duplicate customer-photo indicators and return aggregate summary."""
    frame = review_df.copy()
    if "image_urls" not in frame.columns:
        frame["image_urls"] = [[] for _ in range(len(frame))]

    normalized_urls_by_row: list[list[str]] = []
    fingerprints_by_row: list[list[str]] = []
    sample_urls: dict[str, str] = {}
    rows_by_fingerprint: dict[str, set[int]] = defaultdict(set)

    for row_position, value in enumerate(frame["image_urls"].tolist()):
        urls = normalize_image_urls(value)
        fingerprints = []
        for url in urls:
            fingerprint = _fingerprint_image_url(url)
            if not fingerprint:
                continue
            fingerprints.append(fingerprint)
            sample_urls.setdefault(fingerprint, url)
            rows_by_fingerprint[fingerprint].add(row_position)
        normalized_urls_by_row.append(urls)
        fingerprints_by_row.append(_dedupe_urls(fingerprints))

    fingerprint_counts = Counter(
        {
            fingerprint: len(row_positions)
            for fingerprint, row_positions in rows_by_fingerprint.items()
        }
    )
    duplicate_fingerprints = {
        fingerprint
        for fingerprint, count in fingerprint_counts.items()
        if count >= 2
    }

    image_counts: list[int] = []
    duplicate_counts: list[int] = []
    cluster_sizes: list[int] = []
    duplicate_scores: list[float] = []
    duplicate_flags: list[int] = []
    duplicate_ids: list[list[str]] = []
    duplicate_reasons: list[list[str]] = []

    for urls, fingerprints in zip(normalized_urls_by_row, fingerprints_by_row):
        image_count = len(urls)
        row_duplicates = [fingerprint for fingerprint in fingerprints if fingerprint in duplicate_fingerprints]
        duplicate_count = len(row_duplicates)
        cluster_size = max((fingerprint_counts[fingerprint] for fingerprint in row_duplicates), default=0)
        duplicate_score = _score_duplicate_photo_signal(
            image_count=image_count,
            duplicate_count=duplicate_count,
            cluster_size=cluster_size,
        )

        image_counts.append(image_count)
        duplicate_counts.append(duplicate_count)
        cluster_sizes.append(cluster_size)
        duplicate_scores.append(duplicate_score)
        duplicate_flags.append(1 if duplicate_count > 0 else 0)
        duplicate_ids.append([fingerprint[:12] for fingerprint in row_duplicates])
        duplicate_reasons.append(
            _build_duplicate_photo_reasons(
                duplicate_count=duplicate_count,
                cluster_size=cluster_size,
            )
        )

    frame["image_urls"] = normalized_urls_by_row
    frame["image_count"] = image_counts
    frame["duplicate_image_count"] = duplicate_counts
    frame["duplicate_image_cluster_size"] = cluster_sizes
    frame["duplicate_image_score"] = duplicate_scores
    frame["duplicate_image_flag"] = duplicate_flags
    frame["duplicate_image_fingerprints"] = duplicate_ids
    frame["image_duplicate_reasons"] = duplicate_reasons

    photo_reviews = int(sum(1 for count in image_counts if count > 0))
    duplicate_photo_reviews = int(sum(duplicate_flags))
    duplicate_ratio = float(duplicate_photo_reviews / photo_reviews) if photo_reviews else 0.0
    largest_cluster = int(max(fingerprint_counts.values(), default=0))
    duplicate_clusters = [
        {
            "fingerprint": fingerprint[:12],
            "review_count": int(count),
            "review_indices": [int(index + 1) for index in sorted(rows_by_fingerprint[fingerprint])],
            "sample_url": sample_urls.get(fingerprint, ""),
        }
        for fingerprint, count in fingerprint_counts.most_common()
        if count >= 2
    ][:5]

    summary = {
        "photo_reviews": photo_reviews,
        "photo_review_ratio": float(photo_reviews / len(frame)) if len(frame) else 0.0,
        "duplicate_photo_reviews": duplicate_photo_reviews,
        "duplicate_photo_review_ratio": duplicate_ratio,
        "duplicate_photo_cluster_count": len(duplicate_fingerprints),
        "largest_duplicate_photo_cluster": largest_cluster,
        "photo_forensics_risk": _photo_forensics_risk(duplicate_ratio, largest_cluster),
        "duplicate_photo_clusters": duplicate_clusters,
    }
    return frame, summary


def _dedupe_urls(values: object) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _fingerprint_image_url(url: str) -> str:
    canonical = _canonicalize_image_url(url)
    if not canonical:
        return ""
    return hashlib.sha1(canonical.encode("utf-8", errors="ignore")).hexdigest()


def _canonicalize_image_url(url: str) -> str:
    raw_url = url.strip()
    if not raw_url:
        return ""
    if raw_url.startswith("data:image"):
        return f"data-image:{hashlib.sha1(raw_url.encode('utf-8', errors='ignore')).hexdigest()}"
    if raw_url.startswith("//"):
        raw_url = f"https:{raw_url}"

    parsed = urlparse(raw_url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if not hostname and not path:
        return ""

    filtered_query = [
        (key.lower(), value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key and not key.lower().startswith("utm_") and key.lower() not in IMAGE_QUERY_NOISE_KEYS
    ]
    filtered_query.sort()
    normalized = urlunparse(
        (
            parsed.scheme.lower() or "https",
            hostname,
            path,
            "",
            "&".join(f"{key}={value}" for key, value in filtered_query),
            "",
        )
    )
    return normalized.lower()


def _score_duplicate_photo_signal(image_count: int, duplicate_count: int, cluster_size: int) -> float:
    if image_count <= 0 or duplicate_count <= 0:
        return 0.0
    duplicate_density = duplicate_count / max(image_count, 1)
    cluster_pressure = min(max(cluster_size - 1, 0) / 3, 1.0)
    return float(min(max(0.68 * duplicate_density + 0.32 * cluster_pressure, 0.0), 1.0))


def _build_duplicate_photo_reasons(duplicate_count: int, cluster_size: int) -> list[str]:
    if duplicate_count <= 0:
        return []
    if cluster_size >= 4:
        return [f"The same customer photo appears across a large cluster of {cluster_size} reviews."]
    return [f"The same customer photo appears in {cluster_size} reviews."]


def _photo_forensics_risk(duplicate_ratio: float, largest_cluster: int) -> str:
    if duplicate_ratio <= 0 or largest_cluster <= 1:
        return "none"
    if duplicate_ratio >= 0.35 or largest_cluster >= 4:
        return "high"
    if duplicate_ratio >= 0.18 or largest_cluster >= 3:
        return "medium"
    return "low"
