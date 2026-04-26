"""Evaluate trained review and rating anti-fraud models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

from fake_rating_detector.data_loader import load_ratings_data
from fake_rating_detector.inference import predict_dataframe as predict_rating_dataframe
from review_scraper_detector.abstention import (
    apply_review_abstention_policy,
    build_review_uncertainty_frame,
    summarize_review_triage,
)
from review_scraper_detector.inference import _load_artifacts as load_review_artifacts
from review_scraper_detector.hybrid_combiner import predict_hybrid_meta_probabilities
from review_scraper_detector.manipulation import analyze_review_manipulation_patterns
from review_scraper_detector.training import (
    _classification_metrics,
    _prepare_hybrid_signal_frame,
    build_feature_matrix,
    load_review_training_data,
)
from review_scraper_detector.utils import ensure_directory, save_json


DEFAULT_REVIEW_PROBES = [
    {
        "name": "short_generic_extreme_positive",
        "review_text": "Amazing!!! Best purchase ever!!! Must buy now!!!",
        "rating": 5,
        "expected": "suspicious",
    },
    {
        "name": "grounded_positive_detail",
        "review_text": "I used it for three weeks. The battery lasts two days, the buttons feel firm, and delivery was on time.",
        "rating": 5,
        "expected": "clean",
    },
    {
        "name": "repeated_promo_language",
        "review_text": "Perfect product, perfect product, perfect product. Trust me, everyone needs this today.",
        "rating": 5,
        "expected": "suspicious",
    },
    {
        "name": "mixed_uncertain_review",
        "review_text": "Looks okay, but I need more time. Packaging was normal and setup took about ten minutes.",
        "rating": 3,
        "expected": "manual_or_clean",
    },
    {
        "name": "negative_specific_complaint",
        "review_text": "The left hinge started clicking after four days, and support asked for a video before replacing it.",
        "rating": 2,
        "expected": "clean",
    },
]


def parse_args() -> argparse.Namespace:
    """Parse CLI options."""
    parser = argparse.ArgumentParser(description="Evaluate trained anti-fraud models and write thesis-ready reports.")
    parser.add_argument("--review-dataset", type=Path, default=Path("data") / "combined_review_training.csv")
    parser.add_argument("--ratings-dataset", type=Path, default=Path("data") / "sample_ratings.csv")
    parser.add_argument("--artifacts-dir", type=Path, default=Path("models"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs") / "evaluation")
    parser.add_argument("--skip-review", action="store_true")
    parser.add_argument("--skip-ratings", action="store_true")
    parser.add_argument("--max-error-examples", type=int, default=12)
    return parser.parse_args()


def main() -> None:
    """Run requested evaluations."""
    args = parse_args()
    output_dir = ensure_directory(args.output_dir)
    summary: dict[str, object] = {}

    if not args.skip_review:
        summary["review_model"] = evaluate_review_model(
            dataset_path=args.review_dataset,
            artifacts_dir=args.artifacts_dir,
            output_dir=output_dir,
            max_error_examples=args.max_error_examples,
        )

    if not args.skip_ratings:
        summary["rating_model"] = evaluate_rating_model(
            dataset_path=args.ratings_dataset,
            artifacts_dir=args.artifacts_dir,
            output_dir=output_dir,
            max_error_examples=args.max_error_examples,
        )

    save_json(summary, output_dir / "evaluation_summary.json")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def evaluate_review_model(
    dataset_path: Path,
    artifacts_dir: Path,
    output_dir: Path,
    max_error_examples: int,
) -> dict:
    """Evaluate the review text and hybrid model on a labeled CSV."""
    review_df = load_review_evaluation_data(dataset_path)
    model, bundle = load_review_artifacts(artifacts_dir)
    feature_matrix = build_feature_matrix(review_df, vectorizer=bundle["vectorizer"], fit_vectorizer=False)
    labels = review_df["label"].to_numpy(dtype=np.int32)

    text_probabilities = _predict_review_text_probabilities(model, feature_matrix)
    signal_df, manipulation_summary = analyze_review_manipulation_patterns(
        _prepare_hybrid_signal_frame(review_df),
        include_page_context=False,
        slang_model=bundle.get("slang_signal_model"),
    )
    probabilities, threshold = _review_probabilities_from_bundle(bundle, signal_df, text_probabilities)
    predictions = (probabilities >= threshold).astype(np.int32)

    evaluated_df = review_df.copy().reset_index(drop=True)
    evaluated_df["text_probability"] = text_probabilities
    evaluated_df["suspicious_probability"] = probabilities
    evaluated_df["prediction"] = predictions
    evaluated_df["prediction_error"] = evaluated_df["prediction"] != evaluated_df["label"]
    evaluated_df["language_profile"] = evaluated_df["review_text"].map(_language_profile)
    evaluated_df["length_bucket"] = evaluated_df["review_text"].map(_length_bucket)
    evaluated_df["rating_bucket"] = evaluated_df["rating"].map(_rating_bucket)

    triage_summary: dict[str, object] = {}
    if bundle.get("abstention_policy") is not None:
        uncertainty_df = build_review_uncertainty_frame(
            signal_df,
            text_probabilities=text_probabilities,
            hybrid_probabilities=probabilities,
            threshold=threshold,
            vectorizer=bundle["vectorizer"],
        )
        triaged = apply_review_abstention_policy(uncertainty_df, bundle["abstention_policy"])
        triage_summary = summarize_review_triage(triaged)
        evaluated_df["triage_label"] = triaged["triage_label"].to_numpy()
        evaluated_df["uncertainty_score"] = triaged["uncertainty_score"].to_numpy()
        evaluated_df["ood_score"] = triaged["ood_score"].to_numpy()

    report = {
        "dataset_path": str(dataset_path),
        "records": int(len(evaluated_df)),
        "threshold": float(threshold),
        "metrics": _classification_metrics(labels, predictions, probabilities),
        "text_only_metrics": _classification_metrics(
            labels,
            (text_probabilities >= float(bundle.get("threshold", 0.5))).astype(np.int32),
            text_probabilities,
        ),
        "calibration": _calibration_report(labels, probabilities),
        "threshold_profiles": _threshold_profiles(labels, probabilities),
        "slice_metrics": {
            "source": _slice_metrics(evaluated_df, "source"),
            "product_family": _slice_metrics(evaluated_df, "product_family"),
            "language_profile": _slice_metrics(evaluated_df, "language_profile"),
            "length_bucket": _slice_metrics(evaluated_df, "length_bucket"),
            "rating_bucket": _slice_metrics(evaluated_df, "rating_bucket"),
        },
        "error_examples": _review_error_examples(evaluated_df, max_error_examples),
        "robustness_probes": _review_robustness_probes(model, bundle),
        "manipulation_summary": manipulation_summary,
        "triage_summary": triage_summary,
        "recommendations": _review_recommendations(labels, predictions, probabilities, triage_summary),
    }
    save_json(report, output_dir / "review_model_evaluation.json")
    return {
        "report_path": str(output_dir / "review_model_evaluation.json"),
        "metrics": report["metrics"],
        "calibration": {
            "ece": report["calibration"]["expected_calibration_error"],
            "brier_score": report["calibration"]["brier_score"],
        },
    }


def evaluate_rating_model(
    dataset_path: Path,
    artifacts_dir: Path,
    output_dir: Path,
    max_error_examples: int,
) -> dict:
    """Evaluate the site-level rating anomaly model when labels are available."""
    ratings_df = load_ratings_data(dataset_path)
    result = predict_rating_dataframe(ratings_df, artifacts_dir=artifacts_dir)
    predictions_df = pd.DataFrame(result.get("predictions", []))
    if predictions_df.empty:
        report = {"dataset_path": str(dataset_path), "records": 0, "metrics": None}
        save_json(report, output_dir / "rating_model_evaluation.json")
        return {"report_path": str(output_dir / "rating_model_evaluation.json"), "metrics": None}

    has_labels = "is_fake" in predictions_df.columns and (predictions_df["is_fake"].astype(int) >= 0).all()
    labels = predictions_df["is_fake"].to_numpy(dtype=np.int32) if has_labels else None
    anomaly_scores = predictions_df["anomaly_score"].to_numpy(dtype=float)
    predicted = predictions_df["is_suspicious"].to_numpy(dtype=np.int32)
    predictions_df["length_bucket"] = predictions_df["review_text"].fillna("").astype(str).map(_length_bucket)
    predictions_df["rating_bucket"] = predictions_df["rating"].map(_rating_bucket)
    predictions_df["language_profile"] = predictions_df["review_text"].fillna("").astype(str).map(_language_profile)
    if has_labels:
        predictions_df["prediction_error"] = predicted != labels

    report = {
        "dataset_path": str(dataset_path),
        "records": int(len(predictions_df)),
        "labels_available": bool(has_labels),
        "metrics": _classification_metrics(labels, predicted, anomaly_scores) if has_labels else None,
        "calibration": _calibration_report(labels, _minmax(anomaly_scores)) if has_labels else None,
        "slice_metrics": {
            "rating_bucket": _slice_metrics(predictions_df, "rating_bucket", score_column="anomaly_score") if has_labels else [],
            "language_profile": _slice_metrics(predictions_df, "language_profile", score_column="anomaly_score") if has_labels else [],
            "length_bucket": _slice_metrics(predictions_df, "length_bucket", score_column="anomaly_score") if has_labels else [],
        },
        "error_examples": _rating_error_examples(predictions_df, max_error_examples) if has_labels else [],
        "suspicious_user_summary": result.get("suspicious_users", [])[:10],
        "summary": result.get("summary", {}),
        "recommendations": _rating_recommendations(predictions_df, has_labels),
    }
    save_json(report, output_dir / "rating_model_evaluation.json")
    return {
        "report_path": str(output_dir / "rating_model_evaluation.json"),
        "metrics": report["metrics"],
        "labels_available": bool(has_labels),
    }


def load_review_evaluation_data(dataset_path: Path) -> pd.DataFrame:
    """Load review data for evaluation, including older CSVs without split lineage."""
    try:
        return load_review_training_data(dataset_path)
    except ValueError as exc:
        if "legacy augmented reviews" not in str(exc) and "split_group" not in str(exc):
            raise

    raw_df = pd.read_csv(dataset_path)
    df = raw_df.rename(columns={"text": "review_text", "is_suspicious": "label", "is_fake": "label"}).copy()
    if "review_text" not in df.columns or "label" not in df.columns:
        raise ValueError("Evaluation CSV must contain `review_text` and `label` columns.")
    df["review_text"] = df["review_text"].fillna("").astype(str)
    df["label"] = pd.to_numeric(df["label"], errors="coerce").fillna(0).astype(int)
    df["rating"] = pd.to_numeric(df.get("rating", 0.0), errors="coerce").fillna(0.0)
    if "source" not in df.columns:
        df["source"] = "legacy_evaluation"
    df["source"] = df["source"].fillna("legacy_evaluation").astype(str)
    if "product_family" not in df.columns:
        df["product_family"] = "unknown"
    df["product_family"] = df["product_family"].fillna("unknown").astype(str)
    if "origin_family" not in df.columns:
        df["origin_family"] = ""
    df["origin_family"] = df["origin_family"].fillna("").astype(str)
    if "holdout_group" not in df.columns:
        df["holdout_group"] = df["source"] + "|" + df["product_family"]
    if "split_group" not in df.columns:
        df["split_group"] = df.index.astype(str)
    cleaned = df[df["review_text"].str.strip().str.len() >= 1].reset_index(drop=True)
    if cleaned["label"].nunique() < 2:
        raise ValueError("Evaluation dataset must contain at least two labels.")
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


def _predict_review_text_probabilities(model, feature_matrix: np.ndarray) -> np.ndarray:
    from review_scraper_detector.model import predict_probabilities

    return predict_probabilities(model, feature_matrix)


def _review_probabilities_from_bundle(bundle: dict, signal_df: pd.DataFrame, text_probabilities: np.ndarray) -> tuple[np.ndarray, float]:
    hybrid_combiner = bundle.get("hybrid_meta_combiner")
    if hybrid_combiner is None:
        return text_probabilities, float(bundle.get("threshold", 0.5))
    return (
        predict_hybrid_meta_probabilities(
            hybrid_combiner,
            review_df=signal_df,
            text_probabilities=text_probabilities,
        ),
        float(bundle.get("hybrid_threshold", 0.5)),
    )


def _calibration_report(labels: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> dict:
    labels = np.asarray(labels, dtype=np.int32)
    probabilities = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, float | int]] = []
    ece = 0.0
    for index in range(bins):
        left = edges[index]
        right = edges[index + 1]
        if index == bins - 1:
            mask = (probabilities >= left) & (probabilities <= right)
        else:
            mask = (probabilities >= left) & (probabilities < right)
        count = int(mask.sum())
        if count == 0:
            rows.append({"bin": index + 1, "count": 0, "confidence_mean": 0.0, "positive_rate": 0.0})
            continue
        confidence = float(probabilities[mask].mean())
        positive_rate = float(labels[mask].mean())
        ece += float(count / max(len(labels), 1)) * abs(confidence - positive_rate)
        rows.append(
            {
                "bin": index + 1,
                "count": count,
                "confidence_mean": confidence,
                "positive_rate": positive_rate,
            }
        )
    return {
        "expected_calibration_error": float(ece),
        "brier_score": float(brier_score_loss(labels, probabilities)) if len(set(labels.tolist())) > 1 else None,
        "bins": rows,
    }


def _threshold_profiles(labels: np.ndarray, probabilities: np.ndarray) -> list[dict]:
    thresholds = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80]
    return [
        {
            "threshold": threshold,
            **_classification_metrics(labels, (probabilities >= threshold).astype(np.int32), probabilities),
        }
        for threshold in thresholds
    ]


def _slice_metrics(df: pd.DataFrame, column: str, score_column: str = "suspicious_probability") -> list[dict]:
    rows: list[dict] = []
    if "label" in df.columns:
        label_column = "label"
    elif "is_fake" in df.columns:
        label_column = "is_fake"
    else:
        return rows
    for value, group in df.groupby(column, dropna=False):
        labels = group[label_column].to_numpy(dtype=np.int32)
        predictions = group["prediction"].to_numpy(dtype=np.int32) if "prediction" in group.columns else group["is_suspicious"].to_numpy(dtype=np.int32)
        scores = group[score_column].to_numpy(dtype=float)
        metric = _classification_metrics(labels, predictions, scores)
        rows.append({"slice": str(value), "records": int(len(group)), "metrics": metric})
    return sorted(rows, key=lambda item: item["records"], reverse=True)


def _review_error_examples(df: pd.DataFrame, max_examples: int) -> dict[str, list[dict]]:
    false_positives = df[(df["label"] == 0) & (df["prediction"] == 1)].sort_values("suspicious_probability", ascending=False)
    false_negatives = df[(df["label"] == 1) & (df["prediction"] == 0)].sort_values("suspicious_probability", ascending=True)
    return {
        "false_positives": _review_rows(false_positives.head(max_examples)),
        "false_negatives": _review_rows(false_negatives.head(max_examples)),
    }


def _rating_error_examples(df: pd.DataFrame, max_examples: int) -> dict[str, list[dict]]:
    false_positives = df[(df["is_fake"] == 0) & (df["is_suspicious"] == 1)].sort_values("anomaly_score", ascending=False)
    false_negatives = df[(df["is_fake"] == 1) & (df["is_suspicious"] == 0)].sort_values("anomaly_score", ascending=True)
    return {
        "false_positives": _rating_rows(false_positives.head(max_examples)),
        "false_negatives": _rating_rows(false_negatives.head(max_examples)),
    }


def _review_rows(rows: pd.DataFrame) -> list[dict]:
    return [
        {
            "review_text": str(row.review_text)[:450],
            "rating": float(row.rating),
            "source": str(row.source),
            "product_family": str(row.product_family),
            "label": int(row.label),
            "prediction": int(row.prediction),
            "probability": float(row.suspicious_probability),
        }
        for row in rows.itertuples(index=False)
    ]


def _rating_rows(rows: pd.DataFrame) -> list[dict]:
    return [
        {
            "user_id": str(row.user_id),
            "item_id": str(row.item_id),
            "rating": float(row.rating),
            "review_text": str(row.review_text)[:350],
            "label": int(row.is_fake),
            "prediction": int(row.is_suspicious),
            "anomaly_score": float(row.anomaly_score),
            "reasons": list(row.suspicion_reasons) if isinstance(row.suspicion_reasons, list) else [],
        }
        for row in rows.itertuples(index=False)
    ]


def _review_robustness_probes(model, bundle: dict) -> list[dict]:
    probe_df = pd.DataFrame(DEFAULT_REVIEW_PROBES)
    probe_df["source"] = "robustness_probe"
    probe_df["product_family"] = "general"
    probe_df["origin_family"] = "probe"
    probe_df["holdout_group"] = "probe"
    probe_df["split_group"] = probe_df["name"]
    feature_matrix = build_feature_matrix(probe_df, vectorizer=bundle["vectorizer"], fit_vectorizer=False)
    text_probabilities = _predict_review_text_probabilities(model, feature_matrix)
    signal_df, _ = analyze_review_manipulation_patterns(
        _prepare_hybrid_signal_frame(probe_df),
        include_page_context=False,
        slang_model=bundle.get("slang_signal_model"),
    )
    probabilities, threshold = _review_probabilities_from_bundle(bundle, signal_df, text_probabilities)
    rows: list[dict] = []
    for index, row in probe_df.reset_index(drop=True).iterrows():
        probability = float(probabilities[index])
        rows.append(
            {
                "name": row["name"],
                "expected": row["expected"],
                "rating": float(row["rating"]),
                "probability": probability,
                "text_probability": float(text_probabilities[index]),
                "prediction": "suspicious" if probability >= threshold else "clean",
                "threshold": float(threshold),
                "review_text": row["review_text"],
            }
        )
    return rows


def _review_recommendations(labels: np.ndarray, predictions: np.ndarray, probabilities: np.ndarray, triage_summary: dict) -> list[str]:
    metrics = _classification_metrics(labels, predictions, probabilities)
    recommendations: list[str] = []
    if float(metrics["precision"]) < 0.75:
        recommendations.append("Increase clean-review diversity or raise the production threshold to reduce false positives.")
    if float(metrics["recall"]) < 0.75:
        recommendations.append("Add more confirmed manipulation examples and lower the review threshold for investigative mode.")
    calibration = _calibration_report(labels, probabilities)
    if float(calibration["expected_calibration_error"]) > 0.10:
        recommendations.append("Recalibrate probabilities with a larger validation split or isotonic/Platt calibration.")
    if triage_summary and float(triage_summary.get("manual_review_ratio", 0.0)) > 0.35:
        recommendations.append("The abstention band is broad; tighten manual-review thresholds after reviewing false positives.")
    if not recommendations:
        recommendations.append("Current metrics are stable; next improvement should focus on more real marketplace data.")
    return recommendations


def _rating_recommendations(predictions_df: pd.DataFrame, has_labels: bool) -> list[str]:
    if not has_labels:
        return ["Rating dataset has no labels; add `is_fake` labels to measure precision, recall, F1, and calibration."]
    suspicious_ratio = float(predictions_df["is_suspicious"].mean()) if len(predictions_df) else 0.0
    recommendations: list[str] = []
    if suspicious_ratio > 0.35:
        recommendations.append("Suspicious ratio is high; inspect false positives and consider a stricter anomaly threshold.")
    if suspicious_ratio < 0.03:
        recommendations.append("Suspicious ratio is very low; add stronger attack examples or soften the anomaly threshold.")
    if not recommendations:
        recommendations.append("Site-level model has a plausible suspicious-rate range; inspect user clusters for label quality.")
    return recommendations


def _language_profile(text: str) -> str:
    has_cyrillic = any("а" <= char.lower() <= "я" or char.lower() == "ё" for char in text)
    has_latin = any("a" <= char.lower() <= "z" for char in text)
    if has_cyrillic and has_latin:
        return "mixed_ru_en"
    if has_cyrillic:
        return "ru"
    if has_latin:
        return "en_or_latin"
    return "other"


def _length_bucket(text: str) -> str:
    words = len(str(text).split())
    if words < 6:
        return "very_short"
    if words < 18:
        return "short"
    if words < 60:
        return "medium"
    return "long"


def _rating_bucket(value: object) -> str:
    rating = float(value or 0)
    if rating <= 1.5:
        return "very_low"
    if rating < 3.5:
        return "middle"
    if rating < 4.75:
        return "high"
    return "extreme_high"


def _minmax(values: Iterable[float]) -> np.ndarray:
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        return array
    minimum = float(np.min(array))
    maximum = float(np.max(array))
    if maximum <= minimum:
        return np.zeros_like(array)
    return (array - minimum) / (maximum - minimum)


if __name__ == "__main__":
    main()
