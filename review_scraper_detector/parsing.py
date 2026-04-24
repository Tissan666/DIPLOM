"""HTML parsing logic for extracting reviews from product pages."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

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
    """Parse Amazon review blocks using data-hook attributes."""
    reviews: list[ParsedReview] = []
    for block in soup.select("[data-hook='review']"):
        text = _extract_first_text(block, ["[data-hook='review-body']", "[data-hook='review-body'] span"])
        if not text:
            continue

        reviews.append(
            ParsedReview(
                author=_extract_first_text(block, [".a-profile-name"]),
                title=_extract_first_text(block, ["[data-hook='review-title'] span", "[data-hook='review-title']"]),
                rating=extract_rating_value(
                    _extract_first_text(block, ["[data-hook='review-star-rating']", "[data-hook='cmps-review-star-rating']"])
                ),
                date=_extract_first_text(block, ["[data-hook='review-date']"]),
                review_text=text,
                source_url=source_url,
                source_site=source_site,
                image_urls=_extract_image_urls(block, source_url),
            )
        )
    return reviews


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
    if not value or value.startswith("#"):
        return ""
    if value.startswith("data:image/gif"):
        return ""
    if value.startswith("//"):
        value = f"https:{value}"
    return urljoin(source_url, value)


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
        key = normalize_whitespace(review.review_text).lower()
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        deduplicated.append(review)
    return deduplicated


def _infer_site_name(source_url: str) -> str:
    """Convert a product URL into a simplified site label."""
    parsed = urlparse(source_url)
    if parsed.scheme == "file":
        return "local-file"
    hostname = (parsed.hostname or "unknown").lower()
    return hostname.replace("www.", "")
