"""Uncertainty-aware abstention policy for suspicious review triage."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.pipeline import FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer

TRIAGE_CONFIDENT_SUSPICIOUS = "confident_suspicious"
TRIAGE_CONFIDENT_CLEAN = "confident_clean"
TRIAGE_MANUAL_REVIEW = "needs_manual_review"


def build_review_uncertainty_frame(
    review_df: pd.DataFrame,
    text_probabilities: np.ndarray,
    hybrid_probabilities: np.ndarray,
    threshold: float,
    vectorizer: TfidfVectorizer | FeatureUnion,
) -> pd.DataFrame:
    """Build one uncertainty feature frame for review-level triage."""
    frame = review_df.copy().reset_index(drop=True)
    text_probs = np.asarray(text_probabilities, dtype=np.float32).reshape(-1)
    hybrid_probs = np.asarray(hybrid_probabilities, dtype=np.float32).reshape(-1)
    if len(frame) != len(text_probs) or len(frame) != len(hybrid_probs):
        raise ValueError("Uncertainty features require one text and hybrid probability per review row.")

    text_values = frame["review_text"].fillna("").astype(str)
    token_lists = text_values.str.lower().str.findall(r"[\w'-]+")
    token_counts = token_lists.str.len().fillna(0).to_numpy(dtype=np.float32)
    lexical_coverage = _lexical_coverage_values(token_lists.tolist(), vectorizer=vectorizer)
    domain_labels = (
        frame["slang_domain_label"].fillna("general").astype(str)
        if "slang_domain_label" in frame.columns
        else pd.Series(["general"] * len(frame), index=frame.index, dtype="object")
    )

    frame["text_suspicious_probability"] = np.clip(text_probs, 0.0, 1.0)
    frame["suspicious_probability"] = np.clip(hybrid_probs, 0.0, 1.0)
    frame["decision_margin"] = np.abs(frame["suspicious_probability"] - float(threshold))
    frame["text_hybrid_gap"] = np.abs(frame["text_suspicious_probability"] - frame["suspicious_probability"])
    frame["text_manipulation_gap"] = np.abs(
        frame["text_suspicious_probability"] - _numeric_series(frame, "rating_manipulation_score")
    )
    frame["lexical_coverage"] = lexical_coverage
    frame["short_evidence_component"] = np.clip((8.0 - token_counts) / 8.0, 0.0, 1.0)
    frame["novel_slang_component"] = np.clip(
        0.45
        * (
            (_numeric_series(frame, "slang_hit_count") > 0.0)
            & (
                (_numeric_series(frame, "slang_learned_suspicious_count") + _numeric_series(frame, "slang_learned_authentic_count"))
                <= 0.0
            )
        ).astype(float)
        + 0.30
        * (
            (_numeric_series(frame, "slang_known_marketplace_flag") <= 0.0)
            & (_numeric_series(frame, "slang_bilingual_mix_flag") >= 1.0)
        ).astype(float)
        + 0.25
        * (
            (domain_labels == "general")
            & (_numeric_series(frame, "slang_hit_count") > 0.0)
            & (_numeric_series(frame, "slang_domain_grounding") < 0.22)
        ).astype(float),
        0.0,
        1.0,
    )
    frame["ood_score"] = np.clip(
        0.48 * np.clip((0.62 - frame["lexical_coverage"]) / 0.62, 0.0, 1.0)
        + 0.22 * frame["short_evidence_component"]
        + 0.30 * frame["novel_slang_component"],
        0.0,
        1.0,
    )
    evidence_strength = np.maximum.reduce(
        [
            np.abs(frame["text_suspicious_probability"] - 0.5) * 2.0,
            np.abs(frame["suspicious_probability"] - 0.5) * 2.0,
            _numeric_series(frame, "local_manipulation_score"),
            _numeric_series(frame, "slang_authenticity_score"),
            _numeric_series(frame, "slang_manipulation_score"),
        ]
    )
    frame["weak_evidence_component"] = np.clip((0.72 - evidence_strength) / 0.72, 0.0, 1.0)
    frame["uncertainty_score"] = np.clip(
        0.44 * np.clip((0.20 - frame["decision_margin"]) / 0.20, 0.0, 1.0)
        + 0.18 * np.clip(frame["text_hybrid_gap"] / 0.45, 0.0, 1.0)
        + 0.16 * np.clip(frame["text_manipulation_gap"] / 0.65, 0.0, 1.0)
        + 0.12 * frame["weak_evidence_component"]
        + 0.10 * frame["ood_score"],
        0.0,
        1.0,
    )
    frame["automation_confidence"] = np.clip(1.0 - np.maximum(frame["uncertainty_score"], frame["ood_score"]), 0.0, 1.0)
    return frame


def train_review_abstention_policy(
    uncertainty_df: pd.DataFrame,
    labels: Sequence[int] | np.ndarray,
    threshold: float,
) -> tuple[dict, dict]:
    """Tune the manual-review gate on a validation holdout."""
    frame = uncertainty_df.copy().reset_index(drop=True)
    label_values = np.asarray(labels, dtype=np.int32).reshape(-1)
    if len(frame) != len(label_values):
        raise ValueError("Abstention-policy calibration requires one label per review row.")

    suspicious_candidates = np.unique(
        np.round(np.linspace(max(float(threshold) + 0.08, 0.60), min(0.92, float(threshold) + 0.30), 8), 3)
    )
    clean_candidates = np.unique(
        np.round(np.linspace(max(0.08, float(threshold) - 0.30), min(0.40, float(threshold) - 0.08), 8), 3)
    )
    uncertainty_candidates = _candidate_thresholds(frame["uncertainty_score"].to_numpy(dtype=float), fallback=[0.34, 0.42, 0.50, 0.58])
    ood_candidates = _candidate_thresholds(frame["ood_score"].to_numpy(dtype=float), fallback=[0.30, 0.40, 0.50, 0.62])

    baseline_predictions = (frame["suspicious_probability"].to_numpy(dtype=float) >= float(threshold)).astype(np.int32)
    baseline_errors = baseline_predictions != label_values

    best_policy: dict | None = None
    best_report: dict | None = None
    best_score = -1e9

    for suspicious_threshold in suspicious_candidates:
        for clean_threshold in clean_candidates:
            if clean_threshold >= float(threshold) or suspicious_threshold <= float(threshold):
                continue
            if clean_threshold >= suspicious_threshold:
                continue
            for uncertainty_threshold in uncertainty_candidates:
                for ood_threshold in ood_candidates:
                    candidate_policy = {
                        "threshold": float(threshold),
                        "confident_suspicious_threshold": float(suspicious_threshold),
                        "confident_clean_threshold": float(clean_threshold),
                        "uncertainty_threshold": float(uncertainty_threshold),
                        "ood_threshold": float(ood_threshold),
                        "strategy": "validation_grid_search",
                    }
                    triaged = apply_review_abstention_policy(frame, candidate_policy)
                    report = _evaluate_abstention_policy(
                        triaged,
                        labels=label_values,
                        threshold=float(threshold),
                        baseline_errors=baseline_errors,
                    )
                    score = float(report["selection_score"])
                    if score > best_score:
                        best_score = score
                        best_policy = candidate_policy
                        best_report = report

    if best_policy is None or best_report is None:
        best_policy = {
            "threshold": float(threshold),
            "confident_suspicious_threshold": float(min(0.88, max(float(threshold) + 0.12, 0.68))),
            "confident_clean_threshold": float(max(0.12, min(float(threshold) - 0.12, 0.32))),
            "uncertainty_threshold": 0.46,
            "ood_threshold": 0.46,
            "strategy": "fallback_defaults",
        }
        best_report = _evaluate_abstention_policy(
            apply_review_abstention_policy(frame, best_policy),
            labels=label_values,
            threshold=float(threshold),
            baseline_errors=baseline_errors,
        )

    best_policy["validation_metrics"] = {
        key: value
        for key, value in best_report.items()
        if key not in {"selection_score"}
    }
    return best_policy, best_report


def apply_review_abstention_policy(review_df: pd.DataFrame, policy: dict) -> pd.DataFrame:
    """Apply the triage policy and mark reviews that need manual moderation."""
    frame = review_df.copy().reset_index(drop=True)
    suspicious_threshold = float(policy["confident_suspicious_threshold"])
    clean_threshold = float(policy["confident_clean_threshold"])
    uncertainty_threshold = float(policy["uncertainty_threshold"])
    ood_threshold = float(policy["ood_threshold"])

    triage_labels: list[str] = []
    manual_review_flags: list[int] = []
    manual_review_reasons: list[list[str]] = []

    for _, row in frame.iterrows():
        probability = float(row.get("suspicious_probability", 0.0) or 0.0)
        uncertainty_score = float(row.get("uncertainty_score", 0.0) or 0.0)
        ood_score = float(row.get("ood_score", 0.0) or 0.0)

        reasons: list[str] = []
        if clean_threshold < probability < suspicious_threshold:
            reasons.append("The hybrid score falls inside the manual-review band.")
        if uncertainty_score > uncertainty_threshold:
            reasons.append("The model signals disagree too much for an automated decision.")
        if ood_score > ood_threshold:
            reasons.append("The review looks out-of-domain relative to the training corpus.")
        if float(row.get("lexical_coverage", 1.0) or 1.0) < 0.32:
            reasons.append("Too little of the wording matches patterns seen during training.")
        if float(row.get("text_hybrid_gap", 0.0) or 0.0) > 0.24:
            reasons.append("The raw text model and the hybrid fraud model disagree materially.")

        if not reasons and probability >= suspicious_threshold:
            triage_labels.append(TRIAGE_CONFIDENT_SUSPICIOUS)
            manual_review_flags.append(0)
            manual_review_reasons.append([])
            continue
        if not reasons and probability <= clean_threshold:
            triage_labels.append(TRIAGE_CONFIDENT_CLEAN)
            manual_review_flags.append(0)
            manual_review_reasons.append([])
            continue

        triage_labels.append(TRIAGE_MANUAL_REVIEW)
        manual_review_flags.append(1)
        manual_review_reasons.append(reasons or ["The review needs a human decision because the evidence is not decisive enough."])

    frame["triage_label"] = triage_labels
    frame["requires_manual_review"] = np.asarray(manual_review_flags, dtype=np.int32)
    frame["manual_review_reasons"] = manual_review_reasons
    return frame


def summarize_review_triage(review_df: pd.DataFrame) -> dict[str, float | int]:
    """Aggregate triage counts and uncertainty metrics for one review batch."""
    triage_series = review_df.get("triage_label", pd.Series([], dtype="object")).fillna("").astype(str)
    total_reviews = int(len(review_df))
    confident_suspicious = int((triage_series == TRIAGE_CONFIDENT_SUSPICIOUS).sum())
    confident_clean = int((triage_series == TRIAGE_CONFIDENT_CLEAN).sum())
    manual_review = int((triage_series == TRIAGE_MANUAL_REVIEW).sum())
    if total_reviews:
        uncertainty_series = pd.to_numeric(
            review_df.get("uncertainty_score", pd.Series(0.0, index=review_df.index)),
            errors="coerce",
        ).fillna(0.0)
        ood_series = pd.to_numeric(
            review_df.get("ood_score", pd.Series(0.0, index=review_df.index)),
            errors="coerce",
        ).fillna(0.0)
    else:
        uncertainty_series = pd.Series([], dtype=np.float32)
        ood_series = pd.Series([], dtype=np.float32)
    return {
        "confident_suspicious_reviews": confident_suspicious,
        "confident_clean_reviews": confident_clean,
        "manual_review_reviews": manual_review,
        "manual_review_ratio": float(manual_review / max(total_reviews, 1)),
        "automated_decision_ratio": float((confident_suspicious + confident_clean) / max(total_reviews, 1)),
        "uncertainty_mean": float(uncertainty_series.mean()) if total_reviews else 0.0,
        "ood_alert_ratio": float((ood_series >= 0.45).mean()) if total_reviews else 0.0,
    }


def _evaluate_abstention_policy(
    triaged_df: pd.DataFrame,
    labels: np.ndarray,
    threshold: float,
    baseline_errors: np.ndarray,
) -> dict:
    """Score one candidate policy on the validation split."""
    triage_series = triaged_df["triage_label"].fillna("").astype(str)
    confident_mask = triage_series != TRIAGE_MANUAL_REVIEW
    coverage = float(confident_mask.mean()) if len(triaged_df) else 0.0
    automated_predictions = np.where(triage_series == TRIAGE_CONFIDENT_SUSPICIOUS, 1, 0)

    if confident_mask.any():
        confident_accuracy = float(np.mean(automated_predictions[confident_mask] == labels[confident_mask]))
    else:
        confident_accuracy = 0.0

    suspicious_mask = triage_series == TRIAGE_CONFIDENT_SUSPICIOUS
    clean_mask = triage_series == TRIAGE_CONFIDENT_CLEAN
    suspicious_precision = float(np.mean(labels[suspicious_mask] == 1)) if suspicious_mask.any() else 1.0
    clean_precision = float(np.mean(labels[clean_mask] == 0)) if clean_mask.any() else 1.0
    manual_mask = triage_series == TRIAGE_MANUAL_REVIEW
    manual_error_capture = float(np.mean(manual_mask[baseline_errors])) if baseline_errors.any() else 0.0

    selection_score = (
        1.85 * confident_accuracy
        + 0.35 * min(coverage, 0.86)
        + 0.32 * manual_error_capture
        + 0.16 * suspicious_precision
        + 0.12 * clean_precision
        - 0.90 * max(0.0, 0.84 - confident_accuracy)
        - 0.25 * max(0.0, 0.18 - coverage)
    )

    return {
        "threshold": float(threshold),
        "coverage": coverage,
        "manual_review_ratio": float(manual_mask.mean()) if len(triaged_df) else 0.0,
        "confident_accuracy": confident_accuracy,
        "suspicious_precision": suspicious_precision,
        "clean_precision": clean_precision,
        "manual_error_capture": manual_error_capture,
        "selection_score": float(selection_score),
    }


def _lexical_coverage_values(
    token_lists: Sequence[list[str]],
    vectorizer: TfidfVectorizer | FeatureUnion,
) -> np.ndarray:
    """Measure how much of the review vocabulary was seen during training."""
    known_tokens = _known_word_vocabulary(vectorizer)
    if not known_tokens:
        return np.zeros(len(token_lists), dtype=np.float32)

    coverage_values: list[float] = []
    for tokens in token_lists:
        filtered_tokens = [token for token in tokens if token]
        if not filtered_tokens:
            coverage_values.append(0.0)
            continue
        known_count = sum(1 for token in filtered_tokens if token in known_tokens)
        coverage_values.append(float(known_count / max(len(filtered_tokens), 1)))
    return np.asarray(coverage_values, dtype=np.float32)


def _known_word_vocabulary(vectorizer: TfidfVectorizer | FeatureUnion) -> set[str]:
    """Extract the fitted word vocabulary from the review vectorizer bundle."""
    if isinstance(vectorizer, TfidfVectorizer):
        return set(getattr(vectorizer, "vocabulary_", {}).keys())
    if isinstance(vectorizer, FeatureUnion):
        for name, transformer in vectorizer.transformer_list:
            if name == "word_tfidf":
                return _known_word_vocabulary(transformer)
    return set()


def _candidate_thresholds(values: np.ndarray, fallback: list[float]) -> np.ndarray:
    """Create a compact candidate grid from one validation feature distribution."""
    finite_values = values[np.isfinite(values)]
    if finite_values.size == 0:
        return np.asarray(fallback, dtype=float)
    quantiles = np.quantile(finite_values, [0.35, 0.50, 0.65, 0.80, 0.90])
    candidates = np.unique(np.round(np.clip(quantiles, 0.05, 0.95), 3))
    if candidates.size == 0:
        return np.asarray(fallback, dtype=float)
    return candidates.astype(float)


def _numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    """Return one numeric column with a stable float fallback."""
    if column not in frame.columns:
        return pd.Series(np.full(len(frame), float(default), dtype=np.float32), index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)
