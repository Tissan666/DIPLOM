"""Optional CLIP/ViT image-text alignment signals for customer review photos."""

from __future__ import annotations

import io
import os
from functools import lru_cache
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import requests

from .image_signals import normalize_image_urls
from .safe_urls import decode_data_image, is_safe_image_source
from .utils import normalize_whitespace

DEFAULT_CLIP_MODEL = "openai/clip-vit-base-patch32"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
STOCK_MARKETING_THRESHOLD = 0.58
SYNTHETIC_IMAGE_THRESHOLD = 0.66

CATEGORY_HINTS = {
    "footwear": [
        "boot",
        "boots",
        "shoe",
        "shoes",
        "sneaker",
        "sneakers",
        "sandal",
        "sandals",
        "обув",
        "ботин",
        "кроссов",
        "сандал",
        "туфл",
    ],
    "apparel": ["shirt", "dress", "jacket", "pants", "jeans", "hoodie", "одеж", "куртк", "плать", "рубаш", "джинс"],
    "electronics": ["phone", "laptop", "camera", "headphone", "charger", "электрон", "телефон", "ноутбук", "наушник"],
    "beauty": ["cream", "serum", "makeup", "shampoo", "beauty", "крем", "сыворот", "космет", "шампун"],
    "home goods": ["chair", "table", "lamp", "kitchen", "mug", "blanket", "home", "стул", "ламп", "кухн", "дом"],
    "grocery": ["coffee", "tea", "snack", "food", "protein", "кофе", "чай", "еда", "продукт"],
}

POSITIVE_CATEGORY_PROMPTS = {
    "footwear": "shoes, sneakers, sandals, or boots",
    "apparel": "clothing, apparel, or fabric details",
    "electronics": "an electronic device or accessory",
    "beauty": "a beauty, skincare, or cosmetic product",
    "home goods": "a home goods item or household product",
    "grocery": "food, grocery, or packaged consumable product",
}

MISMATCH_NEGATIVE_PROMPTS = [
    ("packaging_only", "a photo of only a shipping box, packaging, label, or parcel"),
    ("unrelated_product", "a photo of a different unrelated product"),
    ("blank_or_screenshot", "a blank image, screenshot, document, receipt, or text-only picture"),
]

STOCK_MARKETING_PROMPTS = [
    ("stock_catalog", "a polished ecommerce catalog product photo on a clean white background"),
    ("studio_render", "a professional studio render or 3D product mockup with perfect lighting"),
    ("marketing_banner", "a marketing banner advertisement with text overlays, discount badges, or graphic design"),
    ("listing_screenshot", "a screenshot from an online catalog or marketplace product listing"),
    ("packshot", "a studio packshot product image prepared for a commercial catalog"),
]

SYNTHETIC_IMAGE_PROMPTS = [
    ("ai_generated", "an AI-generated synthetic product image"),
    ("diffusion_artifact", "a diffusion-generated image with unnatural textures, warped details, or hallucinated text"),
    ("cgi_synthetic", "a computer-generated CGI product image rather than a real camera photo"),
    ("overprocessed_synthetic", "an overly smooth synthetic image with artificial lighting and unrealistic shadows"),
]

STOCK_MARKETING_LABELS = {label for label, _ in STOCK_MARKETING_PROMPTS}
SYNTHETIC_IMAGE_LABELS = {label for label, _ in SYNTHETIC_IMAGE_PROMPTS}
STOCK_URL_HINTS = {
    "ad",
    "advert",
    "banner",
    "catalog",
    "hero",
    "listing",
    "marketing",
    "mockup",
    "packshot",
    "promo",
    "product-image",
    "render",
    "studio",
    "white-bg",
    "white-background",
}
CUSTOMER_URL_HINTS = {"buyer", "cr-media", "customer", "photo-review", "review", "reviews", "ugc", "user"}
SYNTHETIC_URL_HINTS = {
    "ai-generated",
    "aigenerated",
    "automatic1111",
    "comfyui",
    "dall-e",
    "dalle",
    "diffusion",
    "generated",
    "midjourney",
    "sdxl",
    "stable-diffusion",
    "stablediffusion",
    "synthetic",
    "text-to-image",
}
SYNTHETIC_METADATA_HINTS = {
    "automatic1111",
    "comfyui",
    "dall-e",
    "dalle",
    "diffusion",
    "midjourney",
    "negative prompt",
    "positive prompt",
    "sampler",
    "sdxl",
    "stable diffusion",
    "stablediffusion",
    "steps:",
}


