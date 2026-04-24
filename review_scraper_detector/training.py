"""Training pipeline for suspicious review text classification."""

from __future__ import annotations

from pathlib import Path
import re

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.pipeline import FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit

from .abstention import (
    apply_review_abstention_policy,
    build_review_uncertainty_frame,
    summarize_review_triage,
    train_review_abstention_policy,
)
from .hybrid_combiner import predict_hybrid_meta_probabilities, train_hybrid_meta_combiner
from .manipulation import analyze_review_manipulation_patterns
from .model import ReviewClassifier, predict_probabilities, train_classifier
from .sample_data import create_sample_review_dataset
from .slang_signals import learn_slang_lexicon, train_slang_signal_calibrator
from .utils import (
    ensure_directory,
    infer_review_product_family,
    make_review_holdout_group,
    make_review_split_group,
    make_source_group,
    normalize_group_component,
    save_json,
    set_global_seed,
)


def train_review_classifier(
    dataset_path: str | Path,
    artifacts_dir: str | Path = "models",
    output_dir: str | Path = "outputs",
    epochs: int = 12,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    test_size: float = 0.2,
    validation_size: float = 0.15,
    calibration_size: float = 0.1,
    random_state: int = 42,
    max_features: int = 5000,
    char_max_features: int = 0,
    hidden_dims: list[int] | None = None,
    dropout: float = 0.25,
) -> dict:
    """Train a suspicious review classifier and save all required artifacts."""
    set_global_seed(random_state)
    dataset_path = Path(dataset_path)
    artifacts_dir = ensure_directory(artifacts_dir)
    output_dir = ensure_directory(output_dir)

    training_df = load_review_training_data(dataset_path)
    train_df, val_df, calibration_df, test_df = _split_grouped_review_dataset(
        training_df,
        test_size=test_size,
        validation_size=validation_size,
        calibration_size=calibration_size,
        random_state=random_state,
    )

    vectorizer = build_text_vectorizer(
        max_features=max_features,
        char_max_features=char_max_features,
    )

    train_matrix = build_feature_matrix(train_df, vectorizer=vectorizer, fit_vectorizer=True)
    val_matrix = build_feature_matrix(val_df, vectorizer=vectorizer, fit_vectorizer=False)
    calibration_matrix = build_feature_matrix(calibration_df, vectorizer=vectorizer, fit_vectorizer=False)
    test_matrix = build_feature_matrix(test_df, vectorizer=vectorizer, fit_vectorizer=False)

    train_labels = train_df["label"].to_numpy(dtype=np.float32)
    val_labels = val_df["label"].to_numpy(dtype=np.float32)
    calibration_labels = calibration_df["label"].to_numpy(dtype=np.float32)
    test_labels = test_df["label"].to_numpy(dtype=np.float32)

    hidden_dims = hidden_dims or [512, 128]
    model = ReviewClassifier(input_dim=train_matrix.shape[1], hidden_dims=hidden_dims, dropout=dropout)
    positive_count = float(max(1.0, train_labels.sum()))
    negative_count = float(max(1.0, len(train_labels) - train_labels.sum()))
    history = train_classifier(
        model=model,
        train_matrix=train_matrix,
        train_labels=train_labels,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        val_matrix=val_matrix,
        val_labels=val_labels,
        pos_weight=negative_count / positive_count,
        patience=6,
    )

    validation_probabilities = predict_probabilities(model, val_matrix)
    text_threshold = _select_threshold(val_labels, validation_probabilities)
    validation_predictions = (validation_probabilities >= text_threshold).astype(int)
    validation_metrics = _classification_metrics(val_labels, validation_predictions, validation_probabilities)

    learned_slang_lexicon, slang_lexicon_report = learn_slang_lexicon(
        _prepare_hybrid_signal_frame(train_df),
        labels=train_labels,
    )
    slang_signal_model, slang_signal_calibration = train_slang_signal_calibrator(
        _prepare_hybrid_signal_frame(val_df),
        labels=val_labels,
        learned_lexicon=learned_slang_lexicon,
        random_state=random_state,
    )

    calibration_probabilities = predict_probabilities(model, calibration_matrix)
    calibration_signals, _ = analyze_review_manipulation_patterns(
        _prepare_hybrid_signal_frame(calibration_df),
        include_page_context=False,
        slang_model=slang_signal_model,
    )
    hybrid_combiner, hybrid_calibration = train_hybrid_meta_combiner(
        review_df=calibration_signals,
        text_probabilities=calibration_probabilities,
        labels=calibration_labels,
        random_state=random_state,
    )
    hybrid_threshold = 0.5
    validation_signals, _ = analyze_review_manipulation_patterns(
        _prepare_hybrid_signal_frame(val_df),
        include_page_context=False,
        slang_model=slang_signal_model,
    )
    validation_hybrid_probabilities = predict_hybrid_meta_probabilities(
        hybrid_combiner,
        review_df=validation_signals,
        text_probabilities=validation_probabilities,
    )
    validation_uncertainty = build_review_uncertainty_frame(
        validation_signals,
        text_probabilities=validation_probabilities,
        hybrid_probabilities=validation_hybrid_probabilities,
        threshold=hybrid_threshold,
        vectorizer=vectorizer,
    )
    abstention_policy, abstention_calibration = train_review_abstention_policy(
        validation_uncertainty,
        labels=val_labels,
        threshold=hybrid_threshold,
    )

    test_probabilities = predict_probabilities(model, test_matrix)
    text_test_predictions = (test_probabilities >= text_threshold).astype(int)
    text_test_metrics = _classification_metrics(test_labels, text_test_predictions, test_probabilities)
    test_signals, _ = analyze_review_manipulation_patterns(
        _prepare_hybrid_signal_frame(test_df),
        include_page_context=False,
        slang_model=slang_signal_model,
    )
    hybrid_test_probabilities = predict_hybrid_meta_probabilities(
        hybrid_combiner,
        review_df=test_signals,
        text_probabilities=test_probabilities,
    )
    test_uncertainty = build_review_uncertainty_frame(
        test_signals,
        text_probabilities=test_probabilities,
        hybrid_probabilities=hybrid_test_probabilities,
        threshold=hybrid_threshold,
        vectorizer=vectorizer,
    )
    test_triaged = apply_review_abstention_policy(test_uncertainty, abstention_policy)
    triage_summary = summarize_review_triage(test_triaged)
    test_predictions = (hybrid_test_probabilities >= hybrid_threshold).astype(int)
    metrics = _classification_metrics(test_labels, test_predictions, hybrid_test_probabilities)

    model_path = artifacts_dir / "review_text_classifier.pt"
    bundle_path = artifacts_dir / "review_text_bundle.joblib"
    torch.save(model.state_dict(), model_path)
    joblib.dump(
        {
            "vectorizer": vectorizer,
            "threshold": text_threshold,
            "hybrid_threshold": hybrid_threshold,
            "hybrid_strategy": "logistic_meta_combiner",
            "hybrid_meta_combiner": hybrid_combiner,
            "hybrid_meta_calibration": hybrid_calibration,
            "slang_signal_model": slang_signal_model,
            "slang_signal_calibration": slang_signal_calibration,
            "abstention_policy": abstention_policy,
            "abstention_calibration": abstention_calibration,
            "input_dim": int(train_matrix.shape[1]),
            "hidden_dims": hidden_dims,
            "metrics": metrics,
            "validation_metrics": validation_metrics,
            "text_test_metrics": text_test_metrics,
            "numeric_feature_names": _numeric_feature_names(),
            "max_features": int(max_features),
            "char_max_features": int(char_max_features),
            "dropout": float(dropout),
        },
        bundle_path,
    )

    metrics_path = output_dir / "review_metrics.json"
    history_path = output_dir / "review_training_history.json"
    slang_diagnostics_path = output_dir / "review_slang_diagnostics.json"
    save_json(
        {
            "hybrid_test_metrics": metrics,
            "text_test_metrics": text_test_metrics,
            "text_validation_metrics": validation_metrics,
            "hybrid_calibration": hybrid_calibration,
            "hybrid_threshold": hybrid_threshold,
            "text_threshold": text_threshold,
            "slang_signal_calibration": slang_signal_calibration,
            "abstention_calibration": abstention_calibration,
            "triage_summary": triage_summary,
        },
        metrics_path,
    )
    save_json(history, history_path)
    save_json(
        {
            "learned_lexicon": learned_slang_lexicon,
            "lexicon_report": slang_lexicon_report,
            "slang_signal_calibration": slang_signal_calibration,
            "abstention_calibration": abstention_calibration,
        },
        slang_diagnostics_path,
    )

    summary = {
        "dataset_path": str(dataset_path),
        "records_total": int(len(training_df)),
        "train_records": int(len(train_df)),
        "validation_records": int(len(val_df)),
        "calibration_records": int(len(calibration_df)),
        "test_records": int(len(test_df)),
        "split_group_count": int(training_df["split_group"].nunique()),
        "holdout_group_count": int(training_df["holdout_group"].nunique()),
        "train_split_groups": int(train_df["split_group"].nunique()),
        "validation_split_groups": int(val_df["split_group"].nunique()),
        "calibration_split_groups": int(calibration_df["split_group"].nunique()),
        "test_split_groups": int(test_df["split_group"].nunique()),
        "train_holdout_groups": int(train_df["holdout_group"].nunique()),
        "validation_holdout_groups": int(val_df["holdout_group"].nunique()),
        "calibration_holdout_groups": int(calibration_df["holdout_group"].nunique()),
        "test_holdout_groups": int(test_df["holdout_group"].nunique()),
        "threshold": hybrid_threshold,
        "text_threshold": text_threshold,
        "hybrid_threshold": hybrid_threshold,
        "hybrid_strategy": "logistic_meta_combiner",
        "max_features": int(max_features),
        "char_max_features": int(char_max_features),
        "hidden_dims": [int(value) for value in hidden_dims],
        "dropout": float(dropout),
        "validation_metrics": validation_metrics,
        "text_test_metrics": text_test_metrics,
        "hybrid_calibration": hybrid_calibration,
        "slang_lexicon_report": slang_lexicon_report,
        "slang_signal_calibration": slang_signal_calibration,
        "abstention_calibration": abstention_calibration,
        "triage_summary": triage_summary,
        "metrics": metrics,
        "label_distribution": {
            str(key): int(value)
            for key, value in training_df["label"].value_counts().sort_index().items()
        },
        "source_distribution": {
            str(key): int(value)
            for key, value in training_df["source"].value_counts().sort_values(ascending=False).items()
        },
        "product_family_distribution": {
            str(key): int(value)
            for key, value in training_df["product_family"].value_counts().sort_values(ascending=False).items()
        },
        "artifacts": {
            "model_path": str(model_path),
            "bundle_path": str(bundle_path),
            "metrics_path": str(metrics_path),
            "history_path": str(history_path),
            "slang_diagnostics_path": str(slang_diagnostics_path),
        },
    }
    save_json(summary, output_dir / "review_training_summary.json")
    return summary


