"""Heuristics for page-level rating-manipulation detection."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .slang_signals import build_page_slang_profiles, build_slang_suspicion_reason
from .utils import normalize_whitespace

PROMOTIONAL_PHRASES = [
    "buy now",
    "100% recommended",
    "best purchase ever",
    "must buy",
    "trust me",
    "perfect product",
    "changed my life",
    "highly recommended",
]


def analyze_review_manipulation_patterns(
    review_df: pd.DataFrame,
    include_page_context: bool = True,
    slang_model: dict | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Estimate rating-manipulation signals available from a scraped review page."""
    frame = review_df.copy().reset_index(drop=True)
    if frame.empty:
        return frame, _empty_summary()

    frame["author"] = _text_series(frame, "author")
    frame["title"] = _text_series(frame, "title")
    frame["review_text"] = _text_series(frame, "review_text")
    frame["rating"] = _numeric_series(frame, "rating")
    frame["parsed_date"] = pd.to_datetime(_text_series(frame, "date"), errors="coerce")

    frame["normalized_text"] = frame["review_text"].str.lower()
    frame["normalized_title"] = frame["title"].str.lower()
    frame["word_count"] = frame["review_text"].str.split().str.len().fillna(0).astype(float)
    frame["unique_word_ratio"] = frame["normalized_text"].map(_unique_word_ratio)
    frame["generic_phrase_flag"] = frame["normalized_text"].map(_contains_promotional_phrase).astype(float)
    frame["extreme_rating_flag"] = frame["rating"].isin([1.0, 5.0]).astype(float)
    frame["short_extreme_flag"] = ((frame["word_count"] <= 8) & (frame["extreme_rating_flag"] == 1.0)).astype(float)

    slang_page_context = build_page_slang_profiles(
        texts=frame["review_text"].tolist(),
        titles=frame["title"].tolist(),
        source_sites=(
            frame["source_site"].fillna("").astype(str).tolist()
            if "source_site" in frame.columns
            else frame["source"].fillna("").astype(str).tolist()
            if "source" in frame.columns
            else None
        ),
        slang_model=slang_model,
    )
    slang_profiles = pd.DataFrame(slang_page_context["profiles"], index=frame.index)
    frame = pd.concat([frame, slang_profiles], axis=1)

    frame["duplicate_text_count"] = frame["normalized_text"].map(frame.loc[frame["normalized_text"] != "", "normalized_text"].value_counts()).fillna(1.0)
    frame["duplicate_title_count"] = frame["normalized_title"].map(frame.loc[frame["normalized_title"] != "", "normalized_title"].value_counts()).fillna(1.0)

    author_keys = frame["author"].copy()
    author_keys = author_keys.where(author_keys != "", frame.index.map(lambda index: f"anonymous_{index}"))
    author_counts = author_keys.value_counts()
    frame["author_review_count"] = author_keys.map(author_counts).fillna(1.0)

    valid_days = frame.loc[frame["parsed_date"].notna(), "parsed_date"].dt.floor("D")
    day_counts = valid_days.value_counts()
    extreme_day_counts = valid_days[frame.loc[frame["parsed_date"].notna(), "extreme_rating_flag"] == 1.0].value_counts()
    frame["date_burst_count"] = frame["parsed_date"].dt.floor("D").map(day_counts).fillna(0.0)
    frame["date_extreme_count"] = frame["parsed_date"].dt.floor("D").map(extreme_day_counts).fillna(0.0)

    if not include_page_context:
        frame["duplicate_text_count"] = 1.0
        frame["duplicate_title_count"] = 1.0
        frame["author_review_count"] = 1.0
        frame["date_burst_count"] = 0.0
        frame["date_extreme_count"] = 0.0
        frame["slang_template_dup_count"] = 0
        frame["slang_template_dup_component"] = 0.0
        frame["slang_template_cluster_flag"] = 0.0

    page_review_count = len(frame) if include_page_context else 0
    page_extreme_ratio = float(frame["extreme_rating_flag"].mean()) if page_review_count else 0.0
    page_five_star_ratio = float((frame["rating"] >= 4.5).mean()) if page_review_count else 0.0
    page_one_star_ratio = float((frame["rating"] <= 1.5).mean()) if page_review_count else 0.0
    page_duplicate_ratio = float((frame["duplicate_text_count"] > 1).mean()) if page_review_count else 0.0
    page_author_concentration = float(author_counts.max() / page_review_count) if page_review_count and not author_counts.empty else 0.0
    page_same_day_ratio = float(day_counts.max() / page_review_count) if page_review_count and not day_counts.empty else 0.0
    page_slang_signal_ratio = float((frame["slang_manipulation_score"] >= 0.45).mean()) if page_review_count else 0.0
    page_bilingual_slang_ratio = float(frame["slang_bilingual_mix_flag"].mean()) if page_review_count else 0.0
    page_organic_slang_ratio = float((frame["slang_profile_label"] == "organic").mean()) if page_review_count else 0.0
    page_slang_template_ratio = float(slang_page_context.get("slang_template_cluster_ratio", 0.0) or 0.0) if include_page_context else 0.0
    slang_authenticity_mean = float(frame["slang_authenticity_score"].mean()) if page_review_count else 0.5
    slang_manipulation_mean = float(frame["slang_manipulation_score"].mean()) if page_review_count else 0.0
    slang_domain_label = str(slang_page_context.get("dominant_domain", "general") or "general")
    slang_domain_confidence = float(slang_page_context.get("domain_confidence", 0.0) or 0.0)
    slang_marketplace_label = str(slang_page_context.get("dominant_marketplace", "generic") or "generic")
    slang_model_strategy = str(slang_page_context.get("slang_model_strategy", "rule_based") or "rule_based")

    frame["duplicate_text_component"] = np.clip((frame["duplicate_text_count"] - 1.0) / 2.0, 0.0, 1.0)
    frame["duplicate_title_component"] = np.clip((frame["duplicate_title_count"] - 1.0) / 2.0, 0.0, 1.0)
    frame["author_repeat_component"] = np.clip((frame["author_review_count"] - 1.0) / 3.0, 0.0, 1.0)
    frame["date_burst_component"] = np.clip((frame["date_burst_count"] - 2.0) / 4.0, 0.0, 1.0)
    frame["date_extreme_component"] = np.clip((frame["date_extreme_count"] - 2.0) / 4.0, 0.0, 1.0)
    frame["generic_text_component"] = np.clip(
        0.45 * frame["generic_phrase_flag"]
        + 0.25 * np.clip(1.0 - frame["unique_word_ratio"], 0.0, 1.0)
        + 0.30 * frame["slang_manipulation_score"],
        0.0,
        1.0,
    )
    frame["slang_authenticity_credit"] = np.clip(
        frame["slang_authenticity_score"] * (1.0 - frame["slang_manipulation_score"]),
        0.0,
        1.0,
    )
    frame["local_manipulation_score"] = np.clip(
        0.24 * frame["generic_phrase_flag"]
        + 0.18 * frame["short_extreme_flag"]
        + 0.12 * frame["extreme_rating_flag"]
        + 0.18 * np.clip(1.0 - frame["unique_word_ratio"], 0.0, 1.0)
        + 0.18 * frame["slang_manipulation_score"]
        + 0.10 * frame["slang_bilingual_hype_flag"]
        + 0.08 * frame["slang_low_detail_flag"]
        - 0.16 * frame["slang_authenticity_credit"],
        0.0,
        1.0,
    )

    page_sample_gate = np.clip((page_review_count - 3.0) / 5.0, 0.0, 1.0)
    page_extreme_component = np.clip((page_extreme_ratio - 0.65) / 0.35, 0.0, 1.0)
    page_skew_component = np.clip(max(page_five_star_ratio, page_one_star_ratio) - 0.6, 0.0, 0.4) / 0.4
    page_duplicate_component = np.clip(page_duplicate_ratio / 0.35, 0.0, 1.0)
    page_author_component = np.clip((page_author_concentration - 0.15) / 0.35, 0.0, 1.0) * page_sample_gate
    page_same_day_component = np.clip((page_same_day_ratio - 0.2) / 0.5, 0.0, 1.0) * page_sample_gate
    page_slang_signal_component = np.clip((page_slang_signal_ratio - 0.12) / 0.38, 0.0, 1.0) * page_sample_gate
    page_bilingual_slang_component = np.clip((page_bilingual_slang_ratio - 0.08) / 0.22, 0.0, 1.0) * page_sample_gate
    page_slang_template_component = np.clip(page_slang_template_ratio / 0.35, 0.0, 1.0) * page_sample_gate

    frame["author_risk_score"] = np.clip(
        0.38 * frame["author_repeat_component"]
        + 0.20 * frame["date_burst_component"]
        + 0.16 * frame["duplicate_text_component"]
        + 0.10 * frame["generic_text_component"]
        + 0.08 * frame["slang_manipulation_score"]
        + 0.08 * frame["slang_template_dup_component"]
        - 0.08 * frame["slang_authenticity_credit"],
        0.0,
        1.0,
    )

    frame["rating_manipulation_score"] = np.clip(
        0.18 * frame["duplicate_text_component"]
        + 0.10 * frame["duplicate_title_component"]
        + 0.15 * frame["author_repeat_component"]
        + 0.11 * frame["date_burst_component"]
        + 0.08 * frame["date_extreme_component"]
        + 0.12 * frame["short_extreme_flag"]
        + 0.08 * frame["generic_text_component"]
        + 0.08 * frame["slang_manipulation_score"]
        + 0.07 * frame["slang_template_dup_component"]
        + 0.04 * page_extreme_component
        + 0.06 * page_duplicate_component
        + 0.05 * page_author_component
        + 0.05 * page_same_day_component
        + 0.07 * page_skew_component
        + 0.04 * page_slang_signal_component
        + 0.04 * page_bilingual_slang_component
        + 0.04 * page_slang_template_component
        - 0.08 * frame["slang_authenticity_credit"],
        0.0,
        1.0,
    )

    frame["manipulation_reasons"] = frame.apply(
        lambda row: _derive_manipulation_reasons(
            row=row,
            page_extreme_ratio=page_extreme_ratio,
            page_duplicate_ratio=page_duplicate_ratio,
            page_same_day_ratio=page_same_day_ratio,
            page_author_concentration=page_author_concentration,
            page_slang_signal_ratio=page_slang_signal_ratio,
            page_bilingual_slang_ratio=page_bilingual_slang_ratio,
            page_slang_template_ratio=page_slang_template_ratio,
            page_review_count=page_review_count,
        ),
        axis=1,
    )

    suspicious_authors = (
        frame.assign(author_key=author_keys)
        .loc[author_keys.str.startswith("anonymous_") == False]
        .groupby("author_key")
        .agg(
            review_count=("author_key", "size"),
            average_manipulation_score=("rating_manipulation_score", "mean"),
            suspicious_reviews=("rating_manipulation_score", lambda values: int(np.sum(np.asarray(values) >= 0.55))),
        )
        .sort_values(["suspicious_reviews", "average_manipulation_score", "review_count"], ascending=[False, False, False])
        .reset_index()
        .rename(columns={"author_key": "author"})
    )

    summary = {
        "suspicious_authors": int(len(suspicious_authors.loc[suspicious_authors["suspicious_reviews"] > 0])),
        "authors_with_repeated_activity": int((frame["author_review_count"] > 1).sum()),
        "page_extreme_rating_ratio": page_extreme_ratio,
        "page_duplicate_text_ratio": page_duplicate_ratio,
        "page_same_day_burst_ratio": page_same_day_ratio,
        "page_author_concentration": page_author_concentration,
        "slang_authenticity_mean": slang_authenticity_mean,
        "slang_manipulation_mean": slang_manipulation_mean,
        "page_slang_signal_ratio": page_slang_signal_ratio,
        "page_bilingual_slang_ratio": page_bilingual_slang_ratio,
        "page_organic_slang_ratio": page_organic_slang_ratio,
        "slang_domain_label": slang_domain_label,
        "slang_domain_confidence": slang_domain_confidence,
        "slang_marketplace_label": slang_marketplace_label,
        "slang_template_cluster_ratio": page_slang_template_ratio,
        "slang_model_strategy": slang_model_strategy,
        "manipulation_score_mean": float(frame["rating_manipulation_score"].mean()),
        "rating_manipulation_risk": _risk_level(float(frame["rating_manipulation_score"].mean())),
        "suspicious_author_records": suspicious_authors.to_dict(orient="records"),
    }
    return frame, summary


