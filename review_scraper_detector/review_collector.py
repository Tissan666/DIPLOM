"""Async Playwright review collector for public e-commerce pages.

This module is intentionally compliance-oriented: it renders dynamic pages like
a browser, waits politely between actions, records access barriers, and stops on
captcha/403/429 instead of trying to bypass them.
"""

from __future__ import annotations

import asyncio
import csv
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .parsing import parse_reviews_from_html
from .utils import ensure_directory, normalize_whitespace


try:  # Playwright is optional until the collector is used.
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Page,
        Response,
        TimeoutError as PlaywrightTimeoutError,
        async_playwright,
    )
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - import guard for environments without Playwright.
    Browser = BrowserContext = Page = Response = object  # type: ignore
    PlaywrightTimeoutError = TimeoutError  # type: ignore
    async_playwright = None  # type: ignore
    sync_playwright = None  # type: ignore


class CaptchaRequired(RuntimeError):
    """Raised when a page asks for robot verification."""


class AccessLimited(RuntimeError):
    """Raised when a platform returns an access/rate-limit barrier."""


@dataclass
class ReviewCollectorConfig:
    """Runtime settings for the research collector."""

    headless: bool = False
    locale: str = "ru-RU"
    timezone_id: str = "Europe/Samara"
    viewport_width: int = 1366
    viewport_height: int = 768
    action_delay_min_ms: int = 2000
    action_delay_max_ms: int = 3000
    navigation_timeout_ms: int = 45000
    navigation_retry_budget_ms: int = 180000
    max_scroll_rounds: int = 80
    stable_rounds_to_stop: int = 3
    output_dir: Path = Path("outputs") / "collected_reviews"
    user_agent: str | None = None
    browser_channel: str | None = None
    slow_mo_ms: int = 0


@dataclass
class CollectedReview:
    """Normalized review record exported for later ML analysis."""

    source_url: str
    marketplace: str
    author: str
    title: str
    rating: float
    date: str
    review_text: str
    photos_count: int = 0


@dataclass
class CollectionResult:
    """Result envelope that can be saved and discussed in a diploma report."""

    status: str
    source_url: str
    marketplace: str
    reviews: list[CollectedReview] = field(default_factory=list)
    message: str = ""
    rounds_completed: int = 0
    http_statuses: list[int] = field(default_factory=list)
    extraction_sources: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketplaceAdapter:
    """Marketplace-specific selectors and JSON response hints."""

    name: str
    host_markers: tuple[str, ...]
    reviews_tab_selectors: tuple[str, ...] = ()
    show_more_selectors: tuple[str, ...] = ()
    review_container_selectors: tuple[str, ...] = ()
    spinner_selectors: tuple[str, ...] = ()
    review_api_keywords: tuple[str, ...] = ()
    empty_markers: tuple[str, ...] = ()


