"""Run backend-only smoke checks for the review integrity API."""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app import app
from fake_rating_detector.data_loader import prepare_ratings_dataframe
from fake_rating_detector.explanations import derive_suspicion_reasons
from fake_rating_detector.features import FeatureEngineeringPipeline
from review_scraper_detector.abstention import apply_review_abstention_policy
from review_scraper_detector import scraping
from review_scraper_detector.ai_text_signals import _score_ai_text
from review_scraper_detector.image_ocr_signals import _score_ocr_text
from review_scraper_detector.marketplace_api import _marketplace_from_url, collect_reviews_via_public_marketplace_api
from review_scraper_detector.parsing import parse_reviews_from_html
from review_scraper_detector.review_collector import (
    CollectedReview,
    CollectionResult,
    _records_from_rendered_card_payloads,
    _reviews_from_payload,
    amazon_product_url,
    amazon_review_url,
)

ROOT_DIR = Path(__file__).resolve().parent
SAMPLE_HTML_PATH = ROOT_DIR / "examples" / "sample_product_reviews.html"
SAMPLE_RATINGS_PATH = ROOT_DIR / "data" / "sample_ratings.csv"
SMOKE_HISTORY_PATH = ROOT_DIR / "outputs" / "backend_smoke_history.sqlite3"


def _print_step(name: str) -> None:
    print(f"\n== {name} ==", flush=True)


def _fail(message: str) -> int:
    print(f"FAIL: {message}", flush=True)
    return 1


def _read_sample_records(limit: int = 40) -> list[dict]:
    with SAMPLE_RATINGS_PATH.open("r", encoding="utf-8", newline="") as file:
        return [row for index, row in enumerate(csv.DictReader(file)) if index < limit]


def _expect_json_response(response, expected_status: int, expected_error_code: str | None = None) -> tuple[int, dict]:
    data = response.get_json(silent=True)
    if response.status_code != expected_status:
        return _fail(f"Expected HTTP {expected_status}, got {response.status_code}: {response.get_data(as_text=True)}"), {}
    if not isinstance(data, dict):
        return _fail("Expected a JSON object response."), {}
    if expected_error_code and data.get("error_code") != expected_error_code:
        return _fail(f"Expected error_code={expected_error_code}, got {data.get('error_code')}."), data
    return 0, data


def check_health(client) -> int:
    _print_step("Health")
    status, data = _expect_json_response(client.get("/health"), 200)
    if status:
        return status
    if not data.get("artifacts_ready"):
        return _fail("Model artifacts are not ready. Run training before backend smoke checks.")
    if not data.get("review_artifacts_compatible") or not data.get("rating_artifacts_compatible"):
        return _fail("Model artifacts exist but are not compatible with the current backend code.")
    if "scrapedo_configured" not in data:
        return _fail("Health response does not include Scrape.do fallback configuration status.")

    vision = data.get("vision_capabilities")
    if not isinstance(vision, dict):
        return _fail("Health response does not include vision capability diagnostics.")
    text_capabilities = data.get("text_capabilities")
    if not isinstance(text_capabilities, dict) or "ai_text" not in text_capabilities:
        return _fail("Health response does not include AI-text capability diagnostics.")
    ocr_status = vision.get("ocr")
    alignment_status = vision.get("image_alignment")
    if not isinstance(ocr_status, dict) or not isinstance(alignment_status, dict):
        return _fail("Vision capability diagnostics should include OCR and image alignment objects.")

    expected_ocr_statuses = {"disabled", "not_configured", "engine_unavailable", "ready"}
    expected_alignment_statuses = {"disabled", "not_configured", "dependencies_ready", "model_unavailable", "ready"}
    if ocr_status.get("status") not in expected_ocr_statuses:
        return _fail(f"Unexpected OCR capability status: {ocr_status.get('status')}.")
    if alignment_status.get("status") not in expected_alignment_statuses:
        return _fail(f"Unexpected image alignment capability status: {alignment_status.get('status')}.")

    print(
        "OK: artifacts are ready. "
        f"OCR={ocr_status.get('status')}; image_alignment={alignment_status.get('status')}; "
        f"ai_text={text_capabilities.get('ai_text', {}).get('status')}.",
        flush=True,
    )
    return 0


def check_validation(client) -> int:
    _print_step("Input validation")

    checks = [
        ({}, "INPUT_SOURCE_MISSING"),
        ({"url": "example.com/product"}, "INVALID_URL"),
        ({"records": []}, "INVALID_INPUT"),
        ({"url": "https://example.com/product", "html": "<html></html>"}, "INPUT_SOURCE_AMBIGUOUS"),
    ]

    for payload, expected_code in checks:
        status, _data = _expect_json_response(client.post("/api/predict", json=payload), 400, expected_code)
        if status:
            return status

    print("OK: validation errors are stable.", flush=True)
    return 0