def _derive_manipulation_reasons(
    row: pd.Series,
    page_extreme_ratio: float,
    page_duplicate_ratio: float,
    page_same_day_ratio: float,
    page_author_concentration: float,
    page_slang_signal_ratio: float,
    page_bilingual_slang_ratio: float,
    page_slang_template_ratio: float,
    page_review_count: int,
) -> list[str]:
    """Generate user-facing reasons for manipulation-related suspicion."""
    reasons: list[str] = []
    if row["duplicate_text_count"] >= 2:
        reasons.append("The same or nearly identical review text appears multiple times on this page.")
    if row["duplicate_title_count"] >= 2 and row["title"]:
        reasons.append("The review title repeats across multiple ratings.")
    if row["author_review_count"] >= 2 and row["author"]:
        reasons.append("The same author appears unusually often in the current review sample.")
    if row["date_burst_count"] >= 3:
        reasons.append("Many reviews were published in a tight date cluster.")
    if row["date_extreme_count"] >= 3:
        reasons.append("The date cluster is dominated by extreme ratings.")
    if row["short_extreme_flag"] >= 1:
        reasons.append("An extreme rating is paired with a very short explanation.")
    if row["generic_phrase_flag"] >= 1:
        reasons.append("The wording resembles promotional or templated review language.")

    slang_reason = build_slang_suspicion_reason(row.to_dict())
    if slang_reason:
        reasons.append(slang_reason)

    if page_extreme_ratio >= 0.7:
        reasons.append("The page is dominated by extreme ratings, which may indicate manipulation.")
    if page_duplicate_ratio >= 0.25:
        reasons.append("A noticeable share of the page contains duplicated review content.")
    if page_review_count >= 4 and page_same_day_ratio >= 0.35:
        reasons.append("A large portion of the reviews appeared on the same day.")
    if page_review_count >= 4 and page_author_concentration >= 0.25:
        reasons.append("A small set of authors contributes a disproportionate share of reviews.")
    if page_review_count >= 4 and page_slang_signal_ratio >= 0.25:
        reasons.append("Many comments rely on hype-heavy slang instead of grounded product detail.")
    if page_review_count >= 4 and page_bilingual_slang_ratio >= 0.18:
        reasons.append("Russian and English slang are mixed unusually often across the current review page.")
    if page_review_count >= 4 and page_slang_template_ratio >= 0.18:
        reasons.append("A repeated slang template appears across multiple reviews on the page.")
    return reasons


