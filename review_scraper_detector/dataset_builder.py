"""Dataset ingestion and normalization for stronger review-classifier training."""

from __future__ import annotations

import gzip
import json
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .sample_data import generate_sample_review_dataset, generate_suspicious_variants_from_real_reviews
from .utils import (
    ensure_directory,
    infer_review_product_family,
    make_review_holdout_group,
    make_review_split_group,
    make_source_group,
    normalize_group_component,
    normalize_whitespace,
    save_json,
)

try:  # pragma: no cover - optional dependency in some environments
    from ucimlrepo import fetch_ucirepo
except Exception:  # pragma: no cover
    fetch_ucirepo = None

try:  # pragma: no cover - optional dependency for large public datasets
    from datasets import load_dataset
except Exception:  # pragma: no cover
    load_dataset = None


DEFAULT_GRAMMAR_ZIP = Path.home() / "Downloads" / "GrammarandProductReviews.zip"
DEFAULT_RECIPE_ZIP = Path.home() / "Downloads" / "recipe+reviews+and+user+feedback+dataset.zip"
DEFAULT_TURKISH_ZIP = Path.home() / "Downloads" / "turkish+user+review+dataset.zip"
DEFAULT_AMAZON_ZIP = Path.home() / "Downloads" / "amazon+commerce+reviews+set.zip"
DEFAULT_YELP_OPEN_REVIEW_JSON = Path.home() / "Downloads" / "yelp_academic_dataset_review.json"
DEFAULT_YELPNYC_PATH = Path.home() / "Downloads" / "YelpNYC.csv"
DEFAULT_AMAZON_REVIEWS_2023_REPO = "McAuley-Lab/Amazon-Reviews-2023"
DEFAULT_AMAZON_REVIEWS_2023_CONFIG = "raw_review_All_Beauty"