def check_optional_ip_records(client) -> int:
    _print_step("Optional IP records")

    missing_ip_records = [
        {
            "user_id": f"user-{index}",
            "item_id": "sku-optional-ip",
            "rating": 5,
            "timestamp": f"2026-04-0{index + 1}",
            "review_text": f"Grounded customer note {index} with enough detail.",
            "geo_country": "RU",
        }
        for index in range(4)
    ]
    missing_ip_frame = prepare_ratings_dataframe(pd.DataFrame(missing_ip_records))
    if "ip_address" not in missing_ip_frame.columns:
        return _fail("Optional-IP records should be normalized with an ip_address column.")
    if missing_ip_frame["ip_address"].nunique() != len(missing_ip_frame):
        return _fail(f"Missing IP values should not collapse into one shared IP: {missing_ip_frame['ip_address'].tolist()}.")

    missing_ip_features = FeatureEngineeringPipeline(text_embedding_dim=0).fit_transform(missing_ip_frame)
    if missing_ip_features[["ip_rating_count", "ip_unique_users", "ip_ratings_last_1h"]].to_numpy().sum() != 0:
        return _fail("Missing IP values should not contribute to shared-IP or IP-burst features.")
    if any(
        "IP address" in reason or "short-term burst" in reason
        for reasons in derive_suspicion_reasons(missing_ip_features)
        for reason in reasons
    ):
        return _fail("Missing IP values should not create IP-related suspicion reasons.")

    shared_ip_records = [
        {
            "user_id": f"user-{index}",
            "item_id": "sku-shared-ip",
            "rating": 5,
            "timestamp": f"2026-04-01T00:{index}0:00",
            "review_text": f"Shared IP customer note {index} with enough detail.",
            "ip_address": "10.0.0.1",
            "geo_country": "RU",
        }
        for index in range(4)
    ]
    shared_ip_frame = prepare_ratings_dataframe(pd.DataFrame(shared_ip_records))
    shared_ip_features = FeatureEngineeringPipeline(text_embedding_dim=0).fit_transform(shared_ip_frame)
    if float(shared_ip_features["ip_unique_users"].max()) < 4:
        return _fail("Real shared IP values should still produce a multi-user IP signal.")
    if float(shared_ip_features["ip_ratings_last_1h"].max()) < 3:
        return _fail("Real shared IP values should still produce an hourly IP-burst signal.")

    print("OK: missing IP is neutral, while real shared IP remains detectable.", flush=True)
    return 0


def check_cyrillic_ocr_patterns(client) -> int:
    _print_step("Cyrillic OCR patterns")

    promo_signal = _score_ocr_text(
        "\u0421\u043a\u0438\u0434\u043a\u0430 20%, \u0430\u043a\u0446\u0438\u044f, "
        "\u0440\u0435\u043a\u043b\u0430\u043c\u0430, \u043e\u0444\u0438\u0446\u0438\u0430\u043b\u044c\u043d\u044b\u0439 "
        "\u043c\u0430\u0433\u0430\u0437\u0438\u043d",
        source_site="wildberries",
    )
    promo_labels = set(promo_signal.get("image_ocr_labels", []))
    if not {"sale_discount", "watermark_marker"}.issubset(promo_labels):
        return _fail(f"Cyrillic promo OCR labels were not detected: {sorted(promo_labels)}.")

    foreign_marketplace_signal = _score_ocr_text(
        "\u0412\u043e\u0434\u044f\u043d\u043e\u0439 \u0437\u043d\u0430\u043a \u041e\u0437\u043e\u043d",
        source_site="wildberries",
    )
    foreign_labels = set(foreign_marketplace_signal.get("image_ocr_labels", []))
    if "foreign_marketplace_watermark" not in foreign_labels:
        return _fail(f"Cyrillic foreign marketplace OCR label was not detected: {sorted(foreign_labels)}.")

    own_marketplace_signal = _score_ocr_text(
        "\u0412\u0411 \u0432\u0430\u0439\u043b\u0434\u0431\u0435\u0440\u0440\u0438\u0437",
        source_site="wildberries",
    )
    own_labels = set(own_marketplace_signal.get("image_ocr_labels", []))
    if "marketplace_text" not in own_labels or "foreign_marketplace_watermark" in own_labels:
        return _fail(f"Own marketplace OCR label should not be treated as foreign: {sorted(own_labels)}.")

    print("OK: Cyrillic OCR promo and marketplace labels are stable.", flush=True)
    return 0