class ReviewCollector:
    """Collect public reviews from dynamic product pages with ethical limits."""

    adapters = [
        MarketplaceAdapter(
            name="wildberries",
            host_markers=("wildberries.", "wb.ru"),
            reviews_tab_selectors=(
                "button:has-text('Отзывы')",
                "a:has-text('Отзывы')",
                "[data-link*='feedback']",
                "[data-testid*='feedback']",
                "[class*='feedback']",
            ),
            show_more_selectors=(
                "button:has-text('Показать ещё')",
                "button:has-text('Показать еще')",
                "button:has-text('Больше отзывов')",
                "[class*='feedback'] button",
            ),
            review_container_selectors=(
                "[class*='feedback__item']",
                "[class*='comments__item']",
                "[class*='review']",
                "[data-testid*='feedback']",
            ),
            review_api_keywords=("feedback", "comments", "reviews", "nm-2-card", "valuation"),
            empty_markers=("отзывов пока нет", "нет отзывов"),
        ),
        MarketplaceAdapter(
            name="ozon",
            host_markers=("ozon.",),
            reviews_tab_selectors=(
                "a[href*='reviews']",
                "button:has-text('Отзывы')",
                "a:has-text('Отзывы')",
                "[data-widget*='webReview']",
                "[data-widget*='review']",
            ),
            show_more_selectors=(
                "button:has-text('Показать ещё')",
                "button:has-text('Показать еще')",
                "button:has-text('Загрузить ещё')",
                "button:has-text('Все отзывы')",
            ),
            review_container_selectors=(
                "[data-review-id]",
                "[data-widget*='webReview']",
                "[data-widget*='review']",
                "[class*='review']",
                "[class*='comment']",
            ),
            review_api_keywords=("review", "reviews", "comments", "ugc", "feedback"),
            empty_markers=("отзывов пока нет", "нет отзывов"),
        ),
        MarketplaceAdapter(
            name="aliexpress",
            host_markers=("aliexpress.", "aliexpress.ru"),
            reviews_tab_selectors=(
                "a[href*='review']",
                "button:has-text('Отзывы')",
                "a:has-text('Отзывы')",
                "button:has-text('Reviews')",
                "a:has-text('Reviews')",
            ),
            show_more_selectors=(
                "button:has-text('Show more')",
                "button:has-text('Показать ещё')",
                "button:has-text('Показать еще')",
                "button:has-text('More')",
            ),
            review_container_selectors=(
                "[class*='feedback']",
                "[class*='review']",
                "[class*='comment']",
                "[data-pl*='review']",
            ),
            review_api_keywords=("review", "reviews", "feedback", "buyer", "evaluation"),
            empty_markers=("no reviews", "нет отзывов"),
        ),
    ]

    review_container_selectors = [
        "[data-review-id]",
        "[data-qa*='review']",
        "[itemprop='review']",
        ".review",
        ".review-item",
        ".review-card",
        "[class*='review']",
        "[class*='feedback']",
        "[class*='comment']",
    ]

    show_more_selectors = [
        "button:has-text('Показать ещё')",
        "button:has-text('Показать еще')",
        "button:has-text('Все отзывы')",
        "button:has-text('Show more')",
        "a:has-text('Показать ещё')",
        "a:has-text('Все отзывы')",
    ]

    reviews_tab_selectors = [
        "text=Отзывы",
        "text=Все отзывы",
        "text=Reviews",
        "a[href*='review']",
        "button:has-text('Отзывы')",
        "[data-qa*='review']",
    ]

    spinner_selectors = [
        "[class*='spinner']",
        "[class*='preloader']",
        "[class*='loader']",
        "[data-qa*='loader']",
        "[aria-busy='true']",
    ]

    captcha_markers = [
        "captcha",
        "recaptcha",
        "hcaptcha",
        "robot",
        "verify you are human",
        "подтвердите, что вы не робот",
        "проверка безопасности",
        "капча",
    ]

    access_markers = [
        "access denied",
        "forbidden",
        "too many requests",
        "temporarily blocked",
        "доступ ограничен",
        "слишком много запросов",
    ]

    def __init__(self, config: ReviewCollectorConfig | None = None) -> None:
        self.config = config or ReviewCollectorConfig()
        self._playwright = None
        self._browser: Browser | None = None
        self.http_statuses: list[int] = []
        self.network_reviews: list[CollectedReview] = []
        self.rendered_scroll_reviews: list[CollectedReview] = []

    async def __aenter__(self) -> "ReviewCollector":
        await self.start()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

    async def start(self) -> None:
        """Start Chromium without stealth patches or protection bypasses."""
        if async_playwright is None:
            raise RuntimeError("Playwright is not installed. Run `pip install -r requirements.txt` and `playwright install chromium`.")

        self._playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "headless": self.config.headless,
            "slow_mo": self.config.slow_mo_ms,
            "args": ["--disable-dev-shm-usage"],
        }
        if self.config.browser_channel:
            launch_kwargs["channel"] = self.config.browser_channel
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)

    async def close(self) -> None:
        """Close browser resources cleanly."""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def collect(
        self,
        url: str,
        marketplace: str = "generic",
        max_reviews: int | None = None,
    ) -> CollectionResult:
        """Collect reviews from one product URL."""
        if self._browser is None:
            await self.start()

        self.http_statuses = []
        self.network_reviews = []
        self.rendered_scroll_reviews = []
        adapter = self._adapter_for_url(url, marketplace)
        marketplace = adapter.name
        context = await self._new_context()
        page = await context.new_page()
        page.on("response", lambda response: self._handle_response(response, adapter, url, marketplace))

        try:
            response = await self._goto_with_backoff(page, url)
            if response is not None and response.status in {403, 429}:
                raise AccessLimited(f"HTTP {response.status} received while opening the page.")

            await self._polite_pause()
            await self._detect_access_barrier(page)
            await self._open_reviews_section(page, adapter)
            rounds = await self._load_reviews_until_stable(
                page,
                adapter,
                source_url=url,
                marketplace=marketplace,
                max_reviews=max_reviews,
            )

            html = await page.content()
            parsed = parse_reviews_from_html(html=html, source_url=url)
            html_records = [
                CollectedReview(
                    source_url=row.get("source_url", url),
                    marketplace=marketplace,
                    author=normalize_whitespace(str(row.get("author", ""))),
                    title=normalize_whitespace(str(row.get("title", ""))),
                    rating=float(row.get("rating", 0.0) or 0.0),
                    date=normalize_whitespace(str(row.get("date", ""))),
                    review_text=normalize_whitespace(str(row.get("review_text", ""))),
                    photos_count=0,
                )
                for row in parsed
            ]
            state_records = await self._extract_spa_state_reviews(page, url, marketplace)
            records = _deduplicate_collected_reviews(
                [*self.network_reviews, *state_records, *self.rendered_scroll_reviews, *html_records]
            )
            if max_reviews is not None:
                records = records[:max_reviews]

            extraction_sources = {
                "network_json": len(self.network_reviews),
                "spa_state": len(state_records),
                "scroll_dom": len(self.rendered_scroll_reviews),
                "html_dom": len(html_records),
                "deduplicated_total": len(records),
            }
            result = CollectionResult(
                status="success",
                source_url=url,
                marketplace=marketplace,
                reviews=records,
                message=f"Collected {len(records)} review(s).",
                rounds_completed=rounds,
                http_statuses=self.http_statuses,
                extraction_sources=extraction_sources,
            )
            self.save_result(result)
            return result

        except CaptchaRequired as exc:
            result = self._barrier_result("captcha_required", url, marketplace, str(exc))
            await page.screenshot(path=str(self.config.output_dir / "captcha_required.png"), full_page=True)
            self.save_result(result)
            return result

        except AccessLimited as exc:
            result = self._barrier_result("access_limited", url, marketplace, str(exc))
            await page.screenshot(path=str(self.config.output_dir / "access_limited.png"), full_page=True)
            self.save_result(result)
            return result

        except PlaywrightTimeoutError as exc:
            result = self._barrier_result("timeout", url, marketplace, str(exc))
            self.save_result(result)
            return result

        finally:
            await context.close()

    async def _new_context(self) -> BrowserContext:
        """Create a regular browser context with explicit research settings."""
        assert self._browser is not None
        kwargs = {
            "locale": self.config.locale,
            "timezone_id": self.config.timezone_id,
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
        }
        if self.config.user_agent:
            kwargs["user_agent"] = self.config.user_agent
        return await self._browser.new_context(**kwargs)

    async def _goto_with_backoff(self, page: Page, url: str, attempts: int = 2) -> Response | None:
        """Open the page with safe retries for flaky public-page navigation."""
        last_response: Response | None = None
        last_error: Exception | None = None
        wait_modes = ("domcontentloaded", "load", "commit")
        navigation_timeout_ms = min(self.config.navigation_timeout_ms, 25_000)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(self.config.navigation_retry_budget_ms, navigation_timeout_ms) / 1000.0
        trials_completed = 0
        max_trials = 12

        for candidate_url in _navigation_url_variants(url):
            for attempt in range(attempts):
                remaining_ms = int((deadline - loop.time()) * 1000)
                if trials_completed >= max_trials or remaining_ms <= 1000:
                    break
                trials_completed += 1
                wait_until = wait_modes[min(attempt, len(wait_modes) - 1)]
                try:
                    last_response = await page.goto(
                        candidate_url,
                        wait_until=wait_until,
                        timeout=min(navigation_timeout_ms, remaining_ms),
                    )
                    if last_response is None or last_response.status != 429:
                        return last_response
                except Exception as exc:
                    last_error = exc
                    if not _is_transient_navigation_error(exc):
                        raise

                remaining_seconds = max(deadline - loop.time(), 0.0)
                wait_seconds = min((2**attempt) + random.uniform(0.3, 1.4), 30.0, remaining_seconds)
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
            if trials_completed >= max_trials or loop.time() >= deadline:
                break

        if last_error is not None:
            raise last_error
        return last_response

    async def _open_reviews_section(self, page: Page, adapter: MarketplaceAdapter) -> None:
        """Click a visible reviews tab/button if the page provides one."""
        for selector in self._merged_selectors(adapter.reviews_tab_selectors, self.reviews_tab_selectors):
            locator = page.locator(selector).first
            try:
                if await locator.count() and await locator.is_visible(timeout=1000):
                    await locator.click(timeout=3000)
                    await self._wait_for_dynamic_content(page)
                    return
            except Exception:
                continue

    async def _load_reviews_until_stable(
        self,
        page: Page,
        adapter: MarketplaceAdapter,
        source_url: str,
        marketplace: str,
        max_reviews: int | None = None,
    ) -> int:
        """Scroll/click until review count stops growing."""
        stable_rounds = 0
        previous_count = await self._review_count(page, adapter)
        rounds_completed = 0
        previous_total = 0

        for round_index in range(self.config.max_scroll_rounds):
            rounds_completed = round_index + 1
            await self._detect_access_barrier(page)
            if await self._has_empty_reviews_marker(page, adapter):
                break

            clicked = await self._click_show_more_if_available(page, adapter)
            if not clicked:
                scrolled_to_last = await self._scroll_last_review_into_view(page, adapter)
                if not scrolled_to_last:
                    await self._smooth_scroll(page)

            await self._wait_for_dynamic_content(page)
            await self._capture_current_rendered_reviews(page, source_url, marketplace)
            current_total = len(_deduplicate_collected_reviews([*self.network_reviews, *self.rendered_scroll_reviews]))
            current_count = max(await self._review_count(page, adapter), len(self.network_reviews), current_total)

            if max_reviews is not None and current_count >= max_reviews:
                break

            if current_count <= previous_count and current_total <= previous_total:
                stable_rounds += 1
            else:
                stable_rounds = 0

            previous_count = max(previous_count, current_count)
            previous_total = max(previous_total, current_total)
            if stable_rounds >= self.config.stable_rounds_to_stop:
                break

        return rounds_completed

    async def _capture_current_rendered_reviews(self, page: Page, source_url: str, marketplace: str) -> None:
        """Accumulate currently rendered review blocks during virtualized scrolling."""
        try:
            parsed = parse_reviews_from_html(html=await page.content(), source_url=source_url)
        except Exception:
            return
        records = [
            CollectedReview(
                source_url=row.get("source_url", source_url),
                marketplace=marketplace,
                author=normalize_whitespace(str(row.get("author", ""))),
                title=normalize_whitespace(str(row.get("title", ""))),
                rating=float(row.get("rating", 0.0) or 0.0),
                date=normalize_whitespace(str(row.get("date", ""))),
                review_text=normalize_whitespace(str(row.get("review_text", ""))),
                photos_count=0,
            )
            for row in parsed
        ]
        self.rendered_scroll_reviews = _deduplicate_collected_reviews([*self.rendered_scroll_reviews, *records])

    async def _click_show_more_if_available(self, page: Page, adapter: MarketplaceAdapter) -> bool:
        """Click a regular 'show more' control when present."""
        for selector in self._merged_selectors(adapter.show_more_selectors, self.show_more_selectors):
            locator = page.locator(selector).first
            try:
                if await locator.count() and await locator.is_visible(timeout=800):
                    await locator.scroll_into_view_if_needed(timeout=3000)
                    await self._polite_pause()
                    await locator.click(timeout=3000)
                    return True
            except Exception:
                continue
        return False

    async def _scroll_last_review_into_view(self, page: Page, adapter: MarketplaceAdapter) -> bool:
        """Scroll the last rendered review-like element into view when possible."""
        for selector in self._merged_selectors(adapter.review_container_selectors, self.review_container_selectors):
            try:
                locator = page.locator(selector)
                count = await locator.count()
                if count > 0:
                    await locator.nth(count - 1).scroll_into_view_if_needed(timeout=3000)
                    await self._polite_pause()
                    return True
            except Exception:
                continue
        return False

    async def _smooth_scroll(self, page: Page) -> None:
        """Use gradual scrolling to trigger normal lazy loading without bursts."""
        steps = random.randint(4, 7)
        base_delta = random.randint(420, 720)
        for index in range(steps):
            easing = 0.5 - 0.5 * np_cos(index / max(1, steps - 1) * 3.14159)
            delta = int(base_delta * (0.65 + easing))
            await page.mouse.wheel(0, delta)
            await asyncio.sleep(random.uniform(0.18, 0.42))
        await self._polite_pause()

    async def _wait_for_dynamic_content(self, page: Page) -> None:
        """Wait for network/spinner changes instead of using only fixed sleeps."""
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        for selector in self._merged_selectors((), self.spinner_selectors):
            try:
                spinner = page.locator(selector).first
                if await spinner.count():
                    await spinner.wait_for(state="hidden", timeout=5000)
            except Exception:
                continue

        await self._polite_pause()

    async def _has_empty_reviews_marker(self, page: Page, adapter: MarketplaceAdapter) -> bool:
        """Detect marketplace messages that explicitly say there are no more reviews."""
        if not adapter.empty_markers:
            return False
        try:
            body_text = (await page.locator("body").inner_text(timeout=1500)).lower()
        except Exception:
            return False
        return any(marker in body_text for marker in adapter.empty_markers)

    async def _extract_spa_state_reviews(self, page: Page, source_url: str, marketplace: str) -> list[CollectedReview]:
        """Extract review-like data from embedded SPA JSON state when available."""
        try:
            script_payloads = await page.evaluate(
                """() => Array.from(document.scripts)
                    .map((script) => script.textContent || '')
                    .filter((text) => text.includes('review') || text.includes('feedback') || text.includes('comment'))
                    .slice(0, 40)
                """
            )
        except Exception:
            return []

        records: list[CollectedReview] = []
        for payload in script_payloads:
            for json_payload in _extract_json_objects_from_text(str(payload)):
                records.extend(_reviews_from_payload(json_payload, source_url, marketplace))
        return _deduplicate_collected_reviews(records)

    async def _review_count(self, page: Page, adapter: MarketplaceAdapter) -> int:
        """Return the best-effort count of rendered review-like blocks."""
        counts = []
        for selector in self._merged_selectors(adapter.review_container_selectors, self.review_container_selectors):
            try:
                counts.append(await page.locator(selector).count())
            except Exception:
                continue
        return max(counts or [0])

    async def _detect_access_barrier(self, page: Page) -> None:
        """Stop collection when the site shows captcha or access barriers."""
        body_text = ""
        try:
            body_text = (await page.locator("body").inner_text(timeout=3000)).lower()
        except Exception:
            return

        if any(marker in body_text for marker in self.captcha_markers):
            raise CaptchaRequired("Robot verification page detected. Collection stopped by ethical policy.")

        if any(marker in body_text for marker in self.access_markers):
            raise AccessLimited("Access limitation message detected on the page.")

        # Some marketplaces return 403 for images, analytics, or optional widgets.
        # We treat access as limited only when the main navigation failed or the
        # visible page explicitly reports a barrier.

    async def _polite_pause(self) -> None:
        """Apply a small delay to avoid creating burst traffic."""
        delay_ms = random.randint(self.config.action_delay_min_ms, self.config.action_delay_max_ms)
        await asyncio.sleep(delay_ms / 1000.0)

    def _track_response_status(self, response: Response) -> None:
        """Store response statuses for later research reporting."""
        try:
            self.http_statuses.append(int(response.status))
        except Exception:
            pass

    def _handle_response(
        self,
        response: Response,
        adapter: MarketplaceAdapter,
        source_url: str,
        marketplace: str,
    ) -> None:
        """Track response statuses and schedule JSON review extraction."""
        self._track_response_status(response)
        try:
            asyncio.create_task(self._capture_review_response(response, adapter, source_url, marketplace))
        except RuntimeError:
            pass

    async def _capture_review_response(
        self,
        response: Response,
        adapter: MarketplaceAdapter,
        source_url: str,
        marketplace: str,
    ) -> None:
        """Extract review records from normal page JSON/XHR responses."""
        try:
            response_url = response.url.lower()
            content_type = (response.headers.get("content-type") or "").lower()
            if response.status >= 400:
                return
            if "json" not in content_type and not any(keyword in response_url for keyword in adapter.review_api_keywords):
                return
            if not any(keyword in response_url for keyword in adapter.review_api_keywords):
                return

            payload = await response.json()
        except Exception:
            return

        records = _reviews_from_payload(payload, source_url, marketplace)
        if records:
            self.network_reviews = _deduplicate_collected_reviews([*self.network_reviews, *records])

    def _barrier_result(self, status: str, url: str, marketplace: str, message: str) -> CollectionResult:
        """Build a result for blocked/limited sessions."""
        return CollectionResult(
            status=status,
            source_url=url,
            marketplace=marketplace,
            reviews=[],
            message=message,
            http_statuses=self.http_statuses,
        )

    def _adapter_for_url(self, url: str, marketplace: str) -> MarketplaceAdapter:
        """Select a marketplace adapter from URL/domain or explicit marketplace name."""
        hostname = (urlparse(url).hostname or "").lower()
        requested = marketplace.lower().strip()
        for adapter in self.adapters:
            if requested == adapter.name or any(marker in hostname for marker in adapter.host_markers):
                return adapter
        return MarketplaceAdapter(
            name=requested or "generic",
            host_markers=(),
            review_api_keywords=("review", "reviews", "feedback", "comment", "comments", "rating"),
        )

    def _merged_selectors(self, primary: tuple[str, ...], fallback: list[str] | tuple[str, ...]) -> list[str]:
        """Merge selector lists while preserving order."""
        merged: list[str] = []
        for selector in [*primary, *fallback]:
            if selector not in merged:
                merged.append(selector)
        return merged

    def save_result(self, result: CollectionResult) -> None:
        """Save collection output as JSON and CSV for downstream analysis."""
        output_dir = ensure_directory(self.config.output_dir)
        safe_name = _safe_filename(urlparse(result.source_url).netloc or result.marketplace)

        json_path = output_dir / f"{safe_name}_reviews.json"
        csv_path = output_dir / f"{safe_name}_reviews.csv"
        meta_path = output_dir / f"{safe_name}_meta.json"

        with json_path.open("w", encoding="utf-8") as file:
            json.dump([asdict(review) for review in result.reviews], file, ensure_ascii=False, indent=2)

        fieldnames = list(asdict(CollectedReview("", "", "", "", 0.0, "", "")).keys())
        with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(asdict(review) for review in result.reviews)

        with meta_path.open("w", encoding="utf-8") as file:
            json.dump(
                {
                    "status": result.status,
                    "source_url": result.source_url,
                    "marketplace": result.marketplace,
                    "message": result.message,
                    "reviews_count": len(result.reviews),
                    "rounds_completed": result.rounds_completed,
                    "http_statuses": result.http_statuses[-100:],
                    "extraction_sources": result.extraction_sources,
                },
                file,
                ensure_ascii=False,
                indent=2,
            )


