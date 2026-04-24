"""Inference utilities for suspicious review analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import os
from pathlib import Path
from urllib.parse import urlparse

import joblib
import numpy as np
import pandas as pd
import torch

from fake_rating_detector.inference import predict_records as predict_rating_records
from .abstention import apply_review_abstention_policy, build_review_uncertainty_frame, summarize_review_triage
from .hybrid_combiner import predict_hybrid_meta_probabilities
from .image_ocr_signals import build_image_ocr_signals
from .image_signals import build_image_duplicate_signals, normalize_image_urls
from .image_temporal_clusters import build_image_temporal_cluster_signals
from .image_text_alignment import build_image_text_alignment_signals
from .model import ReviewClassifier, predict_probabilities
from .manipulation import analyze_review_manipulation_patterns
from .parsing import parse_reviews_from_html
from .marketplace_api import collect_reviews_via_public_marketplace_api
from .review_collector import CollectionResult, ReviewCollectorConfig, collect_reviews_sync
from .schemas import AnalysisRequest, AnalysisSummary, ReviewPrediction
from .scraping import DEFAULT_WAIT_MS, fetch_html_via_scrapingbee
from .training import build_feature_matrix
from .utils import normalize_whitespace


DEFAULT_BROWSER_COLLECTOR_MAX_REVIEWS = 160


def artifacts_exist(artifacts_dir: str | Path = "models") -> bool:
    """Return True if the trained review classifier artifacts exist."""
    artifacts_dir = Path(artifacts_dir)
    return (artifacts_dir / "review_text_classifier.pt").exists() and (artifacts_dir / "review_text_bundle.joblib").exists()


def analyze_product_url(
    product_url: str,
    artifacts_dir: str | Path = "models",
    api_key: str | None = None,
    render_js: bool = True,
    country_code: str | None = None,
    wait_ms: int = DEFAULT_WAIT_MS,
    scroll_rounds: int = 0,
    scroll_delay_ms: int = 1200,
) -> dict:
    """Fetch a product page through the external ScrapingBee API and classify reviews."""
    html = fetch_html_via_scrapingbee(
        url=product_url,
        api_key=api_key,
        render_js=render_js,
        country_code=country_code,
        wait_ms=wait_ms,
        scroll_rounds=scroll_rounds,
        scroll_delay_ms=scroll_delay_ms,
    )
    return analyze_html_document(
        html=html,
        source_url=product_url,
        artifacts_dir=artifacts_dir,
        source_type="url",
    )


def analyze_html_document(
    html: str,
    source_url: str,
    artifacts_dir: str | Path = "models",
    source_type: str = "html",
) -> dict:
    """Parse review HTML and run suspicious-review classification."""
    reviews = parse_reviews_from_html(html=html, source_url=source_url)
    return analyze_review_records(
        records=reviews,
        source_url=source_url,
        artifacts_dir=artifacts_dir,
        source_type=source_type,
    )


def analyze_review_records(
    records: list[dict],
    source_url: str,
    artifacts_dir: str | Path = "models",
    source_type: str = "records",
) -> dict:
    """Run suspicious-review classification for already collected review records."""
    source_site = _infer_site_name(source_url)
    request_meta = AnalysisRequest(
        source_url=source_url,
        source_site=source_site,
        source_type=source_type,
        model_family="calibrated-hybrid-neural-rating-antifraud",
    )

    if not records:
        empty_summary = AnalysisSummary(
            source_url=source_url,
            source_site=source_site,
            source_type=source_type,
            total_reviews=0,
            suspicious_reviews=0,
            clean_reviews=0,
            confident_suspicious_reviews=0,
            confident_clean_reviews=0,
            manual_review_reviews=0,
            suspicious_ratio=0.0,
            manual_review_ratio=0.0,
            automated_decision_ratio=0.0,
            threshold=0.0,
            average_probability=0.0,
            highest_probability=0.0,
            uncertainty_mean=0.0,
            ood_alert_ratio=0.0,
            risk_level="none",
            suspicious_authors=0,
            manipulation_score_mean=0.0,
            rating_manipulation_risk="none",
            slang_authenticity_mean=0.5,
            slang_manipulation_mean=0.0,
            page_slang_signal_ratio=0.0,
            page_bilingual_slang_ratio=0.0,
            page_organic_slang_ratio=0.0,
            slang_domain_label="general",
            slang_domain_confidence=0.0,
            slang_template_cluster_ratio=0.0,
            photo_reviews=0,
            photo_review_ratio=0.0,
            duplicate_photo_reviews=0,
            duplicate_photo_review_ratio=0.0,
            duplicate_photo_cluster_count=0,
            largest_duplicate_photo_cluster=0,
            photo_forensics_risk="none",
            photo_temporal_cluster_reviews=0,
            photo_temporal_cluster_ratio=0.0,
            photo_temporal_cluster_count=0,
            largest_photo_temporal_cluster=0,
            photo_temporal_cluster_risk="none",
            photo_temporal_cluster_window_hours=48.0,
            image_alignment_reviews=0,
            image_alignment_mismatch_reviews=0,
            image_alignment_mismatch_ratio=0.0,
            image_alignment_mean=0.0,
            image_alignment_model_status="no_images",
            image_alignment_model_name="",
            stock_marketing_photo_reviews=0,
            stock_marketing_photo_ratio=0.0,
            stock_marketing_score_mean=0.0,
            synthetic_image_reviews=0,
            synthetic_image_ratio=0.0,
            synthetic_image_score_mean=0.0,
            image_ocr_reviews=0,
            image_ocr_flagged_reviews=0,
            image_ocr_flagged_ratio=0.0,
            image_ocr_score_mean=0.0,
            image_ocr_status="no_images",
        )
        return {
            "request": request_meta.to_dict(),
            "summary": empty_summary.to_dict(),
            "highlights": {
                "top_reasons": [],
                "most_suspicious_review": None,
                "notes": ["No review blocks were extracted from the provided page."],
            },
            "reviews": [],
        }

    model, bundle = _load_artifacts(artifacts_dir)
    review_df = pd.DataFrame(records)
    for column, default_value in {
        "author": "",
        "title": "",
        "rating": 0.0,
        "date": "",
        "review_text": "",
        "source_url": source_url,
        "source_site": source_site,
    }.items():
        if column not in review_df.columns:
            review_df[column] = default_value
    if "image_urls" not in review_df.columns:
        review_df["image_urls"] = [[] for _ in range(len(review_df))]
    else:
        review_df["image_urls"] = review_df["image_urls"].map(normalize_image_urls)
    manipulation_df, manipulation_summary = analyze_review_manipulation_patterns(
        review_df,
        slang_model=bundle.get("slang_signal_model"),
    )
    manipulation_df, image_summary = build_image_duplicate_signals(manipulation_df)
    manipulation_df, image_temporal_summary = build_image_temporal_cluster_signals(manipulation_df)
    manipulation_df, image_alignment_summary = build_image_text_alignment_signals(
        manipulation_df,
        source_url=source_url,
        source_site=source_site,
    )
    manipulation_df, image_ocr_summary = build_image_ocr_signals(
        manipulation_df,
        source_site=source_site,
    )
    image_summary = {**image_summary, **image_temporal_summary, **image_alignment_summary, **image_ocr_summary}
    feature_matrix = build_feature_matrix(review_df, vectorizer=bundle["vectorizer"], fit_vectorizer=False)
    text_probabilities = predict_probabilities(model, feature_matrix)
    combined_probabilities, threshold = _score_hybrid_probabilities(
        bundle=bundle,
        text_probabilities=text_probabilities,
        manipulation_df=manipulation_df,
    )
    combined_probabilities = _apply_image_forensics_boost(combined_probabilities, manipulation_df)
    if bundle.get("abstention_policy") is not None:
        manipulation_df = build_review_uncertainty_frame(
            manipulation_df,
            text_probabilities=text_probabilities,
            hybrid_probabilities=combined_probabilities,
            threshold=threshold,
            vectorizer=bundle["vectorizer"],
        )
        manipulation_df = apply_review_abstention_policy(manipulation_df, bundle["abstention_policy"])
    predictions = (combined_probabilities >= threshold).astype(int)

    review_predictions = _build_review_predictions(
        review_df=manipulation_df,
        text_probabilities=text_probabilities,
        combined_probabilities=combined_probabilities,
        predictions=predictions,
    )
    review_dicts = [review.to_dict() for review in review_predictions]
    summary = _build_summary(
        request_meta=request_meta,
        review_dicts=review_dicts,
        threshold=threshold,
        manipulation_summary=manipulation_summary,
        triage_summary=summarize_review_triage(manipulation_df),
        image_summary=image_summary,
    )

    return {
        "request": request_meta.to_dict(),
        "summary": summary.to_dict(),
        "highlights": _build_highlights(review_dicts, manipulation_summary, image_summary),
        "reviews": review_dicts,
    }


def _load_artifacts(artifacts_dir: str | Path) -> tuple[ReviewClassifier, dict]:
    """Load the trained text classifier and its vectorizer bundle."""
    artifacts_dir = Path(artifacts_dir)
    model_path = artifacts_dir / "review_text_classifier.pt"
    bundle_path = artifacts_dir / "review_text_bundle.joblib"

    if not model_path.exists() or not bundle_path.exists():
        raise FileNotFoundError("Model artifacts are missing. Run `python train.py` first.")

    bundle = joblib.load(bundle_path)
    model = ReviewClassifier(
        input_dim=bundle["input_dim"],
        hidden_dims=bundle["hidden_dims"],
    )
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()
    return model, bundle


def _build_review_predictions(
    review_df: pd.DataFrame,
    text_probabilities: np.ndarray,
    combined_probabilities: np.ndarray,
    predictions: np.ndarray,
) -> list[ReviewPrediction]:
    """Convert raw model outputs into normalized review prediction records."""
    review_predictions: list[ReviewPrediction] = []

    for index, row in review_df.reset_index(drop=True).iterrows():
        probability = float(combined_probabilities[index])
        risk_level = _risk_level(probability)
        review_text = normalize_whitespace(str(row.get("review_text", "")))

        review_predictions.append(
            ReviewPrediction(
                review_id=index + 1,
                author=normalize_whitespace(str(row.get("author", ""))),
                title=normalize_whitespace(str(row.get("title", ""))),
                rating=float(row.get("rating", 0.0) or 0.0),
                date=normalize_whitespace(str(row.get("date", ""))),
                review_text=review_text,
                source_url=normalize_whitespace(str(row.get("source_url", ""))),
                source_site=normalize_whitespace(str(row.get("source_site", ""))),
                text_suspicious_probability=float(text_probabilities[index]),
                rating_manipulation_score=float(row.get("rating_manipulation_score", 0.0) or 0.0),
                author_risk_score=float(row.get("author_risk_score", 0.0) or 0.0),
                slang_authenticity_score=float(row.get("slang_authenticity_score", 0.5) or 0.5),
                slang_manipulation_score=float(row.get("slang_manipulation_score", 0.0) or 0.0),
                slang_profile_label=str(row.get("slang_profile_label", "neutral") or "neutral"),
                slang_domain_label=str(row.get("slang_domain_label", "general") or "general"),
                slang_template_dup_count=int(row.get("slang_template_dup_count", 0) or 0),
                suspicious_probability=probability,
                is_suspicious=int(predictions[index]),
                triage_label=str(
                    row.get(
                        "triage_label",
                        "confident_suspicious" if int(predictions[index]) else "confident_clean",
                    )
                    or "confident_clean"
                ),
                requires_manual_review=int(row.get("requires_manual_review", 0) or 0),
                uncertainty_score=float(row.get("uncertainty_score", 0.0) or 0.0),
                ood_score=float(row.get("ood_score", 0.0) or 0.0),
                decision_margin=float(row.get("decision_margin", 0.0) or 0.0),
                risk_level=risk_level,
                word_count=len(review_text.split()),
                character_count=len(review_text),
                image_count=int(row.get("image_count", 0) or 0),
                duplicate_image_count=int(row.get("duplicate_image_count", 0) or 0),
                duplicate_image_cluster_size=int(row.get("duplicate_image_cluster_size", 0) or 0),
                duplicate_image_score=float(row.get("duplicate_image_score", 0.0) or 0.0),
                duplicate_image_flag=int(row.get("duplicate_image_flag", 0) or 0),
                image_temporal_cluster_score=float(row.get("image_temporal_cluster_score", 0.0) or 0.0),
                image_temporal_cluster_flag=int(row.get("image_temporal_cluster_flag", 0) or 0),
                image_temporal_cluster_size=int(row.get("image_temporal_cluster_size", 0) or 0),
                image_temporal_cluster_author_count=int(row.get("image_temporal_cluster_author_count", 0) or 0),
                image_temporal_cluster_window_hours=float(row.get("image_temporal_cluster_window_hours", 0.0) or 0.0),
                image_temporal_cluster_fingerprint=str(row.get("image_temporal_cluster_fingerprint", "") or ""),
                image_text_alignment_score=float(row.get("image_text_alignment_score", 0.0) or 0.0),
                image_text_mismatch_score=float(row.get("image_text_mismatch_score", 0.0) or 0.0),
                image_text_mismatch_flag=int(row.get("image_text_mismatch_flag", 0) or 0),
                image_text_alignment_label=str(row.get("image_text_alignment_label", "not_evaluated") or "not_evaluated"),
                image_text_alignment_model=str(row.get("image_text_alignment_model", "") or ""),
                image_stock_marketing_score=float(row.get("image_stock_marketing_score", 0.0) or 0.0),
                image_stock_marketing_flag=int(row.get("image_stock_marketing_flag", 0) or 0),
                image_stock_marketing_label=str(row.get("image_stock_marketing_label", "not_evaluated") or "not_evaluated"),
                image_synthetic_score=float(row.get("image_synthetic_score", 0.0) or 0.0),
                image_synthetic_flag=int(row.get("image_synthetic_flag", 0) or 0),
                image_synthetic_label=str(row.get("image_synthetic_label", "not_evaluated") or "not_evaluated"),
                image_ocr_score=float(row.get("image_ocr_score", 0.0) or 0.0),
                image_ocr_flag=int(row.get("image_ocr_flag", 0) or 0),
                image_ocr_text=normalize_whitespace(str(row.get("image_ocr_text", "") or "")),
                image_urls=normalize_image_urls(row.get("image_urls", [])),
                duplicate_image_fingerprints=list(row.get("duplicate_image_fingerprints", []) or []),
                image_temporal_cluster_reasons=list(row.get("image_temporal_cluster_reasons", []) or []),
                image_text_alignment_reasons=list(row.get("image_text_alignment_reasons", []) or []),
                image_stock_marketing_reasons=list(row.get("image_stock_marketing_reasons", []) or []),
                image_synthetic_reasons=list(row.get("image_synthetic_reasons", []) or []),
                image_ocr_labels=list(row.get("image_ocr_labels", []) or []),
                image_ocr_reasons=list(row.get("image_ocr_reasons", []) or []),
                detected_slang_terms=list(row.get("slang_terms", []) or []),
                suspicion_reasons=_build_suspicion_reasons(
                    text=review_text,
                    rating=float(row.get("rating", 0.0) or 0.0),
                    probability=float(text_probabilities[index]),
                    manipulation_reasons=row.get("manipulation_reasons", []),
                    manipulation_score=float(row.get("rating_manipulation_score", 0.0) or 0.0),
                    slang_authenticity_score=float(row.get("slang_authenticity_score", 0.5) or 0.5),
                    slang_manipulation_score=float(row.get("slang_manipulation_score", 0.0) or 0.0),
                    slang_domain_label=str(row.get("slang_domain_label", "general") or "general"),
                    slang_template_dup_count=int(row.get("slang_template_dup_count", 0) or 0),
                    slang_terms=list(row.get("slang_terms", []) or []),
                    duplicate_image_score=float(row.get("duplicate_image_score", 0.0) or 0.0),
                    duplicate_image_cluster_size=int(row.get("duplicate_image_cluster_size", 0) or 0),
                    image_duplicate_reasons=list(row.get("image_duplicate_reasons", []) or []),
                    image_temporal_cluster_score=float(row.get("image_temporal_cluster_score", 0.0) or 0.0),
                    image_temporal_cluster_flag=int(row.get("image_temporal_cluster_flag", 0) or 0),
                    image_temporal_cluster_reasons=list(row.get("image_temporal_cluster_reasons", []) or []),
                    image_text_mismatch_score=float(row.get("image_text_mismatch_score", 0.0) or 0.0),
                    image_text_mismatch_flag=int(row.get("image_text_mismatch_flag", 0) or 0),
                    image_text_alignment_reasons=list(row.get("image_text_alignment_reasons", []) or []),
                    image_stock_marketing_score=float(row.get("image_stock_marketing_score", 0.0) or 0.0),
                    image_stock_marketing_flag=int(row.get("image_stock_marketing_flag", 0) or 0),
                    image_stock_marketing_reasons=list(row.get("image_stock_marketing_reasons", []) or []),
                    image_synthetic_score=float(row.get("image_synthetic_score", 0.0) or 0.0),
                    image_synthetic_flag=int(row.get("image_synthetic_flag", 0) or 0),
                    image_synthetic_reasons=list(row.get("image_synthetic_reasons", []) or []),
                    image_ocr_score=float(row.get("image_ocr_score", 0.0) or 0.0),
                    image_ocr_flag=int(row.get("image_ocr_flag", 0) or 0),
                    image_ocr_reasons=list(row.get("image_ocr_reasons", []) or []),
                ),
                manual_review_reasons=list(row.get("manual_review_reasons", []) or []),
            )
        )

    return review_predictions


def _build_summary(
    request_meta: AnalysisRequest,
    review_dicts: list[dict],
    threshold: float,
    manipulation_summary: dict,
    triage_summary: dict,
    image_summary: dict,
) -> AnalysisSummary:
    """Aggregate high-level metrics for the current analysis run."""
    total_reviews = len(review_dicts)
    suspicious_reviews = sum(int(review["is_suspicious"]) for review in review_dicts)
    probabilities = [float(review["suspicious_probability"]) for review in review_dicts]
    suspicious_ratio = float(suspicious_reviews / total_reviews) if total_reviews else 0.0
    average_probability = float(np.mean(probabilities)) if probabilities else 0.0
    highest_probability = float(max(probabilities)) if probabilities else 0.0

    return AnalysisSummary(
        source_url=request_meta.source_url,
        source_site=request_meta.source_site,
        source_type=request_meta.source_type,
        total_reviews=total_reviews,
        suspicious_reviews=suspicious_reviews,
        clean_reviews=total_reviews - suspicious_reviews,
        confident_suspicious_reviews=int(triage_summary.get("confident_suspicious_reviews", 0)),
        confident_clean_reviews=int(triage_summary.get("confident_clean_reviews", 0)),
        manual_review_reviews=int(triage_summary.get("manual_review_reviews", 0)),
        suspicious_ratio=suspicious_ratio,
        manual_review_ratio=float(triage_summary.get("manual_review_ratio", 0.0)),
        automated_decision_ratio=float(triage_summary.get("automated_decision_ratio", 0.0)),
        threshold=float(threshold),
        average_probability=average_probability,
        highest_probability=highest_probability,
        uncertainty_mean=float(triage_summary.get("uncertainty_mean", 0.0)),
        ood_alert_ratio=float(triage_summary.get("ood_alert_ratio", 0.0)),
        risk_level=_risk_level(highest_probability if suspicious_reviews else average_probability),
        suspicious_authors=int(manipulation_summary.get("suspicious_authors", 0)),
        manipulation_score_mean=float(manipulation_summary.get("manipulation_score_mean", 0.0)),
        rating_manipulation_risk=str(manipulation_summary.get("rating_manipulation_risk", "none")),
        slang_authenticity_mean=float(manipulation_summary.get("slang_authenticity_mean", 0.5)),
        slang_manipulation_mean=float(manipulation_summary.get("slang_manipulation_mean", 0.0)),
        page_slang_signal_ratio=float(manipulation_summary.get("page_slang_signal_ratio", 0.0)),
        page_bilingual_slang_ratio=float(manipulation_summary.get("page_bilingual_slang_ratio", 0.0)),
        page_organic_slang_ratio=float(manipulation_summary.get("page_organic_slang_ratio", 0.0)),
        slang_domain_label=str(manipulation_summary.get("slang_domain_label", "general")),
        slang_domain_confidence=float(manipulation_summary.get("slang_domain_confidence", 0.0)),
        slang_template_cluster_ratio=float(manipulation_summary.get("slang_template_cluster_ratio", 0.0)),
        photo_reviews=int(image_summary.get("photo_reviews", 0)),
        photo_review_ratio=float(image_summary.get("photo_review_ratio", 0.0)),
        duplicate_photo_reviews=int(image_summary.get("duplicate_photo_reviews", 0)),
        duplicate_photo_review_ratio=float(image_summary.get("duplicate_photo_review_ratio", 0.0)),
        duplicate_photo_cluster_count=int(image_summary.get("duplicate_photo_cluster_count", 0)),
        largest_duplicate_photo_cluster=int(image_summary.get("largest_duplicate_photo_cluster", 0)),
        photo_forensics_risk=str(image_summary.get("photo_forensics_risk", "none")),
        photo_temporal_cluster_reviews=int(image_summary.get("photo_temporal_cluster_reviews", 0)),
        photo_temporal_cluster_ratio=float(image_summary.get("photo_temporal_cluster_ratio", 0.0)),
        photo_temporal_cluster_count=int(image_summary.get("photo_temporal_cluster_count", 0)),
        largest_photo_temporal_cluster=int(image_summary.get("largest_photo_temporal_cluster", 0)),
        photo_temporal_cluster_risk=str(image_summary.get("photo_temporal_cluster_risk", "none")),
        photo_temporal_cluster_window_hours=float(image_summary.get("photo_temporal_cluster_window_hours", 48.0)),
        image_alignment_reviews=int(image_summary.get("image_alignment_reviews", 0)),
        image_alignment_mismatch_reviews=int(image_summary.get("image_alignment_mismatch_reviews", 0)),
        image_alignment_mismatch_ratio=float(image_summary.get("image_alignment_mismatch_ratio", 0.0)),
        image_alignment_mean=float(image_summary.get("image_alignment_mean", 0.0)),
        image_alignment_model_status=str(image_summary.get("image_alignment_model_status", "not_evaluated")),
        image_alignment_model_name=str(image_summary.get("image_alignment_model_name", "")),
        stock_marketing_photo_reviews=int(image_summary.get("stock_marketing_photo_reviews", 0)),
        stock_marketing_photo_ratio=float(image_summary.get("stock_marketing_photo_ratio", 0.0)),
        stock_marketing_score_mean=float(image_summary.get("stock_marketing_score_mean", 0.0)),
        synthetic_image_reviews=int(image_summary.get("synthetic_image_reviews", 0)),
        synthetic_image_ratio=float(image_summary.get("synthetic_image_ratio", 0.0)),
        synthetic_image_score_mean=float(image_summary.get("synthetic_image_score_mean", 0.0)),
        image_ocr_reviews=int(image_summary.get("image_ocr_reviews", 0)),
        image_ocr_flagged_reviews=int(image_summary.get("image_ocr_flagged_reviews", 0)),
        image_ocr_flagged_ratio=float(image_summary.get("image_ocr_flagged_ratio", 0.0)),
        image_ocr_score_mean=float(image_summary.get("image_ocr_score_mean", 0.0)),
        image_ocr_status=str(image_summary.get("image_ocr_status", "not_evaluated")),
    )


def _build_highlights(review_dicts: list[dict], manipulation_summary: dict, image_summary: dict) -> dict:
    """Create compact highlights for dashboards and the mini frontend."""
    reasons = Counter(
        reason
        for review in review_dicts
        for reason in review.get("suspicion_reasons", [])
    )
    top_reasons = [
        {"reason": reason, "count": count}
        for reason, count in reasons.most_common(4)
    ]

    sorted_reviews = sorted(
        review_dicts,
        key=lambda review: float(review.get("suspicious_probability", 0.0)),
        reverse=True,
    )
    most_suspicious_review = sorted_reviews[0] if sorted_reviews else None

    notes: list[str] = []
    if not review_dicts:
        notes.append("No reviews were available for scoring.")
    elif not any(review.get("is_suspicious") for review in review_dicts):
        notes.append("The model did not flag any extracted reviews as suspicious.")
    else:
        notes.append("Suspicious reviews are ranked by a calibrated hybrid score that combines the neural text model and manipulation signals.")

    manual_review_count = sum(int(review.get("requires_manual_review", 0) or 0) for review in review_dicts)
    if manual_review_count > 0:
        notes.append(
            f"{manual_review_count} review(s) were routed to manual review because the model saw uncertainty or out-of-domain patterns."
        )

    duplicate_photo_reviews = int(image_summary.get("duplicate_photo_reviews", 0) or 0)
    largest_photo_cluster = int(image_summary.get("largest_duplicate_photo_cluster", 0) or 0)
    if duplicate_photo_reviews > 0:
        notes.append(
            f"Customer photo reuse was detected in {duplicate_photo_reviews} review(s); "
            f"the largest shared-photo cluster spans {largest_photo_cluster} reviews."
        )

    temporal_photo_reviews = int(image_summary.get("photo_temporal_cluster_reviews", 0) or 0)
    temporal_window_hours = float(image_summary.get("photo_temporal_cluster_window_hours", 48.0) or 48.0)
    if temporal_photo_reviews > 0:
        notes.append(
            f"Coordinated photo timing was detected in {temporal_photo_reviews} review(s): the same customer image "
            f"appeared across different authors inside a {round(temporal_window_hours, 1)}-hour window."
        )

    image_mismatch_reviews = int(image_summary.get("image_alignment_mismatch_reviews", 0) or 0)
    image_alignment_status = str(image_summary.get("image_alignment_model_status", "not_evaluated") or "not_evaluated")
    if image_mismatch_reviews > 0:
        notes.append(
            f"Image-text alignment flagged {image_mismatch_reviews} customer photo(s) as visually inconsistent "
            "with the review text or inferred product category."
        )
    elif image_alignment_status in {"not_configured", "model_unavailable"} and any(
        int(review.get("image_count", 0) or 0) > 0 for review in review_dicts
    ):
        notes.append(
            "Customer photos were extracted, but CLIP/ViT image-text alignment is not configured on this machine yet."
        )

    stock_marketing_photo_reviews = int(image_summary.get("stock_marketing_photo_reviews", 0) or 0)
    if stock_marketing_photo_reviews > 0:
        notes.append(
            f"Stock/marketing photo detection flagged {stock_marketing_photo_reviews} image(s) that look closer "
            "to catalog, studio, render, banner, or listing assets than user-taken snapshots."
        )

    synthetic_image_reviews = int(image_summary.get("synthetic_image_reviews", 0) or 0)
    if synthetic_image_reviews > 0:
        notes.append(
            f"AI/synthetic image detection produced weak auxiliary hints on {synthetic_image_reviews} image(s); "
            "this signal should support, not replace, human review or stronger fraud evidence."
        )

    image_ocr_flagged_reviews = int(image_summary.get("image_ocr_flagged_reviews", 0) or 0)
    if image_ocr_flagged_reviews > 0:
        notes.append(
            f"OCR found promo text, watermark-like text, contact handles, or marketplace branding on "
            f"{image_ocr_flagged_reviews} customer photo(s)."
        )

    suspicious_authors = manipulation_summary.get("suspicious_author_records", [])
    if suspicious_authors:
        top_author = suspicious_authors[0]
        notes.append(
            f"Top suspicious author cluster: {top_author.get('author', 'unknown')} "
            f"with {top_author.get('suspicious_reviews', 0)} flagged review(s)."
        )

    slang_signal_ratio = float(manipulation_summary.get("page_slang_signal_ratio", 0.0) or 0.0)
    bilingual_slang_ratio = float(manipulation_summary.get("page_bilingual_slang_ratio", 0.0) or 0.0)
    organic_slang_ratio = float(manipulation_summary.get("page_organic_slang_ratio", 0.0) or 0.0)
    slang_authenticity_mean = float(manipulation_summary.get("slang_authenticity_mean", 0.5) or 0.5)
    slang_domain_label = str(manipulation_summary.get("slang_domain_label", "general") or "general")
    slang_domain_confidence = float(manipulation_summary.get("slang_domain_confidence", 0.0) or 0.0)
    slang_template_cluster_ratio = float(manipulation_summary.get("slang_template_cluster_ratio", 0.0) or 0.0)
    slang_model_strategy = str(manipulation_summary.get("slang_model_strategy", "rule_based") or "rule_based")
    enough_reviews_for_page_linguistics = len(review_dicts) >= 4

    if enough_reviews_for_page_linguistics and slang_signal_ratio >= 0.25:
        notes.append("The bilingual slang detector found a visible share of hype-heavy comments that look more coordinated than conversational.")
    elif enough_reviews_for_page_linguistics and organic_slang_ratio >= 0.25 and slang_authenticity_mean >= 0.58:
        notes.append("Several comments use grounded colloquial language with concrete detail, which slightly weakens the fake-review hypothesis.")

    if enough_reviews_for_page_linguistics and bilingual_slang_ratio >= 0.18:
        notes.append("Russian and English slang are mixed unusually often across the current review sample.")
    if enough_reviews_for_page_linguistics and slang_template_cluster_ratio >= 0.18:
        notes.append("A repeated slang template appears across multiple reviews, which strengthens the coordination hypothesis.")
    if slang_domain_label != "general" and slang_domain_confidence >= 0.35:
        notes.append(f"Language grounding was calibrated against the inferred {slang_domain_label} product domain.")
    if slang_model_strategy == "validation_learned_calibrator":
        notes.append("The slang detector also uses validation-calibrated weights and marketplace-aware lexicons, not only hand-written rules.")

    return {
        "top_reasons": top_reasons,
        "most_suspicious_review": most_suspicious_review,
        "suspicious_authors": suspicious_authors[:5],
        "notes": notes,
    }


def _build_suspicion_reasons(
    text: str,
    rating: float,
    probability: float,
    manipulation_reasons: list[str] | None = None,
    manipulation_score: float = 0.0,
    slang_authenticity_score: float = 0.5,
    slang_manipulation_score: float = 0.0,
    slang_domain_label: str = "general",
    slang_template_dup_count: int = 0,
    slang_terms: list[str] | None = None,
    duplicate_image_score: float = 0.0,
    duplicate_image_cluster_size: int = 0,
    image_duplicate_reasons: list[str] | None = None,
    image_temporal_cluster_score: float = 0.0,
    image_temporal_cluster_flag: int = 0,
    image_temporal_cluster_reasons: list[str] | None = None,
    image_text_mismatch_score: float = 0.0,
    image_text_mismatch_flag: int = 0,
    image_text_alignment_reasons: list[str] | None = None,
    image_stock_marketing_score: float = 0.0,
    image_stock_marketing_flag: int = 0,
    image_stock_marketing_reasons: list[str] | None = None,
    image_synthetic_score: float = 0.0,
    image_synthetic_flag: int = 0,
    image_synthetic_reasons: list[str] | None = None,
    image_ocr_score: float = 0.0,
    image_ocr_flag: int = 0,
    image_ocr_reasons: list[str] | None = None,
) -> list[str]:
    """Create lightweight human-readable reasons for suspicious predictions."""
    reasons: list[str] = []
    normalized_text = normalize_whitespace(text)
    lower_text = normalized_text.lower()
    word_count = len(lower_text.split())

    if probability >= 0.8:
        reasons.append("The neural model considers this review highly suspicious.")
    elif probability >= 0.6:
        reasons.append("The review has several linguistic patterns often seen in manipulated feedback.")

    if word_count < 8:
        reasons.append("The review is unusually short and provides very little concrete detail.")
    if lower_text.count("!") >= 3:
        reasons.append("The text relies on heavy emotional punctuation.")
    if any(phrase in lower_text for phrase in ["buy now", "100% recommended", "best purchase ever", "trust me", "must buy"]):
        reasons.append("The wording looks promotional or strongly templated.")
    if len(set(lower_text.split())) < max(3, word_count // 2):
        reasons.append("There is visible repetition, which can indicate scripted review text.")
    if rating in {1.0, 5.0} and word_count < 15:
        reasons.append("An extreme rating is paired with a generic explanation.")
    if slang_template_dup_count >= 2:
        reasons.append("The same slang-heavy language pattern appears in multiple reviews on this page.")
    if slang_manipulation_score >= 0.55:
        detail_label = "product" if slang_domain_label == "general" else slang_domain_label
        if slang_terms:
            reasons.append(
                f"The slang profile looks hype-heavy and weakly grounded in {detail_label} detail "
                f"({', '.join(slang_terms[:3])})."
            )
        else:
            reasons.append(f"The slang profile looks hype-heavy and weakly grounded in {detail_label} detail.")
    if manipulation_score >= 0.55:
        reasons.append("Behavioral and statistical page signals also suggest possible rating manipulation.")
    if duplicate_image_score >= 0.45 and duplicate_image_cluster_size >= 2:
        reasons.append("The customer photo evidence is reused across multiple reviews.")
    if image_temporal_cluster_flag and image_temporal_cluster_score >= 0.55:
        reasons.append("The same customer photo appears in a short time window across different authors.")
    if image_text_mismatch_flag and image_text_mismatch_score >= 0.58:
        reasons.append("The attached customer photo does not match the review text or inferred product category.")
    if image_stock_marketing_flag and image_stock_marketing_score >= 0.58:
        reasons.append("The customer image looks like a stock, catalog, studio, render, banner, or listing asset.")
    if image_synthetic_flag and image_synthetic_score >= 0.66:
        reasons.append("The image has weak AI-generated or synthetic-image indicators; treat this as supporting evidence, not proof.")
    if image_ocr_flag and image_ocr_score >= 0.46:
        reasons.append("OCR found promo, watermark, contact, marketplace, or sales text on the customer photo.")

    for reason in manipulation_reasons or []:
        if reason not in reasons:
            reasons.append(reason)
    for reason in image_duplicate_reasons or []:
        if reason not in reasons:
            reasons.append(reason)
    for reason in image_temporal_cluster_reasons or []:
        if reason not in reasons:
            reasons.append(reason)
    for reason in image_text_alignment_reasons or []:
        if reason not in reasons:
            reasons.append(reason)
    for reason in image_stock_marketing_reasons or []:
        if reason not in reasons:
            reasons.append(reason)
    for reason in image_synthetic_reasons or []:
        if reason not in reasons:
            reasons.append(reason)
    for reason in image_ocr_reasons or []:
        if reason not in reasons:
            reasons.append(reason)

    return reasons


def analyze_site_rating_records(records: list[dict], artifacts_dir: str | Path = "models") -> dict:
    """Run full site-level rating manipulation detection on structured rating records."""
    return predict_rating_records(records=records, artifacts_dir=artifacts_dir)


def _combine_probabilities(text_probabilities: np.ndarray, manipulation_scores: np.ndarray) -> np.ndarray:
    """Legacy fallback combiner for older model bundles without calibration metadata."""
    return np.clip(0.62 * text_probabilities + 0.38 * manipulation_scores, 0.0, 1.0)


def _combined_threshold(text_threshold: float) -> float:
    """Legacy fallback threshold for older model bundles without hybrid calibration."""
    return float(max(0.45, min(0.5, text_threshold)))


def _score_hybrid_probabilities(
    bundle: dict,
    text_probabilities: np.ndarray,
    manipulation_df: pd.DataFrame,
) -> tuple[np.ndarray, float]:
    """Score reviews with the calibrated combiner when available, otherwise use legacy fallback."""
    hybrid_combiner = bundle.get("hybrid_meta_combiner")
    if hybrid_combiner is not None:
        hybrid_threshold = float(bundle.get("hybrid_threshold", 0.5))
        calibrated_probabilities = predict_hybrid_meta_probabilities(
            hybrid_combiner,
            review_df=manipulation_df,
            text_probabilities=text_probabilities,
        )
        return calibrated_probabilities, hybrid_threshold

    combined_probabilities = _combine_probabilities(
        text_probabilities=text_probabilities,
        manipulation_scores=manipulation_df["rating_manipulation_score"].to_numpy(dtype=float),
    )
    return combined_probabilities, _combined_threshold(float(bundle["threshold"]))


def _apply_image_forensics_boost(probabilities: np.ndarray, review_df: pd.DataFrame) -> np.ndarray:
    """Conservatively raise risk when customer-photo evidence is suspicious."""
    if (
        "duplicate_image_score" not in review_df.columns
        and "image_temporal_cluster_score" not in review_df.columns
        and "image_text_mismatch_score" not in review_df.columns
    ):
        return probabilities
    duplicate_scores = (
        review_df["duplicate_image_score"].to_numpy(dtype=float)
        if "duplicate_image_score" in review_df.columns
        else np.zeros(len(review_df), dtype=float)
    )
    temporal_scores = (
        review_df["image_temporal_cluster_score"].to_numpy(dtype=float)
        if "image_temporal_cluster_score" in review_df.columns
        else np.zeros(len(review_df), dtype=float)
    )
    mismatch_scores = (
        review_df["image_text_mismatch_score"].to_numpy(dtype=float)
        if "image_text_mismatch_score" in review_df.columns
        else np.zeros(len(review_df), dtype=float)
    )
    stock_scores = (
        review_df["image_stock_marketing_score"].to_numpy(dtype=float)
        if "image_stock_marketing_score" in review_df.columns
        else np.zeros(len(review_df), dtype=float)
    )
    synthetic_scores = (
        review_df["image_synthetic_score"].to_numpy(dtype=float)
        if "image_synthetic_score" in review_df.columns
        else np.zeros(len(review_df), dtype=float)
    )
    ocr_scores = (
        review_df["image_ocr_score"].to_numpy(dtype=float)
        if "image_ocr_score" in review_df.columns
        else np.zeros(len(review_df), dtype=float)
    )
    photo_scores = np.clip(
        (
            0.30 * duplicate_scores
            + 0.24 * temporal_scores
            + 0.22 * mismatch_scores
            + 0.13 * stock_scores
            + 0.05 * synthetic_scores
            + 0.06 * ocr_scores
        ),
        0.0,
        1.0,
    )
    if not np.any(photo_scores > 0):
        return probabilities
    base_probabilities = np.asarray(probabilities, dtype=float)
    boosted = base_probabilities + 0.22 * np.clip(photo_scores, 0.0, 1.0) * (1.0 - base_probabilities)
    return np.clip(boosted, 0.0, 1.0)


def _risk_level(probability: float) -> str:
    """Convert a probability into a compact risk label."""
    if probability >= 0.85:
        return "high"
    if probability >= 0.55:
        return "medium"
    return "low"


def _infer_site_name(source_url: str) -> str:
    """Convert a URL into a simplified site label."""
    parsed = urlparse(source_url)
    if parsed.scheme == "file":
        return "local-file"
    hostname = (parsed.hostname or "unknown").lower()
    return hostname.replace("www.", "")