def check_ai_text_patterns(client) -> int:
    _print_step("AI-text review signal")

    generated_signal = _score_ai_text(
        "Overall, this wireless charger delivers excellent quality and reliable performance \u2014 "
        "It is worth noting that the modern design, durable materials, and great value for money "
        "make it a perfect choice. In conclusion, I highly recommend it to anyone."
    )
    cliche_signal = _score_ai_text(
        "\u0426\u0435\u043d\u0430 \u0430\u0434\u0435\u043a\u0432\u0430\u0442\u043d\u0430\u044f \u2014 "
        "\u043d\u0435 \u0436\u0430\u043b\u043a\u043e \u043f\u043b\u0430\u0442\u0438\u0442\u044c "
        "\u0437\u0430 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442. "
        "\u0414\u043e\u0441\u0442\u0430\u0432\u043a\u0430/\u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430/"
        "\u0443\u043f\u0430\u043a\u043e\u0432\u043a\u0430 \u2014 "
        "\u043f\u0440\u0438\u044f\u0442\u043d\u043e \u0443\u0434\u0438\u0432\u0438\u043b\u0438."
    )
    structured_marketplace_signal = _score_ai_text(
        "\u0414\u043e\u0441\u0442\u043e\u0438\u043d\u0441\u0442\u0432\u0430: \u041e\u0440\u0438\u0433\u0438\u043d\u0430\u043b, "
        "\u043f\u043b\u043e\u043c\u0431\u044b \u043d\u0430 \u043c\u0435\u0441\u0442\u0435. "
        "\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043a\u0438: \u043d\u0435\u0442. "
        "\u041a\u043e\u043c\u043c\u0435\u043d\u0442\u0430\u0440\u0438\u0439: \u0434\u043e\u0441\u0442\u0430\u0432\u0438\u043b\u0438 "
        "\u0432 \u0441\u0440\u043e\u043a, \u0443\u043f\u0430\u043a\u043e\u0432\u043a\u0430 \u0446\u0435\u043b\u0430\u044f, "
        "\u0441\u0435\u0440\u0438\u0439\u043d\u044b\u0439 \u043d\u043e\u043c\u0435\u0440 \u043f\u0440\u043e\u0431\u0438\u043b\u0441\u044f."
    )
    grounded_signal = _score_ai_text(
        "\u0411\u0440\u0430\u043b \u043b\u0430\u043c\u043f\u0443 \u043d\u0430 \u0440\u0430\u0431\u043e\u0442\u0443 "
        "\u0432 \u0430\u043f\u0440\u0435\u043b\u0435. \u0427\u0435\u0440\u0435\u0437 10 \u0434\u043d\u0435\u0439 "
        "\u0437\u0430\u043c\u0435\u0442\u0438\u043b, \u0447\u0442\u043e \u043f\u0440\u043e\u0432\u043e\u0434 "
        "\u043a\u043e\u0440\u043e\u0442\u043a\u0438\u0439, \u043d\u043e \u0441\u0432\u0435\u0442\u0430 "
        "\u0445\u0432\u0430\u0442\u0430\u0435\u0442 \u0434\u043b\u044f \u0441\u0442\u043e\u043b\u0430."
    )

    if generated_signal["ai_text_score"] <= grounded_signal["ai_text_score"]:
        return _fail(
            "AI-text scorer should rank polished generic review text above concrete usage detail: "
            f"{generated_signal['ai_text_score']} <= {grounded_signal['ai_text_score']}."
        )
    if generated_signal["ai_text_label"] not in {"weak_ai_text_hint", "ai_text_signal", "likely_ai_text"}:
        return _fail(f"Unexpected AI-text label for generated-like sample: {generated_signal['ai_text_label']}.")
    if float(generated_signal.get("ai_text_feature_hits", {}).get("long_dash_density", 0.0)) <= 0:
        return _fail("AI-text scorer did not expose the long-dash punctuation feature.")
    if not any("long dash" in reason for reason in generated_signal.get("ai_text_reasons", [])):
        return _fail("AI-text scorer did not include the long-dash reason for generated-like punctuation.")
    if cliche_signal["ai_text_label"] not in {"ai_text_signal", "likely_ai_text"}:
        return _fail(f"Marketplace-cliche sample should be a clear AI-text signal: {cliche_signal['ai_text_label']}.")
    if not any("marketplace cliches" in reason for reason in cliche_signal.get("ai_text_reasons", [])):
        return _fail("AI-text scorer did not include the marketplace-cliche reason for compact AI-style comments.")
    if structured_marketplace_signal["ai_text_score"] >= cliche_signal["ai_text_score"]:
        return _fail(
            "Structured marketplace reviews with concrete purchase details should score below compact AI cliches: "
            f"{structured_marketplace_signal['ai_text_score']} >= {cliche_signal['ai_text_score']}."
        )

    print(
        "OK: AI-text scorer separates generic polished wording, compact marketplace cliches, and long-dash punctuation from grounded customer detail.",
        flush=True,
    )
    return 0


def check_import_source_proxy(client) -> int:
    _print_step("Import source proxy")

    class FakeImportResponse:
        status_code = 200
        headers = {"content-type": "application/json"}

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int = 65536):
            yield b'{"records":[{"item_id":"sku-1","user":"u1","rating":5,"timestamp":"2026-04-13","text":"proxy import ok"}]}'

    with patch("app.requests.get", return_value=FakeImportResponse()) as fetch_mock:
        response = client.post("/api/import-source", json={"url": "https://example.com/reviews.json"})

    if response.status_code != 200:
        return _fail(f"Import proxy should return HTTP 200, got {response.status_code}.")
    if "proxy import ok" not in response.get_data(as_text=True):
        return _fail("Import proxy did not return the fetched source body.")
    if fetch_mock.call_count != 1:
        return _fail("Import proxy should fetch the external source exactly once.")

    status, _data = _expect_json_response(
        client.post("/api/import-source", json={"url": "http://127.0.0.1/private.json"}),
        400,
        "INVALID_INPUT",
    )
    if status:
        return status

    print("OK: API/file import proxy fetches public sources and rejects local URLs.", flush=True)
    return 0