def build_combined_training_dataset(
    output_path: str | Path,
    seed: int = 42,
    max_rows_per_source: int = 2000,
    synthetic_ratio: float = 1.0,
    include_uci: bool = True,
    include_large_public_data: bool = False,
    large_max_rows_per_source: int | None = None,
    amazon_reviews_2023_repo: str = DEFAULT_AMAZON_REVIEWS_2023_REPO,
    amazon_reviews_2023_config: str = DEFAULT_AMAZON_REVIEWS_2023_CONFIG,
    amazon_reviews_2023_split: str = "full",
    amazon_reviews_2023_shuffle_buffer: int = 256,
    amazon_reviews_2023_max_scan_seconds: float | None = 1800.0,
    yelp_open_review_json: str | Path = DEFAULT_YELP_OPEN_REVIEW_JSON,
    yelpnyc_path: str | Path = DEFAULT_YELPNYC_PATH,
    grammar_zip: str | Path = DEFAULT_GRAMMAR_ZIP,
    recipe_zip: str | Path = DEFAULT_RECIPE_ZIP,
    turkish_zip: str | Path = DEFAULT_TURKISH_ZIP,
    amazon_zip: str | Path = DEFAULT_AMAZON_ZIP,
) -> tuple[pd.DataFrame, dict]:
    """Build a balanced training dataset from local archives, UCI sources, and synthetic samples."""
    output_path = Path(output_path)
    ensure_directory(output_path.parent)

    source_frames: list[pd.DataFrame] = []
    source_reports: list[dict] = []
    large_limit = int(large_max_rows_per_source or max_rows_per_source)
    synthetic_hard_negative_records = 0

    for loader in (
        lambda: _load_grammar_product_reviews(grammar_zip, max_rows_per_source, seed),
        lambda: _load_recipe_reviews_from_zip(recipe_zip, max_rows_per_source, seed),
        lambda: _load_turkish_user_reviews(turkish_zip, max_rows_per_source, seed),
        lambda: _probe_amazon_archive(amazon_zip),
    ):
        frame, report = loader()
        source_reports.append(report)
        if not frame.empty:
            source_frames.append(frame)

    if include_uci:
        for loader in (
            lambda: _load_recipe_reviews_from_uci(max_rows_per_source, seed),
            lambda: _load_travel_profiles_from_uci(max_rows_per_source, seed),
        ):
            frame, report = loader()
            source_reports.append(report)
            if not frame.empty:
                source_frames.append(frame)

    if include_large_public_data:
        for loader in (
            lambda: _load_amazon_reviews_2023(
                repo_id=amazon_reviews_2023_repo,
                config_name=amazon_reviews_2023_config,
                split=amazon_reviews_2023_split,
                max_rows=large_limit,
                seed=seed,
                shuffle_buffer=amazon_reviews_2023_shuffle_buffer,
                max_scan_seconds=amazon_reviews_2023_max_scan_seconds,
            ),
            lambda: _load_yelp_open_reviews(yelp_open_review_json, large_limit, seed),
            lambda: _load_yelpnyc_labeled_reviews(yelpnyc_path, large_limit, seed),
        ):
            frame, report = loader()
            source_reports.append(report)
            if not frame.empty:
                source_frames.append(frame)

    if source_frames:
        source_df = pd.concat(source_frames, ignore_index=True)
        source_df = _finalize_rows(source_df, default_label=0)
        source_df = _drop_duplicate_texts(source_df)
        authentic_df = source_df.loc[source_df["label"] == 0].reset_index(drop=True)
        labeled_suspicious_df = source_df.loc[source_df["label"] == 1].reset_index(drop=True)

        template_seed = generate_sample_review_dataset(
            n_samples=max(3000, len(authentic_df) * 2),
            seed=seed,
        )
        template_authentic_df = template_seed.loc[
            template_seed["label"] == 0,
            [
                "review_text",
                "rating",
                "label",
                "source",
                "product_family",
                "origin_family",
                "holdout_group",
                "split_group",
            ],
        ].reset_index(drop=True)
        template_suspicious_df = template_seed.loc[
            template_seed["label"] == 1,
            [
                "review_text",
                "rating",
                "label",
                "source",
                "product_family",
                "origin_family",
                "holdout_group",
                "split_group",
            ],
        ].reset_index(drop=True)
        hard_negative_target = min(
            len(template_authentic_df),
            max(250, int(len(authentic_df) * 0.15)) if len(authentic_df) else 500,
        )
        template_authentic_df = _sample_rows(
            _finalize_rows(template_authentic_df, default_label=0),
            max_rows=hard_negative_target,
            seed=seed + 11,
        )
        synthetic_hard_negative_records = int(len(template_authentic_df))
        authentic_df = pd.concat([authentic_df, template_authentic_df], ignore_index=True)
        authentic_df = _drop_duplicate_texts(_finalize_rows(authentic_df, default_label=0))
        suspicious_target = max(
            int(len(authentic_df) * synthetic_ratio),
            len(labeled_suspicious_df),
            min(1500, len(authentic_df)),
        )
        synthetic_target = max(0, suspicious_target - len(labeled_suspicious_df))
        augmented_suspicious_df = generate_suspicious_variants_from_real_reviews(
            authentic_df,
            target_count=synthetic_target,
            seed=seed,
        ) if synthetic_target else _empty_training_frame()

        synthetic_suspicious_df = pd.concat(
            [augmented_suspicious_df, template_suspicious_df],
            ignore_index=True,
        )
        synthetic_suspicious_df = _sample_rows(
            _finalize_rows(synthetic_suspicious_df, default_label=1),
            max_rows=synthetic_target,
            seed=seed + 17,
        )
        suspicious_df = pd.concat(
            [labeled_suspicious_df, synthetic_suspicious_df],
            ignore_index=True,
        )

        final_df = pd.concat([authentic_df, suspicious_df], ignore_index=True)
    else:
        final_df = generate_sample_review_dataset(
            n_samples=max(2400, max_rows_per_source * 2),
            seed=seed,
        )

    final_df = _finalize_rows(final_df, default_label=0)
    final_df = final_df.drop_duplicates(subset=["review_text", "label"]).sample(
        frac=1.0,
        random_state=seed,
    ).reset_index(drop=True)
    final_df.to_csv(output_path, index=False, encoding="utf-8")

    build_report = {
        "output_path": str(output_path),
        "records_total": int(len(final_df)),
        "split_group_count": int(final_df["split_group"].nunique()) if "split_group" in final_df.columns else 0,
        "holdout_group_count": int(final_df["holdout_group"].nunique()) if "holdout_group" in final_df.columns else 0,
        "synthetic_hard_negative_records": int(synthetic_hard_negative_records),
        "label_distribution": {
            str(key): int(value)
            for key, value in final_df["label"].value_counts().sort_index().items()
        },
        "source_distribution": {
            str(key): int(value)
            for key, value in final_df["source"].value_counts().sort_values(ascending=False).items()
        },
        "product_family_distribution": {
            str(key): int(value)
            for key, value in final_df["product_family"].value_counts().sort_values(ascending=False).items()
        },
        "source_reports": source_reports,
    }
    report_path = output_path.parent / f"{output_path.stem}_build_report.json"
    save_json(build_report, report_path)
    build_report["report_path"] = str(report_path)
    return final_df, build_report


