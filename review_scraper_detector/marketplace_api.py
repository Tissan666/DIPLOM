"""Marketplace-specific public review API collectors.

These collectors use publicly reachable JSON endpoints when a marketplace
exposes the same review data that a regular product page renders for visitors.
They do not solve captchas, spoof users, or bypass access barriers.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from .review_collector import CollectedReview, CollectionResult, _image_urls_from_payload_value
from .utils import normalize_whitespace

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_MARKETPLACE_HOST_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("wildberries", ("wildberries.ru", "wildberries.by", "wildberries.kz", "wildberries.am", "wildberries.ge", "wb.ru")),
    ("ozon", ("ozon.ru", "ozon.com")),
    ("yandex_market", ("market.yandex.ru",)),
    ("aliexpress", ("aliexpress.ru", "aliexpress.com")),
    ("megamarket", ("megamarket.ru", "sbermegamarket.ru", "goods.ru")),
    ("avito", ("avito.ru",)),
    ("lamoda", ("lamoda.ru",)),
    ("dns", ("dns-shop.ru",)),
    ("citilink", ("citilink.ru",)),
    ("mvideo", ("mvideo.ru",)),
    ("eldorado", ("eldorado.ru",)),
    ("vseinstrumenti", ("vseinstrumenti.ru", "vseinstrumenti.com")),
    ("detsky_mir", ("detmir.ru",)),
    ("goldapple", ("goldapple.ru",)),
    ("sima_land", ("sima-land.ru",)),
    ("amazon", ("amazon.com", "amazon.de", "amazon.co.uk")),
    ("ebay", ("ebay.com", "ebay.co.uk", "ebay.de")),
    ("temu", ("temu.com",)),
    ("shein", ("shein.com",)),
)

_MARKETPLACE_LABELS: dict[str, str] = {
    "wildberries": "Wildberries",
    "ozon": "Ozon",
    "yandex_market": "Yandex Market",
    "aliexpress": "AliExpress",
    "megamarket": "MegaMarket/SberMegaMarket",
    "avito": "Avito",
    "lamoda": "Lamoda",
    "dns": "DNS",
    "citilink": "Citilink",
    "mvideo": "M.Video",
    "eldorado": "Eldorado",
    "vseinstrumenti": "Vseinstrumenti",
    "detsky_mir": "Detsky Mir",
    "goldapple": "Gold Apple",
    "sima_land": "Sima-land",
    "amazon": "Amazon",
    "ebay": "eBay",
    "temu": "Temu",
    "shein": "SHEIN",
}

_SELLER_API_MARKETPLACES = {"wildberries", "ozon", "yandex_market"}


def collect_reviews_via_public_marketplace_api(url: str, max_reviews: int = 1000) -> CollectionResult:
    """Collect reviews from a supported marketplace JSON API or explain why it is skipped."""
    marketplace = _marketplace_from_url(url)
    if marketplace == "wildberries":
        seller_result = collect_wildberries_seller_api_reviews_if_configured(url=url, max_reviews=max_reviews)
        if seller_result and seller_result.status == "success" and seller_result.reviews:
            return seller_result
        public_result = collect_wildberries_reviews(url=url, max_reviews=max_reviews)
        if public_result.status == "success" and public_result.reviews:
            return public_result
        if seller_result and seller_result.status in {"access_limited", "failed"} and public_result.status != "success":
            return seller_result
        if public_result.status != "unsupported":
            return public_result
        return _unsupported_marketplace_api_result(
            url,
            "wildberries",
            (
                "Wildberries API collection needs either an imtId in the URL for the public feedback endpoint "
                "or WB_FEEDBACKS_API_KEY/WILDBERRIES_FEEDBACKS_API_KEY for the official seller feedback API. "
                "The system will continue with Playwright and external HTML collectors."
            ),
            requires_credentials=True,
        )

    if marketplace == "ozon":
        return _unsupported_marketplace_api_result(
            url,
            marketplace,
            (
                "Ozon review API requires authenticated seller API access and is not configured as an "
                "unauthenticated public collector. The system will continue with Playwright and external HTML collectors."
            ),
            requires_credentials=True,
        )
    if marketplace == "yandex_market":
        return _unsupported_marketplace_api_result(
            url,
            marketplace,
            (
                "Yandex Market product feedback API requires Partner API credentials and a businessId. "
                "The system will continue with Playwright and external HTML collectors."
            ),
            requires_credentials=True,
        )
    if marketplace == "aliexpress":
        return _unsupported_marketplace_api_result(
            url,
            marketplace,
            (
                "AliExpress does not expose a stable unauthenticated review API for arbitrary public product URLs in this project. "
                "The system will continue with Playwright and external HTML collectors."
            ),
        )
    if marketplace in _MARKETPLACE_LABELS:
        label = _MARKETPLACE_LABELS[marketplace]
        return _unsupported_marketplace_api_result(
            url,
            marketplace,
            (
                f"{label} is recognized, but no stable unauthenticated review API collector is configured. "
                "The system will continue with Playwright and external HTML collectors."
            ),
            requires_credentials=marketplace in _SELLER_API_MARKETPLACES,
        )

    return _unsupported_marketplace_api_result(
        url,
        marketplace,
        (
            "No marketplace API collector is configured for this URL. "
            "The system will continue with Playwright and external HTML collectors."
        ),
    )


def collect_wildberries_reviews(url: str, max_reviews: int = 1000) -> CollectionResult:
    """Collect Wildberries text feedback through its public feedback JSON endpoint."""
    imt_id = _extract_wildberries_imt_id(url)
    if not imt_id:
        return CollectionResult(
            status="unsupported",
            source_url=url,
            marketplace="wildberries",
            reviews=[],
            message="Wildberries URL does not contain imtId, so the public feedback API cannot be queried directly.",
        )

    http_statuses: list[int] = []
    last_error = ""
    for host in ("feedbacks1.wb.ru", "feedbacks2.wb.ru"):
        endpoint = f"https://{host}/feedbacks/v1/{imt_id}"
        try:
            response = requests.get(
                endpoint,
                params={
                    "isAnswered": "false",
                    "take": max(1, min(max_reviews, 5000)),
                    "skip": 0,
                    "order": "dateDesc",
                },
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Referer": url,
                },
                timeout=35,
            )
            http_statuses.append(int(response.status_code))
            if response.status_code in {403, 429}:
                return CollectionResult(
                    status="access_limited",
                    source_url=url,
                    marketplace="wildberries",
                    reviews=[],
                    message=f"Wildberries public feedback API returned HTTP {response.status_code}.",
                    http_statuses=http_statuses,
                )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            last_error = str(exc)
            continue

        feedbacks = payload.get("feedbacks") if isinstance(payload, dict) else []
        if not isinstance(feedbacks, list):
            feedbacks = []

        records = _deduplicate_reviews(
            review
            for feedback in feedbacks
            if (review := _wildberries_feedback_to_review(feedback, source_url=url)) is not None
        )
        if max_reviews:
            records = records[:max_reviews]

        return CollectionResult(
            status="success",
            source_url=url,
            marketplace="wildberries",
            reviews=records,
            message=f"Collected {len(records)} Wildberries text review(s) from public feedback API.",
            http_statuses=http_statuses,
            extraction_sources={
                "wildberries_feedbacks": len(feedbacks),
                "wildberries_feedback_count": _safe_int(payload.get("feedbackCount")),
                "wildberries_feedback_count_with_text": _safe_int(payload.get("feedbackCountWithText")),
                "deduplicated_total": len(records),
            },
        )

    return CollectionResult(
        status="failed",
        source_url=url,
        marketplace="wildberries",
        reviews=[],
        message=f"Wildberries public feedback API could not be reached. Last error: {last_error}",
        http_statuses=http_statuses,
    )


def collect_wildberries_seller_api_reviews_if_configured(url: str, max_reviews: int = 1000) -> CollectionResult | None:
    """Collect Wildberries seller feedback when an official feedback token is configured."""
    api_key = _first_env_value("WB_FEEDBACKS_API_KEY", "WILDBERRIES_FEEDBACKS_API_KEY", "WILDBERRIES_API_KEY")
    nm_id = _extract_wildberries_nm_id(url)
    if not api_key or not nm_id:
        return None

    endpoint = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
    http_statuses: list[int] = []
    feedbacks: list[dict[str, Any]] = []
    last_error = ""
    for is_answered in (False, True):
        try:
            response = requests.get(
                endpoint,
                params={
                    "isAnswered": str(is_answered).lower(),
                    "take": max(1, min(max_reviews, 5000)),
                    "skip": 0,
                    "order": "dateDesc",
                    "nmId": nm_id,
                },
                headers={
                    "Accept": "application/json",
                    "Authorization": api_key,
                    "User-Agent": DEFAULT_USER_AGENT,
                },
                timeout=35,
            )
            http_statuses.append(int(response.status_code))
            if response.status_code in {401, 402, 403, 429}:
                return CollectionResult(
                    status="access_limited",
                    source_url=url,
                    marketplace="wildberries",
                    reviews=[],
                    message=f"Wildberries official seller feedback API returned HTTP {response.status_code}.",
                    http_statuses=http_statuses,
                    extraction_sources={"wildberries_seller_api": 1, "requires_credentials": 1},
                )
            response.raise_for_status()
            feedbacks.extend(_extract_wildberries_feedbacks(response.json()))
        except Exception as exc:
            last_error = str(exc)
            continue

    if not feedbacks and last_error:
        return CollectionResult(
            status="failed",
            source_url=url,
            marketplace="wildberries",
            reviews=[],
            message=f"Wildberries official seller feedback API could not be reached. Last error: {last_error}",
            http_statuses=http_statuses,
            extraction_sources={"wildberries_seller_api": 1, "requires_credentials": 1},
        )

    records = _deduplicate_reviews(
        review
        for feedback in feedbacks
        if (review := _wildberries_feedback_to_review(feedback, source_url=url)) is not None
    )
    if max_reviews:
        records = records[:max_reviews]

    return CollectionResult(
        status="success",
        source_url=url,
        marketplace="wildberries",
        reviews=records,
        message=f"Collected {len(records)} Wildberries review(s) from official seller feedback API.",
        http_statuses=http_statuses,
        extraction_sources={
            "wildberries_seller_api": len(feedbacks),
            "requires_credentials": 1,
            "deduplicated_total": len(records),
        },
    )


def _extract_wildberries_feedbacks(payload: Any) -> list[dict[str, Any]]:
    """Extract feedback arrays from current and legacy Wildberries response shapes."""
    if not isinstance(payload, dict):
        return []
    candidates = []
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.extend([data.get("feedbacks"), data.get("feedbacksList"), data.get("list")])
    candidates.extend([payload.get("feedbacks"), payload.get("feedbacksList"), payload.get("list")])
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def _wildberries_feedback_to_review(feedback: dict[str, Any], source_url: str) -> CollectedReview | None:
    """Convert one Wildberries feedback object to the project review schema."""
    text_parts = [
        normalize_whitespace(str(feedback.get("text") or "")),
        normalize_whitespace(str(feedback.get("pros") or "")),
        normalize_whitespace(str(feedback.get("cons") or "")),
    ]
    review_text = normalize_whitespace(". ".join(part for part in text_parts if part))
    if len(review_text) < 5:
        return None

    user_details = feedback.get("wbUserDetails") if isinstance(feedback.get("wbUserDetails"), dict) else {}
    photos = feedback.get("photos") or feedback.get("photo") or []
    image_urls = _image_urls_from_payload_value(photos, source_url)
    photos_count = max(len(image_urls), len(photos) if isinstance(photos, list) else 0)

    return CollectedReview(
        source_url=source_url,
        marketplace="wildberries",
        author=normalize_whitespace(str(user_details.get("name") or "")),
        title="",
        rating=float(_safe_int(feedback.get("productValuation"))),
        date=normalize_whitespace(str(feedback.get("createdDate") or "")),
        review_text=review_text,
        photos_count=photos_count,
        image_urls=image_urls,
    )


def _extract_wildberries_imt_id(url: str) -> str:
    """Extract imtId from a Wildberries feedback URL."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    imt_id = (query.get("imtId") or query.get("imtid") or [""])[0]
    return "".join(char for char in str(imt_id) if char.isdigit())