def _safe_filename(value: str) -> str:
    """Convert a domain/name into a filesystem-safe stem."""
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return cleaned.strip("_") or "reviews"


def _navigation_url_variants(url: str) -> list[str]:
    """Return conservative URL variants that still point to public product pages."""
    parsed = urlparse(url)
    variants: list[str] = []

    def add(candidate: str) -> None:
        if candidate and candidate not in variants:
            variants.append(candidate)

    add(url)

    hostname = (parsed.hostname or "").lower()
    netloc = parsed.netloc
    path = parsed.path or "/"

    if hostname and not hostname.startswith("www.") and "aliexpress" in hostname:
        add(parsed._replace(netloc=f"www.{netloc}").geturl())

    if "aliexpress" in hostname and "/reviews" in path:
        product_path = path.replace("/reviews", "").rstrip("/") or "/"
        add(parsed._replace(path=product_path).geturl())
        if product_path.startswith("/item/") and not product_path.endswith(".html"):
            add(parsed._replace(path=f"{product_path}.html").geturl())
        if hostname and not hostname.startswith("www."):
            www_netloc = f"www.{netloc}"
            add(parsed._replace(netloc=www_netloc, path=product_path).geturl())
            if product_path.startswith("/item/") and not product_path.endswith(".html"):
                add(parsed._replace(netloc=www_netloc, path=f"{product_path}.html").geturl())

    return variants