def _load_grammar_product_reviews(
    zip_path: str | Path,
    max_rows: int,
    seed: int,
) -> tuple[pd.DataFrame, dict]:
    """Load English product reviews from the grammar-and-product-review archive."""
    path = Path(zip_path)
    report = {"source": "grammar_product_reviews", "path": str(path), "status": "missing", "records_raw": 0, "records_used": 0}
    if not path.exists():
        report["reason"] = "Archive file was not found."
        return _empty_training_frame(), report

    with zipfile.ZipFile(path) as archive:
        csv_name = next((name for name in archive.namelist() if name.lower().endswith(".csv")), None)
        if csv_name is None:
            report["status"] = "skipped"
            report["reason"] = "No CSV file was found inside the archive."
            return _empty_training_frame(), report

        with archive.open(csv_name) as file_handle:
            raw_df = pd.read_csv(file_handle, low_memory=False)

    report["records_raw"] = int(len(raw_df))
    text_series = (
        raw_df.get("reviews.title", "").fillna("").astype(str).str.strip()
        + ". "
        + raw_df.get("reviews.text", "").fillna("").astype(str).str.strip()
    ).str.strip(" .")
    result_df = pd.DataFrame(
        {
            "review_text": text_series,
            "rating": pd.to_numeric(raw_df.get("reviews.rating", 0.0), errors="coerce").fillna(0.0),
            "label": 0,
            "source": "grammar_product_reviews",
        }
    )
    result_df = _sample_rows(_finalize_rows(result_df, default_label=0), max_rows=max_rows, seed=seed)
    report["status"] = "loaded"
    report["records_used"] = int(len(result_df))
    return result_df, report


def _load_recipe_reviews_from_zip(
    zip_path: str | Path,
    max_rows: int,
    seed: int,
) -> tuple[pd.DataFrame, dict]:
    """Load recipe reviews from the downloaded ZIP archive."""
    path = Path(zip_path)
    report = {"source": "recipe_reviews_zip", "path": str(path), "status": "missing", "records_raw": 0, "records_used": 0}
    if not path.exists():
        report["reason"] = "Archive file was not found."
        return _empty_training_frame(), report

    with zipfile.ZipFile(path) as archive:
        csv_name = next((name for name in archive.namelist() if name.lower().endswith(".csv")), None)
        if csv_name is None:
            report["status"] = "skipped"
            report["reason"] = "No CSV file was found inside the archive."
            return _empty_training_frame(), report

        with archive.open(csv_name) as file_handle:
            raw_df = pd.read_csv(file_handle, low_memory=False)

    report["records_raw"] = int(len(raw_df))
    text_series = (
        raw_df.get("recipe_name", "").fillna("").astype(str).str.strip()
        + ". "
        + raw_df.get("text", "").fillna("").astype(str).str.strip()
    ).str.strip(" .")
    result_df = pd.DataFrame(
        {
            "review_text": text_series,
            "rating": pd.to_numeric(raw_df.get("stars", 0.0), errors="coerce").fillna(0.0),
            "label": 0,
            "source": "recipe_reviews_zip",
        }
    )
    result_df = _sample_rows(_finalize_rows(result_df, default_label=0), max_rows=max_rows, seed=seed + 1)
    report["status"] = "loaded"
    report["records_used"] = int(len(result_df))
    return result_df, report