def build_image_text_alignment_signals(
    review_df: pd.DataFrame,
    source_url: str = "",
    source_site: str = "",
    max_reviews: int | None = None,
    max_images_per_review: int = 2,
    timeout_seconds: float = 5.0,
) -> tuple[pd.DataFrame, dict]:
    """Attach optional image-text mismatch indicators using CLIP when available."""
    frame = _with_default_columns(review_df.copy())
    frame = _apply_url_image_fallbacks(frame)
    if not _alignment_enabled():
        return frame, _summary(frame, model_status="disabled", source_site=source_site)

    image_rows = [
        (index, normalize_image_urls(row.get("image_urls", [])))
        for index, row in frame.iterrows()
        if normalize_image_urls(row.get("image_urls", []))
    ]
    if not image_rows:
        return frame, _summary(frame, model_status="no_images", source_site=source_site)

    if max_reviews is None:
        max_reviews = int(os.getenv("REVIEW_IMAGE_ALIGNMENT_MAX_REVIEWS", "16") or "16")
    image_rows = image_rows[: max(max_reviews, 0)]
    model_name = os.getenv("REVIEW_IMAGE_ALIGNMENT_MODEL", DEFAULT_CLIP_MODEL)

    try:
        model, processor, image_cls, torch_module, device = _load_clip_components(model_name)
    except ImportError:
        return frame, _summary(
            frame,
            model_status="not_configured",
            source_site=source_site,
            model_name=model_name,
        )
    except Exception:
        return frame, _summary(
            frame,
            model_status="model_unavailable",
            source_site=source_site,
            model_name=model_name,
        )

    evaluated_indices: set[int] = set()
    for row_index, urls in image_rows:
        row = frame.loc[row_index]
        category = _infer_product_category(row, source_url=source_url)
        prompts, prompt_labels, positive_count = _build_alignment_prompts(
            review_text=str(row.get("review_text", "")),
            category=category,
        )

        best_result: dict | None = None
        for image_url in urls[:max_images_per_review]:
            image = _load_image(image_url, image_cls=image_cls, timeout_seconds=timeout_seconds)
            if image is None:
                continue
            metadata_synthetic_score, metadata_synthetic_label, metadata_synthetic_reasons = _image_metadata_synthetic_signal(image)
            try:
                result = _score_image_text_alignment(
                    image=image,
                    prompts=prompts,
                    prompt_labels=prompt_labels,
                    positive_count=positive_count,
                    model=model,
                    processor=processor,
                    torch_module=torch_module,
                    device=device,
                )
            except Exception:
                continue
            result["image_url"] = image_url
            result["category"] = category
            if metadata_synthetic_score > result["synthetic_image_score"]:
                result["synthetic_image_score"] = metadata_synthetic_score
                result["top_synthetic_label"] = metadata_synthetic_label
                result["synthetic_image_reasons"] = metadata_synthetic_reasons
            if best_result is None or _image_risk_score(result) > _image_risk_score(best_result):
                best_result = result

        if best_result is None:
            continue

        evaluated_indices.add(int(row_index))
        frame.at[row_index, "image_text_alignment_score"] = best_result["alignment_score"]
        frame.at[row_index, "image_text_mismatch_score"] = best_result["mismatch_score"]
        frame.at[row_index, "image_text_mismatch_flag"] = int(best_result["mismatch_score"] >= 0.58)
        frame.at[row_index, "image_text_alignment_label"] = _alignment_label(best_result["mismatch_score"])
        frame.at[row_index, "image_text_alignment_model"] = model_name
        frame.at[row_index, "image_text_top_negative_label"] = best_result["top_negative_label"]
        frame.at[row_index, "image_text_alignment_reasons"] = _alignment_reasons(best_result)

        current_stock_score = float(frame.at[row_index, "image_stock_marketing_score"] or 0.0)
        if best_result["stock_marketing_score"] >= current_stock_score:
            frame.at[row_index, "image_stock_marketing_score"] = best_result["stock_marketing_score"]
            frame.at[row_index, "image_stock_marketing_flag"] = int(
                best_result["stock_marketing_score"] >= STOCK_MARKETING_THRESHOLD
            )
            frame.at[row_index, "image_stock_marketing_label"] = _stock_marketing_label(
                best_result["stock_marketing_score"],
                best_result["top_stock_label"],
            )
            frame.at[row_index, "image_stock_marketing_reasons"] = _stock_marketing_reasons(best_result)

        current_synthetic_score = float(frame.at[row_index, "image_synthetic_score"] or 0.0)
        if best_result["synthetic_image_score"] >= current_synthetic_score:
            frame.at[row_index, "image_synthetic_score"] = best_result["synthetic_image_score"]
            frame.at[row_index, "image_synthetic_flag"] = int(
                best_result["synthetic_image_score"] >= SYNTHETIC_IMAGE_THRESHOLD
            )
            frame.at[row_index, "image_synthetic_label"] = _synthetic_image_label(
                best_result["synthetic_image_score"],
                best_result["top_synthetic_label"],
            )
            frame.at[row_index, "image_synthetic_reasons"] = _synthetic_image_reasons(best_result)

    return frame, _summary(
        frame,
        model_status="ready" if evaluated_indices else "image_fetch_failed",
        source_site=source_site,
        model_name=model_name,
        evaluated_indices=evaluated_indices,
    )