def _is_transient_navigation_error(exc: Exception | str) -> bool:
    """Detect network/browser startup errors that are worth retrying once or twice."""
    message = str(exc).lower()
    transient_markers = (
        "err_connection_closed",
        "err_connection_reset",
        "err_timed_out",
        "err_network_changed",
        "err_internet_disconnected",
        "navigation timeout",
        "timeout",
        "target page, context or browser has been closed",
        "net::err",
    )
    return any(marker in message for marker in transient_markers)


def _sync_goto_with_backoff(page: Any, url: str, config: ReviewCollectorConfig, attempts: int = 2) -> Any:
    """Sync equivalent of safe navigation retry logic."""
    import time

    last_response: Any = None
    last_error: Exception | None = None
    wait_modes = ("domcontentloaded", "load", "commit")
    navigation_timeout_ms = min(config.navigation_timeout_ms, 25_000)
    deadline = time.monotonic() + max(config.navigation_retry_budget_ms, navigation_timeout_ms) / 1000.0
    trials_completed = 0
    max_trials = 12

    for candidate_url in _navigation_url_variants(url):
        for attempt in range(attempts):
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if trials_completed >= max_trials or remaining_ms <= 1000:
                break
            trials_completed += 1
            wait_until = wait_modes[min(attempt, len(wait_modes) - 1)]
            try:
                last_response = page.goto(
                    candidate_url,
                    wait_until=wait_until,
                    timeout=min(navigation_timeout_ms, remaining_ms),
                )
                if last_response is None or last_response.status != 429:
                    return last_response
            except Exception as exc:
                last_error = exc
                if not _is_transient_navigation_error(exc):
                    raise

            remaining_seconds = max(deadline - time.monotonic(), 0.0)
            wait_seconds = min((2**attempt) + random.uniform(0.3, 1.4), 30.0, remaining_seconds)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
        if trials_completed >= max_trials or time.monotonic() >= deadline:
            break

    if last_error is not None:
        raise last_error
    return last_response