def _contains_promotional_phrase(text: str) -> bool:
    """Check whether a review includes stock promotional language."""
    return any(phrase in text for phrase in PROMOTIONAL_PHRASES)


def _text_series(frame: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    """Return a normalized text column with a stable default value."""
    if column not in frame.columns:
        return pd.Series([default] * len(frame), index=frame.index, dtype="object").map(normalize_whitespace)
    return frame[column].fillna(default).astype(str).map(normalize_whitespace)


def _numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    """Return a numeric column with a stable default value."""
    if column not in frame.columns:
        return pd.Series([default] * len(frame), index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _unique_word_ratio(text: str) -> float:
    """Return the lexical diversity of a review text."""
    tokens = re.findall(r"[\w'-]+", text.lower(), flags=re.UNICODE)
    if not tokens:
        return 1.0
    return float(len(set(tokens)) / len(tokens))


def _risk_level(score: float) -> str:
    """Convert a manipulation score to a short label."""
    if score >= 0.8:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def _empty_summary() -> dict:
    """Return a summary for empty review pages."""
    return {
        "suspicious_authors": 0,
        "authors_with_repeated_activity": 0,
        "page_extreme_rating_ratio": 0.0,
        "page_duplicate_text_ratio": 0.0,
        "page_same_day_burst_ratio": 0.0,
        "page_author_concentration": 0.0,
        "slang_authenticity_mean": 0.5,
        "slang_manipulation_mean": 0.0,
        "page_slang_signal_ratio": 0.0,
        "page_bilingual_slang_ratio": 0.0,
        "page_organic_slang_ratio": 0.0,
        "slang_domain_label": "general",
        "slang_domain_confidence": 0.0,
        "slang_marketplace_label": "generic",
        "slang_template_cluster_ratio": 0.0,
        "slang_model_strategy": "rule_based",
        "manipulation_score_mean": 0.0,
        "rating_manipulation_risk": "none",
        "suspicious_author_records": [],
    }
