"""HTML parsing logic for extracting reviews from product pages."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from .safe_urls import normalize_safe_image_url
from .utils import extract_rating_value, normalize_whitespace


@dataclass
class ParsedReview:
    """Structured representation of one scraped review."""

    author: str
    title: str
    rating: float
    date: str
    review_text: str
    source_url: str
    source_site: str
    image_urls: list[str] = field(default_factory=list)


def parse_reviews_from_html(html: str, source_url: str) -> list[dict]:
    """Extract structured reviews from raw HTML."""
    soup = BeautifulSoup(html, "html.parser")
    source_site = _infer_site_name(source_url)

    collected: list[ParsedReview] = []
    collected.extend(_parse_reviews_from_json_ld(soup, source_url, source_site))

    if "amazon." in source_site:
        collected.extend(_parse_amazon_reviews(soup, source_url, source_site))

    collected.extend(_parse_generic_review_blocks(soup, source_url, source_site))
    return [asdict(review) for review in _deduplicate_reviews(collected)]


def _parse_reviews_from_json_ld(soup: BeautifulSoup, source_url: str, source_site: str) -> list[ParsedReview]:
    """Parse schema.org review data embedded as JSON-LD."""
    reviews: list[ParsedReview] = []
    for script in soup.select("script[type='application/ld+json']"):
        raw_content = script.string or script.get_text(strip=True)
        if not raw_content:
            continue

        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError:
            continue

        for review_obj in _iter_json_ld_reviews(payload):
            text = normalize_whitespace(str(review_obj.get("reviewBody", "")))
            text = _clean_amazon_review_text(text)
            if not text:
                continue

            title = normalize_whitespace(str(review_obj.get("name", "")))
            author_block = review_obj.get("author", {})
            author = ""
            if isinstance(author_block, dict):
                author = normalize_whitespace(str(author_block.get("name", "")))
            else:
                author = normalize_whitespace(str(author_block))

            rating = extract_rating_value(
                review_obj.get("reviewRating", {}).get("ratingValue")
                if isinstance(review_obj.get("reviewRating"), dict)
                else review_obj.get("reviewRating")
            )
            date = normalize_whitespace(str(review_obj.get("datePublished", "")))
            reviews.append(
                ParsedReview(
                    author=author,
                    title=title,
                    rating=rating,
                    date=date,
                    review_text=text,
                    source_url=source_url,
                    source_site=source_site,
                    image_urls=_extract_json_ld_image_urls(review_obj, source_url),
                )
            )
    return reviews


def _iter_json_ld_reviews(payload: object) -> Iterable[dict]:
    """Yield review objects from nested JSON-LD payloads."""
    if isinstance(payload, dict):
        payload_type = payload.get("@type")
        if payload_type == "Review":
            yield payload

        review_field = payload.get("review")
        if isinstance(review_field, list):
            for entry in review_field:
                if isinstance(entry, dict):
                    yield entry
        elif isinstance(review_field, dict):
            yield review_field

        graph = payload.get("@graph")
        if isinstance(graph, list):
            for entry in graph:
                yield from _iter_json_ld_reviews(entry)

    elif isinstance(payload, list):
        for entry in payload:
            yield from _iter_json_ld_reviews(entry)


def _parse_amazon_reviews(soup: BeautifulSoup, source_url: str, source_site: str) -> list[ParsedReview]:
    """Parse Amazon review blocks from product and dedicated review pages."""
    reviews: list[ParsedReview] = []
    selectors = [
        "[data-hook='review']",
        "[id^='customer_review-']",
        ".a-section.review",
        ".review",
        "[class*='customer-review']",
    ]
    seen_blocks: set[int] = set()

    for selector in selectors:
        for block in soup.select(selector):
            block_id = id(block)
            if block_id in seen_blocks:
                continue
            seen_blocks.add(block_id)

            text = _extract_first_text(
                block,
                [
                    "[data-hook='review-body'] span",
                    "[data-hook='review-body']",
                    ".review-text-content span",
                    ".review-text-content",
                    ".a-expander-content.reviewText",
                    "[class*='review-text']",
                ],
            )
            text = _clean_amazon_review_text(text)
            if not text:
                continue

            rating_text = _extract_first_text_or_attribute(
                block,
                [
                    "[data-hook='review-star-rating'] span.a-icon-alt",
                    "[data-hook='cmps-review-star-rating'] span.a-icon-alt",
                    "[data-hook='review-star-rating']",
                    "[data-hook='cmps-review-star-rating']",
                    ".review-rating span.a-icon-alt",
                    ".review-rating",
                    "i.a-icon-star span.a-icon-alt",
                    "[aria-label*='out of 5 stars']",
                ],
                attributes=["aria-label", "title"],
            )

            reviews.append(
                ParsedReview(
                    author=_extract_first_text(block, [".a-profile-name", "[data-hook='genome-widget'] .a-profile-name"]),
                    title=_clean_amazon_review_text(
                        _extract_first_text(
                            block,
                            [
                                "[data-hook='review-title'] span",
                                "[data-hook='review-title']",
                                ".review-title",
                                "[class*='review-title']",
                            ],
                        )
                    ),
                    rating=extract_rating_value(rating_text),
                    date=_extract_first_text(block, ["[data-hook='review-date']", ".review-date"]),
                    review_text=text,
                    source_url=source_url,
                    source_site=source_site,
                    image_urls=_extract_image_urls(block, source_url),
                )
            )
    return reviews


def _clean_amazon_review_text(text: str) -> str:
    """Remove Amazon accessibility boilerplate that is embedded inside review blocks."""
    cleaned = normalize_whitespace(text)
    boilerplate_phrases = (
        "Brief content visible, double tap to read full content.",
        "Full content visible, double tap to read brief content.",
        "Brief content visible, double tap to read full content",
        "Full content visible, double tap to read brief content",
    )
    for phrase in boilerplate_phrases:
        cleaned = cleaned.replace(phrase, " ")
    return normalize_whitespace(cleaned)


def _parse_generic_review_blocks(soup: BeautifulSoup, source_url: str, source_site: str) -> list[ParsedReview]:
    """Use generic review selectors to support multiple e-commerce layouts."""
    selectors = [
        "[itemprop='review']",
        "[data-review-id]",
        ".review",
        ".review-item",
        ".review-card",
        ".review-list-item",
        "[class*='review-item']",
        "[class*='review-card']",
        "[class*='customer-review']",
    ]

    reviews: list[ParsedReview] = []
    seen_blocks: set[int] = set()
    for selector in selectors:
        for block in soup.select(selector):
            block_id = id(block)
            if block_id in seen_blocks:
                continue
            seen_blocks.add(block_id)

            text = _extract_first_text(
                block,
                [
                    "[itemprop='reviewBody']",
                    ".review-text",
                    ".review-content",
                    ".content",
                    ".description",
                    "p",
                ],
            )
            if not text or len(text) < 15:
                continue

            reviews.append(
                ParsedReview(
                    author=_extract_first_text(block, [".author", ".user", "[itemprop='author']", ".reviewer"]),
                    title=_extract_first_text(block, [".review-title", "[itemprop='name']", "h3", "h4"]),
                    rating=extract_rating_value(
                        _extract_first_text(
                            block,
                            [
                                "[itemprop='ratingValue']",
                                ".rating",
                                ".stars",
                                "[aria-label*='star']",
                            ],
                        )
                    ),
                    date=_extract_first_text(block, [".date", "time", "[itemprop='datePublished']"]),
                    review_text=text,
                    source_url=source_url,
                    source_site=source_site,
                    image_urls=_extract_image_urls(block, source_url),
                )
            )
    return reviews


def _extract_first_text(block: Tag, selectors: list[str]) -> str:
    """Return the first non-empty text from a list of CSS selectors."""
    for selector in selectors:
        node = block.select_one(selector)
        if node is not None:
            text = normalize_whitespace(node.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _extract_first_text_or_attribute(block: Tag, selectors: list[str], attributes: list[str]) -> str:
    """Return text or a useful attribute value from the first matching selector."""
    for selector in selectors:
        node = block.select_one(selector)
        if node is None:
            continue

        text = normalize_whitespace(node.get_text(" ", strip=True))
        if text:
            return text

        for attribute in attributes:
            raw_value = node.get(attribute)
            if raw_value:
                value = normalize_whitespace(str(raw_value))
                if value:
                    return value
    return ""


def _extract_image_urls(block: Tag, source_url: str) -> list[str]:
    """Extract likely customer-submitted images from one review block."""
    urls: list[str] = []
    seen: set[str] = set()
    for node in block.select("img, source"):
        if _is_likely_non_review_image(node):
            continue
        for raw_value in _iter_image_candidates(node):
            normalized_url = _normalize_image_candidate(raw_value, source_url)
            if not normalized_url or normalized_url in seen:
                continue
            seen.add(normalized_url)
            urls.append(normalized_url)
    return urls


def _iter_image_candidates(node: Tag) -> Iterable[str]:
    """Yield image URL candidates from common lazy-load and srcset attributes."""
    for attribute in [
        "data-a-hires",
        "data-src",
        "data-original",
        "data-lazy-src",
        "src",
        "content",
    ]:
        raw_value = node.get(attribute)
        if raw_value:
            yield str(raw_value)

    for attribute in ["srcset", "data-srcset"]:
        raw_srcset = node.get(attribute)
        if not raw_srcset:
            continue
        for candidate in str(raw_srcset).split(","):
            yield candidate.strip().split(" ")[0]


def _normalize_image_candidate(raw_value: str, source_url: str) -> str:
    value = normalize_whitespace(raw_value)
    return normalize_safe_image_url(value, source_url)


def _is_likely_non_review_image(node: Tag) -> bool:
    """Filter avatars, stars, logos, and decorative assets from review images."""
    descriptors: list[str] = []
    for current in [node, node.parent, node.parent.parent if node.parent else None]:
        if not isinstance(current, Tag):
            continue
        descriptors.extend(str(item).lower() for item in current.get("class", []))
        for attribute in ["id", "alt", "aria-label", "data-hook"]:
            raw_value = current.get(attribute)
            if raw_value:
                descriptors.append(str(raw_value).lower())

    joined = " ".join(descriptors)
    skip_hints = ("avatar", "profile", "logo", "icon", "sprite", "star", "rating", "badge")
    if any(hint in joined for hint in skip_hints):
        return True

    width = _safe_int(node.get("width"))
    height = _safe_int(node.get("height"))
    return bool(width and height and (width <= 2 or height <= 2))


def _safe_int(value: object) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _extract_json_ld_image_urls(review_obj: dict, source_url: str) -> list[str]:
    """Extract per-review image URLs from schema.org-style JSON-LD blocks."""
    urls: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str):
            normalized_url = _normalize_image_candidate(value, source_url)
            if normalized_url:
                urls.append(normalized_url)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for key in ["url", "contentUrl", "thumbnailUrl"]:
                if key in value:
                    collect(value[key])

    for key in ["image", "associatedMedia", "photo", "photos"]:
        if key in review_obj:
            collect(review_obj[key])

    deduplicated: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduplicated.append(url)
    return deduplicated


def _deduplicate_reviews(reviews: list[ParsedReview]) -> list[ParsedReview]:
    """Remove duplicate review texts while preserving order."""
    deduplicated: list[ParsedReview] = []
    seen_keys: set[str] = set()
    for review in reviews:
        text = normalize_whitespace(review.review_text)
        if _looks_like_non_review_text(text, review):
            continue
        review.review_text = text
        key = text.lower()
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        deduplicated.append(review)
    return deduplicated


def _looks_like_non_review_text(text: str, review: ParsedReview) -> bool:
    """Filter product variants, profile labels, and handles that broad HTML selectors can capture."""
    lowered = normalize_whitespace(text).lower()
    if not lowered:
        return True

    has_review_context = bool(review.author or review.date or float(review.rating or 0.0) > 0.0)
    if has_review_context:
        return False

    token_count = len(re.findall(r"[\w'-]+", lowered))
    if token_count <= 2 and len(lowered) <= 32 and not any(char in lowered for char in ".!?,;:"):
        return True

    if _looks_like_profile_handle(lowered):
        return True

    variant_markers = (
        "sku",
        "size",
        "размер",
        "цвет",
        "color",
        "white",
        "black",
        "yellow",
        "green",
        "pink",
        "blue",
        "set",
        "cm",
        "kg",
        "years",
        "year",
        "лет",
        "года",
    )
    if ("|" in lowered and token_count <= 10) or any(marker in lowered for marker in variant_markers):
        if token_count <= 10 and not any(char in lowered for char in ".!?,;:"):
            return True

    return False


def _looks_like_profile_handle(text: str) -> bool:
    """Return True for short handles/usernames that external HTML can expose as cards."""
    compact = text.strip().lstrip("@")
    if " " in compact:
        parts = compact.split()
        if len(parts) > 2:
            return False
        compact = "".join(parts)
    if len(compact) > 40:
        return False
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,}(?:[a-z]\.)?", compact, flags=re.IGNORECASE))


def _infer_site_name(source_url: str) -> str:
    """Convert a product URL into a simplified site label."""
    parsed = urlparse(source_url)
    if parsed.scheme == "file":
        return "local-file"
    hostname = (parsed.hostname or "unknown").lower()
    return hostname.replace("www.", "")