def collect_reviews_sync(
    url: str,
    marketplace: str = "generic",
    max_reviews: int | None = None,
    config: ReviewCollectorConfig | None = None,
) -> CollectionResult:
    """Synchronous Playwright collector fallback for Windows Store Python issues."""
    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed. Run `pip install -r requirements.txt`.")

    config = config or ReviewCollectorConfig()
    helper = ReviewCollector(config)
    adapter = helper._adapter_for_url(url, marketplace)
    marketplace = adapter.name
    http_statuses: list[int] = []
    network_reviews: list[CollectedReview] = []
    rendered_scroll_reviews: list[CollectedReview] = []

    with sync_playwright() as playwright:
        launch_kwargs: dict[str, Any] = {
            "headless": config.headless,
            "slow_mo": config.slow_mo_ms,
            "args": ["--disable-dev-shm-usage"],
        }
        if config.browser_channel:
            launch_kwargs["channel"] = config.browser_channel
        browser = playwright.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            locale=config.locale,
            timezone_id=config.timezone_id,
            viewport={"width": config.viewport_width, "height": config.viewport_height},
            user_agent=config.user_agent,
        )
        page = context.new_page()

        def on_response(response: Any) -> None:
            try:
                http_statuses.append(int(response.status))
                response_url = response.url.lower()
                content_type = (response.headers.get("content-type") or "").lower()
                if response.status >= 400:
                    return
                if "json" not in content_type and not any(keyword in response_url for keyword in adapter.review_api_keywords):
                    return
                if not any(keyword in response_url for keyword in adapter.review_api_keywords):
                    return
                payload = response.json()
                network_reviews.extend(_reviews_from_payload(payload, url, marketplace))
            except Exception:
                return

        page.on("response", on_response)

        try:
            response = _sync_goto_with_backoff(page, url, config)
            if response is not None and response.status in {403, 429}:
                raise AccessLimited(f"HTTP {response.status} received while opening the page.")
            _sync_polite_pause(config)
            _sync_detect_access_barrier(page, http_statuses)
            _sync_open_reviews_section(page, adapter, helper, config)
            rounds = _sync_load_reviews_until_stable(
                page=page,
                adapter=adapter,
                helper=helper,
                config=config,
                max_reviews=max_reviews,
                network_reviews=network_reviews,
                rendered_scroll_reviews=rendered_scroll_reviews,
                http_statuses=http_statuses,
                source_url=url,
                marketplace=marketplace,
            )

            parsed = parse_reviews_from_html(html=page.content(), source_url=url)
            html_records = [
                CollectedReview(
                    source_url=row.get("source_url", url),
                    marketplace=marketplace,
                    author=normalize_whitespace(str(row.get("author", ""))),
                    title=normalize_whitespace(str(row.get("title", ""))),
                    rating=float(row.get("rating", 0.0) or 0.0),
                    date=normalize_whitespace(str(row.get("date", ""))),
                    review_text=normalize_whitespace(str(row.get("review_text", ""))),
                    photos_count=0,
                )
                for row in parsed
            ]
            state_records = _sync_extract_spa_state_reviews(page, url, marketplace)
            records = _deduplicate_collected_reviews([*network_reviews, *state_records, *rendered_scroll_reviews, *html_records])
            if max_reviews is not None:
                records = records[:max_reviews]

            result = CollectionResult(
                status="success",
                source_url=url,
                marketplace=marketplace,
                reviews=records,
                message=f"Collected {len(records)} review(s).",
                rounds_completed=rounds,
                http_statuses=http_statuses,
                extraction_sources={
                    "network_json": len(network_reviews),
                    "spa_state": len(state_records),
                    "scroll_dom": len(rendered_scroll_reviews),
                    "html_dom": len(html_records),
                    "deduplicated_total": len(records),
                    "runtime": "sync_playwright",
                },
            )
            helper.save_result(result)
            return result

        except CaptchaRequired as exc:
            result = CollectionResult("captcha_required", url, marketplace, [], str(exc), http_statuses=http_statuses)
            helper.save_result(result)
            return result
        except AccessLimited as exc:
            result = CollectionResult("access_limited", url, marketplace, [], str(exc), http_statuses=http_statuses)
            helper.save_result(result)
            return result
        finally:
            context.close()
            browser.close()