def _load_turkish_user_reviews(
    zip_path: str | Path,
    max_rows: int,
    seed: int,
) -> tuple[pd.DataFrame, dict]:
    """Load plain-text Turkish user reviews from the archive."""
    path = Path(zip_path)
    report = {"source": "turkish_user_reviews", "path": str(path), "status": "missing", "records_raw": 0, "records_used": 0}
    if not path.exists():
        report["reason"] = "Archive file was not found."
        return _empty_training_frame(), report

    with zipfile.ZipFile(path) as archive:
        text_name = next((name for name in archive.namelist() if name.lower().endswith(".txt")), None)
        if text_name is None:
            report["status"] = "skipped"
            report["reason"] = "No TXT file was found inside the archive."
            return _empty_training_frame(), report

        raw_text = archive.read(text_name).decode("utf-8", errors="replace")

    category = "general"
    rows: list[dict] = []
    for line in raw_text.splitlines():
        cleaned = normalize_whitespace(line)
        if not cleaned:
            continue
        if cleaned.count("-") >= 8 and len(cleaned.replace("-", "").strip()) <= 30:
            category = cleaned.strip("- ").lower() or "general"
            continue
        if len(cleaned) < 25 or cleaned.isupper():
            continue
        rows.append(
            {
                "review_text": cleaned,
                "rating": 0.0,
                "label": 0,
                "source": "turkish_user_reviews",
                "product_family": normalize_group_component(category, default="general"),
            }
        )

    report["records_raw"] = int(len(rows))
    result_df = pd.DataFrame(rows)
    result_df = _sample_rows(_finalize_rows(result_df, default_label=0), max_rows=max_rows, seed=seed + 2)
    report["status"] = "loaded"
    report["records_used"] = int(len(result_df))
    return result_df, report


def _load_recipe_reviews_from_uci(
    max_rows: int,
    seed: int,
) -> tuple[pd.DataFrame, dict]:
    """Load the UCI recipe-review corpus using ucimlrepo."""
    report = {"source": "uci_recipe_reviews_911", "status": "skipped", "records_raw": 0, "records_used": 0}
    if fetch_ucirepo is None:
        report["reason"] = "ucimlrepo is not installed in the current environment."
        return _empty_training_frame(), report

    dataset = fetch_ucirepo(id=911)
    raw_df = dataset.data.features.copy()
    report["records_raw"] = int(len(raw_df))
    text_series = (
        raw_df.get("recipe_name", "").fillna("").astype(str).str.strip()
        + ". "
        + raw_df.get("text", "").fillna("").astype(str).str.strip()
    ).str.strip(" .")
    result_df = pd.DataFrame(
        {
            "review_text": text_series,
            "rating": pd.to_numeric(raw_df.get("stars", 0.0), errors="coerce").fillna(0.0),
            "label": 0,
            "source": "uci_recipe_reviews_911",
        }
    )
    result_df = _sample_rows(_finalize_rows(result_df, default_label=0), max_rows=max_rows, seed=seed + 3)
    report["status"] = "loaded"
    report["records_used"] = int(len(result_df))
    return result_df, report


def _load_travel_profiles_from_uci(
    max_rows: int,
    seed: int,
) -> tuple[pd.DataFrame, dict]:
    """Load UCI travel-review profiles and convert them into natural-language summaries."""
    report = {"source": "uci_travel_review_ratings_485", "status": "skipped", "records_raw": 0, "records_used": 0}
    if fetch_ucirepo is None:
        report["reason"] = "ucimlrepo is not installed in the current environment."
        return _empty_training_frame(), report

    dataset = fetch_ucirepo(id=485)
    raw_df = dataset.data.features.copy()
    report["records_raw"] = int(len(raw_df))
    for column in raw_df.columns:
        raw_df[column] = pd.to_numeric(raw_df[column], errors="coerce").fillna(0.0)

    raw_df = _sample_rows(raw_df, max_rows=max_rows, seed=seed + 4)
    rows: list[dict] = []
    for _, row in raw_df.iterrows():
        sorted_scores = row.sort_values(ascending=False)
        top_preferences = [name for name, value in sorted_scores.head(3).items() if float(value) > 0]
        low_preferences = [name for name, value in sorted_scores.tail(2).items() if float(value) >= 0]
        non_zero_scores = row.replace(0.0, np.nan)
        avg_rating = float(non_zero_scores.mean()) if np.isfinite(non_zero_scores.mean()) else 0.0

        top_text = ", ".join(top_preferences) if top_preferences else "several travel categories"
        low_text = ", ".join(low_preferences) if low_preferences else "a few other categories"
        summary_text = (
            f"This traveler usually gives higher ratings to {top_text}, "
            f"while {low_text} receive lower scores. The preference pattern looks detailed and organic."
        )
        rows.append(
            {
                "review_text": summary_text,
                "rating": avg_rating,
                "label": 0,
                "source": "uci_travel_review_ratings_485",
            }
        )

    result_df = _finalize_rows(pd.DataFrame(rows), default_label=0)
    report["status"] = "loaded"
    report["records_used"] = int(len(result_df))
    return result_df, report