def check_scraping_fallback_chain(client) -> int:
    _print_step("Scraping provider fallback")
    with (
        patch(
            "review_scraper_detector.scraping.fetch_html_via_scrapingbee",
            side_effect=RuntimeError("ScrapingBee upstream fetch failed"),
        ) as scrapingbee_fetch,
        patch(
            "review_scraper_detector.scraping.fetch_html_via_scrapedo",
            return_value="<html><body>fallback ok</body></html>",
        ) as scrapedo_fetch,
    ):
        html = scraping.fetch_html_with_fallback(
            "https://example.com/product",
            scrapingbee_api_key="scrapingbee-test-key",
            scrapedo_api_key="scrapedo-test-key",
        )

    if "fallback ok" not in html:
        return _fail("Scrape.do fallback did not return the expected HTML.")
    if scrapingbee_fetch.call_count != 1 or scrapedo_fetch.call_count != 1:
        return _fail("Fallback chain should call ScrapingBee once and then Scrape.do once.")

    print("OK: Scrape.do is used when ScrapingBee fails.", flush=True)
    return 0


def _fake_collected_review(source_url: str, marketplace: str = "wildberries") -> CollectedReview:
    return CollectedReview(
        source_url=source_url,
        marketplace=marketplace,
        author="SmokeUser",
        title="",
        rating=5.0,
        date="2026-04-13",
        review_text="Smoke-check review text with enough concrete product detail for URL-mode analysis.",
        photos_count=0,
    )


def check_url_collection_order(client) -> int:
    _print_step("URL collection order")
    source_url = "https://wildberries.ru/catalog/123/detail.aspx?imtId=987654321"

    public_api_result = CollectionResult(
        status="success",
        source_url=source_url,
        marketplace="wildberries",
        reviews=[_fake_collected_review(source_url)],
        message="public api smoke success",
    )
    with (
        patch("review_scraper_detector.inference.collect_reviews_via_public_marketplace_api", return_value=public_api_result),
        patch("review_scraper_detector.inference.collect_reviews_sync") as playwright_mock,
        patch("review_scraper_detector.inference.fetch_html_with_fallback") as external_mock,
    ):
        response = client.post("/api/predict", json={"url": source_url})

    status, data = _expect_json_response(response, 200)
    if status:
        return status
    if playwright_mock.call_count or external_mock.call_count:
        return _fail("Public marketplace API success should stop before Playwright and external collectors.")
    if data.get("collection", {}).get("strategy") != "public_marketplace_api":
        return _fail("URL mode should report public_marketplace_api as the winning strategy.")

    unsupported_api_result = CollectionResult(
        status="unsupported",
        source_url=source_url,
        marketplace="wildberries",
        reviews=[],
        message="unsupported smoke",
    )
    playwright_result = CollectionResult(
        status="success",
        source_url=source_url,
        marketplace="wildberries",
        reviews=[_fake_collected_review(source_url)],
        message="playwright smoke success",
    )
    with (
        patch("review_scraper_detector.inference.collect_reviews_via_public_marketplace_api", return_value=unsupported_api_result),
        patch("review_scraper_detector.inference.collect_reviews_sync", return_value=playwright_result) as playwright_mock,
        patch("review_scraper_detector.inference.fetch_html_with_fallback") as external_mock,
    ):
        response = client.post("/api/predict", json={"url": source_url})

    status, data = _expect_json_response(response, 200)
    if status:
        return status
    if playwright_mock.call_count != 1:
        return _fail("URL mode should call Playwright when public marketplace API has no reviews.")
    if external_mock.call_count:
        return _fail("Playwright success should stop before ScrapingBee/Scrape.do.")
    if data.get("collection", {}).get("strategy") != "playwright_collector":
        return _fail("URL mode should report playwright_collector as the winning strategy.")

    print("OK: URL mode tries public API first and Playwright second.", flush=True)
    return 0