def _extract_wildberries_nm_id(url: str) -> str:
    """Extract the Wildberries product nmId from a catalog URL."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    explicit = (query.get("nmId") or query.get("nmid") or [""])[0]
    if explicit:
        return "".join(char for char in str(explicit) if char.isdigit())

    path_parts = [part for part in parsed.path.split("/") if part]
    if "catalog" in path_parts:
        index = path_parts.index("catalog")
        if len(path_parts) > index + 1:
            return "".join(char for char in path_parts[index + 1] if char.isdigit())
    return ""


def _deduplicate_reviews(reviews: Any) -> list[CollectedReview]:
    """Deduplicate review texts while preserving source order."""
    result: list[CollectedReview] = []
    seen: set[str] = set()
    for review in reviews:
        text_key = normalize_whitespace(review.review_text).lower()
        if not text_key or text_key in seen:
            continue
        seen.add(text_key)
        result.append(review)
    return result


def _safe_int(value: Any) -> int:
    """Convert marketplace numeric fields safely."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _marketplace_from_url(url: str) -> str:
    """Infer a short marketplace name from a URL."""
    hostname = (urlparse(url).hostname or "generic").lower().replace("www.", "")
    for marketplace, markers in _MARKETPLACE_HOST_RULES:
        if any(_hostname_matches(hostname, marker) for marker in markers):
            return marketplace
    return hostname


def _hostname_matches(hostname: str, marker: str) -> bool:
    """Return True when host is exactly a marketplace domain or its subdomain."""
    normalized_host = hostname.lower().strip(".")
    normalized_marker = marker.lower().strip(".")
    return normalized_host == normalized_marker or normalized_host.endswith(f".{normalized_marker}")


def _unsupported_marketplace_api_result(
    url: str,
    marketplace: str,
    message: str,
    *,
    requires_credentials: bool = False,
) -> CollectionResult:
    """Build a trace-friendly unsupported result for known marketplace URLs."""
    return CollectionResult(
        status="unsupported",
        source_url=url,
        marketplace=marketplace,
        reviews=[],
        message=message,
        extraction_sources={
            "known_marketplace": 1 if marketplace in _MARKETPLACE_LABELS else 0,
            "requires_credentials": 1 if requires_credentials else 0,
            "browser_fallback_expected": 1,
        },
    )


def _first_env_value(*names: str) -> str:
    """Return the first non-empty environment variable value from several aliases."""
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return ""