def _with_default_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.reset_index(drop=True)
    if "image_urls" not in frame.columns:
        frame["image_urls"] = [[] for _ in range(len(frame))]
    frame["image_text_alignment_score"] = 0.0
    frame["image_text_mismatch_score"] = 0.0
    frame["image_text_mismatch_flag"] = 0
    frame["image_text_alignment_label"] = "not_evaluated"
    frame["image_text_alignment_model"] = ""
    frame["image_text_top_negative_label"] = ""
    frame["image_text_alignment_reasons"] = [[] for _ in range(len(frame))]
    frame["image_stock_marketing_score"] = 0.0
    frame["image_stock_marketing_flag"] = 0
    frame["image_stock_marketing_label"] = "not_evaluated"
    frame["image_stock_marketing_reasons"] = [[] for _ in range(len(frame))]
    frame["image_synthetic_score"] = 0.0
    frame["image_synthetic_flag"] = 0
    frame["image_synthetic_label"] = "not_evaluated"
    frame["image_synthetic_reasons"] = [[] for _ in range(len(frame))]
    return frame


def _apply_url_image_fallbacks(frame: pd.DataFrame) -> pd.DataFrame:
    """Add conservative URL/path signals before optional vision inference runs."""
    for row_index, row in frame.iterrows():
        urls = normalize_image_urls(row.get("image_urls", []))
        score, label, reasons = _url_stock_marketing_signal(urls)
        if score > 0:
            frame.at[row_index, "image_stock_marketing_score"] = score
            frame.at[row_index, "image_stock_marketing_flag"] = int(score >= STOCK_MARKETING_THRESHOLD)
            frame.at[row_index, "image_stock_marketing_label"] = label
            frame.at[row_index, "image_stock_marketing_reasons"] = reasons

        synthetic_score, synthetic_label, synthetic_reasons = _url_synthetic_image_signal(urls)
        if synthetic_score > 0:
            frame.at[row_index, "image_synthetic_score"] = synthetic_score
            frame.at[row_index, "image_synthetic_flag"] = int(synthetic_score >= SYNTHETIC_IMAGE_THRESHOLD)
            frame.at[row_index, "image_synthetic_label"] = synthetic_label
            frame.at[row_index, "image_synthetic_reasons"] = synthetic_reasons
    return frame