def _sync_open_reviews_section(page: Any, adapter: MarketplaceAdapter, helper: ReviewCollector, config: ReviewCollectorConfig) -> None:
    """Open reviews section in sync Playwright mode."""
    for selector in helper._merged_selectors(adapter.reviews_tab_selectors, helper.reviews_tab_selectors):
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible(timeout=1000):
                locator.click(timeout=3000)
                _sync_wait_for_dynamic_content(page, helper, config)
                return
        except Exception:
            continue


def _sync_load_reviews_until_stable(
    page: Any,
    adapter: MarketplaceAdapter,
    helper: ReviewCollector,
    config: ReviewCollectorConfig,
    max_reviews: int | None,
    network_reviews: list[CollectedReview],
    rendered_scroll_reviews: list[CollectedReview],
    http_statuses: list[int],
    source_url: str,
    marketplace: str,
) -> int:
    """Sync version of the deep-scroll loop."""
    previous_count = _sync_review_count(page, adapter, helper)
    stable_rounds = 0
    rounds_completed = 0
    previous_total = 0
    for round_index in range(config.max_scroll_rounds):
        rounds_completed = round_index + 1
        _sync_detect_access_barrier(page, http_statuses)
        clicked = _sync_click_show_more_if_available(page, adapter, helper, config)
        if not clicked:
            if not _sync_scroll_last_review_into_view(page, adapter, helper, config):
                _sync_smooth_scroll(page, config)
        _sync_wait_for_dynamic_content(page, helper, config)
        _sync_capture_current_rendered_reviews(page, source_url, marketplace, rendered_scroll_reviews)
        current_total = len(_deduplicate_collected_reviews([*network_reviews, *rendered_scroll_reviews]))
        current_count = max(_sync_review_count(page, adapter, helper), len(network_reviews), current_total)
        if max_reviews is not None and current_count >= max_reviews:
            break
        if current_count <= previous_count and current_total <= previous_total:
            stable_rounds += 1
        else:
            stable_rounds = 0
        previous_count = max(previous_count, current_count)
        previous_total = max(previous_total, current_total)
        if stable_rounds >= config.stable_rounds_to_stop:
            break
    return rounds_completed


