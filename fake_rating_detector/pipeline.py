"""End-to-end training pipeline for fake rating anomaly detection."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import torch
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from .data_loader import load_ratings_data
from .explanations import derive_suspicion_reasons
from .features import FeatureEngineeringPipeline
from .model import RatingsAutoencoder, reconstruction_errors, train_autoencoder
from .utils import ensure_directory, save_json, set_global_seed


def _select_threshold(validation_errors: np.ndarray, validation_labels: np.ndarray) -> float:
    """Pick a threshold that maximizes F1-score on a dedicated validation split."""
    candidate_thresholds = np.quantile(validation_errors, np.linspace(0.7, 0.995, 30))
    best_threshold = float(np.quantile(validation_errors, 0.95))
    best_f1 = -1.0

    for threshold in candidate_thresholds:
        predictions = (validation_errors >= threshold).astype(int)
        score = float(f1_score(validation_labels, predictions, zero_division=0))
        if score > best_f1:
            best_f1 = score
            best_threshold = float(threshold)

    return best_threshold


def train_anomaly_detector(
    dataset_path: str | Path,
    artifacts_dir: str | Path = "models",
    output_dir: str | Path = "outputs",
    epochs: int = 35,
    batch_size: int = 64,
    learning_rate: float = 1e-3,
    test_size: float = 0.2,
    validation_size: float = 0.15,
    text_embedding_dim: int = 24,
    text_max_features: int = 2500,
    text_char_max_features: int = 900,
    random_state: int = 42,
) -> dict:
    """Train the Autoencoder, evaluate it, and persist reports plus model artifacts."""
    set_global_seed(random_state)
    dataset_path = Path(dataset_path)
    artifacts_dir = ensure_directory(artifacts_dir)
    output_dir = ensure_directory(output_dir)

    ratings_df = load_ratings_data(dataset_path)
    has_labels = (ratings_df["is_fake"] >= 0).all() and ratings_df["is_fake"].nunique() > 1
    stratify_labels = ratings_df["is_fake"] if has_labels else None
    if not 0.0 < test_size < 1.0:
        raise ValueError("`test_size` must be between 0 and 1.")
    if not 0.0 < validation_size < 1.0:
        raise ValueError("`validation_size` must be between 0 and 1.")
    if test_size + validation_size >= 1.0:
        raise ValueError("`test_size + validation_size` must leave room for training data.")

    train_validation_df, test_df = train_test_split(
        ratings_df,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify_labels,
    )
    validation_fraction = validation_size / (1.0 - test_size)
    train_stratify = train_validation_df["is_fake"] if has_labels else None
    train_df, validation_df = train_test_split(
        train_validation_df,
        test_size=validation_fraction,
        random_state=random_state + 1,
        stratify=train_stratify,
    )
    train_df = train_df.sort_values("timestamp").reset_index(drop=True)
    validation_df = validation_df.sort_values("timestamp").reset_index(drop=True)
    test_df = test_df.sort_values("timestamp").reset_index(drop=True)

    feature_pipeline = FeatureEngineeringPipeline(
        text_embedding_dim=text_embedding_dim,
        text_max_features=text_max_features,
        text_char_max_features=text_char_max_features,
        random_state=random_state,
    )
    train_features = feature_pipeline.fit_transform(train_df)
    validation_features = feature_pipeline.transform(validation_df)
    test_features = feature_pipeline.transform(test_df)

    scaler = StandardScaler()
    train_scaled = scaler.fit_transform(train_features)
    validation_scaled = scaler.transform(validation_features)
    test_scaled = scaler.transform(test_features)

    train_labels = train_df["is_fake"].to_numpy(dtype=int)
    validation_labels = validation_df["is_fake"].to_numpy(dtype=int)
    test_labels = test_df["is_fake"].to_numpy(dtype=int)

    if has_labels and np.sum(train_labels == 0) >= 20:
        training_matrix = train_scaled[train_labels == 0]
    else:
        training_matrix = train_scaled

    hidden_dims = [64, 32, 16]
    model = RatingsAutoencoder(input_dim=train_scaled.shape[1], hidden_dims=hidden_dims)
    history = train_autoencoder(
        model=model,
        train_matrix=training_matrix,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
    )

    if has_labels:
        validation_scores = reconstruction_errors(model, validation_scaled)
        threshold = _select_threshold(validation_scores, validation_labels)
        validation_predictions = (validation_scores >= threshold).astype(int)
        validation_metrics = {
            "accuracy": float(accuracy_score(validation_labels, validation_predictions)),
            "precision": float(precision_score(validation_labels, validation_predictions, zero_division=0)),
            "recall": float(recall_score(validation_labels, validation_predictions, zero_division=0)),
            "f1_score": float(f1_score(validation_labels, validation_predictions, zero_division=0)),
        }
    else:
        validation_scores = reconstruction_errors(model, validation_scaled)
        threshold = float(np.quantile(validation_scores, 0.95))
        validation_metrics = {"accuracy": None, "precision": None, "recall": None, "f1_score": None}
    test_scores = reconstruction_errors(model, test_scaled)
    test_predictions = (test_scores >= threshold).astype(int)

    if has_labels:
        metrics = {
            "accuracy": float(accuracy_score(test_labels, test_predictions)),
            "precision": float(precision_score(test_labels, test_predictions, zero_division=0)),
            "recall": float(recall_score(test_labels, test_predictions, zero_division=0)),
            "f1_score": float(f1_score(test_labels, test_predictions, zero_division=0)),
        }
    else:
        metrics = {"accuracy": None, "precision": None, "recall": None, "f1_score": None}

    test_results = test_df.copy()
    test_results["anomaly_score"] = test_scores
    test_results["is_suspicious"] = test_predictions
    test_results["suspicion_reasons"] = derive_suspicion_reasons(test_features)

    suspicious_ratings = (
        test_results.loc[test_results["is_suspicious"] == 1]
        .sort_values("anomaly_score", ascending=False)
        .reset_index(drop=True)
    )

    suspicious_users = (
        suspicious_ratings.groupby("user_id")
        .agg(
            suspicious_ratings=("user_id", "size"),
            average_anomaly_score=("anomaly_score", "mean"),
            max_anomaly_score=("anomaly_score", "max"),
            unique_target_items=("item_id", "nunique"),
            unique_ips=("ip_address", "nunique"),
        )
        .sort_values(["suspicious_ratings", "average_anomaly_score"], ascending=[False, False])
        .reset_index()
    )

    bundle = {
        "feature_pipeline": feature_pipeline,
        "scaler": scaler,
        "threshold": threshold,
        "input_dim": int(train_scaled.shape[1]),
        "hidden_dims": hidden_dims,
        "feature_names": feature_pipeline.feature_names,
        "text_embedding_dim": int(feature_pipeline.text_embedding_dim),
        "text_embedding_active_dim": int(feature_pipeline.text_embedding_active_dim),
        "text_max_features": int(feature_pipeline.text_max_features),
        "text_char_max_features": int(feature_pipeline.text_char_max_features),
        "validation_metrics": validation_metrics,
        "threshold_selection_split": "validation",
        "metrics": metrics,
    }

    model_path = artifacts_dir / "autoencoder.pt"
    bundle_path = artifacts_dir / "pipeline.joblib"
    torch.save(model.state_dict(), model_path)
    joblib.dump(bundle, bundle_path)

    metrics_path = output_dir / "metrics.json"
    history_path = output_dir / "training_history.json"
    suspicious_ratings_path = output_dir / "suspicious_ratings.json"
    suspicious_users_path = output_dir / "suspicious_users.json"
    summary_path = output_dir / "training_summary.json"

    save_json(
        {
            **metrics,
            "validation_metrics": validation_metrics,
            "threshold_selection_split": "validation",
            "threshold": threshold,
        },
        metrics_path,
    )
    save_json({"epochs": len(history), "loss_history": history}, history_path)
    save_json(suspicious_ratings.drop(columns=["geo_key"], errors="ignore").to_dict(orient="records"), suspicious_ratings_path)
    save_json(suspicious_users.to_dict(orient="records"), suspicious_users_path)

    summary = {
        "dataset_path": str(dataset_path),
        "records_total": int(len(ratings_df)),
        "train_records": int(len(train_df)),
        "validation_records": int(len(validation_df)),
        "test_records": int(len(test_df)),
        "labels_available": bool(has_labels),
        "threshold": threshold,
        "threshold_selection_split": "validation",
        "feature_count": int(train_scaled.shape[1]),
        "text_embedding_dim": int(feature_pipeline.text_embedding_dim),
        "text_embedding_active_dim": int(feature_pipeline.text_embedding_active_dim),
        "text_max_features": int(feature_pipeline.text_max_features),
        "text_char_max_features": int(feature_pipeline.text_char_max_features),
        "validation_metrics": validation_metrics,
        "metrics": metrics,
        "suspicious_ratings_detected": int(len(suspicious_ratings)),
        "suspicious_users_detected": int(len(suspicious_users)),
        "artifacts": {
            "model_path": str(model_path),
            "bundle_path": str(bundle_path),
            "metrics_path": str(metrics_path),
            "history_path": str(history_path),
            "suspicious_ratings_path": str(suspicious_ratings_path),
            "suspicious_users_path": str(suspicious_users_path),
        },
    }
    save_json(summary, summary_path)
    return summary