def _alignment_enabled() -> bool:
    raw_value = os.getenv("REVIEW_IMAGE_ALIGNMENT_ENABLED", "1").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


@lru_cache(maxsize=1)
def image_alignment_capability_status() -> dict:
    """Return lightweight CLIP/ViT readiness diagnostics for health checks."""
    model_name = os.getenv("REVIEW_IMAGE_ALIGNMENT_MODEL", DEFAULT_CLIP_MODEL)
    local_only = os.getenv("REVIEW_IMAGE_ALIGNMENT_LOCAL_ONLY", "0").strip().lower() in {"1", "true", "yes"}
    load_model = os.getenv("REVIEW_IMAGE_ALIGNMENT_HEALTH_LOAD", "0").strip().lower() in {"1", "true", "yes"}

    if not _alignment_enabled():
        return {
            "enabled": False,
            "available": False,
            "status": "disabled",
            "model_name": model_name,
            "local_only": local_only,
            "model_load_checked": False,
        }

    try:
        from PIL import Image  # noqa: F401
        from transformers import CLIPModel, CLIPProcessor  # noqa: F401
        import torch
    except ImportError as exc:
        return {
            "enabled": True,
            "available": False,
            "status": "not_configured",
            "model_name": model_name,
            "local_only": local_only,
            "model_load_checked": False,
            "detail": str(exc),
        }

    device = "cuda" if torch.cuda.is_available() and os.getenv("REVIEW_IMAGE_ALIGNMENT_DEVICE", "auto") != "cpu" else "cpu"
    if not load_model:
        return {
            "enabled": True,
            "available": True,
            "status": "dependencies_ready",
            "model_name": model_name,
            "local_only": local_only,
            "model_load_checked": False,
            "device": device,
        }

    try:
        _model, _processor, _image_cls, _torch_module, loaded_device = _load_clip_components(model_name)
    except Exception as exc:
        return {
            "enabled": True,
            "available": False,
            "status": "model_unavailable",
            "model_name": model_name,
            "local_only": local_only,
            "model_load_checked": True,
            "device": device,
            "detail": str(exc),
        }

    return {
        "enabled": True,
        "available": True,
        "status": "ready",
        "model_name": model_name,
        "local_only": local_only,
        "model_load_checked": True,
        "device": loaded_device,
    }


@lru_cache(maxsize=2)
def _load_clip_components(model_name: str):
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor
    import torch

    local_only = os.getenv("REVIEW_IMAGE_ALIGNMENT_LOCAL_ONLY", "0").strip().lower() in {"1", "true", "yes"}
    model = CLIPModel.from_pretrained(model_name, local_files_only=local_only)
    processor = CLIPProcessor.from_pretrained(model_name, local_files_only=local_only)
    device = "cuda" if torch.cuda.is_available() and os.getenv("REVIEW_IMAGE_ALIGNMENT_DEVICE", "auto") != "cpu" else "cpu"
    model.to(device)
    model.eval()
    return model, processor, Image, torch, device


def _load_image(url: str, image_cls: object, timeout_seconds: float):
    try:
        raw_url = url.strip()
        if not is_safe_image_source(raw_url):
            return None
        parsed = urlparse(raw_url)
        if raw_url.startswith("data:image"):
            image_bytes = decode_data_image(raw_url, max_bytes=MAX_IMAGE_BYTES)
            if image_bytes is None:
                return None
        elif parsed.scheme in {"http", "https"}:
            response = requests.get(raw_url, timeout=timeout_seconds, headers={"User-Agent": "review-image-alignment/1.0"})
            response.raise_for_status()
            image_bytes = response.content[:MAX_IMAGE_BYTES]
        else:
            return None
        image = image_cls.open(io.BytesIO(image_bytes))
        converted = image.convert("RGB")
        converted.info.update(getattr(image, "info", {}) or {})
        return converted
    except Exception:
        return None


