"""Reusable inference utilities for CLI and Flask API predictions."""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
import torch

from .data_loader import prepare_ratings_dataframe
from .explanations import derive_suspicion_reasons
from .model import RatingsAutoencoder, reconstruction_errors
from review_scraper_detector.slang_signals import build_page_slang_profiles, build_slang_suspicion_reason


def artifacts_exist(artifacts_dir: str | Path) -> bool:
    """Return True when both the trained model weights and bundle are available."""
    artifacts_dir = Path(artifacts_dir)
    return (artifacts_dir / "autoencoder.pt").exists() and (artifacts_dir / "pipeline.joblib").exists()


def _load_artifacts(artifacts_dir: str | Path) -> tuple[RatingsAutoencoder, dict]:
    """Load the trained Autoencoder and preprocessing bundle from disk."""
    artifacts_dir = Path(artifacts_dir)
    model_path = artifacts_dir / "autoencoder.pt"
    bundle_path = artifacts_dir / "pipeline.joblib"

    if not model_path.exists() or not bundle_path.exists():
        raise FileNotFoundError("Missing model artifacts. Run `python train.py` first.")

    bundle = joblib.load(bundle_path)
    model = RatingsAutoencoder(input_dim=bundle["input_dim"], hidden_dims=bundle["hidden_dims"])
    state_dict = torch.load(model_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()
    return model, bundle


def predict_dataframe(df: pd.DataFrame, artifacts_dir: str | Path = "models") -> dict:
    """Score a validated dataframe and return JSON-ready anomaly predictions."""
    model, bundle = _load_artifacts(artifacts_dir)

    feature_pipeline = bundle["feature_pipeline"]
    scaler = bundle["scaler"]
    threshold = float(bundle["threshold"])

    feature_frame = feature_pipeline.transform(df)
    scaled_matrix = scaler.transform(feature_frame)
    scores = reconstruction_errors(model, scaled_matrix)
    predictions = (scores >= threshold).astype(int)

    result_df = df.copy().reset_index(drop=True)
    slang_page_context = build_page_slang_profiles(result_df["review_text"].fillna("").tolist())
    slang_profiles = pd.DataFrame(slang_page_context["profiles"], index=result_df.index)
    result_df = pd.concat([result_df, slang_profiles], axis=1)
    result_df["anomaly_score"] = scores
    result_df["is_suspicious"] = predictions
    base_reasons = derive_suspicion_reasons(feature_frame)
    result_df["suspicion_reasons"] = [
        _merge_suspicion_reasons(base_reason_list, slang_profile)
        for base_reason_list, slang_profile in zip(base_reasons, slang_profiles.to_dict(orient="records"))
    ]

    suspicious_users = (
        result_df.loc[result_df["is_suspicious"] == 1]
        .groupby("user_id")
        .agg(
            suspicious_ratings=("user_id", "size"),
            average_anomaly_score=("anomaly_score", "mean"),
            max_anomaly_score=("anomaly_score", "max"),
        )
        .sort_values(["suspicious_ratings", "average_anomaly_score"], ascending=[False, False])
        .reset_index()
    )

    return {
        "summary": {
            "total_records": int(len(result_df)),
            "suspicious_ratings": int(result_df["is_suspicious"].sum()),
            "suspicious_users": int(len(suspicious_users)),
            "slang_flagged_ratings": int((result_df["slang_manipulation_score"] >= 0.45).sum()),
            "slang_authenticity_mean": float(result_df["slang_authenticity_score"].mean()) if len(result_df) else 0.5,
            "slang_manipulation_mean": float(result_df["slang_manipulation_score"].mean()) if len(result_df) else 0.0,
            "page_slang_signal_ratio": float((result_df["slang_manipulation_score"] >= 0.45).mean()) if len(result_df) else 0.0,
            "page_bilingual_slang_ratio": float(result_df["slang_bilingual_mix_flag"].mean()) if len(result_df) else 0.0,
            "page_organic_slang_ratio": float((result_df["slang_profile_label"] == "organic").mean()) if len(result_df) else 0.0,
            "slang_domain_label": str(slang_page_context.get("dominant_domain", "general") or "general"),
            "slang_domain_confidence": float(slang_page_context.get("domain_confidence", 0.0) or 0.0),
            "slang_template_cluster_ratio": float(slang_page_context.get("slang_template_cluster_ratio", 0.0) or 0.0),
            "threshold": threshold,
        },
        "predictions": _serialize_records(result_df),
        "suspicious_users": suspicious_users.to_dict(orient="records"),
    }


def predict_records(records: list[dict], artifacts_dir: str | Path = "models") -> dict:
    """Score raw JSON records received from the Flask API."""
    if not isinstance(records, list) or not records:
        raise ValueError("`records` must be a non-empty list of rating objects.")

    dataframe = pd.DataFrame(records)
    prepared = prepare_ratings_dataframe(dataframe)
    return predict_dataframe(prepared, artifacts_dir=artifacts_dir)


def _serialize_records(df: pd.DataFrame) -> list[dict]:
    """Convert prediction results into JSON-ready dictionaries."""
    json_ready = df.copy()
    drop_columns = [column for column in ["geo_key"] if column in json_ready.columns]
    if drop_columns:
        json_ready = json_ready.drop(columns=drop_columns)
    if "is_fake" in json_ready.columns and (json_ready["is_fake"] < 0).all():
        json_ready = json_ready.drop(columns=["is_fake"])
    json_ready["timestamp"] = json_ready["timestamp"].apply(lambda value: value.isoformat())
    return json_ready.to_dict(orient="records")


def _merge_suspicion_reasons(base_reasons: list[str], slang_profile: dict) -> list[str]:
    """Append bilingual slang reasoning without duplicating explanations."""
    reasons = list(base_reasons)
    slang_reason = build_slang_suspicion_reason(slang_profile)
    if slang_reason and slang_reason not in reasons:
        reasons.append(slang_reason)
    return reasons
