"""Dataset loading and validation for rating manipulation detection."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ["user_id", "item_id", "rating", "timestamp"]
CANONICAL_ALIASES = {
    "user_id": ["user", "userId"],
    "item_id": ["service_id", "item_service_id", "itemId"],
    "rating": ["score", "stars"],
    "timestamp": ["created_at", "datetime", "date"],
    "ip_address": ["ip", "ip_addr"],
    "review_text": ["text", "review", "comment"],
    "is_fake": ["label", "target", "is_anomaly"],
    "geolocation": ["geo_location"],
}
MISSING_IP_MARKERS = {"", "-", "unknown", "none", "null", "nan", "n/a", "na"}


def _rename_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Rename common alternative column names into the project's canonical schema."""
    df = df.copy()
    existing_columns = set(df.columns)

    for canonical_name, aliases in CANONICAL_ALIASES.items():
        if canonical_name in existing_columns:
            continue
        for alias in aliases:
            if alias in existing_columns:
                df = df.rename(columns={alias: canonical_name})
                break

    return df


def prepare_ratings_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Validate incoming data and convert it into a clean dataframe for the pipeline."""
    df = _rename_aliases(df)

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError("Dataset is missing required columns: " + ", ".join(missing))

    if "geo_country" not in df.columns and "geolocation" not in df.columns:
        raise ValueError("Dataset must include either `geo_country` or `geolocation` / `geo_location`.")

    prepared = df.copy()

    if "geo_country" not in prepared.columns:
        geo_parts = prepared["geolocation"].fillna("Unknown|Unknown").astype(str).str.split("|", n=1, expand=True)
        prepared["geo_country"] = geo_parts[0].fillna("Unknown")
        prepared["geo_city"] = geo_parts[1].fillna("Unknown") if geo_parts.shape[1] > 1 else "Unknown"
    else:
        prepared["geo_country"] = prepared["geo_country"].fillna("Unknown").astype(str)
        prepared["geo_city"] = prepared.get("geo_city", "Unknown")
        prepared["geo_city"] = prepared["geo_city"].fillna("Unknown").astype(str)

    if "review_text" not in prepared.columns:
        prepared["review_text"] = ""
    if "is_fake" not in prepared.columns:
        prepared["is_fake"] = -1
    if "ip_address" not in prepared.columns:
        prepared["ip_address"] = ""

    prepared["user_id"] = prepared["user_id"].astype(str)
    prepared["item_id"] = prepared["item_id"].astype(str)
    prepared["ip_address"] = [
        _normalize_optional_ip(value, index)
        for index, value in enumerate(prepared["ip_address"].tolist())
    ]
    prepared["review_text"] = prepared["review_text"].fillna("").astype(str)
    prepared["rating"] = pd.to_numeric(prepared["rating"], errors="coerce")
    prepared["timestamp"] = pd.to_datetime(prepared["timestamp"], errors="coerce", utc=True).dt.tz_localize(None)
    prepared["is_fake"] = pd.to_numeric(prepared["is_fake"], errors="coerce").fillna(-1).astype(int)
    prepared["geo_key"] = prepared["geo_country"] + "|" + prepared["geo_city"]

    prepared = prepared.dropna(subset=["rating", "timestamp"]).reset_index(drop=True)
    return prepared.sort_values("timestamp").reset_index(drop=True)


def _normalize_optional_ip(value: object, row_index: int) -> str:
    """Keep real IP values, but never group missing IPs into one fake shared address."""
    raw_value = "" if pd.isna(value) else str(value).strip()
    if raw_value.lower() in MISSING_IP_MARKERS:
        return f"__missing_ip_{row_index}"
    return raw_value


def load_ratings_data(csv_path: str | Path) -> pd.DataFrame:
    """Load a CSV dataset from disk and apply project-level validation rules."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")

    dataframe = pd.read_csv(csv_path)
    return prepare_ratings_dataframe(dataframe)
