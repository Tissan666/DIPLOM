"""Local AI-generated review text signals.

This module treats AI-text detection as a moderation signal, not proof.  The
runtime scorer blends a small trained logistic model with conservative
handcrafted review-language features so it can work offline and keep false
positives lower on concrete, personal customer feedback.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
import os
import random
import re

import joblib
import numpy as np
import pandas as pd

from .utils import ensure_directory, normalize_whitespace, save_json


AI_TEXT_MODEL_FILENAME = "ai_text_detector.joblib"
AI_TEXT_MODEL_VERSION = "local_ai_text_v1"
AI_TEXT_MIN_WORDS = 12
AI_TEXT_HINT_THRESHOLD = 0.52
AI_TEXT_FLAG_THRESHOLD = 0.66
AI_TEXT_STRONG_THRESHOLD = 0.76
TOKEN_RE = re.compile(r"[A-Za-z\u0400-\u04ff0-9']+", flags=re.IGNORECASE)

NUMERIC_FEATURE_NAMES = [
    "word_count_log",
    "sentence_count_log",
    "avg_sentence_len",
    "sentence_len_cv",
    "unique_word_ratio",
    "generic_phrase_density",
    "connector_density",
    "catalog_phrase_density",
    "personal_detail_density",
    "concrete_detail_density",
    "colloquial_density",
    "digit_density",
    "punctuation_density",
    "long_dash_density",
    "exclamation_density",
    "balanced_structure_score",
    "low_detail_polish_score",
    "repetition_ratio",
    "mixed_script_score",
]

AI_STYLE_PHRASES = [
    "overall",
    "in conclusion",
    "to summarize",
    "it is worth noting",
    "as a user",
    "this product delivers",
    "pleasantly surprised",
    "exceeded my expectations",
    "highly recommend",
    "recommend it to anyone",
    "great value for money",
    "perfect choice",
    "\u0432 \u0446\u0435\u043b\u043e\u043c",
    "\u0441\u043b\u0435\u0434\u0443\u0435\u0442 \u043e\u0442\u043c\u0435\u0442\u0438\u0442\u044c",
    "\u043c\u043e\u0436\u043d\u043e \u0441\u043a\u0430\u0437\u0430\u0442\u044c",
    "\u0434\u0430\u043d\u043d\u044b\u0439 \u0442\u043e\u0432\u0430\u0440",
    "\u0434\u0430\u043d\u043d\u043e\u0435 \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e",
    "\u043f\u043e\u043a\u0443\u043f\u043a\u0430 \u043e\u043f\u0440\u0430\u0432\u0434\u0430\u043b\u0430",
    "\u043f\u043e\u0434\u0432\u043e\u0434\u044f \u0438\u0442\u043e\u0433",
    "\u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0443\u044e \u043a \u043f\u043e\u043a\u0443\u043f\u043a\u0435",
    "\u043f\u0440\u0438\u044f\u0442\u043d\u043e \u0443\u0434\u0438\u0432\u0438\u043b",
    "\u043f\u0440\u0435\u0432\u0437\u043e\u0448\u0435\u043b \u043e\u0436\u0438\u0434\u0430\u043d\u0438\u044f",
]

CONNECTOR_PHRASES = [
    "however",
    "moreover",
    "furthermore",
    "additionally",
    "therefore",
    "nevertheless",
    "on the other hand",
    "\u043e\u0434\u043d\u0430\u043a\u043e",
    "\u043a\u0440\u043e\u043c\u0435 \u0442\u043e\u0433\u043e",
    "\u0442\u0435\u043c \u043d\u0435 \u043c\u0435\u043d\u0435\u0435",
    "\u043f\u0440\u0438 \u044d\u0442\u043e\u043c",
    "\u0441 \u0434\u0440\u0443\u0433\u043e\u0439 \u0441\u0442\u043e\u0440\u043e\u043d\u044b",
]

CATALOG_PHRASES = [
    "excellent quality",
    "premium quality",
    "durable materials",
    "modern design",
    "user-friendly",
    "reliable performance",
    "high quality",
    "stylish appearance",
    "\u043e\u0442\u043b\u0438\u0447\u043d\u043e\u0435 \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u043e",
    "\u0432\u044b\u0441\u043e\u043a\u043e\u0435 \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u043e",
    "\u043a\u0430\u0447\u0435\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0435 \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u044b",
    "\u0441\u0442\u0438\u043b\u044c\u043d\u044b\u0439 \u0434\u0438\u0437\u0430\u0439\u043d",
    "\u0443\u0434\u043e\u0431\u0435\u043d \u0432 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u0438",
    "\u043d\u0430\u0434\u0435\u0436\u043d\u0430\u044f \u0440\u0430\u0431\u043e\u0442\u0430",
]

AI_REVIEW_CLICHE_PHRASES = [
    "price is fair",
    "worth paying",
    "worth the money",
    "shipping/support/packaging",
    "delivery/support/packaging",
    "pleasantly surprised",
    "\u0446\u0435\u043d\u0430 \u0430\u0434\u0435\u043a\u0432\u0430\u0442\u043d\u0430\u044f",
    "\u043d\u0435 \u0436\u0430\u043b\u043a\u043e \u043f\u043b\u0430\u0442\u0438\u0442\u044c",
    "\u043f\u043b\u0430\u0442\u0438\u0442\u044c \u0437\u0430 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442",
    "\u0434\u043e\u0441\u0442\u0430\u0432\u043a\u0430/\u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430/\u0443\u043f\u0430\u043a\u043e\u0432\u043a\u0430",
    "\u0434\u043e\u0441\u0442\u0430\u0432\u043a\u0430 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430 \u0443\u043f\u0430\u043a\u043e\u0432\u043a\u0430",
    "\u043f\u0440\u0438\u044f\u0442\u043d\u043e \u0443\u0434\u0438\u0432\u0438\u043b\u0438",
    "\u043f\u0440\u0438\u044f\u0442\u043d\u043e \u0443\u0434\u0438\u0432\u0438\u043b\u0430",
]

MARKETPLACE_STRUCTURE_MARKERS = [
    "\u0434\u043e\u0441\u0442\u043e\u0438\u043d\u0441\u0442\u0432\u0430:",
    "\u043d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043a\u0438:",
    "\u043a\u043e\u043c\u043c\u0435\u043d\u0442\u0430\u0440\u0438\u0439:",
    "pros:",
    "cons:",
]

MARKETPLACE_CONCRETE_TERMS = [
    "\u043e\u0440\u0438\u0433\u0438\u043d\u0430\u043b",
    "\u043f\u043b\u043e\u043c\u0431",
    "\u0441\u0435\u0440\u0438\u0439\u043d",
    "\u0433\u0430\u0440\u0430\u043d\u0442",
    "\u043f\u043e\u0434\u0434\u0435\u043b\u043a",
    "\u0443\u043f\u0430\u043a\u043e\u0432",
    "\u043a\u043e\u0440\u043e\u0431",
    "\u0434\u043e\u0441\u0442\u0430\u0432",
    "\u043f\u0440\u043e\u0448\u0438\u0432\u043a",
    "\u0437\u0430\u0440\u044f\u0434",
    "\u0437\u0432\u0443\u043a",
    "\u0430\u0439\u0444\u043e\u043d",
    "\u043c\u0430\u043a\u0431\u0443\u043a",
    "\u0440\u0430\u0437\u043c\u0435\u0440",
    "\u0434\u0435\u0442\u0430\u043b",
    "\u0440\u0435\u0431\u0435\u043d",
    "\u0440\u0435\u0431\u0451\u043d",
]

PERSONAL_DETAIL_TERMS = [
    "i bought",
    "i use",
    "my wife",
    "my husband",
    "my kid",
    "my desk",
    "at work",
    "in the kitchen",
    "after a week",
    "after two weeks",
    "delivered",
    "box arrived",
    "charging",
    "battery",
    "scratched",
    "size",
    "cm",
    "mm",
    "\u0431\u0440\u0430\u043b",
    "\u0431\u0440\u0430\u043b\u0430",
    "\u0437\u0430\u043a\u0430\u0437\u0430\u043b",
    "\u0437\u0430\u043a\u0430\u0437\u0430\u043b\u0430",
    "\u043f\u043e\u043b\u044c\u0437\u0443\u044e\u0441\u044c",
    "\u0434\u043e\u0441\u0442\u0430\u0432\u0438\u043b\u0438",
    "\u0447\u0435\u0440\u0435\u0437 \u043d\u0435\u0434\u0435\u043b\u044e",
    "\u043d\u0430 \u043a\u0443\u0445\u043d\u0435",
    "\u043d\u0430 \u0440\u0430\u0431\u043e\u0442\u0435",
    "\u0440\u0435\u0431\u0435\u043d\u043a\u0443",
    "\u043c\u0443\u0436\u0443",
    "\u0436\u0435\u043d\u0435",
    "\u0440\u0430\u0437\u043c\u0435\u0440",
    "\u0443\u043f\u0430\u043a\u043e\u0432\u043a",
    "\u0446\u0430\u0440\u0430\u043f",
    "\u0437\u0430\u0440\u044f\u0434",
]

COLLOQUIAL_TERMS = [
    "ok",
    "meh",
    "kinda",
    "pretty good",
    "not bad",
    "works fine",
    "for the price",
    "\u043d\u043e\u0440\u043c",
    "\u043d\u043e\u0440\u043c\u0430\u043b\u044c\u043d\u043e",
    "\u0442\u0430\u043a \u0441\u0435\u0431\u0435",
    "\u0437\u0430 \u0441\u0432\u043e\u0438 \u0434\u0435\u043d\u044c\u0433\u0438",
    "\u043f\u043e\u043a\u0430 \u043d\u043e\u0440\u043c",
    "\u0432\u0440\u043e\u0434\u0435",
    "\u043a\u043e\u0440\u043e\u0431\u043a\u0430",
]


def build_ai_text_signals(
    review_df: pd.DataFrame,
    artifacts_dir: str | Path = "models",
) -> tuple[pd.DataFrame, dict]:
    """Attach AI-generated text likelihood signals to review rows."""
    frame = _with_default_columns(review_df.copy())
    if not _ai_text_enabled():
        return frame, _summary(frame, "disabled")

    text_values = [
        normalize_whitespace(f"{row.get('title', '')} {row.get('review_text', '')}")
        for _, row in frame.iterrows()
    ]
    if not any(text_values):
        return frame, _summary(frame, "no_text")

    model_bundle = _load_ai_text_artifact(artifacts_dir)
    model_status = "ready_trained" if model_bundle else "ready_builtin"
    model_name = str(model_bundle.get("version", AI_TEXT_MODEL_VERSION) if model_bundle else f"{AI_TEXT_MODEL_VERSION}_builtin")
    flag_threshold = _flag_threshold_for_bundle(model_bundle)
    prefix_counts = _prefix_counts(text_values)

    for row_index, text in enumerate(text_values):
        signal = _score_ai_text(text, model_bundle=model_bundle)
        prefix = _template_prefix(text)
        prefix_count = prefix_counts.get(prefix, 0) if prefix else 0
        if prefix_count >= 2 and signal["ai_text_score"] >= 0.40 and signal["ai_text_word_count"] >= AI_TEXT_MIN_WORDS:
            signal["ai_text_score"] = float(np.clip(signal["ai_text_score"] + min(0.12, 0.04 * (prefix_count - 1)), 0.0, 1.0))
            signal["ai_text_label"] = _label_for_score(
                signal["ai_text_score"],
                signal["ai_text_word_count"],
                flag_threshold=flag_threshold,
            )
            signal["ai_text_flag"] = int(signal["ai_text_score"] >= flag_threshold)
            signal["ai_text_reasons"].append("The wording contains repeated AI-style review openings across the current page.")

        frame.at[row_index, "ai_text_score"] = signal["ai_text_score"]
        frame.at[row_index, "ai_text_flag"] = signal["ai_text_flag"]
        frame.at[row_index, "ai_text_label"] = signal["ai_text_label"]
        frame.at[row_index, "ai_text_model"] = model_name
        frame.at[row_index, "ai_text_reasons"] = signal["ai_text_reasons"]
        frame.at[row_index, "ai_text_feature_hits"] = signal["ai_text_feature_hits"]
        frame.at[row_index, "ai_text_word_count"] = signal["ai_text_word_count"]

    return frame, _summary(frame, model_status, model_name=model_name)


def train_ai_text_detector(
    artifacts_dir: str | Path = "models",
    output_dir: str | Path = "outputs",
    n_samples: int = 2600,
    random_state: int = 42,
    real_negative_texts: list[str] | None = None,
    max_real_negative_texts: int = 2000,
) -> dict:
    """Train the lightweight AI-text detector with synthetic positives and real marketplace negatives."""
    from scipy import sparse
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    artifacts_dir = ensure_directory(artifacts_dir)
    output_dir = ensure_directory(output_dir)
    texts, labels = _generate_training_examples(n_samples=n_samples, random_state=random_state)
    real_negative_count = 0
    real_negative_holdout_texts: list[str] = []
    if real_negative_texts:
        real_negative_candidates = [
            normalize_whitespace(text)
            for text in real_negative_texts
            if isinstance(text, str) and len(normalize_whitespace(text).split()) >= AI_TEXT_MIN_WORDS
        ]
        real_negative_candidates = list(dict.fromkeys(real_negative_candidates))
        rng = random.Random(random_state + 7919)
        rng.shuffle(real_negative_candidates)
        real_negative_candidates = real_negative_candidates[: max(0, int(max_real_negative_texts))]
        if len(real_negative_candidates) >= 500:
            holdout_target = min(2000, max(250, int(len(real_negative_candidates) * 0.20)))
            real_negative_holdout_texts = real_negative_candidates[:holdout_target]
            real_negative_candidates = real_negative_candidates[holdout_target:]
        texts.extend(real_negative_candidates)
        labels.extend([0] * len(real_negative_candidates))
        real_negative_count = len(real_negative_candidates)

    labels_array = np.asarray(labels, dtype=int)

    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts,
        labels_array,
        test_size=0.22,
        random_state=random_state,
        stratify=labels_array,
    )
    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        analyzer="word",
        max_features=1800,
        token_pattern=r"(?u)\b[\w'-]{2,}\b",
        sublinear_tf=True,
    )
    train_text_matrix = vectorizer.fit_transform(train_texts)
    test_text_matrix = vectorizer.transform(test_texts)
    scaler = StandardScaler()
    train_numeric = scaler.fit_transform(_numeric_feature_matrix(train_texts))
    test_numeric = scaler.transform(_numeric_feature_matrix(test_texts))
    train_matrix = sparse.hstack([train_text_matrix, sparse.csr_matrix(train_numeric)], format="csr")
    test_matrix = sparse.hstack([test_text_matrix, sparse.csr_matrix(test_numeric)], format="csr")

    classifier = LogisticRegression(
        max_iter=1200,
        class_weight="balanced",
        C=1.6,
        random_state=random_state,
    )
    classifier.fit(train_matrix, train_labels)
    model_bundle_for_scoring = {
        "vectorizer": vectorizer,
        "numeric_scaler": scaler,
        "classifier": classifier,
        "threshold": AI_TEXT_FLAG_THRESHOLD,
        "hint_threshold": AI_TEXT_HINT_THRESHOLD,
    }
    probabilities = classifier.predict_proba(test_matrix)[:, 1]
    test_scores = _runtime_ai_text_scores(test_texts, model_bundle_for_scoring)
    real_negative_holdout_scores = _runtime_ai_text_scores(real_negative_holdout_texts, model_bundle_for_scoring)
    calibrated_threshold = _select_ai_text_threshold(
        test_labels=test_labels,
        test_scores=test_scores,
        real_negative_holdout_scores=real_negative_holdout_scores,
    )
    predictions = (test_scores >= calibrated_threshold).astype(int)
    metrics = {
        "accuracy": float(accuracy_score(test_labels, predictions)),
        "precision": float(precision_score(test_labels, predictions, zero_division=0)),
        "recall": float(recall_score(test_labels, predictions, zero_division=0)),
        "f1": float(f1_score(test_labels, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(test_labels, test_scores)),
        "average_precision": float(average_precision_score(test_labels, test_scores)),
        "classifier_roc_auc": float(roc_auc_score(test_labels, probabilities)),
        "classifier_average_precision": float(average_precision_score(test_labels, probabilities)),
    }
    real_negative_holdout_metrics = _clean_holdout_metrics(
        scores=real_negative_holdout_scores,
        threshold=calibrated_threshold,
    )

    bundle = {
        "version": AI_TEXT_MODEL_VERSION,
        "vectorizer": vectorizer,
        "numeric_scaler": scaler,
        "classifier": classifier,
        "threshold": calibrated_threshold,
        "hint_threshold": AI_TEXT_HINT_THRESHOLD,
        "numeric_feature_names": NUMERIC_FEATURE_NAMES,
        "trained_rows": int(len(texts)),
        "real_negative_rows": int(real_negative_count),
        "real_negative_holdout_rows": int(len(real_negative_holdout_texts)),
        "random_state": int(random_state),
        "metrics": metrics,
        "real_negative_holdout_metrics": real_negative_holdout_metrics,
    }
    artifact_path = Path(artifacts_dir) / AI_TEXT_MODEL_FILENAME
    joblib.dump(bundle, artifact_path)
    _load_ai_text_artifact_cached.cache_clear()

    summary = {
        "artifact_path": str(artifact_path),
        "version": AI_TEXT_MODEL_VERSION,
        "training_rows": int(len(texts)),
        "real_negative_rows": int(real_negative_count),
        "real_negative_holdout_rows": int(len(real_negative_holdout_texts)),
        "test_rows": int(len(test_texts)),
        "metrics": metrics,
        "real_negative_holdout_metrics": real_negative_holdout_metrics,
        "threshold": calibrated_threshold,
        "default_threshold": AI_TEXT_FLAG_THRESHOLD,
    }
    save_json(summary, Path(output_dir) / "ai_text_detector_metrics.json")
    return summary


def ai_text_capability_status(artifacts_dir: str | Path = "models") -> dict:
    """Return lightweight AI-text detector readiness diagnostics."""
    if not _ai_text_enabled():
        return {
            "enabled": False,
            "available": False,
            "status": "disabled",
            "model": AI_TEXT_MODEL_VERSION,
        }

    artifact_path = Path(artifacts_dir) / AI_TEXT_MODEL_FILENAME
    if artifact_path.exists():
        bundle = _load_ai_text_artifact(artifacts_dir)
        return {
            "enabled": True,
            "available": True,
            "status": "ready_trained" if bundle else "artifact_error",
            "model": str(bundle.get("version", AI_TEXT_MODEL_VERSION) if bundle else AI_TEXT_MODEL_VERSION),
            "artifact_path": str(artifact_path),
            "trained_rows": int(bundle.get("trained_rows", 0) if bundle else 0),
            "real_negative_rows": int(bundle.get("real_negative_rows", 0) if bundle else 0),
            "real_negative_holdout_rows": int(bundle.get("real_negative_holdout_rows", 0) if bundle else 0),
            "threshold": float(bundle.get("threshold", AI_TEXT_FLAG_THRESHOLD) if bundle else AI_TEXT_FLAG_THRESHOLD),
        }

    return {
        "enabled": True,
        "available": True,
        "status": "ready_builtin",
        "model": f"{AI_TEXT_MODEL_VERSION}_builtin",
        "detail": "Trained artifact is missing; using the bundled conservative scorer.",
    }


def _select_ai_text_threshold(
    test_labels: np.ndarray,
    test_scores: np.ndarray,
    real_negative_holdout_scores: np.ndarray,
    max_clean_holdout_fpr: float = 0.02,
) -> float:
    """Pick a runtime threshold that preserves recall while limiting clean marketplace false positives."""
    if test_scores.size == 0:
        return AI_TEXT_FLAG_THRESHOLD

    best_threshold = AI_TEXT_FLAG_THRESHOLD
    best_score = -1.0
    for threshold in np.linspace(0.52, 0.90, 39):
        predictions = (test_scores >= threshold).astype(int)
        f1 = _safe_f1(test_labels, predictions)
        recall = _safe_recall(test_labels, predictions)
        clean_fpr = _clean_false_positive_rate(real_negative_holdout_scores, threshold)
        if real_negative_holdout_scores.size and clean_fpr > max_clean_holdout_fpr:
            continue
        score = f1 + 0.08 * recall - 0.20 * threshold
        if score > best_score:
            best_score = score
            best_threshold = float(threshold)

    return float(best_threshold)


def _clean_holdout_metrics(scores: np.ndarray, threshold: float) -> dict:
    if scores.size == 0:
        return {
            "rows": 0,
            "flagged": 0,
            "false_positive_rate": None,
            "mean_score": None,
            "p95_score": None,
            "p99_score": None,
            "max_score": None,
        }
    flagged = int((scores >= threshold).sum())
    return {
        "rows": int(scores.size),
        "flagged": flagged,
        "false_positive_rate": float(flagged / scores.size),
        "mean_score": float(np.mean(scores)),
        "p95_score": float(np.quantile(scores, 0.95)),
        "p99_score": float(np.quantile(scores, 0.99)),
        "max_score": float(np.max(scores)),
    }


def _clean_false_positive_rate(scores: np.ndarray, threshold: float) -> float:
    if scores.size == 0:
        return 0.0
    return float((scores >= threshold).sum() / scores.size)


def _safe_f1(labels: np.ndarray, predictions: np.ndarray) -> float:
    true_positive = int(((labels == 1) & (predictions == 1)).sum())
    false_positive = int(((labels == 0) & (predictions == 1)).sum())
    false_negative = int(((labels == 1) & (predictions == 0)).sum())
    denominator = 2 * true_positive + false_positive + false_negative
    return float((2 * true_positive) / denominator) if denominator else 0.0


def _safe_recall(labels: np.ndarray, predictions: np.ndarray) -> float:
    true_positive = int(((labels == 1) & (predictions == 1)).sum())
    false_negative = int(((labels == 1) & (predictions == 0)).sum())
    denominator = true_positive + false_negative
    return float(true_positive / denominator) if denominator else 0.0


def _score_ai_text(text: str, model_bundle: dict | None = None) -> dict:
    normalized_text = normalize_whitespace(text)
    features = _numeric_features(normalized_text)
    word_count = int(features["word_count"])
    heuristic_score = _heuristic_score(features)
    model_probability = _model_probability(normalized_text, model_bundle) if model_bundle else None
    score = heuristic_score if model_probability is None else 0.70 * model_probability + 0.30 * heuristic_score
    structured_marketplace_review = features["marketplace_structure_score"] >= 0.42
    flag_threshold = _flag_threshold_for_bundle(model_bundle)
    hint_threshold = _hint_threshold_for_bundle(model_bundle)

    compact_cliche = features["formulaic_review_cliche_score"] >= 0.65 and word_count >= 8
    if word_count < AI_TEXT_MIN_WORDS:
        score *= max(0.68 if compact_cliche else 0.25, word_count / AI_TEXT_MIN_WORDS)
    if features["personal_detail_density"] >= 0.32 and features["concrete_detail_density"] >= 0.24:
        score *= 0.76
    if features["colloquial_density"] >= 0.14 and features["generic_phrase_density"] < 0.08:
        score *= 0.82
    if features["formulaic_review_cliche_score"] >= 0.65 and not structured_marketplace_review:
        score = max(score, 0.74 + 0.06 * features["long_dash_density"])
    elif features["formulaic_review_cliche_score"] >= 0.35:
        score = min(1.0, score + 0.08)
    if structured_marketplace_review:
        score *= 0.46 if features["marketplace_structure_score"] >= 0.72 else 0.62

    score = float(np.clip(score, 0.0, 1.0))
    label_word_count = AI_TEXT_MIN_WORDS if compact_cliche else word_count
    label = _label_for_score(
        score,
        label_word_count,
        flag_threshold=flag_threshold,
        hint_threshold=hint_threshold,
    )
    reasons = _reasons_for_features(features, score, hint_threshold=hint_threshold)
    feature_hits = {
        key: float(features[key])
        for key in [
            "generic_phrase_density",
            "connector_density",
            "catalog_phrase_density",
            "personal_detail_density",
            "concrete_detail_density",
            "balanced_structure_score",
            "low_detail_polish_score",
            "long_dash_density",
            "formulaic_review_cliche_score",
            "marketplace_structure_score",
        ]
    }
    return {
        "ai_text_score": score,
        "ai_text_flag": int(score >= flag_threshold and (word_count >= AI_TEXT_MIN_WORDS or compact_cliche)),
        "ai_text_label": label,
        "ai_text_reasons": reasons,
        "ai_text_feature_hits": feature_hits,
        "ai_text_word_count": word_count,
    }


def _with_default_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.reset_index(drop=True)
    frame["ai_text_score"] = 0.0
    frame["ai_text_flag"] = 0
    frame["ai_text_label"] = "not_evaluated"
    frame["ai_text_model"] = ""
    frame["ai_text_reasons"] = [[] for _ in range(len(frame))]
    frame["ai_text_feature_hits"] = [{} for _ in range(len(frame))]
    frame["ai_text_word_count"] = 0
    return frame


def _ai_text_enabled() -> bool:
    raw_value = os.getenv("REVIEW_AI_TEXT_ENABLED", "1").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


def _load_ai_text_artifact(artifacts_dir: str | Path) -> dict | None:
    artifact_path = Path(artifacts_dir) / AI_TEXT_MODEL_FILENAME
    if not artifact_path.exists():
        return None
    try:
        return _load_ai_text_artifact_cached(str(artifact_path.resolve()))
    except Exception:
        return None


@lru_cache(maxsize=2)
def _load_ai_text_artifact_cached(artifact_key: str) -> dict:
    return joblib.load(artifact_key)


def _flag_threshold_for_bundle(model_bundle: dict | None) -> float:
    if not model_bundle:
        return AI_TEXT_FLAG_THRESHOLD
    try:
        return float(np.clip(float(model_bundle.get("threshold", AI_TEXT_FLAG_THRESHOLD)), 0.45, 0.95))
    except Exception:
        return AI_TEXT_FLAG_THRESHOLD


def _hint_threshold_for_bundle(model_bundle: dict | None) -> float:
    if not model_bundle:
        return AI_TEXT_HINT_THRESHOLD
    try:
        raw_hint = float(model_bundle.get("hint_threshold", AI_TEXT_HINT_THRESHOLD))
        flag_threshold = _flag_threshold_for_bundle(model_bundle)
        return float(np.clip(min(raw_hint, flag_threshold - 0.08), 0.35, flag_threshold))
    except Exception:
        return AI_TEXT_HINT_THRESHOLD


def _model_probability(text: str, model_bundle: dict | None) -> float | None:
    if not model_bundle:
        return None
    try:
        from scipy import sparse

        text_matrix = model_bundle["vectorizer"].transform([text])
        numeric = model_bundle["numeric_scaler"].transform(_numeric_feature_matrix([text]))
        matrix = sparse.hstack([text_matrix, sparse.csr_matrix(numeric)], format="csr")
        return float(model_bundle["classifier"].predict_proba(matrix)[0, 1])
    except Exception:
        return None


def _runtime_ai_text_scores(texts: list[str], model_bundle: dict | None) -> np.ndarray:
    if not texts:
        return np.asarray([], dtype=float)
    return np.asarray(
        [_score_ai_text(text, model_bundle=model_bundle)["ai_text_score"] for text in texts],
        dtype=float,
    )


def _numeric_feature_matrix(texts: list[str]) -> np.ndarray:
    rows = []
    for text in texts:
        features = _numeric_features(text)
        rows.append([float(features[name]) for name in NUMERIC_FEATURE_NAMES])
    return np.asarray(rows, dtype=float)


def _numeric_features(text: str) -> dict[str, float]:
    normalized_text = normalize_whitespace(text)
    lower_text = normalized_text.lower()
    tokens = TOKEN_RE.findall(lower_text)
    word_tokens = [token for token in tokens if any(character.isalpha() for character in token)]
    word_count = len(word_tokens)
    sentences = [part.strip() for part in re.split(r"[.!?]+", normalized_text) if part.strip()]
    sentence_lengths = [max(1, len(TOKEN_RE.findall(sentence))) for sentence in sentences]
    avg_sentence_len = float(np.mean(sentence_lengths)) if sentence_lengths else 0.0
    sentence_len_cv = float(np.std(sentence_lengths) / max(avg_sentence_len, 1.0)) if len(sentence_lengths) > 1 else 0.0
    unique_word_ratio = float(len(set(word_tokens)) / max(word_count, 1))
    generic_hits = _count_phrase_hits(lower_text, AI_STYLE_PHRASES)
    connector_hits = _count_phrase_hits(lower_text, CONNECTOR_PHRASES)
    catalog_hits = _count_phrase_hits(lower_text, CATALOG_PHRASES)
    cliche_hits = _count_phrase_hits(lower_text, AI_REVIEW_CLICHE_PHRASES)
    marketplace_marker_hits = _count_phrase_hits(lower_text, MARKETPLACE_STRUCTURE_MARKERS)
    marketplace_detail_hits = _count_phrase_hits(lower_text, MARKETPLACE_CONCRETE_TERMS)
    personal_hits = _count_phrase_hits(lower_text, PERSONAL_DETAIL_TERMS)
    colloquial_hits = _count_phrase_hits(lower_text, COLLOQUIAL_TERMS)
    number_hits = len(re.findall(r"\b\d+(?:[.,]\d+)?\b", lower_text))
    unit_hits = len(re.findall(r"\b(?:cm|mm|kg|gb|mah|days?|weeks?|months?|\u0441\u043c|\u043c\u043c|\u043a\u0433|\u0434\u043d\u044f|\u043d\u0435\u0434\u0435\u043b)\b", lower_text))
    concrete_hits = personal_hits + number_hits + unit_hits
    repetition_ratio = _repetition_ratio(word_tokens)
    latin_count = sum(1 for character in normalized_text if "a" <= character.lower() <= "z")
    cyrillic_count = sum(1 for character in normalized_text if "\u0400" <= character <= "\u04ff")
    mixed_script_score = min(latin_count, cyrillic_count) / max(latin_count + cyrillic_count, 1)
    punctuation_density = sum(1 for character in normalized_text if character in ",;:") / max(len(normalized_text), 1)
    long_dash_count = normalized_text.count("\u2014") + normalized_text.count("\u2013")
    slash_bundle_count = len(re.findall(r"\b[0-9a-z\u0400-\u04ff]+(?:/[0-9a-z\u0400-\u04ff]+){2,}\b", lower_text, flags=re.IGNORECASE))
    exclamation_density = normalized_text.count("!") / max(word_count, 1)
    digit_density = sum(1 for character in normalized_text if character.isdigit()) / max(len(normalized_text), 1)
    balanced_structure_score = float(np.clip((generic_hits > 0) + (connector_hits > 0) + (catalog_hits > 0), 0, 3) / 3.0)
    low_detail_polish_score = float(
        np.clip(
            (generic_hits + connector_hits + catalog_hits) / max(concrete_hits + personal_hits + 1, 1),
            0.0,
            1.0,
        )
    )

    return {
        "word_count": float(word_count),
        "word_count_log": float(np.log1p(word_count)),
        "sentence_count_log": float(np.log1p(len(sentences))),
        "avg_sentence_len": float(np.clip(avg_sentence_len / 28.0, 0.0, 1.0)),
        "sentence_len_cv": float(np.clip(sentence_len_cv, 0.0, 1.0)),
        "unique_word_ratio": unique_word_ratio,
        "generic_phrase_density": _density(generic_hits, word_count),
        "connector_density": _density(connector_hits, word_count),
        "catalog_phrase_density": _density(catalog_hits, word_count),
        "personal_detail_density": _density(personal_hits, word_count),
        "concrete_detail_density": _density(concrete_hits, word_count),
        "colloquial_density": _density(colloquial_hits, word_count),
        "digit_density": float(np.clip(digit_density * 12, 0.0, 1.0)),
        "punctuation_density": float(np.clip(punctuation_density * 18, 0.0, 1.0)),
        "long_dash_density": float(np.clip(long_dash_count / max(float(word_count) / 26.0, 1.0), 0.0, 1.0)),
        "exclamation_density": float(np.clip(exclamation_density * 4, 0.0, 1.0)),
        "balanced_structure_score": balanced_structure_score,
        "low_detail_polish_score": low_detail_polish_score,
        "repetition_ratio": repetition_ratio,
        "mixed_script_score": float(np.clip(mixed_script_score * 4, 0.0, 1.0)),
        "formulaic_review_cliche_score": float(
            np.clip(
                (cliche_hits + slash_bundle_count * 1.2 + (1 if cliche_hits >= 2 and long_dash_count else 0)) / 3.0,
                0.0,
                1.0,
            )
        ),
        "marketplace_structure_score": float(
            np.clip((marketplace_marker_hits * 1.4 + marketplace_detail_hits) / 5.0, 0.0, 1.0)
        ),
    }


def _heuristic_score(features: dict[str, float]) -> float:
    word_count = features["word_count"]
    sentence_uniformity = 1.0 - features["sentence_len_cv"]
    score = 0.08
    score += 0.20 * features["generic_phrase_density"]
    score += 0.16 * features["catalog_phrase_density"]
    score += 0.12 * features["connector_density"]
    score += 0.14 * features["low_detail_polish_score"]
    score += 0.10 * features["balanced_structure_score"]
    score += 0.09 * features["long_dash_density"]
    score += 0.16 * features["formulaic_review_cliche_score"]
    score += 0.07 * sentence_uniformity if word_count >= 24 else 0.0
    score += 0.06 * features["unique_word_ratio"] if word_count >= 18 else 0.0
    score += 0.04 * features["mixed_script_score"]
    score -= 0.22 * features["personal_detail_density"]
    score -= 0.18 * features["concrete_detail_density"]
    score -= 0.12 * features["colloquial_density"]
    score -= 0.04 * features["digit_density"]
    return float(np.clip(score, 0.0, 1.0))


def _label_for_score(
    score: float,
    word_count: int,
    flag_threshold: float = AI_TEXT_FLAG_THRESHOLD,
    hint_threshold: float = AI_TEXT_HINT_THRESHOLD,
) -> str:
    if word_count < AI_TEXT_MIN_WORDS:
        return "insufficient_text"
    strong_threshold = max(AI_TEXT_STRONG_THRESHOLD, min(0.95, flag_threshold + 0.10))
    if score >= strong_threshold:
        return "likely_ai_text"
    if score >= flag_threshold:
        return "ai_text_signal"
    if score >= hint_threshold:
        return "weak_ai_text_hint"
    return "human_like_or_low_signal"


def _reasons_for_features(
    features: dict[str, float],
    score: float,
    hint_threshold: float = AI_TEXT_HINT_THRESHOLD,
) -> list[str]:
    if score < hint_threshold:
        return []
    reasons = ["AI-text detector flagged polished/template-like review language; treat this as a moderation signal, not proof."]
    if features["generic_phrase_density"] >= 0.10 or features["catalog_phrase_density"] >= 0.08:
        reasons.append("The wording shows AI-like polish: generic balanced phrasing with weak personal usage detail.")
    if features["low_detail_polish_score"] >= 0.60:
        reasons.append("The text is polished but weakly grounded in concrete ownership, delivery, sizing, or usage details.")
    if features["connector_density"] >= 0.08 and features["sentence_len_cv"] <= 0.35:
        reasons.append("Sentence structure is unusually even and uses formal transition phrases.")
    if features["long_dash_density"] >= 0.35:
        reasons.append("The text uses long dash punctuation patterns that are common in polished generated reviews.")
    if features["formulaic_review_cliche_score"] >= 0.35:
        reasons.append("The review uses compact marketplace cliches about price, delivery, support, or packaging with a synthetic review rhythm.")
    return reasons


def _density(count: int, word_count: int | float) -> float:
    return float(np.clip(count / max(float(word_count) / 9.0, 1.0), 0.0, 1.0))


def _count_phrase_hits(lower_text: str, phrases: list[str]) -> int:
    return sum(1 for phrase in phrases if phrase in lower_text)


def _repetition_ratio(tokens: list[str]) -> float:
    if len(tokens) < 6:
        return 0.0
    bigrams = list(zip(tokens, tokens[1:]))
    counts = Counter(bigrams)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return float(np.clip(repeated / max(len(bigrams), 1), 0.0, 1.0))


def _template_prefix(text: str) -> str:
    words = TOKEN_RE.findall(normalize_whitespace(text).lower())
    if len(words) < AI_TEXT_MIN_WORDS:
        return ""
    return " ".join(words[:8])


def _prefix_counts(texts: list[str]) -> Counter:
    prefixes = [_template_prefix(text) for text in texts]
    return Counter(prefix for prefix in prefixes if prefix)


def _summary(frame: pd.DataFrame, status: str, model_name: str = "") -> dict:
    if "ai_text_word_count" in frame.columns:
        evaluated_mask = frame["ai_text_word_count"].astype(float) >= AI_TEXT_MIN_WORDS
        if "ai_text_flag" in frame.columns:
            evaluated_mask = evaluated_mask | (frame["ai_text_flag"].astype(int) == 1)
    else:
        evaluated_mask = pd.Series([], dtype=bool)
    evaluated_reviews = int(evaluated_mask.sum()) if len(frame) else 0
    flagged_reviews = int(frame["ai_text_flag"].sum()) if "ai_text_flag" in frame.columns else 0
    scores = frame.loc[evaluated_mask, "ai_text_score"].to_numpy(dtype=float) if evaluated_reviews else np.array([], dtype=float)
    labels = Counter(str(label) for label in frame.get("ai_text_label", []) if str(label) not in {"", "not_evaluated"})
    return {
        "ai_text_status": status,
        "ai_text_model_name": model_name,
        "ai_text_reviews": int(evaluated_reviews),
        "ai_text_flagged_reviews": int(flagged_reviews),
        "ai_text_flagged_ratio": float(flagged_reviews / evaluated_reviews) if evaluated_reviews else 0.0,
        "ai_text_score_mean": float(np.mean(scores)) if len(scores) else 0.0,
        "ai_text_top_labels": [
            {"label": label, "count": int(count)}
            for label, count in labels.most_common(5)
        ],
    }


def _generate_training_examples(n_samples: int, random_state: int) -> tuple[list[str], list[int]]:
    rng = random.Random(random_state)
    positive_count = max(100, n_samples // 2)
    negative_count = max(100, n_samples - positive_count)
    texts = [_render_positive_example(rng) for _ in range(positive_count)]
    labels = [1] * positive_count
    texts.extend(_render_negative_example(rng) for _ in range(negative_count))
    labels.extend([0] * negative_count)
    paired = list(zip(texts, labels))
    rng.shuffle(paired)
    shuffled_texts, shuffled_labels = zip(*paired)
    return list(shuffled_texts), list(shuffled_labels)


def _render_positive_example(rng: random.Random) -> str:
    products = [
        "wireless charger",
        "kitchen scale",
        "travel backpack",
        "desk lamp",
        "phone case",
        "\u043f\u043e\u0440\u0442\u0430\u0442\u0438\u0432\u043d\u0430\u044f \u043a\u043e\u043b\u043e\u043d\u043a\u0430",
        "\u043d\u0430\u0441\u0442\u043e\u043b\u044c\u043d\u0430\u044f \u043b\u0430\u043c\u043f\u0430",
        "\u043a\u0443\u0445\u043e\u043d\u043d\u044b\u0435 \u0432\u0435\u0441\u044b",
    ]
    templates = [
        "Overall, this {product} delivers excellent quality and reliable performance \u2014 the design is modern, the materials feel durable, and the value for money is very strong. I can confidently recommend it to anyone looking for a practical everyday option.",
        "It is worth noting that the {product} offers a balanced combination of style, usability, and quality. Moreover, it exceeded my expectations in daily use. In conclusion, this is a perfect choice for customers who want dependable performance.",
        "This {product} pleasantly surprised me with its premium quality and user-friendly design \u2014 additionally, the item looks stylish and performs consistently. Overall, it is a highly recommended purchase.",
        "\u0412 \u0446\u0435\u043b\u043e\u043c, {product} \u043e\u0441\u0442\u0430\u0432\u0438\u043b \u043e\u0447\u0435\u043d\u044c \u043f\u0440\u0438\u044f\u0442\u043d\u043e\u0435 \u0432\u043f\u0435\u0447\u0430\u0442\u043b\u0435\u043d\u0438\u0435 \u2014 \u0441\u043b\u0435\u0434\u0443\u0435\u0442 \u043e\u0442\u043c\u0435\u0442\u0438\u0442\u044c \u0432\u044b\u0441\u043e\u043a\u043e\u0435 \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u043e, \u0443\u0434\u043e\u0431\u0441\u0442\u0432\u043e \u0438 \u0441\u0442\u0438\u043b\u044c\u043d\u044b\u0439 \u0434\u0438\u0437\u0430\u0439\u043d. \u041f\u043e\u0434\u0432\u043e\u0434\u044f \u0438\u0442\u043e\u0433, \u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0443\u044e \u043a \u043f\u043e\u043a\u0443\u043f\u043a\u0435.",
        "\u0414\u0430\u043d\u043d\u044b\u0439 {product} \u043f\u0440\u0435\u0432\u0437\u043e\u0448\u0435\u043b \u043c\u043e\u0438 \u043e\u0436\u0438\u0434\u0430\u043d\u0438\u044f. \u041e\u043d \u0441\u043e\u0447\u0435\u0442\u0430\u0435\u0442 \u043d\u0430\u0434\u0435\u0436\u043d\u0443\u044e \u0440\u0430\u0431\u043e\u0442\u0443, \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0435 \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u044b \u0438 \u043e\u043f\u0442\u0438\u043c\u0430\u043b\u044c\u043d\u043e\u0435 \u0441\u043e\u043e\u0442\u043d\u043e\u0448\u0435\u043d\u0438\u0435 \u0446\u0435\u043d\u044b \u0438 \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u0430. \u041c\u043e\u0436\u043d\u043e \u0441\u043a\u0430\u0437\u0430\u0442\u044c, \u0447\u0442\u043e \u043f\u043e\u043a\u0443\u043f\u043a\u0430 \u043e\u043f\u0440\u0430\u0432\u0434\u0430\u043b\u0430 \u0441\u0435\u0431\u044f.",
        "\u0426\u0435\u043d\u0430 \u0430\u0434\u0435\u043a\u0432\u0430\u0442\u043d\u0430\u044f \u2014 \u043d\u0435 \u0436\u0430\u043b\u043a\u043e \u043f\u043b\u0430\u0442\u0438\u0442\u044c \u0437\u0430 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442. \u0414\u043e\u0441\u0442\u0430\u0432\u043a\u0430/\u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430/\u0443\u043f\u0430\u043a\u043e\u0432\u043a\u0430 \u2014 \u043f\u0440\u0438\u044f\u0442\u043d\u043e \u0443\u0434\u0438\u0432\u0438\u043b\u0438. \u0412 \u0446\u0435\u043b\u043e\u043c {product} \u043e\u0441\u0442\u0430\u0432\u0438\u043b \u0440\u043e\u0432\u043d\u043e\u0435 \u043f\u043e\u043b\u043e\u0436\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0435 \u0432\u043f\u0435\u0447\u0430\u0442\u043b\u0435\u043d\u0438\u0435 \u0438 \u0432\u044b\u0433\u043b\u044f\u0434\u0438\u0442 \u043e\u043f\u0440\u0430\u0432\u0434\u0430\u043d\u043d\u043e\u0439 \u043f\u043e\u043a\u0443\u043f\u043a\u043e\u0439.",
    ]
    return rng.choice(templates).format(product=rng.choice(products))


def _render_negative_example(rng: random.Random) -> str:
    templates = [
        "I bought the {product} for my desk in March. The cable is about 40 cm shorter than I expected, but it charges my old phone fine. The box arrived a little bent.",
        "After two weeks with the {product}, the main button still works but the plastic picked up scratches. For the price it is ok, not amazing.",
        "My wife uses this {product} in the kitchen every morning. Delivery took 5 days, package was normal, one corner had a small dent.",
        "Tried it at work for 10 days. Battery lasts around 6 hours, not 8. Size is good for my bag, but the zipper feels weak.",
        "\u0411\u0440\u0430\u043b {product} \u043d\u0430 \u0434\u0430\u0447\u0443 \u0432 \u0430\u043f\u0440\u0435\u043b\u0435. \u0427\u0435\u0440\u0435\u0437 \u043d\u0435\u0434\u0435\u043b\u044e \u043f\u043e\u044f\u0432\u0438\u043b\u0430\u0441\u044c \u043c\u0435\u043b\u043a\u0430\u044f \u0446\u0430\u0440\u0430\u043f\u0438\u043d\u0430, \u043d\u043e \u0432 \u0446\u0435\u043b\u043e\u043c \u0437\u0430 \u0441\u0432\u043e\u0438 \u0434\u0435\u043d\u044c\u0433\u0438 \u043d\u043e\u0440\u043c.",
        "\u0417\u0430\u043a\u0430\u0437\u0430\u043b\u0430 {product} \u0440\u0435\u0431\u0435\u043d\u043a\u0443. \u0420\u0430\u0437\u043c\u0435\u0440 \u043f\u043e\u0434\u043e\u0448\u0435\u043b, \u0448\u043e\u0432 \u043d\u0430 \u043a\u0440\u0430\u044e \u043a\u0440\u0438\u0432\u043e\u0439, \u0434\u043e\u0441\u0442\u0430\u0432\u0438\u043b\u0438 \u0437\u0430 4 \u0434\u043d\u044f.",
        "\u041f\u043e\u043b\u044c\u0437\u0443\u044e\u0441\u044c {product} \u043d\u0430 \u0440\u0430\u0431\u043e\u0442\u0435. \u041f\u043e\u043a\u0430 \u043d\u043e\u0440\u043c, \u043d\u043e \u0443\u043f\u0430\u043a\u043e\u0432\u043a\u0430 \u043f\u0440\u0438\u0448\u043b\u0430 \u043c\u044f\u0442\u0430\u044f \u0438 \u0437\u0430\u0440\u044f\u0434 \u0434\u0435\u0440\u0436\u0438\u0442 \u0445\u0443\u0436\u0435, \u0447\u0435\u043c \u043f\u0438\u0441\u0430\u043b\u0438.",
    ]
    products = [
        "charger",
        "lamp",
        "backpack",
        "scale",
        "case",
        "\u043b\u0430\u043c\u043f\u0443",
        "\u0440\u044e\u043a\u0437\u0430\u043a",
        "\u0447\u0435\u0445\u043e\u043b",
    ]
    return rng.choice(templates).format(product=rng.choice(products))