def load_review_training_data(dataset_path: str | Path) -> pd.DataFrame:
    """Load and validate a labeled review dataset for classifier training."""
    dataset_path = Path(dataset_path)
    if not dataset_path.exists():
        create_sample_review_dataset(dataset_path)

    df = pd.read_csv(dataset_path)
    renamed = df.rename(
        columns={
            "text": "review_text",
            "is_suspicious": "label",
            "is_fake": "label",
        }
    )

    if "review_text" not in renamed.columns or "label" not in renamed.columns:
        raise ValueError("Training CSV must contain `review_text` and `label` columns.")

    renamed["review_text"] = renamed["review_text"].fillna("").astype(str)
    if "rating" not in renamed.columns:
        renamed["rating"] = 0.0
    if "source" not in renamed.columns:
        renamed["source"] = "unspecified"
    if "split_group" not in renamed.columns:
        source_series = renamed["source"].fillna("unspecified").astype(str)
        if source_series.eq("synthetic_suspicious_augmented").any():
            raise ValueError(
                "This training CSV contains legacy augmented reviews without `split_group` lineage. "
                "Rebuild the dataset with the updated dataset builder before training."
            )
    if "split_group" not in renamed.columns:
        renamed["split_group"] = renamed["review_text"].map(make_review_split_group)

    renamed["rating"] = pd.to_numeric(renamed["rating"], errors="coerce").fillna(0.0)
    renamed["label"] = pd.to_numeric(renamed["label"], errors="coerce").fillna(0).astype(int)
    renamed["source"] = renamed["source"].fillna("unspecified").astype(str)
    if "product_family" not in renamed.columns:
        renamed["product_family"] = [
            infer_review_product_family(review_text=text, source=source)
            for text, source in zip(renamed["review_text"], renamed["source"])
        ]
    else:
        renamed["product_family"] = [
            normalize_group_component(value, default=infer_review_product_family(review_text=text, source=source))
            for value, text, source in zip(renamed["product_family"], renamed["review_text"], renamed["source"])
        ]
    if "origin_family" not in renamed.columns:
        renamed["origin_family"] = ""
    else:
        renamed["origin_family"] = [
            normalize_group_component(value, default="")
            for value in renamed["origin_family"]
        ]
    renamed["split_group"] = renamed["split_group"].fillna("").astype(str)
    missing_groups = renamed["split_group"].str.strip().eq("")
    if missing_groups.any():
        renamed.loc[missing_groups, "split_group"] = renamed.loc[missing_groups, "review_text"].map(make_review_split_group)
    if "holdout_group" not in renamed.columns:
        renamed["holdout_group"] = ""
    renamed["holdout_group"] = renamed["holdout_group"].fillna("").astype(str)
    missing_holdout = renamed["holdout_group"].str.strip().eq("")
    if missing_holdout.any():
        renamed.loc[missing_holdout, "holdout_group"] = [
            make_review_holdout_group(
                source_group=make_source_group(source),
                product_family=product_family,
                origin_family=origin_family,
            )
            for source, product_family, origin_family in zip(
                renamed.loc[missing_holdout, "source"],
                renamed.loc[missing_holdout, "product_family"],
                renamed.loc[missing_holdout, "origin_family"],
            )
        ]

    source_priority = renamed["source"].fillna("").astype(str).str.startswith("synthetic_").astype(int)
    holdout_by_lineage = (
        renamed.assign(_source_priority=source_priority)
        .sort_values(by=["_source_priority", "source", "holdout_group"])
        .groupby("split_group")["holdout_group"]
        .first()
    )
    renamed["holdout_group"] = renamed["split_group"].map(holdout_by_lineage).fillna(renamed["holdout_group"])
    cleaned = renamed[renamed["review_text"].str.strip().str.len() >= 15].reset_index(drop=True)
    if cleaned["label"].nunique() < 2:
        raise ValueError("Training dataset must contain at least two classes for suspicious review training.")
    if cleaned["split_group"].nunique() < 4:
        raise ValueError(
            "Training dataset needs at least four unique split groups for leakage-safe "
            "train/validation/calibration/test splits."
        )
    if cleaned["holdout_group"].nunique() < 4:
        raise ValueError(
            "Training dataset needs at least four unique holdout groups across "
            "`source` / `product_family` / `origin_family` for group-aware validation."
        )
    return cleaned[
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


def _split_grouped_review_dataset(
    training_df: pd.DataFrame,
    test_size: float,
    validation_size: float,
    calibration_size: float,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split data by lineage group for training, validation, calibration, and test."""
    if not 0.0 < test_size < 1.0:
        raise ValueError("`test_size` must be between 0 and 1.")
    if not 0.0 < validation_size < 1.0:
        raise ValueError("`validation_size` must be between 0 and 1.")
    if not 0.0 < calibration_size < 1.0:
        raise ValueError("`calibration_size` must be between 0 and 1.")
    if test_size + validation_size + calibration_size >= 1.0:
        raise ValueError("`test_size + validation_size + calibration_size` must leave room for training data.")

    train_validation_df, test_df = _group_shuffle_split_with_label_coverage(
        training_df,
        test_size=test_size,
        random_state=random_state,
        split_name="test",
    )
    calibration_fraction = calibration_size / (1.0 - test_size)
    train_val_df, calibration_df = _group_shuffle_split_with_label_coverage(
        train_validation_df,
        test_size=calibration_fraction,
        random_state=random_state + 1,
        split_name="calibration",
    )
    validation_fraction = validation_size / (1.0 - test_size - calibration_size)
    train_df, val_df = _group_shuffle_split_with_label_coverage(
        train_val_df,
        test_size=validation_fraction,
        random_state=random_state + 2,
        split_name="validation",
    )
    _assert_disjoint_split_groups(train_df, val_df, "train", "validation")
    _assert_disjoint_split_groups(train_df, calibration_df, "train", "calibration")
    _assert_disjoint_split_groups(train_df, test_df, "train", "test")
    _assert_disjoint_split_groups(val_df, calibration_df, "validation", "calibration")
    _assert_disjoint_split_groups(val_df, test_df, "validation", "test")
    _assert_disjoint_split_groups(calibration_df, test_df, "calibration", "test")
    return train_df, val_df, calibration_df, test_df


def _group_shuffle_split_with_label_coverage(
    df: pd.DataFrame,
    test_size: float,
    random_state: int,
    split_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Find a broader family split where both partitions still contain both classes."""
    groups = df["holdout_group"].fillna("").astype(str).to_numpy()
    splitter = GroupShuffleSplit(n_splits=24, test_size=test_size, random_state=random_state)

    for train_indices, holdout_indices in splitter.split(df, y=df["label"], groups=groups):
        train_partition = df.iloc[train_indices].reset_index(drop=True)
        holdout_partition = df.iloc[holdout_indices].reset_index(drop=True)
        if _has_both_labels(train_partition) and _has_both_labels(holdout_partition):
            return train_partition, holdout_partition

    raise ValueError(
        f"Could not create a leakage-safe {split_name} split with both classes represented. "
        "Increase dataset diversity or reduce the split size."
    )


def _has_both_labels(df: pd.DataFrame) -> bool:
    """Check whether a partition still covers both classes."""
    return df["label"].nunique() >= 2


def _assert_disjoint_split_groups(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    left_name: str,
    right_name: str,
) -> None:
    """Fail fast if any lineage or broader family group leaks between partitions."""
    for column in ("split_group", "holdout_group"):
        overlap = set(left_df[column].tolist()) & set(right_df[column].tolist())
        if overlap:
            raise RuntimeError(
                f"Leakage detected between {left_name} and {right_name}: "
                f"{len(overlap)} shared {column} values."
            )


def _prepare_hybrid_signal_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Provide the minimum schema required by manipulation analysis during training."""
    prepared = df.copy().reset_index(drop=True)
    for column, default_value in {
        "author": "",
        "title": "",
        "date": "",
    }.items():
        if column not in prepared.columns:
            prepared[column] = default_value
    return prepared


def build_text_vectorizer(max_features: int, char_max_features: int = 0):
    """Build a word/character vectorizer for robust fake-review signals."""
    word_vectorizer = TfidfVectorizer(
        max_features=max_features,
        ngram_range=(1, 2),
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
        min_df=2,
        max_df=0.98,
    )
    if char_max_features <= 0:
        return word_vectorizer

    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=char_max_features,
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
        min_df=2,
        max_df=0.98,
    )
    return FeatureUnion(
        [
            ("word_tfidf", word_vectorizer),
            ("char_tfidf", char_vectorizer),
        ]
    )


def build_feature_matrix(
    df: pd.DataFrame,
    vectorizer: TfidfVectorizer,
    fit_vectorizer: bool,
) -> np.ndarray:
    """Convert raw reviews into a dense matrix for the PyTorch model."""
    text_values = df["review_text"].fillna("").astype(str)
    rating_values = pd.to_numeric(df.get("rating", 0.0), errors="coerce").fillna(0.0).to_numpy(dtype=np.float32)
    token_lists = text_values.str.lower().str.findall(r"[\w'-]+")
    word_counts = token_lists.str.len().fillna(0).to_numpy(dtype=np.float32)
    character_counts = text_values.str.len().fillna(0).to_numpy(dtype=np.float32)
    unique_word_ratios = np.array(
        [len(set(tokens)) / max(1, len(tokens)) for tokens in token_lists],
        dtype=np.float32,
    )
    repetition_ratios = 1.0 - unique_word_ratios
    average_word_lengths = np.array(
        [float(np.mean([len(token) for token in tokens])) if tokens else 0.0 for tokens in token_lists],
        dtype=np.float32,
    )
    exclamation_density = text_values.str.count("!").fillna(0).to_numpy(dtype=np.float32) / np.clip(character_counts, 1.0, None)
    question_density = text_values.str.count(r"\?").fillna(0).to_numpy(dtype=np.float32) / np.clip(character_counts, 1.0, None)
    uppercase_ratios = np.array([_uppercase_ratio(text) for text in text_values], dtype=np.float32)
    digit_ratios = np.array([_digit_ratio(text) for text in text_values], dtype=np.float32)

    if fit_vectorizer:
        text_matrix = vectorizer.fit_transform(text_values)
    else:
        text_matrix = vectorizer.transform(text_values)

    dense_text = text_matrix.toarray().astype(np.float32)
    numeric_features = np.column_stack(
        [
            np.clip(rating_values / 5.0, 0.0, 1.0),
            np.clip(word_counts / 120.0, 0.0, 1.0),
            np.clip(character_counts / 600.0, 0.0, 1.0),
            np.clip(unique_word_ratios, 0.0, 1.0),
            np.clip(repetition_ratios, 0.0, 1.0),
            np.clip(average_word_lengths / 12.0, 0.0, 1.0),
            np.clip(exclamation_density * 25.0, 0.0, 1.0),
            np.clip(question_density * 25.0, 0.0, 1.0),
            np.clip(uppercase_ratios * 4.0, 0.0, 1.0),
            np.clip(digit_ratios * 10.0, 0.0, 1.0),
        ]
    ).astype(np.float32)
    return np.hstack([dense_text, numeric_features]).astype(np.float32)


def _select_threshold(labels: np.ndarray, probabilities: np.ndarray) -> float:
    """Choose a probability threshold that maximizes F1-score."""
    best_threshold = 0.5
    best_f1 = -1.0

    for threshold in np.linspace(0.3, 0.8, 26):
        predictions = (probabilities >= threshold).astype(int)
        score = float(f1_score(labels, predictions, zero_division=0))
        if score > best_f1:
            best_f1 = score
            best_threshold = float(threshold)

    return best_threshold


def _classification_metrics(labels: np.ndarray, predictions: np.ndarray, probabilities: np.ndarray | None = None) -> dict:
    """Calculate classification metrics with confusion-matrix details."""
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    metrics = {
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1_score": float(f1_score(labels, predictions, zero_division=0)),
        "confusion_matrix": {
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
        },
    }
    if probabilities is not None and len(set(labels.astype(int).tolist())) > 1:
        metrics["roc_auc"] = float(roc_auc_score(labels, probabilities))
        metrics["pr_auc"] = float(average_precision_score(labels, probabilities))
    else:
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None
    return metrics


def _uppercase_ratio(text: str) -> float:
    """Measure the share of alphabetic characters written in upper case."""
    if not text:
        return 0.0
    alpha_chars = [char for char in text if char.isalpha()]
    if not alpha_chars:
        return 0.0
    uppercase_chars = sum(1 for char in alpha_chars if char.isupper())
    return float(uppercase_chars / len(alpha_chars))


def _digit_ratio(text: str) -> float:
    """Measure how many characters in the text are digits."""
    if not text:
        return 0.0
    digit_count = sum(1 for char in text if char.isdigit())
    return float(digit_count / max(1, len(text)))


def _numeric_feature_names() -> list[str]:
    """Return the names of the appended numeric features."""
    return [
        "rating_scaled",
        "word_count_scaled",
        "character_count_scaled",
        "unique_word_ratio",
        "repetition_ratio",
        "average_word_length_scaled",
        "exclamation_density_scaled",
        "question_density_scaled",
        "uppercase_ratio_scaled",
        "digit_ratio_scaled",
    ]
