"""Safety helpers for user-provided image references."""

from __future__ import annotations

import base64
import binascii
import ipaddress
from urllib.parse import urljoin, urlparse

MAX_DATA_IMAGE_BYTES = 8 * 1024 * 1024
BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}


def normalize_safe_image_url(raw_value: str, source_url: str) -> str:
    """Normalize a candidate image URL and reject unsafe local/internal targets."""
    value = str(raw_value or "").strip()
    if not value or value.startswith("#") or value.startswith("data:image/gif"):
        return ""

    if value.startswith("//"):
        value = f"https:{value}"

    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme not in {"http", "https", "data"}:
        return ""

    if not parsed.scheme:
        source = urlparse(source_url)
        if source.scheme not in {"http", "https"} or not source.netloc:
            return ""
        value = urljoin(source_url, value)

    return value if is_safe_image_source(value) else ""


def is_safe_image_source(url: str) -> bool:
    """Return whether an image reference is safe for backend fetching/decoding."""
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme == "data":
        return _is_safe_data_image(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    return _is_safe_public_host(parsed.hostname)


def decode_data_image(url: str, max_bytes: int = MAX_DATA_IMAGE_BYTES) -> bytes | None:
    """Decode a bounded base64 data:image payload."""
    if not _is_safe_data_image(url, max_bytes=max_bytes):
        return None

    try:
        _header, encoded = url.split(",", 1)
        return base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        return None


def _is_safe_data_image(url: str, max_bytes: int = MAX_DATA_IMAGE_BYTES) -> bool:
    value = str(url or "").strip()
    if not value.startswith("data:image") or "," not in value:
        return False

    header, encoded = value.split(",", 1)
    if ";base64" not in header.lower():
        return False

    estimated_size = (len(encoded) * 3) // 4
    return estimated_size <= max_bytes


def _is_safe_public_host(hostname: str | None) -> bool:
    if not hostname:
        return False

    normalized = hostname.strip("[]").rstrip(".").lower()
    if normalized in BLOCKED_HOSTNAMES or normalized.endswith((".localhost", ".local")):
        return False

    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return True

    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )
