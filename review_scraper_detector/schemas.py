"""Structured response schemas for review analysis results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class ReviewPrediction:
    """Normalized prediction record for one extracted review."""

    review_id: int
    author: str
    title: str
    rating: float
    date: str
    review_text: str
    source_url: str
    source_site: str
    text_suspicious_probability: float
    rating_manipulation_score: float
    author_risk_score: float
    slang_authenticity_score: float
    slang_manipulation_score: float
    slang_profile_label: str
    slang_domain_label: str
    slang_template_dup_count: int
    suspicious_probability: float
    is_suspicious: int
    triage_label: str
    requires_manual_review: int
    uncertainty_score: float
    ood_score: float
    decision_margin: float
    risk_level: str
    word_count: int
    character_count: int
    image_count: int
    duplicate_image_count: int
    duplicate_image_cluster_size: int
    duplicate_image_score: float
    duplicate_image_flag: int
    image_temporal_cluster_score: float
    image_temporal_cluster_flag: int
    image_temporal_cluster_size: int
    image_temporal_cluster_author_count: int
    image_temporal_cluster_window_hours: float
    image_temporal_cluster_fingerprint: str
    image_text_alignment_score: float
    image_text_mismatch_score: float
    image_text_mismatch_flag: int
    image_text_alignment_label: str
    image_text_alignment_model: str
    image_stock_marketing_score: float
    image_stock_marketing_flag: int
    image_stock_marketing_label: str
    image_synthetic_score: float
    image_synthetic_flag: int
    image_synthetic_label: str
    image_ocr_score: float
    image_ocr_flag: int
    image_ocr_text: str
    image_urls: list[str] = field(default_factory=list)
    duplicate_image_fingerprints: list[str] = field(default_factory=list)
    image_temporal_cluster_reasons: list[str] = field(default_factory=list)
    image_text_alignment_reasons: list[str] = field(default_factory=list)
    image_stock_marketing_reasons: list[str] = field(default_factory=list)
    image_synthetic_reasons: list[str] = field(default_factory=list)
    image_ocr_labels: list[str] = field(default_factory=list)
    image_ocr_reasons: list[str] = field(default_factory=list)
    detected_slang_terms: list[str] = field(default_factory=list)
    suspicion_categories: list[str] = field(default_factory=list)
    suspicion_reasons: list[str] = field(default_factory=list)
    manual_review_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert the dataclass into a JSON-ready dictionary."""
        return asdict(self)


@dataclass
class AnalysisSummary:
    """Compact aggregate metrics for one review analysis request."""

    source_url: str
    source_site: str
    source_type: str
    total_reviews: int
    suspicious_reviews: int
    clean_reviews: int
    confident_suspicious_reviews: int
    confident_clean_reviews: int
    manual_review_reviews: int
    suspicious_ratio: float
    manual_review_ratio: float
    automated_decision_ratio: float
    threshold: float
    average_probability: float
    highest_probability: float
    uncertainty_mean: float
    ood_alert_ratio: float
    risk_level: str
    suspicious_authors: int
    manipulation_score_mean: float
    rating_manipulation_risk: str
    slang_authenticity_mean: float
    slang_manipulation_mean: float
    page_slang_signal_ratio: float
    page_bilingual_slang_ratio: float
    page_organic_slang_ratio: float
    slang_domain_label: str
    slang_domain_confidence: float
    slang_template_cluster_ratio: float
    photo_reviews: int
    photo_review_ratio: float
    duplicate_photo_reviews: int
    duplicate_photo_review_ratio: float
    duplicate_photo_cluster_count: int
    largest_duplicate_photo_cluster: int
    photo_forensics_risk: str
    photo_temporal_cluster_reviews: int
    photo_temporal_cluster_ratio: float
    photo_temporal_cluster_count: int
    largest_photo_temporal_cluster: int
    photo_temporal_cluster_risk: str
    photo_temporal_cluster_window_hours: float
    image_alignment_reviews: int
    image_alignment_mismatch_reviews: int
    image_alignment_mismatch_ratio: float
    image_alignment_mean: float
    image_alignment_model_status: str
    image_alignment_model_name: str
    stock_marketing_photo_reviews: int
    stock_marketing_photo_ratio: float
    stock_marketing_score_mean: float
    synthetic_image_reviews: int
    synthetic_image_ratio: float
    synthetic_image_score_mean: float
    image_ocr_reviews: int
    image_ocr_flagged_reviews: int
    image_ocr_flagged_ratio: float
    image_ocr_score_mean: float
    image_ocr_status: str

    def to_dict(self) -> dict:
        """Convert the dataclass into a JSON-ready dictionary."""
        return asdict(self)


@dataclass
class AnalysisRequest:
    """Metadata describing the input source for the current analysis."""

    source_url: str
    source_site: str
    source_type: str
    model_family: str

    def to_dict(self) -> dict:
        """Convert the dataclass into a JSON-ready dictionary."""
        return asdict(self)
