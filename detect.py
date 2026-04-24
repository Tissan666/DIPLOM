"""Analyze product reviews from a URL or local HTML file."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from fake_rating_detector.data_loader import prepare_ratings_dataframe
from fake_rating_detector.inference import predict_dataframe
from review_scraper_detector.inference import analyze_html_document, analyze_product_url
from review_scraper_detector.scraping import DEFAULT_WAIT_MS
from review_scraper_detector.utils import save_json


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for review analysis."""
    parser = argparse.ArgumentParser(description="Scrape product reviews and detect suspicious texts.")
    parser.add_argument(
        "url",
        nargs="?",
        help="Product page URL to fetch and analyze.",
    )
    parser.add_argument(
        "--html-file",
        type=Path,
        help="Optional local HTML file for offline parsing tests.",
    )
    parser.add_argument(
        "--ratings-file",
        type=Path,
        help="Optional CSV file with site ratings for full manipulation detection.",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("models"),
        help="Directory containing the trained review model artifacts.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Optional ScrapingBee API key. If omitted, the app uses SCRAPINGBEE_API_KEY.",
    )
    parser.add_argument(
        "--country-code",
        type=str,
        default=None,
        help="Optional ScrapingBee premium proxy country code, for example `us`.",
    )
    parser.add_argument(
        "--wait-ms",
        type=int,
        default=DEFAULT_WAIT_MS,
        help="Extra waiting time in milliseconds for rendered pages.",
    )
    parser.add_argument(
        "--scroll-rounds",
        type=int,
        default=24,
        help="ScrapingBee deep-scroll rounds before parsing rendered HTML.",
    )
    parser.add_argument(
        "--scroll-delay-ms",
        type=int,
        default=1200,
        help="Delay between ScrapingBee deep-scroll rounds.",
    )
    parser.add_argument(
        "--disable-js",
        action="store_true",
        help="Disable JavaScript rendering when requesting the page through ScrapingBee.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs") / "scraped_review_predictions.json",
        help="Path to save the JSON analysis result.",
    )
    return parser.parse_args()


def main() -> None:
    """Run review scraping and suspicious review detection from the terminal."""
    args = parse_args()

    if not args.url and not args.html_file and not args.ratings_file:
        raise SystemExit("Provide a product URL, `--html-file`, or `--ratings-file`.")

    if args.ratings_file:
        ratings_df = pd.read_csv(args.ratings_file)
        prepared_ratings_df = prepare_ratings_dataframe(ratings_df)
        result = predict_dataframe(prepared_ratings_df, artifacts_dir=args.artifacts_dir)
        save_json(result, args.output)
        _print_ratings_report(result)
        print(f"\nFull JSON report saved to: {args.output}")
        return

    if args.html_file:
        html = args.html_file.read_text(encoding="utf-8")
        source_url = args.url or f"file://{args.html_file.resolve()}"
        result = analyze_html_document(
            html=html,
            source_url=source_url,
            artifacts_dir=args.artifacts_dir,
            source_type="html_file",
        )
    else:
        result = analyze_product_url(
            product_url=args.url,
            artifacts_dir=args.artifacts_dir,
            api_key=args.api_key,
            render_js=not args.disable_js,
            country_code=args.country_code,
            wait_ms=args.wait_ms,
            scroll_rounds=args.scroll_rounds,
            scroll_delay_ms=args.scroll_delay_ms,
        )

    save_json(result, args.output)
    _print_console_report(result)
    print(f"\nFull JSON report saved to: {args.output}")


def _print_console_report(result: dict) -> None:
    """Print suspicious reviews in a human-friendly console format."""
    request_meta = result.get("request", {})
    summary = result.get("summary", {})
    reviews = result.get("reviews", [])

    print("=== Review Analysis Summary ===")
    print(f"Source URL: {request_meta.get('source_url', summary.get('source_url', 'unknown'))}")
    print(f"Source site: {request_meta.get('source_site', summary.get('source_site', 'unknown'))}")
    print(f"Source type: {request_meta.get('source_type', summary.get('source_type', 'unknown'))}")
    print(f"Total reviews: {summary.get('total_reviews', 0)}")
    print(f"Suspicious reviews: {summary.get('suspicious_reviews', 0)}")
    print(f"Average probability: {summary.get('average_probability', 0):.3f}")
    print(f"Threshold: {summary.get('threshold', 'n/a')}")

    suspicious_reviews = [review for review in reviews if review.get("is_suspicious") == 1]
    if not suspicious_reviews:
        print("\nNo suspicious reviews were detected.")
        return

    print("\n=== Suspicious Reviews ===")
    for review in sorted(suspicious_reviews, key=lambda row: row.get("suspicious_probability", 0), reverse=True):
        print(f"\n[#{review.get('review_id', '?')}] Probability: {review.get('suspicious_probability', 0):.3f}")
        print(f"Risk level: {review.get('risk_level', 'unknown')}")
        print(f"Author: {review.get('author', '') or 'unknown'}")
        print(f"Rating: {review.get('rating', 0)}")
        print(f"Title: {review.get('title', '')}")
        print(f"Text: {review.get('review_text', '')}")
        reasons = review.get("suspicion_reasons", [])
        if reasons:
            print("Reasons:")
            for reason in reasons:
                print(f"  - {reason}")


def _print_ratings_report(result: dict) -> None:
    """Print suspicious ratings and users from the full site anti-fraud model."""
    summary = result.get("summary", {})
    predictions = result.get("predictions", [])
    suspicious_users = result.get("suspicious_users", [])

    print("=== Site Rating Manipulation Summary ===")
    print(f"Total records: {summary.get('total_records', 0)}")
    print(f"Suspicious ratings: {summary.get('suspicious_ratings', 0)}")
    print(f"Suspicious users: {summary.get('suspicious_users', 0)}")
    print(f"Threshold: {summary.get('threshold', 'n/a')}")

    suspicious_predictions = [row for row in predictions if row.get("is_suspicious") == 1]
    if suspicious_predictions:
        print("\n=== Top Suspicious Ratings ===")
        for row in sorted(suspicious_predictions, key=lambda item: item.get("anomaly_score", 0), reverse=True)[:8]:
            print(
                f"\nUser {row.get('user_id')} -> item {row.get('item_id')} | "
                f"rating {row.get('rating')} | anomaly {row.get('anomaly_score', 0):.3f}"
            )
            reasons = row.get("suspicion_reasons", [])
            if reasons:
                print("Reasons:")
                for reason in reasons:
                    print(f"  - {reason}")

    if suspicious_users:
        print("\n=== Suspicious Users ===")
        for user_row in suspicious_users[:8]:
            print(
                f"{user_row.get('user_id')}: {user_row.get('suspicious_ratings')} suspicious ratings, "
                f"avg anomaly {user_row.get('average_anomaly_score', 0):.3f}"
            )


if __name__ == "__main__":
    main()