def _infer_product_category(row: pd.Series, source_url: str) -> str:
    for field in ["product_category", "category", "item_category", "product_type", "slang_domain_label"]:
        value = normalize_whitespace(str(row.get(field, "") or ""))
        if value and value != "general":
            return value.lower()

    haystack = " ".join(
        [
            source_url,
            str(row.get("source_url", "")),
            str(row.get("source_site", "")),
            str(row.get("title", "")),
            str(row.get("review_text", "")),
        ]
    ).lower()
    for category, hints in CATEGORY_HINTS.items():
        if any(hint in haystack for hint in hints):
            return category
    return "general product"


def _build_alignment_prompts(review_text: str, category: str) -> tuple[list[str], list[str], int]:
    category_phrase = POSITIVE_CATEGORY_PROMPTS.get(category, category.replace("-", " "))
    review_snippet = _truncate_text(review_text, max_chars=220)
    positive_prompts = [
        f"a real customer photo matching this product review: {review_snippet}",
        f"a real customer photo of {category_phrase}",
        f"a product photo that is visually relevant to {category_phrase}",
        "a casual user-taken customer snapshot with natural lighting and an imperfect real environment",
        "a customer photo showing the product in use, handled, worn, unpacked, or placed in a real home",
    ]
    negative_prompts = [prompt for _, prompt in MISMATCH_NEGATIVE_PROMPTS + STOCK_MARKETING_PROMPTS + SYNTHETIC_IMAGE_PROMPTS]
    labels = [
        "review_match",
        "category_match",
        "product_relevance",
        "casual_customer_snapshot",
        "product_in_use",
    ] + [label for label, _ in MISMATCH_NEGATIVE_PROMPTS + STOCK_MARKETING_PROMPTS + SYNTHETIC_IMAGE_PROMPTS]
    return positive_prompts + negative_prompts, labels, len(positive_prompts)


def _score_image_text_alignment(
    image: object,
    prompts: list[str],
    prompt_labels: list[str],
    positive_count: int,
    model: object,
    processor: object,
    torch_module: object,
    device: str,
) -> dict:
    inputs = processor(text=prompts, images=image, return_tensors="pt", padding=True, truncation=True)
    inputs = {key: value.to(device) if hasattr(value, "to") else value for key, value in inputs.items()}
    with torch_module.no_grad():
        logits = model(**inputs).logits_per_image[0]
        probabilities = logits.softmax(dim=0).detach().cpu().numpy()

    positive_mass = float(np.sum(probabilities[:positive_count]))
    probability_by_label = {
        label: float(probability)
        for label, probability in zip(prompt_labels, probabilities)
    }
    mismatch_labels = [label for label, _ in MISMATCH_NEGATIVE_PROMPTS + STOCK_MARKETING_PROMPTS]
    mismatch_scores = [probability_by_label.get(label, 0.0) for label in mismatch_labels]
    top_negative_label = max(mismatch_labels, key=lambda label: probability_by_label.get(label, 0.0))
    top_negative_score = float(probability_by_label.get(top_negative_label, 0.0))
    negative_mass = float(np.sum(mismatch_scores))

    stock_scores = [probability_by_label.get(label, 0.0) for label in STOCK_MARKETING_LABELS]
    stock_mass = float(np.sum(stock_scores))
    top_stock_label = max(STOCK_MARKETING_LABELS, key=lambda label: probability_by_label.get(label, 0.0))
    top_stock_score = float(probability_by_label.get(top_stock_label, 0.0))
    synthetic_scores = [probability_by_label.get(label, 0.0) for label in SYNTHETIC_IMAGE_LABELS]
    synthetic_mass = float(np.sum(synthetic_scores))
    top_synthetic_label = max(SYNTHETIC_IMAGE_LABELS, key=lambda label: probability_by_label.get(label, 0.0))
    top_synthetic_score = float(probability_by_label.get(top_synthetic_label, 0.0))
    customer_snapshot_score = max(
        probability_by_label.get("casual_customer_snapshot", 0.0),
        probability_by_label.get("product_in_use", 0.0),
    )

    mismatch_score = float(np.clip(0.72 * negative_mass + 0.28 * max(0.0, top_negative_score - positive_mass), 0.0, 1.0))
    if positive_mass < 0.34 and negative_mass >= 0.50:
        mismatch_score = max(mismatch_score, 0.62)

    stock_marketing_score = float(
        np.clip(
            0.64 * stock_mass + 0.36 * max(0.0, top_stock_score - customer_snapshot_score),
            0.0,
            1.0,
        )
    )
    if top_stock_score >= 0.24 and stock_mass >= 0.38:
        stock_marketing_score = max(stock_marketing_score, STOCK_MARKETING_THRESHOLD)

    synthetic_image_score = float(
        np.clip(
            0.58 * synthetic_mass + 0.42 * max(0.0, top_synthetic_score - max(customer_snapshot_score, positive_mass * 0.4)),
            0.0,
            1.0,
        )
    )
    if top_synthetic_score >= 0.26 and synthetic_mass >= 0.42:
        synthetic_image_score = max(synthetic_image_score, SYNTHETIC_IMAGE_THRESHOLD)

    return {
        "alignment_score": positive_mass,
        "mismatch_score": mismatch_score,
        "top_negative_label": top_negative_label,
        "top_negative_score": top_negative_score,
        "negative_mass": negative_mass,
        "stock_marketing_score": stock_marketing_score,
        "stock_marketing_mass": stock_mass,
        "top_stock_label": top_stock_label,
        "top_stock_score": top_stock_score,
        "synthetic_image_score": synthetic_image_score,
        "synthetic_image_mass": synthetic_mass,
        "top_synthetic_label": top_synthetic_label,
        "top_synthetic_score": top_synthetic_score,
        "synthetic_image_reasons": [],
    }


