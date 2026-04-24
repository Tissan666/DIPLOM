"""Shared helper functions used across training, reporting, and inference."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch


def ensure_directory(path: str | Path) -> Path:
    """Create a directory if it does not exist and return it as a Path object."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def set_global_seed(seed: int = 42) -> None:
    """Set all important random seeds for reproducible experiments."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _json_default(value: Any) -> Any:
    """Convert common scientific Python values into JSON-serializable objects."""
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


def save_json(data: Any, output_path: str | Path) -> None:
    """Write structured data to disk as formatted UTF-8 JSON."""
    output_path = Path(output_path)
    ensure_directory(output_path.parent)
    with output_path.open("w", encoding="utf-8") as file_handle:
        json.dump(
            data,
            file_handle,
            indent=2,
            ensure_ascii=False,
            default=_json_default,
        )