def check_url_analysis_depth_modes(client) -> int:
    _print_step("URL analysis depth modes")
    source_url = "https://wildberries.ru/catalog/123/detail.aspx?imtId=987654321"

    public_review = _fake_collected_review(source_url)
    public_api_result = CollectionResult(
        status="success",
        source_url=source_url,
        marketplace="wildberries",
        reviews=[public_review],
        message="public api smoke success",
    )
    with (
        patch("review_scraper_detector.inference.collect_reviews_via_public_marketplace_api", return_value=public_api_result),
        patch("review_scraper_detector.inference.collect_reviews_sync") as playwright_mock,
        patch("review_scraper_detector.inference.fetch_html_with_fallback") as external_mock,
    ):
        response = client.post(
            "/api/predict",
            json={"url": source_url, "analysis_depth": "standard", "wait_ms": 6000, "scroll_rounds": 16},
        )

    status, data = _expect_json_response(response, 200)
    if status:
        return status
    if playwright_mock.call_count or external_mock.call_count:
        return _fail("Standard depth should keep the existing public-API short circuit.")
    if data.get("collection", {}).get("analysis_depth") != "standard":
        return _fail("Standard depth should be reported in collection metadata.")

    enriched_review = _fake_collected_review(source_url)
    enriched_review.photos_count = 1
    enriched_review.image_urls = ["https://example.com/review-photo.jpg"]
    playwright_result = CollectionResult(
        status="success",
        source_url=source_url,
        marketplace="wildberries",
        reviews=[enriched_review],
        message="playwright enrichment smoke success",
        extraction_sources={"rendered_card_dom": 1},
    )
    with (
        patch("review_scraper_detector.inference.collect_reviews_via_public_marketplace_api", return_value=public_api_result),
        patch("review_scraper_detector.inference.collect_reviews_sync", return_value=playwright_result) as playwright_mock,
        patch("review_scraper_detector.inference.fetch_html_with_fallback") as external_mock,
    ):
        response = client.post(
            "/api/predict",
            json={"url": source_url, "analysis_depth": "deep", "wait_ms": 12000, "scroll_rounds": 48},
        )

    status, data = _expect_json_response(response, 200)
    if status:
        return status
    if playwright_mock.call_count != 1:
        return _fail("Deep depth should enrich successful public API records with Playwright.")
    if external_mock.call_count:
        return _fail("Deep public-API enrichment should not fall through to external HTML when API records exist.")
    collection = data.get("collection", {})
    if collection.get("analysis_depth") != "deep":
        return _fail("Deep depth should be reported in collection metadata.")
    attempts = collection.get("attempts", [])
    if not any(attempt.get("strategy") == "playwright_enrichment" for attempt in attempts):
        return _fail("Deep depth should include a Playwright enrichment attempt in the trace.")
    reviews = data.get("reviews", [])
    if not reviews or int(reviews[0].get("image_count", 0) or 0) < 1:
        return _fail("Deep depth should merge Playwright image data into public API records.")

    print("OK: URL depth modes are routed through backend collection profiles.", flush=True)
    return 0


def check_marketplace_api_diagnostics(client) -> int:
    _print_step("Marketplace API diagnostics")

    samples = [
        ("https://www.ozon.ru/product/example-123/", "ozon", "seller API"),
        ("https://market.yandex.ru/product--example/123", "yandex_market", "businessId"),
        ("https://aliexpress.ru/item/1005001234567890.html", "aliexpress", "AliExpress"),
        ("https://megamarket.ru/catalog/details/example-100/", "megamarket", "stable unauthenticated"),
        ("https://www.lamoda.ru/p/example/", "lamoda", "stable unauthenticated"),
        ("https://www.dns-shop.ru/product/example/", "dns", "stable unauthenticated"),
    ]

    for url, expected_marketplace, expected_message_part in samples:
        result = collect_reviews_via_public_marketplace_api(url, max_reviews=5)
        if result.status != "unsupported":
            return _fail(f"{expected_marketplace} API diagnostic should be unsupported, got {result.status}.")
        if result.marketplace != expected_marketplace:
            return _fail(f"Expected marketplace={expected_marketplace}, got {result.marketplace}.")
        if expected_message_part not in result.message:
            return _fail(f"{expected_marketplace} diagnostic message is not specific enough: {result.message}")
        if result.extraction_sources.get("known_marketplace") != 1:
            return _fail(f"{expected_marketplace} should be marked as a known marketplace.")
        if result.extraction_sources.get("browser_fallback_expected") != 1:
            return _fail(f"{expected_marketplace} should point to browser/external fallback.")

    print("OK: known marketplaces get specific API limitation diagnostics.", flush=True)
    return 0


