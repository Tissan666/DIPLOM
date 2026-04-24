"""Structured data ingestion helpers for bots, CLI, and future integrations."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd

from fake_rating_detector.data_loader import CANONICAL_ALIASES, prepare_ratings_dataframe


SUPPORTED_STRUCTURED_EXTENSIONS = {".json", ".csv", ".xls", ".xlsx"}
SUPPORTED_HTML_EXTENSIONS = {".html", ".htm"}


def _rename_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Rename common alternative fields into the canonical schema."""
    renamed = df.copy()
    existing_columns = set(renamed.columns)

    for canonical_name, aliases in CANONICAL_ALIASES.items():
        if canonical_name in existing_columns:
            continue
        for alias in aliases:
            if alias in existing_columns:
                renamed = renamed.rename(columns={alias: canonical_name})
                existing_columns = set(renamed.columns)
                break

    return renamed


def _prepare_flexible_dataframe(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Fill reasonable defaults before passing data into the anti-fraud pipeline."""
    prepared = _rename_aliases(df)

    if "user_id" not in prepared.columns:
        prepared["user_id"] = [f"imported_user_{index + 1}" for index in range(len(prepared))]
    if "item_id" not in prepared.columns:
        prepared["item_id"] = Path(source_name).stem or "imported-item"
    if "ip_address" not in prepared.columns:
        prepared["ip_address"] = "0.0.0.0"
    if "geo_country" not in prepared.columns and "geolocation" not in prepared.columns:
        prepared["geo_country"] = "Unknown"
        prepared["geo_city"] = "Unknown"
    elif "geo_country" in prepared.columns and "geo_city" not in prepared.columns:
        prepared["geo_city"] = "Unknown"
    if "review_text" not in prepared.columns:
        prepared["review_text"] = ""

    return prepare_ratings_dataframe(prepared)


def _decode_text_bytes(content: bytes) -> str:
    """Decode uploaded text using a small list of practical fallbacks."""
    for encoding in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to decode the uploaded file. Expected UTF-8, UTF-8-SIG, or CP1251 text.")


def parse_structured_records_from_bytes(content: bytes, filename: str) -> list[dict]:
    """Parse JSON/CSV/Excel bytes into normalized structured rating records."""
    suffix = Path(filename).suffix.lower()

    if suffix == ".json":
        payload = json.loads(_decode_text_bytes(content))
        if isinstance(payload, list):
            dataframe = pd.DataFrame(payload)
        elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
            dataframe = pd.DataFrame(payload["records"])
        else:
            raise ValueError("JSON must be a list of objects or an object with a `records` list.")
    elif suffix == ".csv":
        dataframe = pd.read_csv(io.StringIO(_decode_text_bytes(content)))
    elif suffix in {".xls", ".xlsx"}:
        dataframe = pd.read_excel(io.BytesIO(content))
    else:
        raise ValueError(f"Unsupported structured file format: {suffix or 'unknown'}")

    prepared = _prepare_flexible_dataframe(dataframe, source_name=filename)
    return prepared.to_dict(orient="records")


def parse_html_from_bytes(content: bytes) -> str:
    """Decode HTML bytes into a unicode string."""
    return _decode_text_bytes(content)