def _load_amazon_reviews_2023(
    repo_id: str,
    config_name: str,
    split: str,
    max_rows: int,
    seed: int,
    shuffle_buffer: int = 256,
    max_scan_seconds: float | None = 1800.0,
) -> tuple[pd.DataFrame, dict]:
    """Load Amazon Reviews 2023 from Hugging Face in streaming mode."""
    started_at = time.monotonic()
    report = {
        "source": "amazon_reviews_2023",
        "repo_id": repo_id,
        "config": config_name,
        "split": split,
        "shuffle_buffer": int(shuffle_buffer),
        "max_scan_seconds": None if max_scan_seconds is None else float(max_scan_seconds),
        "status": "skipped",
        "records_raw": 0,
        "records_used": 0,
    }
    if load_dataset is None:
        report["reason"] = "The optional `datasets` package is not installed."
        return _empty_training_frame(), report

    try:
        dataset = load_dataset(
            repo_id,
            config_name,
            split=split,
            streaming=True,
            trust_remote_code=True,
        )
        if shuffle_buffer > 0 and hasattr(dataset, "shuffle"):
            buffer_size = max(1, min(int(shuffle_buffer), max(1, int(max_rows))))
            dataset = dataset.shuffle(seed=seed, buffer_size=buffer_size)
            report["shuffle_buffer"] = int(buffer_size)
    except Exception as exc:
        report["status"] = "failed"
        report["reason"] = str(exc)
        report["elapsed_seconds"] = round(time.monotonic() - started_at, 3)
        return _empty_training_frame(), report

    rows: list[dict] = []
    scanned = 0
    timed_out = False
    for record in dataset:
        if max_scan_seconds is not None and max_scan_seconds > 0:
            if time.monotonic() - started_at >= max_scan_seconds:
                timed_out = True
                break
        scanned += 1
        text = _join_text_parts(record.get("title"), record.get("text"))
        if len(text) < 15:
            continue
        rows.append(
            {
                "review_text": text,
                "rating": _coerce_rating(record.get("rating")),
                "label": 0,
                "source": f"amazon_reviews_2023:{config_name}",
            }
        )
        if len(rows) >= max_rows:
            break

    result_df = _finalize_rows(pd.DataFrame(rows), default_label=0)
    if timed_out:
        report["status"] = "partial_timeout" if not result_df.empty else "timeout"
        report["reason"] = "Stopped by Amazon Reviews 2023 scan time budget."
    else:
        report["status"] = "loaded" if not result_df.empty else "empty"
    report["records_raw"] = int(scanned)
    report["records_used"] = int(len(result_df))
    report["elapsed_seconds"] = round(time.monotonic() - started_at, 3)
    return result_df, report


def _load_yelp_open_reviews(
    review_path: str | Path,
    max_rows: int,
    seed: int,
) -> tuple[pd.DataFrame, dict]:
    """Load normal review text from the official Yelp Open Dataset JSONL file."""
    path = _resolve_yelp_open_path(review_path)
    report = {
        "source": "yelp_open_dataset",
        "path": str(review_path),
        "resolved_path": str(path) if path else None,
        "status": "missing",
        "records_raw": 0,
        "records_used": 0,
    }
    if path is None or not path.exists():
        report["reason"] = "Yelp review JSON file was not found."
        return _empty_training_frame(), report

    rows: list[dict] = []
    scanned = 0
    try:
        for record in _iter_json_records(path):
            scanned += 1
            text = normalize_whitespace(str(record.get("text", "")))
            if len(text) < 15:
                continue
            rows.append(
                {
                    "review_text": text,
                    "rating": _coerce_rating(record.get("stars")),
                    "label": 0,
                    "source": "yelp_open_dataset",
                }
            )
            if len(rows) >= max_rows:
                break
    except Exception as exc:
        report["status"] = "failed"
        report["reason"] = str(exc)
        report["records_raw"] = int(scanned)
        return _empty_training_frame(), report

    result_df = _finalize_rows(pd.DataFrame(rows), default_label=0)
    result_df = _sample_rows(result_df, max_rows=max_rows, seed=seed + 5)
    report["status"] = "loaded" if not result_df.empty else "empty"
    report["records_raw"] = int(scanned)
    report["records_used"] = int(len(result_df))
    return result_df, report


