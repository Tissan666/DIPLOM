"""Collect public product reviews through a regular Playwright browser session."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from review_scraper_detector.review_collector import (
    ReviewCollector,
    ReviewCollectorConfig,
    _is_transient_navigation_error,
    collect_reviews_sync,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the educational collector."""
    parser = argparse.ArgumentParser(description="Collect publicly visible product reviews with Playwright.")
    parser.add_argument("url", help="Product page URL.")
    parser.add_argument("--marketplace", default="generic", help="Marketplace name for exported records.")
    parser.add_argument("--headless", action="store_true", help="Run Chromium in headless mode.")
    parser.add_argument("--max-reviews", type=int, default=None, help="Optional max number of reviews to collect.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs") / "collected_reviews")
    parser.add_argument("--locale", default="ru-RU")
    parser.add_argument("--timezone", default="Europe/Samara")
    parser.add_argument(
        "--navigation-budget-ms",
        type=int,
        default=180000,
        help="Maximum time budget for opening URL variants before giving up.",
    )
    return parser.parse_args()


def is_async_playwright_runtime_error(message: str) -> bool:
    """Detect async Playwright driver issues where sync Playwright still works."""
    lower_message = message.lower()
    return any(
        marker in lower_message
        for marker in (
            "permissionerror",
            "winerror 5",
            "access is denied",
            "отказано в доступе",
            "connection closed while reading from the driver",
        )
    )


def build_config(args: argparse.Namespace, headless: bool | None = None) -> ReviewCollectorConfig:
    """Build collector config from CLI arguments."""
    return ReviewCollectorConfig(
        headless=args.headless if headless is None else headless,
        locale=args.locale,
        timezone_id=args.timezone,
        navigation_retry_budget_ms=args.navigation_budget_ms,
        output_dir=args.output_dir,
    )


async def run_async_collection(args: argparse.Namespace, config: ReviewCollectorConfig):
    """Run one async collection job."""
    async with ReviewCollector(config) as collector:
        return await collector.collect(
            url=args.url,
            marketplace=args.marketplace,
            max_reviews=args.max_reviews,
        )


def print_result(result: object, output_dir: Path) -> None:
    """Print a compact result for the terminal."""
    print(f"Status: {result.status}")
    print(f"Message: {result.message}")
    print(f"Reviews collected: {len(result.reviews)}")
    print(f"Output directory: {output_dir}")


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    config = build_config(args)

    try:
        result = asyncio.run(run_async_collection(args, config))
    except PermissionError:
        result = collect_reviews_sync(
            url=args.url,
            marketplace=args.marketplace,
            max_reviews=args.max_reviews,
            config=config,
        )
    except Exception as exc:
        if is_async_playwright_runtime_error(str(exc)):
            result = collect_reviews_sync(
                url=args.url,
                marketplace=args.marketplace,
                max_reviews=args.max_reviews,
                config=config,
            )
        elif args.headless and _is_transient_navigation_error(exc):
            print(f"Headless navigation was unstable; retrying once in visible Chromium: {exc}")
            headed_config = build_config(args, headless=False)
            result = collect_reviews_sync(
                url=args.url,
                marketplace=args.marketplace,
                max_reviews=args.max_reviews,
                config=headed_config,
            )
        else:
            raise

    print_result(result, args.output_dir)


if __name__ == "__main__":
    main()
