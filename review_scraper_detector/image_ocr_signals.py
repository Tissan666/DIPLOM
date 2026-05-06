"""Optional OCR signals for customer review photos."""

from __future__ import annotations

import io
import os
import re
import shutil
from collections import Counter
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import requests

from .image_signals import normalize_image_urls
from .safe_urls import decode_data_image, is_safe_image_source
from .utils import normalize_whitespace

MAX_IMAGE_BYTES = 8 * 1024 * 1024
OCR_TEXT_LIMIT = 700
OCR_FLAG_THRESHOLD = 0.46
TESSERACT_COMMAND_ENV_NAMES = ("TESSERACT_CMD", "TESSERACT_EXE_PATH", "PYTESSERACT_TESSERACT_CMD")
COMMON_WINDOWS_TESSERACT_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)

PROMO_PATTERNS = {
    "sale_discount": [
        r"\bsale\b",
        r"\bdiscount\b",
        r"\bcoupon\b",
        r"\bpromo\b",
        r"\b\d{1,2}\s?%\s?off\b",
        r"\bfree shipping\b",
        r"\bclearance\b",
        r"\bскидк",
        r"\bакци",
        r"\bраспродаж",
        r"\bпромо",
    ],
    "hype_claim": [
        r"\bbest product\b",
        r"\bbest seller\b",
        r"\btop choice\b",
        r"\bmust buy\b",
        r"\b#\s?1\b",
        r"\bnumber one\b",
        r"\bхит продаж\b",
        r"\bлучший товар\b",
        r"\bтоп товар\b",
    ],
    "watermark_marker": [
        r"\bwatermark\b",
        r"\bofficial store\b",
        r"\bsponsored\b",
        r"\badvertisement\b",
        r"\bреклама\b",
        r"\bофициальный магазин\b",
    ],
    "contact_or_store": [
        r"\bwhatsapp\b",
        r"\btelegram\b",
        r"\binstagram\b",
        r"\btiktok\b",
        r"\bvk\b",
        r"@[a-z0-9_.-]{3,}",
        r"\b[a-z0-9-]+\.(com|ru|net|shop|store)\b",
    ],
}

MARKETPLACE_ALIASES = {
    "amazon": ["amazon", "amzn"],
    "aliexpress": ["aliexpress", "ali express"],
    "temu": ["temu"],
    "shein": ["shein"],
    "ozon": ["ozon", "озон"],
    "wildberries": ["wildberries", "wb", "вб", "вайлдберриз"],
    "walmart": ["walmart"],
    "ebay": ["ebay"],
    "etsy": ["etsy"],
    "yandex_market": ["yandex market", "яндекс маркет", "market.yandex"],
    "lamoda": ["lamoda", "ламода"],
    "kaspi": ["kaspi", "каспи"],
    "flipkart": ["flipkart"],
    "allegro": ["allegro"],
}


def build_image_ocr_signals(
    review_df: pd.DataFrame,
    source_site: str = "",
    max_reviews: int | None = None,
    max_images_per_review: int = 2,
    timeout_seconds: float = 5.0,
) -> tuple[pd.DataFrame, dict]:
    """Attach OCR-based promo/watermark/marketplace text signals when available."""
    frame = _with_default_columns(review_df.copy())
    if not _ocr_enabled():
        return frame, _summary(frame, model_status="disabled")

    image_rows = [
        (index, normalize_image_urls(row.get("image_urls", [])))
        for index, row in frame.iterrows()
        if normalize_image_urls(row.get("image_urls", []))
    ]
    if not image_rows:
        return frame, _summary(frame, model_status="no_images")

    if max_reviews is None:
        max_reviews = int(os.getenv("REVIEW_IMAGE_OCR_MAX_REVIEWS", "20") or "20")
    image_rows = image_rows[: max(max_reviews, 0)]

    try:
        from PIL import Image, ImageOps
        import pytesseract
    except ImportError:
        return frame, _summary(frame, model_status="not_configured")

    _configure_tesseract_command(pytesseract)

    evaluated_indices: set[int] = set()
    engine_failed = False
    for row_index, urls in image_rows:
        best_signal: dict | None = None
        for image_url in urls[:max_images_per_review]:
            image = _load_image(image_url, image_cls=Image, timeout_seconds=timeout_seconds)
            if image is None:
                continue
            try:
                ocr_text = _extract_text(image, image_ops=ImageOps, pytesseract_module=pytesseract)
            except Exception:
                engine_failed = True
                continue

            signal = _score_ocr_text(ocr_text, source_site=source_site)
            signal["image_url"] = image_url
            if best_signal is None or signal["image_ocr_score"] > best_signal["image_ocr_score"]:
                best_signal = signal

        if best_signal is None:
            continue

        evaluated_indices.add(int(row_index))
        frame.at[row_index, "image_ocr_text"] = best_signal["image_ocr_text"]
        frame.at[row_index, "image_ocr_score"] = best_signal["image_ocr_score"]
        frame.at[row_index, "image_ocr_flag"] = int(best_signal["image_ocr_score"] >= OCR_FLAG_THRESHOLD)
        frame.at[row_index, "image_ocr_labels"] = best_signal["image_ocr_labels"]
        frame.at[row_index, "image_ocr_reasons"] = best_signal["image_ocr_reasons"]

    return frame, _summary(
        frame,
        model_status="ready" if evaluated_indices else "engine_unavailable" if engine_failed else "image_fetch_failed",
        evaluated_indices=evaluated_indices,
    )


