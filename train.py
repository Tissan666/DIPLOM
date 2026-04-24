"""Train the suspicious review text classifier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fake_rating_detector.pipeline import train_anomaly_detector
from fake_rating_detector.sample_data import create_sample_dataset as create_ratings_sample_dataset
from review_scraper_detector.dataset_builder import (
    DEFAULT_AMAZON_ZIP,
    DEFAULT_AMAZON_REVIEWS_2023_CONFIG,
    DEFAULT_AMAZON_REVIEWS_2023_REPO,
    DEFAULT_GRAMMAR_ZIP,
    DEFAULT_RECIPE_ZIP,
    DEFAULT_TURKISH_ZIP,
    DEFAULT_YELP_OPEN_REVIEW_JSON,
    DEFAULT_YELPNYC_PATH,
    build_combined_training_dataset,
)
from review_scraper_detector.sample_data import create_sample_review_dataset
from review_scraper_detector.training import train_review_classifier
from review_scraper_detector.utils import save_json


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for training."""
    parser = argparse.ArgumentParser(description="Train the suspicious review classifier.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data") / "combined_review_training.csv",
        help="Path to the training CSV that will be generated or reused.",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("models"),
        help="Directory where trained model artifacts will be written.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory where metrics and summaries will be saved.",
    )
    parser.add_argument("--epochs", type=int, default=12, help="Number of training epochs.")
    parser.add_argument("--batch-size", type=int, default=32, help="Training batch size.")
    parser.add_argument("--learning-rate", type=float, default=1e-3, help="Adam learning rate.")
    parser.add_argument("--test-size", type=float, default=0.2, help="Test split fraction.")
    parser.add_argument("--validation-size", type=float, default=0.15, help="Validation split fraction.")
    parser.add_argument("--calibration-size", type=float, default=0.1, help="Calibration split fraction for the hybrid combiner.")
    parser.add_argument("--ratings-epochs", type=int, default=24, help="Number of epochs for the rating-behavior Autoencoder.")
    parser.add_argument("--ratings-batch-size", type=int, default=64, help="Batch size for the rating-behavior Autoencoder.")
    parser.add_argument("--ratings-learning-rate", type=float, default=1e-3, help="Learning rate for the rating-behavior Autoencoder.")
    parser.add_argument("--ratings-text-embedding-dim", type=int, default=24, help="Dense semantic text dimensions for the records model.")
    parser.add_argument("--ratings-text-max-features", type=int, default=2500, help="Maximum word n-gram TF-IDF features for the records text branch.")
    parser.add_argument("--ratings-text-char-max-features", type=int, default=900, help="Maximum char n-gram TF-IDF features for the records text branch.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--sample-size", type=int, default=800, help="Rows in synthetic demo dataset.")
    parser.add_argument("--ratings-sample-size", type=int, default=1500, help="Rows in the synthetic rating-manipulation dataset.")
    parser.add_argument(
        "--ratings-dataset",
        type=Path,
        default=Path("data") / "sample_ratings.csv",
        help="Path to the structured rating dataset used by the behavior model.",
    )
    parser.add_argument(
        "--skip-ratings-model",
        action="store_true",
        help="Skip training the rating-behavior Autoencoder.",
    )
    parser.add_argument(
        "--no-external-data",
        action="store_true",
        help="Disable ZIP/UCI ingestion and train only on the synthetic fallback dataset.",
    )
    parser.add_argument(
        "--skip-uci",
        action="store_true",
        help="Skip the UCI datasets even when external-data mode is enabled.",
    )
    parser.add_argument(
        "--max-rows-per-source",
        type=int,
        default=2000,
        help="Maximum rows to keep from each external source before balancing.",
    )
    parser.add_argument(
        "--synthetic-ratio",
        type=float,
        default=1.0,
        help="How many suspicious synthetic rows to generate relative to the authentic-review count.",
    )
    parser.add_argument(
        "--review-max-features",
        type=int,
        default=5000,
        help="Maximum TF-IDF features for the review neural classifier. Lower values use less RAM.",
    )
    parser.add_argument(
        "--review-char-max-features",
        type=int,
        default=0,
        help="Optional character n-gram TF-IDF features for template/repetition detection.",
    )
    parser.add_argument(
        "--review-hidden-dims",
        type=str,
        default="512,128",
        help="Comma-separated hidden layer sizes for the review neural classifier.",
    )
    parser.add_argument(
        "--review-dropout",
        type=float,
        default=0.25,
        help="Dropout for the review neural classifier.",
    )
    parser.add_argument(
        "--include-large-public-data",
        action="store_true",
        help="Enable Amazon Reviews 2023, Yelp Open Dataset, and YelpNYC loaders.",
    )
    parser.add_argument(
        "--large-max-rows-per-source",
        type=int,
        default=None,
        help="Rows to keep from each large public source. Defaults to --max-rows-per-source.",
    )
    parser.add_argument(
        "--amazon-reviews-2023-repo",
        type=str,
        default=DEFAULT_AMAZON_REVIEWS_2023_REPO,
        help="Hugging Face dataset repo for Amazon Reviews 2023.",
    )
    parser.add_argument(
        "--amazon-reviews-2023-config",
        type=str,
        default=DEFAULT_AMAZON_REVIEWS_2023_CONFIG,
        help="Hugging Face config/subset for Amazon Reviews 2023, e.g. raw_review_All_Beauty.",
    )
    parser.add_argument(
        "--amazon-reviews-2023-split",
        type=str,
        default="full",
        help="Hugging Face split for Amazon Reviews 2023.",
    )
    parser.add_argument(
        "--yelp-open-review-json",
        type=Path,
        default=DEFAULT_YELP_OPEN_REVIEW_JSON,
        help="Path to yelp_academic_dataset_review.json/json.gz/zip.",
    )
    parser.add_argument(
        "--yelpnyc-path",
        type=Path,
        default=DEFAULT_YELPNYC_PATH,
        help="Path to labeled YelpNYC CSV/JSON/ZIP after receiving/downloading it.",
    )
    parser.add_argument(
        "--grammar-zip",
        type=Path,
        default=DEFAULT_GRAMMAR_ZIP,
        help="Path to GrammarandProductReviews.zip.",
    )
    parser.add_argument(
        "--recipe-zip",
        type=Path,
        default=DEFAULT_RECIPE_ZIP,
        help="Path to recipe+reviews+and+user+feedback+dataset.zip.",
    )
    parser.add_argument(
        "--turkish-zip",
        type=Path,
        default=DEFAULT_TURKISH_ZIP,
        help="Path to turkish+user+review+dataset.zip.",
    )
    parser.add_argument(
        "--amazon-zip",
        type=Path,
        default=DEFAULT_AMAZON_ZIP,
        help="Path to amazon+commerce+reviews+set.zip.",
    )
    parser.add_argument(
        "--regenerate-sample",
        action="store_true",
        help="Force recreation of the demo training dataset.",
    )
    return parser.parse_args()