def check_marketplace_history_regressions(client) -> int:
    _print_step("Marketplace history regressions")

    wb_url = "https://www.wildberries.by/catalog/242340502/feedbacks?imtId=51004983&size=380528712"
    if _marketplace_from_url(wb_url) != "wildberries":
        return _fail("wildberries.by should be recognized as Wildberries, not as an unknown host.")

    wb_payload = {
        "feedbacks": [
            {
                "text": "Замечательный конструктор, ребенок собирал с удовольствием.",
                "productValuation": 5,
                "createdDate": "2026-05-01T13:33:26Z",
                "wbUserDetails": {"name": "Покупатель WB"},
                "photos": [{"fullSize": "https://example.com/photo.jpg"}],
            }
        ]
    }
    wb_records = _reviews_from_payload(wb_payload, wb_url, "wildberries")
    if len(wb_records) != 1:
        return _fail(f"Wildberries network payload should produce one review, got {len(wb_records)}.")
    if wb_records[0].rating != 5.0:
        return _fail(f"Wildberries productValuation should map to rating, got {wb_records[0].rating}.")
    if wb_records[0].author != "Покупатель WB":
        return _fail(f"Wildberries wbUserDetails.name should map to author, got {wb_records[0].author!r}.")
    if wb_records[0].photos_count != 1 or wb_records[0].image_urls != ["https://example.com/photo.jpg"]:
        return _fail(f"Wildberries photos should map to image URLs, got count={wb_records[0].photos_count}, urls={wb_records[0].image_urls}.")

    noisy_html = """
    <html><body>
      <div class="review-card"><p>lady.nadya.k l.</p></div>
      <div class="review-card"><p>White Yellow Set | 1-2Years</p></div>
      <div class="review-card"><span class="rating">5 stars</span><p>Костюм супер, ткань мягкая, доставка быстрая, размер подошел.</p></div>
    </body></html>
    """
    parsed = parse_reviews_from_html(noisy_html, source_url="https://aliexpress.ru/item/1005005210266264/reviews")
    texts = [row.get("review_text", "") for row in parsed]
    if any("lady.nadya" in text or "White Yellow Set" in text for text in texts):
        return _fail(f"Generic parser should filter handles and product variants, got {texts}.")
    if not any("Костюм супер" in text for text in texts):
        return _fail("Generic parser should keep the real review after filtering noisy blocks.")

    policy = {
        "threshold": 0.5,
        "confident_suspicious_threshold": 0.65,
        "confident_clean_threshold": 0.25,
        "uncertainty_threshold": 0.35,
        "ood_threshold": 0.45,
    }
    triaged = apply_review_abstention_policy(
        pd.DataFrame(
            [
                {
                    "review_text": "Очень хорошее качество, ребенок собирал с удовольствием, деталей хватило.",
                    "suspicious_probability": 0.002,
                    "uncertainty_score": 0.06,
                    "ood_score": 0.58,
                    "slang_authenticity_score": 0.78,
                    "slang_manipulation_score": 0.03,
                    "rating_manipulation_score": 0.02,
                    "slang_template_dup_count": 0,
                }
            ]
        ),
        policy,
    )
    if int(triaged.loc[0, "requires_manual_review"]) != 0:
        return _fail(f"Clearly low-risk organic OOD reviews should not be forced to manual review: {triaged.loc[0, 'manual_review_reasons']}")
    short_triaged = apply_review_abstention_policy(
        pd.DataFrame(
            [
                {
                    "review_text": "\u0420\u0435\u0431\u0435\u043d\u043e\u043a \u0434\u043e\u0432\u043e\u043b\u0435\u043d!",
                    "suspicious_probability": 0.003,
                    "uncertainty_score": 0.10,
                    "ood_score": 0.64,
                    "slang_authenticity_score": 0.5,
                    "slang_manipulation_score": 0.03,
                    "rating_manipulation_score": 0.02,
                    "slang_template_dup_count": 0,
                    "ai_text_score": 0.0,
                }
            ]
        ),
        policy,
    )
    if int(short_triaged.loc[0, "requires_manual_review"]) != 0:
        return _fail(f"Short low-risk marketplace comments should not be forced to manual review: {short_triaged.loc[0, 'manual_review_reasons']}")

    print("OK: marketplace regressions from history are covered.", flush=True)
    return 0


def _amazon_review_smoke_html() -> str:
    return """
    <html>
      <body>
        <div id="cm_cr-review_list">
          <div data-hook="review" id="customer_review-R1">
            <span class="a-profile-name">AmazonSmokeUser</span>
            <i data-hook="review-star-rating" aria-label="5.0 out of 5 stars">
              <span class="a-icon-alt">5.0 out of 5 stars</span>
            </i>
            <a data-hook="review-title"><span>Reliable in daily use</span></a>
            <span data-hook="review-date">Reviewed in the United States on April 30, 2026</span>
            <span data-hook="review-body">
              <span>Brief content visible, double tap to read full content. I used this product every day for a week, checked the setup process, battery behavior, and packaging details.</span>
            </span>
          </div>
        </div>
      </body>
    </html>
    """


def check_amazon_review_helpers(client) -> int:
    _print_step("Amazon review helpers")
    source_url = "https://www.amazon.com/Example-Product/dp/B08TEST123/ref=sr_1_3?th=1#averageCustomerReviewsAnchor"
    product_url = amazon_product_url(source_url)
    if product_url != "https://www.amazon.com/dp/B08TEST123/":
        return _fail(f"Amazon canonical product URL was not derived cleanly: {product_url}")

    review_url = amazon_review_url(source_url)
    if "/product-reviews/B08TEST123/" not in review_url:
        return _fail(f"Amazon review URL was not derived from the product URL: {review_url}")

    parsed = parse_reviews_from_html(_amazon_review_smoke_html(), source_url=review_url)
    if len(parsed) != 1:
        return _fail(f"Amazon parser should extract one review from data-hook markup, got {len(parsed)}.")
    if parsed[0].get("rating") != 5.0:
        return _fail(f"Amazon parser should extract the star rating, got {parsed[0].get('rating')}.")
    if "battery behavior" not in parsed[0].get("review_text", ""):
        return _fail("Amazon parser did not extract the review body text.")
    if "double tap to read" in parsed[0].get("review_text", "").lower():
        return _fail("Amazon parser should remove accessibility boilerplate from review text.")

    print("OK: Amazon review URL derivation and parser selectors are stable.", flush=True)
    return 0


