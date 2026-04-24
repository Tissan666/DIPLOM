"""Human-readable explanations for suspicious rating predictions."""

from __future__ import annotations

import pandas as pd


def derive_suspicion_reasons(feature_frame: pd.DataFrame) -> list[list[str]]:
    """Generate simple textual reasons from engineered features."""
    all_reasons: list[list[str]] = []

    for _, row in feature_frame.iterrows():
        reasons: list[str] = []

        if row["ip_unique_users"] >= 4:
            reasons.append("The same IP address is associated with many accounts.")
        if row["ip_ratings_last_1h"] >= 3:
            reasons.append("The rating happened in an unusual short-term burst.")
        if row["user_ratings_last_24h"] >= 3:
            reasons.append("The user posted several ratings in a short period.")
        if row["text_duplicate_count"] >= 3:
            reasons.append("The review text is duplicated across several ratings.")
        if row["rating_deviation_from_item_mean"] >= 1.8:
            reasons.append("The rating strongly deviates from the normal score for this item.")
        if row["rating_zscore_item"] >= 2.0:
            reasons.append("The score is statistically unusual compared with other ratings for this item.")
        if row["short_review_flag"] >= 1 and row["extreme_rating_flag"] >= 1:
            reasons.append("The rating is extreme and paired with a very short review.")
        if row.get("promotional_phrase_flag", 0.0) >= 1.0:
            reasons.append("The wording uses promotional stock phrases that often appear in coordinated ratings.")
        if row.get("slang_manipulation_score", 0.0) >= 0.55:
            reasons.append("The language pattern looks hype-heavy and weakly grounded in real usage detail.")
        if row.get("slang_template_dup_component", 0.0) >= 0.5:
            reasons.append("A similar slang-heavy template repeats across multiple ratings.")

        all_reasons.append(reasons)

    return all_reasons