def _alignment_label(mismatch_score: float) -> str:
    if mismatch_score >= 0.72:
        return "strong_mismatch"
    if mismatch_score >= 0.58:
        return "mismatch"
    if mismatch_score >= 0.38:
        return "weak_match"
    return "aligned"


def _alignment_reasons(result: dict) -> list[str]:
    mismatch_score = float(result.get("mismatch_score", 0.0) or 0.0)
    if mismatch_score < 0.58:
        return []

    category = str(result.get("category", "product") or "product")
    negative_label = str(result.get("top_negative_label", "unrelated_product") or "unrelated_product")
    label_description = {
        "packaging_only": "packaging, box, or label rather than the reviewed product",
        "unrelated_product": "a different or unrelated product",
        "blank_or_screenshot": "a blank image, screenshot, receipt, or text-only artifact",
        "stock_catalog": "a polished catalog product photo rather than a customer snapshot",
        "studio_render": "a studio render or mockup rather than a real customer snapshot",
        "marketing_banner": "a marketing banner or advertisement rather than a customer snapshot",
        "listing_screenshot": "a catalog/listing screenshot rather than a customer snapshot",
        "packshot": "a studio packshot rather than a customer snapshot",
    }.get(negative_label, "visual evidence that does not match the review")
    return [
        f"The customer photo looks closer to {label_description} than to the review text or inferred {category} category."
    ]


def _stock_marketing_label(score: float, top_stock_label: str) -> str:
    if score < 0.34:
        return "customer_like"
    if score < STOCK_MARKETING_THRESHOLD:
        return "possible_stock"
    return top_stock_label or "stock_marketing"


def _stock_marketing_reasons(result: dict) -> list[str]:
    stock_score = float(result.get("stock_marketing_score", 0.0) or 0.0)
    if stock_score < STOCK_MARKETING_THRESHOLD:
        return []

    top_label = str(result.get("top_stock_label", "stock_marketing") or "stock_marketing")
    label_description = {
        "stock_catalog": "a polished ecommerce catalog image",
        "studio_render": "a studio render or 3D mockup",
        "marketing_banner": "a marketing banner or promotional creative",
        "listing_screenshot": "a screenshot from a catalog or marketplace listing",
        "packshot": "a studio packshot prepared for product marketing",
    }.get(top_label, "a stock or marketing asset")
    return [f"The customer image looks like {label_description}, not a user-taken product photo."]