def _sync_capture_current_rendered_reviews(
    page: Any,
    source_url: str,
    marketplace: str,
    rendered_scroll_reviews: list[CollectedReview],
) -> None:
    """Accumulate rendered review blocks during sync virtualized scrolling."""
    try:
        parsed = parse_reviews_from_html(html=page.content(), source_url=source_url)
    except Exception:
        return
    records = [
        CollectedReview(
            source_url=row.get("source_url", source_url),
            marketplace=marketplace,
            author=normalize_whitespace(str(row.get("author", ""))),
            title=normalize_whitespace(str(row.get("title", ""))),
            rating=float(row.get("rating", 0.0) or 0.0),
            date=normalize_whitespace(str(row.get("date", ""))),
            review_text=normalize_whitespace(str(row.get("review_text", ""))),
            photos_count=0,
        )
        for row in parsed
    ]
    rendered_scroll_reviews[:] = _deduplicate_collected_reviews([*rendered_scroll_reviews, *records])


def _sync_click_show_more_if_available(page: Any, adapter: MarketplaceAdapter, helper: ReviewCollector, config: ReviewCollectorConfig) -> bool:
    """Click show-more controls in sync mode."""
    for selector in helper._merged_selectors(adapter.show_more_selectors, helper.show_more_selectors):
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible(timeout=800):
                locator.scroll_into_view_if_needed(timeout=3000)
                _sync_polite_pause(config)
                locator.click(timeout=3000)
                return True
        except Exception:
            continue
    return False


def _sync_scroll_last_review_into_view(page: Any, adapter: MarketplaceAdapter, helper: ReviewCollector, config: ReviewCollectorConfig) -> bool:
    """Scroll to last rendered review in sync mode."""
    for selector in helper._merged_selectors(adapter.review_container_selectors, helper.review_container_selectors):
        try:
            locator = page.locator(selector)
            count = locator.count()
            if count > 0:
                locator.nth(count - 1).scroll_into_view_if_needed(timeout=3000)
                _sync_polite_pause(config)
                return True
        except Exception:
            continue
    return False


def _sync_wait_for_dynamic_content(page: Any, helper: ReviewCollector, config: ReviewCollectorConfig) -> None:
    """Wait for network/spinner updates in sync mode."""
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    for selector in helper.spinner_selectors:
        try:
            spinner = page.locator(selector).first
            if spinner.count():
                spinner.wait_for(state="hidden", timeout=5000)
        except Exception:
            continue
    _sync_polite_pause(config)


def _sync_smooth_scroll(page: Any, config: ReviewCollectorConfig) -> None:
    """Gradual sync scrolling."""
    steps = random.randint(4, 7)
    base_delta = random.randint(420, 720)
    for index in range(steps):
        easing = 0.5 - 0.5 * np_cos(index / max(1, steps - 1) * 3.14159)
        page.mouse.wheel(0, int(base_delta * (0.65 + easing)))
        page.wait_for_timeout(random.randint(180, 420))
    _sync_polite_pause(config)


def _sync_review_count(page: Any, adapter: MarketplaceAdapter, helper: ReviewCollector) -> int:
    """Count review-like blocks in sync mode."""
    counts = []
    for selector in helper._merged_selectors(adapter.review_container_selectors, helper.review_container_selectors):
        try:
            counts.append(page.locator(selector).count())
        except Exception:
            continue
    return max(counts or [0])


def _sync_detect_access_barrier(page: Any, http_statuses: list[int]) -> None:
    """Stop on visible captcha/access barriers in sync mode."""
    try:
        body_text = page.locator("body").inner_text(timeout=3000).lower()
    except Exception:
        return
    if any(marker in body_text for marker in ReviewCollector.captcha_markers):
        raise CaptchaRequired("Robot verification page detected. Collection stopped by ethical policy.")
    if any(marker in body_text for marker in ReviewCollector.access_markers):
        raise AccessLimited("Access limitation message detected on the page.")


def _sync_extract_spa_state_reviews(page: Any, source_url: str, marketplace: str) -> list[CollectedReview]:
    """Extract review-like data from embedded SPA state in sync mode."""
    try:
        script_payloads = page.evaluate(
            """() => Array.from(document.scripts)
                .map((script) => script.textContent || '')
                .filter((text) => text.includes('review') || text.includes('feedback') || text.includes('comment'))
                .slice(0, 40)
            """
        )
    except Exception:
        return []
    records: list[CollectedReview] = []
    for payload in script_payloads:
        for json_payload in _extract_json_objects_from_text(str(payload)):
            records.extend(_reviews_from_payload(json_payload, source_url, marketplace))
    return _deduplicate_collected_reviews(records)


def _sync_polite_pause(config: ReviewCollectorConfig) -> None:
    """Apply sync delay between user-like actions."""
    import time

    time.sleep(random.randint(config.action_delay_min_ms, config.action_delay_max_ms) / 1000.0)


def _deduplicate_collected_reviews(reviews: list[CollectedReview]) -> list[CollectedReview]:
    """Deduplicate reviews from DOM, SPA state, and network responses."""
    deduplicated: list[CollectedReview] = []
    seen: set[str] = set()
    for review in reviews:
        text = normalize_whitespace(review.review_text)
        if len(text) < 15:
            continue
        if float(review.rating or 0.0) <= 0.0 and _looks_like_product_variant_text(text):
            continue
        key = f"{review.author.lower()}::{text.lower()[:240]}"
        if key in seen:
            continue
        seen.add(key)
        review.review_text = text
        deduplicated.append(review)
    return deduplicated


