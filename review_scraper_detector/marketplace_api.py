"""Marketplace-specific public review API collectors.

These collectors use publicly reachable JSON endpoints when a marketplace
exposes the same review data that a regular product page renders for visitors.
They do not solve captchas, spoof users, or bypass access barriers.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from .review_collector import CollectedReview, CollectionResult
from .utils import normalize_whitespace

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def collect_reviews_via_public_marketplace_api(url: str, max_reviews: int = 1000) -> CollectionResult:
    """Collect reviews from a supported public marketplace JSON API."""
    hostname = (urlparse(url).hostname or "").lower()
    if "wildberries" in hostname or hostname.endswith("wb.ru"):
        return collect_wildberries_reviews(url=url, max_reviews=max_reviews)

    return CollectionResult(
        status="unsupported",
        source_url=url,
        marketplace=_marketplace_from_url(url),
        reviews=[],
        message="No public marketplace review API collector is configured for this URL.",
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
    photos_count = len(photos) if isinstance(photos, list) else 0

    return CollectedReview(
        source_url=source_url,
        marketplace="wildberries",
        author=normalize_whitespace(str(user_details.get("name") or "")),
        title="",
        rating=float(_safe_int(feedback.get("productValuation"))),
        date=normalize_whitespace(str(feedback.get("createdDate") or "")),
        review_text=review_text,
        photos_count=photos_count,
    )


def _extract_wildberries_imt_id(url: str) -> str:
    """Extract imtId from a Wildberries feedback URL."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    imt_id = (query.get("imtId") or query.get("imtid") or [""])[0]
    return "".join(char for char in str(imt_id) if char.isdigit())


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
    if "wildberries" in hostname or hostname.endswith("wb.ru"):
        return "wildberries"
    if "ozon" in hostname:
        return "ozon"
    if "aliexpress" in hostname:
        return "aliexpress"
    return hostname