def check_rendered_review_card_payloads(client) -> int:
    _print_step("Rendered review card payloads")
    payloads = [
        {
            "author": "AmazonSmokeUser",
            "title": "5.0 out of 5 stars Reliable in daily use",
            "ratingText": "5.0 out of 5 stars",
            "date": "Reviewed in the United States on April 30, 2026",
            "reviewText": (
                "Brief content visible, double tap to read full content. "
                "I used this product every day for a week, checked the setup process, battery behavior, and packaging details."
            ),
            "photoUrls": ["https://example.com/review-a.jpg", "https://example.com/review-b.jpg"],
        }
    ]
    records = _records_from_rendered_card_payloads(payloads, "https://www.amazon.com/dp/B08TEST123/", "amazon")
    if len(records) != 1:
        return _fail(f"Rendered DOM card conversion should produce one review, got {len(records)}.")
    record = records[0]
    if record.rating != 5.0:
        return _fail(f"Rendered DOM card conversion should parse rating, got {record.rating}.")
    if record.title != "Reliable in daily use":
        return _fail(f"Rendered DOM card conversion should strip duplicated rating from title, got {record.title!r}.")
    if "double tap to read" in record.review_text.lower():
        return _fail("Rendered DOM card conversion should remove accessibility boilerplate.")
    if record.photos_count != 2 or len(record.image_urls) != 2:
        return _fail(f"Rendered DOM card conversion should keep photo count, got {record.photos_count}.")

    print("OK: rendered Playwright DOM card payloads are normalized.", flush=True)
    return 0


def check_amazon_external_review_url_analysis(client) -> int:
    _print_step("Amazon external review URL analysis")
    source_url = "https://www.amazon.com/Example-Product/dp/B08TEST123"
    unsupported_api_result = CollectionResult(
        status="unsupported",
        source_url=source_url,
        marketplace="amazon",
        reviews=[],
        message="Amazon API smoke unsupported",
    )
    failed_playwright_result = CollectionResult(
        status="no_reviews",
        source_url=source_url,
        marketplace="amazon",
        reviews=[],
        message="Rendered the public page, but no review records were extracted.",
    )

    with (
        patch("review_scraper_detector.inference.collect_reviews_via_public_marketplace_api", return_value=unsupported_api_result),
        patch("review_scraper_detector.inference.collect_reviews_sync", return_value=failed_playwright_result),
        patch("review_scraper_detector.inference.fetch_html_with_fallback", return_value=_amazon_review_smoke_html()) as fetch_mock,
    ):
        response = client.post("/api/predict", json={"url": source_url})

    status, data = _expect_json_response(response, 200)
    if status:
        return status
    if fetch_mock.call_count != 1:
        return _fail("Amazon external fallback should fetch the product URL first and stop after parsed reviews.")
    fetched_url = str(fetch_mock.call_args.kwargs.get("url") or "")
    if fetched_url != source_url:
        return _fail(f"Amazon external fallback should fetch the product page first, got {fetched_url}.")
    if data.get("summary", {}).get("total_reviews") != 1:
        return _fail("Amazon external fallback did not analyze the parsed review.")
    attempts = data.get("collection", {}).get("attempts", [])
    external_attempts = [attempt for attempt in attempts if attempt.get("strategy") == "external_html_collectors"]
    if not external_attempts or external_attempts[-1].get("status") != "success":
        return _fail("Amazon external fallback should report a successful parsed HTML attempt.")

    print("OK: Amazon external fallback uses the product page first and parses reviews.", flush=True)
    return 0


def check_url_external_fallback_analysis(client) -> int:
    _print_step("URL external fallback analysis")
    html = SAMPLE_HTML_PATH.read_text(encoding="utf-8")
    unsupported_api_result = CollectionResult(
        status="unsupported",
        source_url="https://example.com/product/reviews",
        marketplace="example.com",
        reviews=[],
        message="unsupported smoke",
    )
    failed_playwright_result = CollectionResult(
        status="failed",
        source_url="https://example.com/product/reviews",
        marketplace="example.com",
        reviews=[],
        message="playwright unavailable in smoke",
    )
    with (
        patch("review_scraper_detector.inference.collect_reviews_via_public_marketplace_api", return_value=unsupported_api_result),
        patch("review_scraper_detector.inference.collect_reviews_sync", return_value=failed_playwright_result),
        patch("review_scraper_detector.inference.fetch_html_with_fallback", return_value=html) as fetch_mock,
    ):
        response = client.post("/api/predict", json={"url": "https://example.com/product/reviews"})

    status, data = _expect_json_response(response, 200)
    if status:
        return status
    if fetch_mock.call_count != 1:
        return _fail("URL mode should call the live-page fetcher exactly once.")
    if data.get("summary", {}).get("total_reviews", 0) < 1:
        return _fail("URL-mode smoke check returned no parsed reviews.")
    if data.get("request", {}).get("source_type") != "url":
        return _fail("URL-mode smoke check did not preserve source_type=url.")
    if data.get("collection", {}).get("strategy") != "external_html_collectors":
        return _fail("URL-mode smoke check should report external_html_collectors after API and Playwright fail.")
    if not data.get("history", {}).get("report_id"):
        return _fail("URL-mode smoke check did not return a saved report id.")

    print(f"OK: URL external fallback analyzed {data.get('summary', {}).get('total_reviews')} review(s).", flush=True)
    return 0