def _synthetic_image_label(score: float, top_synthetic_label: str) -> str:
    if score < 0.38:
        return "natural_photo_like"
    if score < SYNTHETIC_IMAGE_THRESHOLD:
        return "weak_synthetic_hint"
    return top_synthetic_label or "synthetic_image_hint"


def _synthetic_image_reasons(result: dict) -> list[str]:
    if result.get("synthetic_image_reasons"):
        return list(result["synthetic_image_reasons"])

    synthetic_score = float(result.get("synthetic_image_score", 0.0) or 0.0)
    if synthetic_score < SYNTHETIC_IMAGE_THRESHOLD:
        return []

    top_label = str(result.get("top_synthetic_label", "synthetic_image_hint") or "synthetic_image_hint")
    label_description = {
        "ai_generated": "AI-generated visual style",
        "diffusion_artifact": "diffusion-like artifacts, warped details, or hallucinated text",
        "cgi_synthetic": "CGI/synthetic rendering cues",
        "overprocessed_synthetic": "overly smooth synthetic lighting or unrealistic shadows",
    }.get(top_label, "synthetic-image cues")
    return [
        f"Weak auxiliary signal: the image shows {label_description}. Treat this as supporting evidence, not proof."
    ]


def _url_stock_marketing_signal(urls: list[str]) -> tuple[float, str, list[str]]:
    best_score = 0.0
    best_label = "not_evaluated"
    for url in urls:
        normalized_url = url.lower().replace("_", "-")
        customer_hits = [hint for hint in CUSTOMER_URL_HINTS if hint in normalized_url]
        stock_hits = [hint for hint in STOCK_URL_HINTS if hint in normalized_url]
        if not stock_hits:
            continue

        strong_hits = {"banner", "catalog", "hero", "marketing", "mockup", "packshot", "promo", "render", "studio"}
        score = 0.62 if any(hit in strong_hits for hit in stock_hits) else 0.46
        if customer_hits:
            score -= 0.22
        score = float(np.clip(score, 0.0, 1.0))
        if score > best_score:
            best_score = score
            best_label = f"url_hint:{stock_hits[0]}"

    if best_score <= 0:
        return 0.0, "not_evaluated", []
    if best_score >= STOCK_MARKETING_THRESHOLD:
        return best_score, best_label, ["The image URL/path contains stock, catalog, render, promo, or marketing hints."]
    return best_score, "possible_stock_url_hint", []


def _url_synthetic_image_signal(urls: list[str]) -> tuple[float, str, list[str]]:
    best_score = 0.0
    best_label = "not_evaluated"
    for url in urls:
        normalized_url = url.lower().replace("_", "-")
        customer_hits = [hint for hint in CUSTOMER_URL_HINTS if hint in normalized_url]
        synthetic_hits = [hint for hint in SYNTHETIC_URL_HINTS if hint in normalized_url]
        if not synthetic_hits:
            continue

        strong_hits = {
            "ai-generated",
            "aigenerated",
            "automatic1111",
            "comfyui",
            "dall-e",
            "dalle",
            "midjourney",
            "sdxl",
            "stable-diffusion",
            "stablediffusion",
            "synthetic",
            "text-to-image",
        }
        has_strong_hint = any(hit in strong_hits for hit in synthetic_hits)
        score = 0.74 if has_strong_hint else 0.48
        if customer_hits:
            score -= 0.08 if has_strong_hint else 0.24
        score = float(np.clip(score, 0.0, 1.0))
        if score > best_score:
            best_score = score
            best_label = f"url_hint:{synthetic_hits[0]}"

    if best_score <= 0:
        return 0.0, "not_evaluated", []
    if best_score >= SYNTHETIC_IMAGE_THRESHOLD:
        return best_score, best_label, [
            "Weak auxiliary signal: the image URL/path contains AI-generated or synthetic-image hints."
        ]
    return best_score, "weak_synthetic_url_hint", []


