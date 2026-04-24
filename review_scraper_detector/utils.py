"""Shared helpers for review scraping and model training."""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any

import numpy as np
import torch

_GROUP_COMPONENT_PATTERN = re.compile(r"[^a-z0-9]+")
_PRODUCT_FAMILY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("wireless_mouse", ("wireless mouse", "mouse pad", "scroll wheel", "cursor", "pointer")),
    ("coffee_machine", ("coffee machine", "espresso", "steam pressure", "water tank", "drip tray")),
    ("phone_case", ("phone case", "camera bump", "cutouts line up", "buttons still feel")),
    ("power_bank", ("power bank", "indicator lights", "charged my phone", "cable connection")),
    ("kitchen_blender", ("kitchen blender", "frozen berries", "jar locks", "blades rinse")),
    ("gaming_headset", ("gaming headset", "ear cups", "mic quality", "desk setup", "volume wheel")),
    ("vacuum_cleaner", ("vacuum cleaner", "low carpet", "main brush", "empty the bin")),
    ("led_desk_lamp", ("led desk lamp", "warm light", "touch panel", "brightness steps")),
)


def ensure_directory(path: str | Path) -> Path:
    """Create a directory if it does not exist and return it."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def set_global_seed(seed: int = 42) -> None:
    """Set seeds for reproducible PyTorch training."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def extract_rating_value(raw_value: Any) -> float:
    """Convert a rating string like '4.0 out of 5 stars' into a float."""
    if raw_value is None:
        return 0.0
    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    match = re.search(r"(\d+(?:[\.,]\d+)?)", str(raw_value))
    if not match:
        return 0.0
    return float(match.group(1).replace(",", "."))


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace for cleaner parsing output."""
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_group_component(value: Any, default: str = "unspecified") -> str:
    """Normalize grouping metadata into a stable ASCII token."""
    if value is None:
        return default
    try:
        if bool(np.isnan(value)):
            return default
    except (TypeError, ValueError):
        pass
    text_value = str(value).strip()
    if text_value.lower() in {"", "nan", "none", "<na>"}:
        return default
    normalized = normalize_whitespace(text_value).lower()
    token = _GROUP_COMPONENT_PATTERN.sub("_", normalized).strip("_")
    return token or default


def make_review_split_group(review_text: Any) -> str:
    """Build a stable lineage id so related reviews stay in the same split."""
    normalized_text = normalize_whitespace(str(review_text or "")).lower() or "__empty_review__"
    digest = hashlib.blake2b(normalized_text.encode("utf-8"), digest_size=12).hexdigest()
    return f"review::{digest}"


def make_source_group(source: Any) -> str:
    """Collapse dataset-specific source identifiers into a stable grouping key."""
    normalized_source = normalize_whitespace(str(source or "")).lower()
    base_source = normalized_source.split(":", 1)[0]
    return normalize_group_component(base_source, default="unspecified")


def infer_review_product_family(review_text: Any, source: Any = "") -> str:
    """Infer a coarse product/domain family for group-aware validation."""
    normalized_source = normalize_whitespace(str(source or "")).lower()
    if any(keyword in normalized_source for keyword in ("recipe", "food", "cooking")):
        return "food_recipe"
    if "travel" in normalized_source:
        return "travel"
    if any(keyword in normalized_source for keyword in ("yelp", "restaurant", "business")):
        return "local_business"
    if "beauty" in normalized_source:
        return "beauty"

    normalized_text = normalize_whitespace(str(review_text or "")).lower()
    for family, keywords in _PRODUCT_FAMILY_PATTERNS:
        if any(keyword in normalized_text for keyword in keywords):
            return family

    if any(keyword in normalized_text for keyword in ("recipe", "dish", "meal", "ingredients", "oven", "cook")):
        return "food_recipe"
    if any(keyword in normalized_text for keyword in ("hotel", "flight", "trip", "traveler", "travel", "tour")):
        return "travel"
    if any(keyword in normalized_text for keyword in ("restaurant", "waiter", "service", "table", "menu", "delivery")):
        return "local_business"
    return "general"


def make_review_holdout_group(
    source_group: Any,
    product_family: Any,
    origin_family: Any = "",
) -> str:
    """Build the broader family id used for group-aware train/validation/test splits."""
    source_token = normalize_group_component(source_group, default="unspecified")
    product_token = normalize_group_component(product_family, default="general")
    origin_token = normalize_group_component(origin_family, default="")
    parts = [
        f"source::{source_token}",
        f"product::{product_token}",
    ]
    if origin_token:
        parts.append(f"origin::{origin_token}")
    return "::".join(parts)


def save_json(data: Any, output_path: str | Path) -> None:
    """Persist structured data as UTF-8 JSON."""
    output_path = Path(output_path)
    ensure_directory(output_path.parent)
    with output_path.open("w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, indent=2, ensure_ascii=False, default=_json_default)


def _json_default(value: Any) -> Any:
    """Serialize common non-JSON Python values."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