def _load_yelpnyc_labeled_reviews(
    dataset_path: str | Path,
    max_rows: int,
    seed: int,
) -> tuple[pd.DataFrame, dict]:
    """Load labeled YelpNYC-style fake-review data from CSV, JSONL, JSON, or ZIP."""
    path = Path(dataset_path)
    report = {
        "source": "yelpnyc_labeled_reviews",
        "path": str(path),
        "status": "missing",
        "records_raw": 0,
        "records_used": 0,
    }
    if not path.exists():
        report["reason"] = "YelpNYC file was not found. The official labeled dataset is provided by request."
        return _empty_training_frame(), report

    try:
        raw_df = _read_labeled_review_table(path, max_rows=max_rows)
    except Exception as exc:
        report["status"] = "failed"
        report["reason"] = str(exc)
        return _empty_training_frame(), report

    report["records_raw"] = int(len(raw_df))
    if raw_df.empty:
        report["status"] = "empty"
        return _empty_training_frame(), report

    text_column = _first_existing_column(
        raw_df,
        ["review_text", "text", "review", "content", "reviewContent", "review_content"],
    )
    label_column = _first_existing_column(
        raw_df,
        ["label", "is_fake", "is_spam", "fake", "filtered", "spam", "is_suspicious"],
    )
    rating_column = _first_existing_column(
        raw_df,
        ["rating", "stars", "reviewRating", "review_rating", "score"],
    )
    if text_column is None or label_column is None:
        report["status"] = "skipped"
        report["reason"] = "Could not detect text and label columns in the YelpNYC file."
        report["columns"] = list(raw_df.columns)
        return _empty_training_frame(), report

    result_df = pd.DataFrame(
        {
            "review_text": raw_df[text_column].fillna("").astype(str),
            "rating": raw_df[rating_column].map(_coerce_rating) if rating_column else 0.0,
            "label": _normalize_fake_label_series(raw_df[label_column]),
            "source": "yelpnyc_labeled_reviews",
        }
    )
    result_df = _sample_rows(_finalize_rows(result_df, default_label=0), max_rows=max_rows, seed=seed + 6)
    report["status"] = "loaded" if not result_df.empty else "empty"
    report["records_used"] = int(len(result_df))
    report["label_distribution"] = {
        str(key): int(value)
        for key, value in result_df["label"].value_counts().sort_index().items()
    }
    return result_df, report


def _probe_amazon_archive(zip_path: str | Path) -> tuple[pd.DataFrame, dict]:
    """Inspect the Amazon archive and report its availability for future parsing."""
    path = Path(zip_path)
    report = {"source": "amazon_commerce_reviews_set", "path": str(path), "status": "missing", "records_raw": 0, "records_used": 0}
    if not path.exists():
        report["reason"] = "Archive file was not found."
        return _empty_training_frame(), report

    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
    report["archive_members"] = members[:5]

    extracted_arff = Path("data") / "external_temp" / "Amazon_initial_50_30_10000.arff"
    if any(member.lower().endswith(".rar") for member in members):
        report["status"] = "skipped"
        report["reason"] = "The archive contains a nested RAR file. No safe text-review parser is configured for it yet."
        if extracted_arff.exists():
            head = extracted_arff.read_bytes()[:4096]
            if head and set(head) == {0}:
                report["reason"] += " The extracted ARFF snapshot appears zero-filled, so it was excluded from training."
        return _empty_training_frame(), report

    report["status"] = "skipped"
    report["reason"] = "No directly usable text review file was detected inside the archive."
    return _empty_training_frame(), report