def _image_metadata_synthetic_signal(image: object) -> tuple[float, str, list[str]]:
    info = getattr(image, "info", {}) or {}
    info_text = " ".join(f"{key}={str(value)[:600]}" for key, value in info.items()).lower()
    hits = [hint for hint in SYNTHETIC_METADATA_HINTS if hint in info_text]
    if not hits:
        return 0.0, "not_evaluated", []
    return 0.86, f"metadata_hint:{hits[0]}", [
        "Weak auxiliary signal: image metadata contains AI-generation workflow or prompt hints."
    ]


def _image_risk_score(result: dict) -> float:
    return max(
        float(result.get("mismatch_score", 0.0) or 0.0),
        float(result.get("stock_marketing_score", 0.0) or 0.0),
        float(result.get("synthetic_image_score", 0.0) or 0.0) * 0.72,
    )


def _summary(
    frame: pd.DataFrame,
    model_status: str,
    source_site: str,
    model_name: str = "",
    evaluated_indices: set[int] | None = None,
) -> dict:
    evaluated_indices = evaluated_indices or set()
    evaluated_reviews = len(evaluated_indices)
    mismatch_reviews = int(frame["image_text_mismatch_flag"].sum()) if "image_text_mismatch_flag" in frame.columns else 0
    stock_marketing_reviews = (
        int(frame["image_stock_marketing_flag"].sum())
        if "image_stock_marketing_flag" in frame.columns
        else 0
    )
    synthetic_image_reviews = (
        int(frame["image_synthetic_flag"].sum())
        if "image_synthetic_flag" in frame.columns
        else 0
    )
    photo_reviews = sum(1 for value in frame.get("image_urls", []) if normalize_image_urls(value))
    alignment_values = (
        frame.loc[list(evaluated_indices), "image_text_alignment_score"].to_numpy(dtype=float)
        if evaluated_indices
        else np.array([], dtype=float)
    )
    stock_marketing_scores = (
        frame.loc[
            [index for index, value in enumerate(frame.get("image_urls", [])) if normalize_image_urls(value)],
            "image_stock_marketing_score",
        ].to_numpy(dtype=float)
        if photo_reviews
        else np.array([], dtype=float)
    )
    synthetic_scores = (
        frame.loc[
            [index for index, value in enumerate(frame.get("image_urls", [])) if normalize_image_urls(value)],
            "image_synthetic_score",
        ].to_numpy(dtype=float)
        if photo_reviews
        else np.array([], dtype=float)
    )
    return {
        "image_alignment_model_status": model_status,
        "image_alignment_model_name": model_name,
        "image_alignment_source_site": source_site,
        "image_alignment_reviews": int(evaluated_reviews),
        "image_alignment_mismatch_reviews": int(mismatch_reviews),
        "image_alignment_mismatch_ratio": float(mismatch_reviews / evaluated_reviews) if evaluated_reviews else 0.0,
        "image_alignment_mean": float(np.mean(alignment_values)) if len(alignment_values) else 0.0,
        "stock_marketing_photo_reviews": int(stock_marketing_reviews),
        "stock_marketing_photo_ratio": float(stock_marketing_reviews / photo_reviews) if photo_reviews else 0.0,
        "stock_marketing_score_mean": float(np.mean(stock_marketing_scores)) if len(stock_marketing_scores) else 0.0,
        "synthetic_image_reviews": int(synthetic_image_reviews),
        "synthetic_image_ratio": float(synthetic_image_reviews / photo_reviews) if photo_reviews else 0.0,
        "synthetic_image_score_mean": float(np.mean(synthetic_scores)) if len(synthetic_scores) else 0.0,
    }


def _truncate_text(value: str, max_chars: int) -> str:
    normalized = normalize_whitespace(value)
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[:max_chars].rsplit(' ', 1)[0]}..."