def _with_default_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.reset_index(drop=True)
    if "image_urls" not in frame.columns:
        frame["image_urls"] = [[] for _ in range(len(frame))]
    frame["image_ocr_text"] = ""
    frame["image_ocr_score"] = 0.0
    frame["image_ocr_flag"] = 0
    frame["image_ocr_labels"] = [[] for _ in range(len(frame))]
    frame["image_ocr_reasons"] = [[] for _ in range(len(frame))]
    return frame


def _ocr_enabled() -> bool:
    raw_value = os.getenv("REVIEW_IMAGE_OCR_ENABLED", "1").strip().lower()
    return raw_value not in {"0", "false", "no", "off"}


@lru_cache(maxsize=1)
def ocr_capability_status() -> dict:
    """Return lightweight OCR readiness diagnostics for health checks."""
    languages = os.getenv("REVIEW_IMAGE_OCR_LANG", "eng+rus")
    if not _ocr_enabled():
        return {
            "enabled": False,
            "available": False,
            "status": "disabled",
            "engine": "tesseract",
            "languages": languages,
        }

    try:
        from PIL import Image, ImageOps  # noqa: F401
        import pytesseract
    except ImportError as exc:
        return {
            "enabled": True,
            "available": False,
            "status": "not_configured",
            "engine": "tesseract",
            "languages": languages,
            "detail": str(exc),
        }

    tesseract_command = _configure_tesseract_command(pytesseract)
    try:
        version = str(pytesseract.get_tesseract_version())
    except Exception as exc:
        return {
            "enabled": True,
            "available": False,
            "status": "engine_unavailable",
            "engine": "tesseract",
            "languages": languages,
            "tesseract_cmd": tesseract_command or None,
            "detail": str(exc),
        }

    return {
        "enabled": True,
        "available": True,
        "status": "ready",
        "engine": "tesseract",
        "version": version,
        "languages": languages,
        "tesseract_cmd": tesseract_command or "tesseract",
    }


def _configure_tesseract_command(pytesseract_module: object) -> str:
    """Point pytesseract at an explicit tesseract.exe when PATH is not configured."""
    tesseract_command = _resolve_tesseract_command()
    if not tesseract_command:
        return ""

    pytesseract_backend = getattr(pytesseract_module, "pytesseract", pytesseract_module)
    setattr(pytesseract_backend, "tesseract_cmd", tesseract_command)
    return tesseract_command


def _resolve_tesseract_command() -> str:
    for env_name in TESSERACT_COMMAND_ENV_NAMES:
        raw_value = os.getenv(env_name, "").strip().strip('"').strip("'")
        if not raw_value:
            continue
        resolved = shutil.which(raw_value)
        if resolved:
            return resolved
        candidate_path = Path(raw_value)
        if candidate_path.is_file():
            return str(candidate_path)

    resolved = shutil.which("tesseract")
    if resolved:
        return resolved

    for common_path in COMMON_WINDOWS_TESSERACT_PATHS:
        candidate_path = Path(common_path)
        if candidate_path.is_file():
            return str(candidate_path)
    return ""


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
            response = requests.get(raw_url, timeout=timeout_seconds, headers={"User-Agent": "review-image-ocr/1.0"})
            response.raise_for_status()
            image_bytes = response.content[:MAX_IMAGE_BYTES]
        else:
            return None
        return image_cls.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None


def _extract_text(image: object, image_ops: object, pytesseract_module: object) -> str:
    processed = image_ops.grayscale(image)
    width, height = processed.size
    if max(width, height) < 1400:
        scale = min(2.5, 1400 / max(width, height))
        new_size = (int(width * scale), int(height * scale))
        resampling = getattr(getattr(type(image), "Resampling", object), "LANCZOS", 1)
        processed = processed.resize(new_size, resampling)

    languages = os.getenv("REVIEW_IMAGE_OCR_LANG", "eng+rus")
    config = os.getenv("REVIEW_IMAGE_OCR_CONFIG", "--psm 6")
    try:
        text = pytesseract_module.image_to_string(processed, lang=languages, config=config)
    except Exception:
        text = pytesseract_module.image_to_string(processed, lang="eng", config=config)
    return normalize_whitespace(text)