def _reviews_from_payload(payload: Any, source_url: str, marketplace: str) -> list[CollectedReview]:
    """Recursively extract review-like dictionaries from JSON payloads."""
    records: list[CollectedReview] = []
    for node in _walk_json(payload):
        if not isinstance(node, dict):
            continue
        record = _review_from_dict(node, source_url, marketplace)
        if record is not None:
            records.append(record)
    return _deduplicate_collected_reviews(records)


def _review_from_dict(node: dict[str, Any], source_url: str, marketplace: str) -> CollectedReview | None:
    """Convert a review-like JSON object into a normalized record."""
    text_parts = [
        _stringify_review_text_value(
            _get_first_value(node, ["review_text", "reviewText", "text", "comment", "content", "message", "feedbackText"])
        ),
        _stringify_review_text_value(_get_first_value(node, ["pros", "advantages", "positiveText", "positive"])),
        _stringify_review_text_value(_get_first_value(node, ["cons", "disadvantages", "negativeText", "negative"])),
    ]
    text = normalize_whitespace(". ".join(part for part in text_parts if part))
    if len(text) < 15:
        return None

    rating = _coerce_float(_get_first_value(node, ["rating", "rate", "stars", "valuation", "grade", "score"]))
    author = _get_first_value(
        node,
        ["author", "authorName", "userName", "username", "nickname", "customerName", "buyerName", "name"],
    )
    if isinstance(author, dict):
        author = _get_first_value(author, ["name", "nickname", "userName", "displayName"])
    author = normalize_whitespace(str(author or ""))
    date = normalize_whitespace(str(_get_first_value(node, ["date", "createdAt", "created_at", "publishedAt", "time"]) or ""))

    normalized_keys = {_normalize_key(key) for key in node.keys()}
    review_markers = {
        "review",
        "reviewtext",
        "feedback",
        "feedbacktext",
        "comment",
        "evaluation",
        "evaluationid",
        "buyername",
        "customername",
    }
    if rating <= 0.0 and not author and not date and not (normalized_keys & review_markers):
        return None
    if rating <= 0.0 and _looks_like_product_variant_text(text):
        return None

    photos = _get_first_value(node, ["photos", "images", "media", "pictures"])
    photos_count = len(photos) if isinstance(photos, list) else 0

    return CollectedReview(
        source_url=source_url,
        marketplace=marketplace,
        author=author,
        title=normalize_whitespace(str(_get_first_value(node, ["title", "subject", "summary"]) or "")),
        rating=float(rating or 0.0),
        date=date,
        review_text=text,
        photos_count=photos_count,
    )


def _walk_json(payload: Any):
    """Yield every node from a nested JSON structure."""
    yield payload
    if isinstance(payload, dict):
        for value in payload.values():
            yield from _walk_json(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk_json(item)


def _get_first_value(node: dict[str, Any], keys: list[str]) -> Any:
    """Return the first value matching one of several common key names."""
    normalized = {_normalize_key(key): value for key, value in node.items()}
    for key in keys:
        value = normalized.get(_normalize_key(key))
        if value not in (None, ""):
            return value
    return ""


def _stringify_review_text_value(value: Any) -> str:
    """Convert marketplace review text values into a clean string."""
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return normalize_whitespace(value)
    if isinstance(value, (int, float)):
        return normalize_whitespace(str(value))
    if isinstance(value, list):
        parts = [_stringify_review_text_value(item) for item in value]
        return normalize_whitespace(". ".join(part for part in parts if part))
    if isinstance(value, dict):
        preferred_keys = [
            "text",
            "content",
            "message",
            "value",
            "title",
            "body",
            "translation",
            "original",
        ]
        parts = [_stringify_review_text_value(_get_first_value(value, preferred_keys))]
        if not any(parts):
            parts = [_stringify_review_text_value(item) for item in value.values()]
        return normalize_whitespace(". ".join(part for part in parts if part))
    return normalize_whitespace(str(value))


def _normalize_key(value: str) -> str:
    """Normalize JSON keys for loose marketplace matching."""
    return "".join(char.lower() for char in str(value) if char.isalnum())


def _coerce_float(value: Any) -> float:
    """Safely convert values like '5 stars' or 4.5 into float."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").replace(",", ".")
    number = ""
    for char in text:
        if char.isdigit() or char == ".":
            number += char
        elif number:
            break
    try:
        return float(number) if number else 0.0
    except ValueError:
        return 0.0


def _looks_like_product_variant_text(text: str) -> bool:
    """Filter SKU/price/stock fragments that can appear in marketplace JSON."""
    lowered = normalize_whitespace(text).lower()
    variant_markers = [
        "осталось",
        "шт.",
        "₽",
        "china mainland",
        "mainland",
        "light blue",
        "dark blue",
        "black",
        "white",
        "blue",
        "china",
        "sku",
        "размер",
        "size",
    ]
    return any(marker in lowered for marker in variant_markers) or ("|" in lowered and len(lowered.split()) <= 8)


def _extract_json_objects_from_text(text: str) -> list[Any]:
    """Best-effort extraction of JSON from embedded SPA script tags."""
    stripped = text.strip()
    if not stripped:
        return []
    candidates = []
    if stripped.startswith("{") or stripped.startswith("["):
        candidates.append(stripped)
    for marker in ("window.__INITIAL_STATE__=", "window.__NUXT__=", "window.__APOLLO_STATE__="):
        if marker in stripped:
            candidate = stripped.split(marker, 1)[1].split("</script>", 1)[0].strip().rstrip(";")
            candidates.append(candidate)

    parsed: list[Any] = []
    for candidate in candidates[:5]:
        try:
            parsed.append(json.loads(candidate))
        except Exception:
            continue
    return parsed


def np_cos(value: float) -> float:
    """Small cosine helper to avoid adding NumPy as a hard dependency here."""
    import math

    return math.cos(value)