def parse_hidden_dims(raw_value: str) -> list[int]:
    """Parse comma-separated hidden dimensions from CLI."""
    dims = [int(part.strip()) for part in raw_value.split(",") if part.strip()]
    if not dims:
        raise ValueError("--review-hidden-dims must contain at least one integer.")
    return dims


def main() -> None:
    """Optionally create a sample dataset and train the classifier."""
    args = parse_args()
    dataset_build_report: dict | None = None

    if not args.no_external_data:
        dataset_df, dataset_build_report = build_combined_training_dataset(
            output_path=args.dataset,
            seed=args.seed,
            max_rows_per_source=args.max_rows_per_source,
            synthetic_ratio=args.synthetic_ratio,
            include_uci=not args.skip_uci,
            include_large_public_data=args.include_large_public_data,
            large_max_rows_per_source=args.large_max_rows_per_source,
            amazon_reviews_2023_repo=args.amazon_reviews_2023_repo,
            amazon_reviews_2023_config=args.amazon_reviews_2023_config,
            amazon_reviews_2023_split=args.amazon_reviews_2023_split,
            yelp_open_review_json=args.yelp_open_review_json,
            yelpnyc_path=args.yelpnyc_path,
            grammar_zip=args.grammar_zip,
            recipe_zip=args.recipe_zip,
            turkish_zip=args.turkish_zip,
            amazon_zip=args.amazon_zip,
        )
        print(f"Combined training dataset created at: {args.dataset} ({len(dataset_df)} rows)")
    elif args.regenerate_sample or not args.dataset.exists():
        create_sample_review_dataset(args.dataset, n_samples=args.sample_size, seed=args.seed)
        print(f"Sample review dataset created at: {args.dataset}")

    review_summary = train_review_classifier(
        dataset_path=args.dataset,
        artifacts_dir=args.artifacts_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        test_size=args.test_size,
        validation_size=args.validation_size,
        calibration_size=args.calibration_size,
        random_state=args.seed,
        max_features=args.review_max_features,
        char_max_features=args.review_char_max_features,
        hidden_dims=parse_hidden_dims(args.review_hidden_dims),
        dropout=args.review_dropout,
    )
    if dataset_build_report is not None:
        review_summary["dataset_build"] = dataset_build_report
        save_json(review_summary, args.output_dir / "review_training_summary.json")

    rating_summary: dict | None = None
    if not args.skip_ratings_model:
        if args.regenerate_sample or not args.ratings_dataset.exists():
            create_ratings_sample_dataset(
                output_path=args.ratings_dataset,
                n_records=args.ratings_sample_size,
                seed=args.seed,
            )
            print(f"Sample rating dataset created at: {args.ratings_dataset}")

        rating_summary = train_anomaly_detector(
            dataset_path=args.ratings_dataset,
            artifacts_dir=args.artifacts_dir,
            output_dir=args.output_dir,
            epochs=args.ratings_epochs,
            batch_size=args.ratings_batch_size,
            learning_rate=args.ratings_learning_rate,
            test_size=args.test_size,
            validation_size=args.validation_size,
            text_embedding_dim=args.ratings_text_embedding_dim,
            text_max_features=args.ratings_text_max_features,
            text_char_max_features=args.ratings_text_char_max_features,
            random_state=args.seed,
        )

    summary = {
        "review_text_model": review_summary,
        "rating_behavior_model": rating_summary,
    }
    save_json(summary, args.output_dir / "system_training_summary.json")

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