def _score_ocr_text(text: str, source_site: str) -> dict:
    normalized_text = normalize_whitespace(text)
    lower_text = normalized_text.lower()
    labels: list[str] = []
    reasons: list[str] = []

    if not lower_text:
        return {
            "image_ocr_text": "",
            "image_ocr_score": 0.0,
            "image_ocr_labels": [],
            "image_ocr_reasons": [],
        }

    for label, patterns in PROMO_PATTERNS.items():
        if any(re.search(pattern, lower_text, flags=re.IGNORECASE) for pattern in patterns):
            labels.append(label)

    marketplace_hits = _marketplace_hits(lower_text)
    source_marketplace = _source_marketplace(source_site)
    foreign_marketplaces = [marketplace for marketplace in marketplace_hits if marketplace != source_marketplace]
    if marketplace_hits:
        labels.append("marketplace_text")
    if foreign_marketplaces:
        labels.append("foreign_marketplace_watermark")

    score = 0.0
    label_counts = Counter(labels)
    score += 0.18 * min(label_counts.get("sale_discount", 0), 1)
    score += 0.18 * min(label_counts.get("hype_claim", 0), 1)
    score += 0.20 * min(label_counts.get("watermark_marker", 0), 1)
    score += 0.18 * min(label_counts.get("contact_or_store", 0), 1)
    score += 0.16 * min(label_counts.get("marketplace_text", 0), 1)
    score += 0.32 * min(label_counts.get("foreign_marketplace_watermark", 0), 1)
    if len(normalized_text) > 80 and labels:
        score += 0.08
    score = float(np.clip(score, 0.0, 1.0))

    if "sale_discount" in labels:
        reasons.append("OCR found sale, discount, coupon, promo, or similar marketing text on the photo.")
    if "hype_claim" in labels:
        reasons.append("OCR found hype claims such as best product, best seller, top choice, or must buy.")
    if "watermark_marker" in labels:
        reasons.append("OCR found ad, sponsored, official-store, or watermark-style text on the photo.")
    if "contact_or_store" in labels:
        reasons.append("OCR found contact handles, social links, or store/domain text on the photo.")
    if foreign_marketplaces:
        reasons.append(
            f"OCR found marketplace text that does not match the source site: {', '.join(foreign_marketplaces[:3])}."
        )
    elif marketplace_hits:
        reasons.append(f"OCR found marketplace branding text on the photo: {', '.join(marketplace_hits[:3])}.")

    return {
        "image_ocr_text": normalized_text[:OCR_TEXT_LIMIT],
        "image_ocr_score": score,
        "image_ocr_labels": sorted(set(labels)),
        "image_ocr_reasons": reasons,
    }


def _marketplace_hits(lower_text: str) -> list[str]:
    hits = []
    for marketplace, aliases in MARKETPLACE_ALIASES.items():
        if any(alias in lower_text for alias in aliases):
            hits.append(marketplace)
    return hits


def _source_marketplace(source_site: str) -> str:
    normalized = (source_site or "").lower()
    for marketplace, aliases in MARKETPLACE_ALIASES.items():
        if marketplace in normalized or any(alias.replace(" ", "") in normalized for alias in aliases):
            return marketplace
    return ""


def _summary(frame: pd.DataFrame, model_status: str, evaluated_indices: set[int] | None = None) -> dict:
    evaluated_indices = evaluated_indices or set()
    evaluated_reviews = len(evaluated_indices)
    flagged_reviews = int(frame["image_ocr_flag"].sum()) if "image_ocr_flag" in frame.columns else 0
    ocr_values = (
        frame.loc[list(evaluated_indices), "image_ocr_score"].to_numpy(dtype=float)
        if evaluated_indices
        else np.array([], dtype=float)
    )
    labels = Counter(
        label
        for labels_value in frame.get("image_ocr_labels", [])
        for label in (labels_value if isinstance(labels_value, list) else [])
    )
    return {
        "image_ocr_status": model_status,
        "image_ocr_reviews": int(evaluated_reviews),
        "image_ocr_flagged_reviews": int(flagged_reviews),
        "image_ocr_flagged_ratio": float(flagged_reviews / evaluated_reviews) if evaluated_reviews else 0.0,
        "image_ocr_score_mean": float(np.mean(ocr_values)) if len(ocr_values) else 0.0,
        "image_ocr_top_labels": [
            {"label": label, "count": int(count)}
            for label, count in labels.most_common(5)
        ],
    }