def _finalize_rows(df: pd.DataFrame, default_label: int) -> pd.DataFrame:
    """Normalize columns into the expected training schema."""
    if df.empty:
        return _empty_training_frame()

    normalized = df.copy()
    if "source" not in normalized.columns:
        normalized["source"] = "unspecified"
    if "rating" not in normalized.columns:
        normalized["rating"] = 0.0
    if "label" not in normalized.columns:
        normalized["label"] = default_label

    normalized["review_text"] = normalized["review_text"].fillna("").astype(str).map(normalize_whitespace)
    normalized["rating"] = pd.to_numeric(normalized["rating"], errors="coerce").fillna(0.0).clip(lower=0.0, upper=5.0)
    normalized["label"] = pd.to_numeric(normalized["label"], errors="coerce").fillna(default_label).astype(int)
    normalized["source"] = normalized["source"].fillna("unspecified").astype(str)
    if "product_family" not in normalized.columns:
        normalized["product_family"] = [
            infer_review_product_family(review_text=text, source=source)
            for text, source in zip(normalized["review_text"], normalized["source"])
        ]
    else:
        normalized["product_family"] = [
            normalize_group_component(value, default=infer_review_product_family(review_text=text, source=source))
            for value, text, source in zip(normalized["product_family"], normalized["review_text"], normalized["source"])
        ]
    if "origin_family" not in normalized.columns:
        normalized["origin_family"] = ""
    else:
        normalized["origin_family"] = [
            normalize_group_component(value, default="")
            for value in normalized["origin_family"]
        ]
    if "split_group" not in normalized.columns:
        normalized["split_group"] = normalized["review_text"].map(make_review_split_group)
    else:
        normalized["split_group"] = normalized["split_group"].fillna("").astype(str)
        missing_groups = normalized["split_group"].str.strip().eq("")
        if missing_groups.any():
            normalized.loc[missing_groups, "split_group"] = normalized.loc[missing_groups, "review_text"].map(make_review_split_group)
    if "holdout_group" not in normalized.columns:
        normalized["holdout_group"] = ""
    normalized["holdout_group"] = normalized["holdout_group"].fillna("").astype(str)
    missing_holdout = normalized["holdout_group"].str.strip().eq("")
    if missing_holdout.any():
        normalized.loc[missing_holdout, "holdout_group"] = [
            make_review_holdout_group(
                source_group=make_source_group(source),
                product_family=product_family,
                origin_family=origin_family,
            )
            for source, product_family, origin_family in zip(
                normalized.loc[missing_holdout, "source"],
                normalized.loc[missing_holdout, "product_family"],
                normalized.loc[missing_holdout, "origin_family"],
            )
        ]

    # Keep one canonical broader family per lineage so augmented descendants
    # never drift into a different split than their source review.
    source_priority = normalized["source"].fillna("").astype(str).str.startswith("synthetic_").astype(int)
    holdout_by_lineage = (
        normalized.assign(_source_priority=source_priority)
        .sort_values(by=["_source_priority", "source", "holdout_group"])
        .groupby("split_group")["holdout_group"]
        .first()
    )
    normalized["holdout_group"] = normalized["split_group"].map(holdout_by_lineage).fillna(normalized["holdout_group"])

    normalized = normalized[normalized["review_text"].str.len() >= 15].reset_index(drop=True)
    return normalized[
        [
            "review_text",
            "rating",
            "label",
            "source",
            "product_family",
            "origin_family",
            "holdout_group",
            "split_group",
        ]
    ]


def _sample_rows(df: pd.DataFrame, max_rows: int, seed: int) -> pd.DataFrame:
    """Sample rows deterministically when a source is too large."""
    if df.empty or len(df) <= max_rows:
        return df.reset_index(drop=True)
    return df.sample(n=max_rows, random_state=seed).reset_index(drop=True)