def check_html_analysis(client) -> int:
    _print_step("Inline HTML analysis")
    html = SAMPLE_HTML_PATH.read_text(encoding="utf-8")
    response = client.post(
        "/api/predict",
        json={
            "html": html,
            "source_url": "sample-local-html",
        },
    )
    status, data = _expect_json_response(response, 200)
    if status:
        return status

    summary = data.get("summary", {})
    if summary.get("total_reviews", 0) < 1:
        return _fail("HTML smoke check returned no reviews.")
    if not data.get("history", {}).get("report_id"):
        return _fail("HTML smoke check did not return a saved report id.")

    print(f"OK: analyzed {summary.get('total_reviews')} review(s).", flush=True)
    return 0


def check_empty_html_analysis(client) -> int:
    _print_step("Empty HTML analysis")
    response = client.post("/api/predict", json={"html": "<html><body>No review blocks here.</body></html>"})
    status, data = _expect_json_response(response, 200)
    if status:
        return status

    if data.get("summary", {}).get("total_reviews") != 0:
        return _fail("Empty HTML smoke check should return zero reviews.")
    if not data.get("history", {}).get("report_id"):
        return _fail("Empty HTML smoke check did not return a saved report id.")

    print("OK: empty HTML returns a stable empty result.", flush=True)
    return 0


def check_unsafe_image_sources(client) -> int:
    _print_step("Unsafe image source filtering")
    html = """
    <html>
      <body>
        <article class="review-item">
          <p class="review-text">I used this product for two weeks and the real-world details look normal.</p>
          <img src="file:///C:/Windows/win.ini" alt="customer photo">
          <img src="http://127.0.0.1/private-image.png" alt="customer photo">
        </article>
      </body>
    </html>
    """
    response = client.post(
        "/api/predict",
        json={
            "html": html,
            "source_url": "https://example.com/product",
        },
    )
    status, data = _expect_json_response(response, 200)
    if status:
        return status

    reviews = data.get("reviews", [])
    if not reviews:
        return _fail("Unsafe-image smoke check returned no review.")
    if any(review.get("image_count", 0) for review in reviews):
        return _fail("Unsafe local/internal image sources should be filtered before image analysis.")
    if not data.get("history", {}).get("report_id"):
        return _fail("Unsafe-image smoke check did not return a saved report id.")

    print("OK: local and internal image sources are ignored.", flush=True)
    return 0


def check_records_analysis(client) -> int:
    _print_step("Structured records analysis")
    records = _read_sample_records()
    response = client.post("/api/predict", json={"records": records})
    status, data = _expect_json_response(response, 200)
    if status:
        return status

    summary = data.get("summary", {})
    total = summary.get("total_records") or summary.get("total_reviews") or 0
    if total < 1:
        return _fail("Structured-record smoke check returned no analyzed records.")
    if not data.get("history", {}).get("report_id"):
        return _fail("Structured-record smoke check did not return a saved report id.")

    print(f"OK: analyzed {total} record(s).", flush=True)
    return 0


def check_history_api(client) -> int:
    _print_step("Analysis history")
    status, data = _expect_json_response(client.get("/api/history?limit=5"), 200)
    if status:
        return status

    reports = data.get("reports")
    if not isinstance(reports, list) or not reports:
        return _fail("History list should contain saved analysis reports.")

    report_id = reports[0].get("id")
    if not report_id:
        return _fail("History list item has no report id.")

    status, detail = _expect_json_response(client.get(f"/api/history/{report_id}"), 200)
    if status:
        return status
    if not isinstance(detail.get("summary"), dict):
        return _fail("History detail should return the saved full report.")

    status, _missing = _expect_json_response(client.get("/api/history/missing-report-id"), 404, "REPORT_NOT_FOUND")
    if status:
        return status

    print(f"OK: history list and report detail work ({len(reports)} recent report(s)).", flush=True)
    return 0


def main() -> int:
    app.config["HISTORY_DB_PATH"] = SMOKE_HISTORY_PATH
    if SMOKE_HISTORY_PATH.exists():
        SMOKE_HISTORY_PATH.unlink()

    checks = [
        check_health,
        check_validation,
        check_optional_ip_records,
        check_cyrillic_ocr_patterns,
        check_ai_text_patterns,
        check_import_source_proxy,
        check_scraping_fallback_chain,
        check_url_collection_order,
        check_url_analysis_depth_modes,
        check_marketplace_api_diagnostics,
        check_marketplace_history_regressions,
        check_amazon_review_helpers,
        check_rendered_review_card_payloads,
        check_amazon_external_review_url_analysis,
        check_url_external_fallback_analysis,
        check_html_analysis,
        check_empty_html_analysis,
        check_unsafe_image_sources,
        check_records_analysis,
        check_history_api,
    ]
    with app.test_client() as client:
        for check in checks:
            status = check(client)
            if status:
                return status

    print("\nBackend smoke checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
