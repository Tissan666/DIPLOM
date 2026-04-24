"""Calibrated meta-combiner for hybrid suspicious-review scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

HYBRID_META_FEATURE_NAMES = [
    "text_probability",
    "local_manipulation_score",
    "rating_manipulation_score",
    "slang_manipulation_score",
    "slang_authenticity_score",
    "generic_phrase_flag",
    "short_extreme_flag",
    "extreme_rating_flag",
    "word_count_scaled",
]


def build_hybrid_feature_matrix(review_df: pd.DataFrame, text_probabilities: np.ndarray) -> np.ndarray:
    """Build a stable feature matrix for the hybrid probability combiner."""
    frame = review_df.reset_index(drop=True).copy()
    text_values = np.asarray(text_probabilities, dtype=np.float32).reshape(-1)
    if len(frame) != len(text_values):
        raise ValueError("Hybrid feature construction requires one text probability per review row.")

    feature_matrix = np.column_stack(
        [
            np.clip(text_values, 0.0, 1.0),
            np.clip(_numeric_column(frame, "local_manipulation_score"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "rating_manipulation_score"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_manipulation_score"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "slang_authenticity_score", default=0.5), 0.0, 1.0),
            np.clip(_numeric_column(frame, "generic_phrase_flag"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "short_extreme_flag"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "extreme_rating_flag"), 0.0, 1.0),
            np.clip(_numeric_column(frame, "word_count") / 80.0, 0.0, 1.0),
        ]
    ).astype(np.float32)
    return feature_matrix


def train_hybrid_meta_combiner(
    review_df: pd.DataFrame,
    text_probabilities: np.ndarray,
    labels: np.ndarray,
    random_state: int = 42,
) -> tuple[LogisticRegression, dict]:
    """Fit a compact logistic combiner on a dedicated calibration holdout."""
    calibration_features = build_hybrid_feature_matrix(review_df, text_probabilities)
    calibration_labels = np.asarray(labels, dtype=np.int32).reshape(-1)
    if len(calibration_features) != len(calibration_labels):
        raise ValueError("Hybrid combiner labels must match the calibration feature count.")
    if len(np.unique(calibration_labels)) < 2:
        raise ValueError("Hybrid combiner calibration requires both classes to be present.")

    combiner = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=random_state,
    )
    combiner.fit(calibration_features, calibration_labels)
    fitted_probabilities = combiner.predict_proba(calibration_features)[:, 1].astype(float)

    return combiner, {
        "feature_names": list(HYBRID_META_FEATURE_NAMES),
        "coefficients": {
            name: float(value)
            for name, value in zip(HYBRID_META_FEATURE_NAMES, combiner.coef_[0], strict=False)
        },
        "intercept": float(combiner.intercept_[0]),
        "fit_log_loss": float(log_loss(calibration_labels, fitted_probabilities)),
        "fit_brier_score": float(brier_score_loss(calibration_labels, fitted_probabilities)),
    }


def predict_hybrid_meta_probabilities(
    combiner: LogisticRegression,
    review_df: pd.DataFrame,
    text_probabilities: np.ndarray,
) -> np.ndarray:
    """Predict calibrated suspicious-review probabilities from review signals."""
    feature_matrix = build_hybrid_feature_matrix(review_df, text_probabilities)
    return combiner.predict_proba(feature_matrix)[:, 1].astype(float)


def _numeric_column(frame: pd.DataFrame, column: str, default: float = 0.0) -> np.ndarray:
    """Return one numeric column as a float array with a stable default."""
    if column not in frame.columns:
        return np.full(len(frame), float(default), dtype=np.float32)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).to_numpy(dtype=np.float32)