def _drop_duplicate_texts(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicate review texts regardless of source."""
    deduplicated = df.copy()
    deduplicated["_normalized_text"] = deduplicated["review_text"].str.lower().map(normalize_whitespace)
    deduplicated = deduplicated.drop_duplicates(subset=["_normalized_text"]).drop(columns=["_normalized_text"])
    return deduplicated.reset_index(drop=True)


def _resolve_yelp_open_path(review_path: str | Path) -> Path | None:
    """Resolve common Yelp Open Dataset review-file locations."""
    path = Path(review_path)
    if path.exists() and path.is_file():
        return path
    if path.exists() and path.is_dir():
        matches = sorted(path.rglob("yelp_academic_dataset_review.json*"))
        return matches[0] if matches else None

    downloads = Path.home() / "Downloads"
    candidates = [
        downloads / "yelp_academic_dataset_review.json",
        downloads / "yelp_academic_dataset_review.json.gz",
        downloads / "yelp_dataset" / "yelp_academic_dataset_review.json",
        downloads / "Yelp Dataset" / "yelp_academic_dataset_review.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _iter_json_records(path: Path):
    """Yield dictionaries from JSONL, JSON, GZIP, or ZIP files."""
    suffixes = [suffix.lower() for suffix in path.suffixes]
    if ".zip" in suffixes:
        with zipfile.ZipFile(path) as archive:
            member = next(
                (
                    name
                    for name in archive.namelist()
                    if "review" in name.lower() and name.lower().endswith((".json", ".jsonl"))
                ),
                None,
            )
            if member is None:
                raise ValueError("No review JSON/JSONL member was found inside the ZIP archive.")
            with archive.open(member) as file_handle:
                for raw_line in file_handle:
                    record = _parse_json_line(raw_line.decode("utf-8", errors="replace"))
                    if record is not None:
                        yield record
        return

    opener = gzip.open if ".gz" in suffixes else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as file_handle:
        first_chunk = file_handle.read(1)
        file_handle.seek(0)
        if first_chunk == "[":
            payload = json.load(file_handle)
            if isinstance(payload, list):
                for record in payload:
                    if isinstance(record, dict):
                        yield record
            return

        for line in file_handle:
            record = _parse_json_line(line)
            if record is not None:
                yield record


def _parse_json_line(line: str) -> dict | None:
    """Parse one JSON object line with basic validation."""
    line = line.strip()
    if not line:
        return None
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _read_labeled_review_table(path: Path, max_rows: int) -> pd.DataFrame:
    """Read a labeled fake-review table from common file formats."""
    suffix = path.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            member = next(
                (
                    name
                    for name in archive.namelist()
                    if name.lower().endswith((".csv", ".json", ".jsonl"))
                ),
                None,
            )
            if member is None:
                raise ValueError("No CSV/JSON/JSONL file was found inside the YelpNYC ZIP archive.")
            with archive.open(member) as file_handle:
                if member.lower().endswith(".csv"):
                    return pd.read_csv(file_handle, nrows=max_rows, low_memory=False)
                records = []
                for raw_line in file_handle:
                    record = _parse_json_line(raw_line.decode("utf-8", errors="replace"))
                    if record:
                        records.append(record)
                    if len(records) >= max_rows:
                        break
                return pd.DataFrame(records)

    if suffix == ".csv":
        return pd.read_csv(path, nrows=max_rows, low_memory=False)
    if suffix in {".json", ".jsonl"} or path.name.lower().endswith(".json.gz"):
        rows = []
        for record in _iter_json_records(path):
            rows.append(record)
            if len(rows) >= max_rows:
                break
        return pd.DataFrame(rows)
    raise ValueError(f"Unsupported labeled dataset format: {path.suffix}")


def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first matching column name, ignoring case and punctuation."""
    normalized_columns = {_normalize_column_name(column): column for column in df.columns}
    for candidate in candidates:
        normalized = _normalize_column_name(candidate)
        if normalized in normalized_columns:
            return normalized_columns[normalized]
    return None


def _normalize_column_name(value: str) -> str:
    """Normalize a column name for fuzzy matching."""
    return "".join(char.lower() for char in str(value) if char.isalnum())


def _normalize_fake_label(value: object) -> int:
    """Normalize common fake-review label encodings into 0=normal, 1=suspicious."""
    if pd.isna(value):
        return 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"fake", "fraud", "spam", "spammer", "filtered", "suspicious", "deceptive", "1", "true", "yes"}:
            return 1
        if text in {"genuine", "real", "normal", "recommended", "truthful", "not-spam", "not_spam", "0", "false", "no"}:
            return 0
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0
    if numeric < 0:
        return 1
    return 1 if numeric == 1 else 0


def _normalize_fake_label_series(values: pd.Series) -> pd.Series:
    """Normalize a label column while handling common -1/1 encodings."""
    numeric_values = pd.to_numeric(values, errors="coerce")
    unique_numeric = set(numeric_values.dropna().astype(float).unique().tolist())
    if unique_numeric and unique_numeric.issubset({-1.0, 1.0}):
        return numeric_values.map(lambda value: 1 if float(value) < 0 else 0).astype(int)
    return values.map(_normalize_fake_label).astype(int)


def _join_text_parts(*parts: object) -> str:
    """Join title/body fields into one normalized review text."""
    return normalize_whitespace(". ".join(str(part).strip() for part in parts if str(part).strip()))


def _coerce_rating(value: object) -> float:
    """Convert a rating-like value into a 0..5 float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _empty_training_frame() -> pd.DataFrame:
    """Return an empty frame with the standard training columns."""
    return pd.DataFrame(
        columns=[
            "review_text",
            "rating",
            "label",
            "source",
            "product_family",
            "origin_family",
            "holdout_group",
            "split_group",
        ]
    )
