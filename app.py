"""Flask API for suspicious review analysis and the React dashboard."""

from __future__ import annotations

import os
import ipaddress
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, Response, jsonify, request, send_from_directory
import requests

from analysis_history import get_analysis_report, list_analysis_reports, save_analysis_report
from fake_rating_detector.inference import (
    artifacts_compatible as rating_artifacts_compatible,
    artifacts_exist as rating_artifacts_exist,
)
from review_scraper_detector.inference import (
    analyze_html_document,
    analyze_product_url,
    analyze_site_rating_records,
    artifacts_compatible as review_artifacts_compatible,
    artifacts_exist,
)
from review_scraper_detector.ai_text_signals import ai_text_capability_status
from review_scraper_detector.image_ocr_signals import ocr_capability_status
from review_scraper_detector.image_text_alignment import image_alignment_capability_status
from review_scraper_detector.scraping import DEFAULT_WAIT_MS

PROJECT_ROOT = Path(__file__).resolve().parent
ARTIFACTS_DIR = PROJECT_ROOT / "models"
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"
HISTORY_DB_PATH = PROJECT_ROOT / "outputs" / "analysis_history.sqlite3"
MAX_SCRAPING_WAIT_MS = 30000
MAX_SCRAPING_SCROLL_ROUNDS = 80
MIN_SCRAPING_SCROLL_DELAY_MS = 500
MAX_SCRAPING_SCROLL_DELAY_MS = 1500
MAX_IMPORT_SOURCE_BYTES = 10 * 1024 * 1024
IMPORT_SOURCE_TIMEOUT_SECONDS = 25
BLOCKED_IMPORT_HOSTNAMES = {"localhost", "localhost.localdomain"}
ANALYSIS_DEPTHS = {"fast", "standard", "deep"}


def _load_backend_env_file(path: Path = PROJECT_ROOT / ".env") -> None:
    """Load local backend env values without requiring python-dotenv."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


_load_backend_env_file()
app = Flask(__name__, static_folder=None)
app.config["HISTORY_DB_PATH"] = Path(os.getenv("ANALYSIS_HISTORY_DB_PATH", str(HISTORY_DB_PATH)))


def _error_response(error_code: str, message: str, status: int) -> tuple:
    """Return a stable API error contract for the frontend."""
    return jsonify({"error_code": error_code, "error": message, "message": message}), status


def _backend_scrapingbee_api_key() -> str | None:
    """Return the backend-owned ScrapingBee API key without exposing it to the client."""
    api_key = (os.getenv("SCRAPINGBEE_API_KEY") or "").strip()
    return api_key or None


def _backend_scrapedo_api_key() -> str | None:
    """Return the backend-owned Scrape.do API key without exposing it to the client."""
    api_key = (os.getenv("SCRAPEDO_API_KEY") or "").strip()
    return api_key or None


def _backend_bool_env(name: str, default: bool) -> bool:
    """Parse backend-owned boolean flags from environment variables."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"", "0", "false", "no", "off"}


def _backend_scraping_country() -> str | None:
    """Return the backend-owned ScrapingBee country override, if configured."""
    country_code = (os.getenv("SCRAPINGBEE_COUNTRY_CODE") or "").strip()
    return country_code or None


def _value_error_code(message: str) -> str:
    """Map known validation failures to stable frontend-facing codes."""
    normalized_message = message.lower()
    if "scraping service api key is missing" in normalized_message:
        return "SCRAPING_SERVICE_NOT_CONFIGURED"
    if "scrapingbee api key is missing" in normalized_message or "scrapingbee_api_key" in normalized_message:
        return "SCRAPINGBEE_NOT_CONFIGURED"
    if "scrape.do api key is missing" in normalized_message or "scrapedo_api_key" in normalized_message:
        return "SCRAPEDO_NOT_CONFIGURED"
    if "must start with http:// or https://" in normalized_message:
        return "INVALID_URL"
    if "wait_ms" in normalized_message:
        return "INVALID_SCRAPING_WAIT"
    return "INVALID_INPUT"


def _runtime_error_code(message: str) -> tuple[str, int]:
    """Map runtime scrape failures to user-facing API errors."""
    normalized_message = message.lower()
    if "timed out" in normalized_message or "timeout" in normalized_message:
        return "SCRAPING_TIMEOUT", 504
    if "rate limit" in normalized_message or "credits issue" in normalized_message:
        return "SCRAPING_RATE_LIMITED", 502
    if "bot-protection" in normalized_message or "blocked or rejected" in normalized_message:
        return "SCRAPING_BLOCKED", 502
    if "scrapingbee" in normalized_message or "scrape.do" in normalized_message:
        return "SCRAPING_FETCH_FAILED", 502
    return "ANALYSIS_FAILED", 500


def _bounded_int(value: object, *, default: int, minimum: int, maximum: int, name: str) -> int:
    """Parse and validate small integer request controls before starting expensive work."""
    if value is None or value == "":
        parsed = default
    else:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"`{name}` must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"`{name}` must be between {minimum} and {maximum}.")
    return parsed


def _history_db_path() -> Path:
    """Return the configured analysis-history database path."""
    return Path(app.config["HISTORY_DB_PATH"])


def _active_source_keys(payload: dict) -> list[str]:
    """Return request source keys that carry a meaningful value."""
    keys: list[str] = []
    for key in ("records", "html", "url"):
        if key not in payload or payload[key] is None:
            continue
        value = payload[key]
        if isinstance(value, str) and not value.strip():
            continue
        keys.append(key)
    return keys


def _validated_records(payload: dict) -> list[dict]:
    """Validate and return structured rating records from the request."""
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("`records` must be a non-empty JSON array.")
    if not records:
        raise ValueError("`records` must contain at least one rating record.")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("Every item in `records` must be a JSON object.")
    return records


def _validated_html(payload: dict) -> str:
    """Validate and return inline HTML from the request."""
    html = payload.get("html")
    if not isinstance(html, str) or not html.strip():
        raise ValueError("`html` must be a non-empty string.")
    return html


def _validated_url(payload: dict) -> str:
    """Validate and return a public product page URL from the request."""
    url = payload.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("`url` must be a non-empty string.")
    normalized_url = url.strip()
    if not normalized_url.startswith(("http://", "https://")):
        raise ValueError("`url` must start with http:// or https://.")
    return normalized_url


def _validated_source_url(payload: dict) -> str:
    """Return an optional display/source URL for inline HTML analysis."""
    source_url = payload.get("source_url", "inline-html")
    if source_url is None:
        return "inline-html"
    return str(source_url).strip() or "inline-html"


def _validated_analysis_depth(payload: dict) -> str:
    """Return the requested URL collection depth profile."""
    raw_depth = payload.get("analysis_depth", "standard")
    if raw_depth is None or raw_depth == "":
        return "standard"
    normalized_depth = str(raw_depth).strip().lower()
    if normalized_depth not in ANALYSIS_DEPTHS:
        raise ValueError("`analysis_depth` must be one of: fast, standard, deep.")
    return normalized_depth


def _validated_public_fetch_url(payload: dict) -> str:
    """Validate an API import URL before the backend fetches it for the browser."""
    url = payload.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("`url` must be a non-empty string.")

    normalized_url = url.strip()
    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("`url` must start with http:// or https://.")
    if not _is_public_hostname(parsed.hostname):
        raise ValueError("`url` must point to a public HTTP(S) host.")
    return normalized_url


def _is_public_hostname(hostname: str | None) -> bool:
    """Reject obvious local/private hosts for backend-owned import fetching."""
    if not hostname:
        return False

    normalized = hostname.strip("[]").rstrip(".").lower()
    if normalized in BLOCKED_IMPORT_HOSTNAMES or normalized.endswith((".localhost", ".local")):
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


def _fetch_import_source(url: str) -> tuple[bytes, str]:
    """Fetch a public structured-data source with a bounded response size."""
    try:
        response = requests.get(
            url,
            timeout=IMPORT_SOURCE_TIMEOUT_SECONDS,
            stream=True,
            headers={
                "Accept": "application/json, application/x-ndjson, text/csv, text/tab-separated-values, text/html, */*",
                "User-Agent": "review-integrity-importer/1.0",
            },
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise RuntimeError(f"Could not fetch the API source: HTTP {status}.") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not fetch the API source: {exc}") from exc

    chunks: list[bytes] = []
    total_size = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total_size += len(chunk)
        if total_size > MAX_IMPORT_SOURCE_BYTES:
            raise ValueError("Imported source is too large. Maximum allowed size is 10 MB.")
        chunks.append(chunk)

    content_type = response.headers.get("content-type", "application/octet-stream")
    return b"".join(chunks), content_type


@app.get("/")
def index() -> Response:
    """Serve the built React frontend when it is available."""
    if (FRONTEND_DIST_DIR / "index.html").exists():
        return send_from_directory(FRONTEND_DIST_DIR, "index.html")
    return Response(
        """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Review Integrity API</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 0; background: #f7f6f3; color: #102236; }
      main { max-width: 760px; margin: 64px auto; padding: 0 24px; }
      section { background: white; border: 1px solid #dde6ee; border-radius: 20px; padding: 24px; box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08); }
      code { background: #eef4f7; padding: 2px 6px; border-radius: 6px; }
      ul { line-height: 1.7; }
    </style>
  </head>
  <body>
    <main>
      <section>
        <h1>Frontend build not found</h1>
        <p>The Flask API is running, but the React frontend has not been built yet.</p>
        <ul>
          <li>For local development, run <code>python run_dev.py</code> and open <code>http://127.0.0.1:5173</code>.</li>
          <li>For a built frontend, run <code>cd frontend</code>, <code>npm install</code>, then <code>npm run build</code>.</li>
          <li>API health is available at <code>/health</code>.</li>
        </ul>
      </section>
    </main>
  </body>
</html>
        """.strip(),
        mimetype="text/html",
        status=503,
    )


@app.get("/assets/<path:asset_path>")
def frontend_assets(asset_path: str):
    """Serve built React frontend assets when available."""
    return send_from_directory(FRONTEND_ASSETS_DIR, asset_path)


@app.get("/health")
def health() -> tuple:
    """Return API health and model artifact readiness."""
    review_ready = artifacts_exist(ARTIFACTS_DIR)
    rating_ready = rating_artifacts_exist(ARTIFACTS_DIR)
    review_compatible, review_error = review_artifacts_compatible(ARTIFACTS_DIR) if review_ready else (False, None)
    rating_compatible, rating_error = rating_artifacts_compatible(ARTIFACTS_DIR) if rating_ready else (False, None)
    ready = review_ready and rating_ready and review_compatible and rating_compatible
    status_label = "ok" if ready else "artifacts_incompatible" if review_ready and rating_ready else "artifacts_missing"
    return (
        jsonify(
            {
                "status": status_label,
                "artifacts_ready": ready,
                "review_artifacts_ready": review_ready,
                "rating_artifacts_ready": rating_ready,
                "review_artifacts_compatible": review_compatible,
                "rating_artifacts_compatible": rating_compatible,
                "review_artifacts_error": review_error,
                "rating_artifacts_error": rating_error,
                "scrapingbee_configured": _backend_scrapingbee_api_key() is not None,
                "scrapedo_configured": _backend_scrapedo_api_key() is not None,
                "scrapingbee_render_js": _backend_bool_env("SCRAPINGBEE_RENDER_JS", True),
                "scrapingbee_country_code": _backend_scraping_country(),
                "artifacts_dir": str(ARTIFACTS_DIR),
                "history_enabled": True,
                "history_db_path": str(_history_db_path()),
                "vision_capabilities": {
                    "ocr": ocr_capability_status(),
                    "image_alignment": image_alignment_capability_status(),
                },
                "text_capabilities": {
                    "ai_text": ai_text_capability_status(ARTIFACTS_DIR),
                },
                "ui_url": "http://127.0.0.1:5000/",
                "frontend_dev_url": "http://127.0.0.1:5173/",
            }
        ),
        200 if ready else 503,
    )


@app.get("/history")
@app.get("/api/history")
def history_index() -> tuple:
    """Return recent saved analysis reports."""
    try:
        limit = _bounded_int(request.args.get("limit"), default=30, minimum=1, maximum=100, name="limit")
    except ValueError as exc:
        message = str(exc)
        return _error_response(_value_error_code(message), message, 400)

    reports = list_analysis_reports(_history_db_path(), limit=limit)
    return jsonify({"count": len(reports), "reports": reports}), 200


@app.get("/history/<report_id>")
@app.get("/api/history/<report_id>")
def history_detail(report_id: str) -> tuple:
    """Return one saved analysis report."""
    normalized_report_id = (report_id or "").strip()
    if not normalized_report_id:
        return _error_response("REPORT_ID_INVALID", "`report_id` must be a non-empty value.", 400)

    report = get_analysis_report(_history_db_path(), normalized_report_id)
    if report is None:
        return _error_response("REPORT_NOT_FOUND", "Saved analysis report was not found.", 404)
    return jsonify(report), 200


@app.post("/api/import-source")
def import_source() -> tuple | Response:
    """Backend proxy for user-provided API/data URLs to avoid browser CORS limits."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error_response("REQUEST_BODY_INVALID", "Request body must be a JSON object.", 400)

    try:
        url = _validated_public_fetch_url(payload)
        body, content_type = _fetch_import_source(url)
    except ValueError as exc:
        message = str(exc)
        return _error_response(_value_error_code(message), message, 400)
    except RuntimeError as exc:
        message = str(exc)
        return _error_response("IMPORT_SOURCE_FETCH_FAILED", message, 502)

    return Response(body, content_type=content_type)


@app.post("/predict")
@app.post("/api/predict")
def predict() -> tuple:
    """Analyze review pages or full rating datasets."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error_response("REQUEST_BODY_INVALID", "Request body must be a JSON object.", 400)

    source_keys = _active_source_keys(payload)
    if not source_keys:
        return _error_response("INPUT_SOURCE_MISSING", "Provide exactly one source: `url`, `html`, or `records`.", 400)
    if len(source_keys) > 1:
        return _error_response(
            "INPUT_SOURCE_AMBIGUOUS",
            "Provide only one source per request: `url`, `html`, or `records`.",
            400,
        )

    try:
        source_key = source_keys[0]

        if source_key == "records":
            records = _validated_records(payload)
            if not rating_artifacts_exist(ARTIFACTS_DIR):
                return _error_response(
                    "RATING_ARTIFACTS_MISSING",
                    "Rating anti-fraud artifacts are missing. Run training first.",
                    503,
                )
            result = analyze_site_rating_records(
                records=records,
                artifacts_dir=ARTIFACTS_DIR,
            )
        elif source_key == "html":
            html = _validated_html(payload)
            if not artifacts_exist(ARTIFACTS_DIR):
                return _error_response(
                    "REVIEW_ARTIFACTS_MISSING",
                    "Review model artifacts are missing. Run training first.",
                    503,
                )
            result = analyze_html_document(
                html=html,
                source_url=_validated_source_url(payload),
                artifacts_dir=ARTIFACTS_DIR,
                source_type="inline_html",
            )
        elif source_key == "url":
            product_url = _validated_url(payload)
            if not artifacts_exist(ARTIFACTS_DIR):
                return _error_response(
                    "REVIEW_ARTIFACTS_MISSING",
                    "Review model artifacts are missing. Run training first.",
                    503,
                )
            result = analyze_product_url(
                product_url=product_url,
                artifacts_dir=ARTIFACTS_DIR,
                api_key=_backend_scrapingbee_api_key(),
                scrapedo_api_key=_backend_scrapedo_api_key(),
                render_js=_backend_bool_env("SCRAPINGBEE_RENDER_JS", True),
                country_code=_backend_scraping_country(),
                wait_ms=_bounded_int(
                    payload.get("wait_ms"),
                    default=DEFAULT_WAIT_MS,
                    minimum=0,
                    maximum=MAX_SCRAPING_WAIT_MS,
                    name="wait_ms",
                ),
                scroll_rounds=_bounded_int(
                    payload.get("scroll_rounds"),
                    default=24,
                    minimum=0,
                    maximum=MAX_SCRAPING_SCROLL_ROUNDS,
                    name="scroll_rounds",
                ),
                scroll_delay_ms=_bounded_int(
                    payload.get("scroll_delay_ms"),
                    default=1200,
                    minimum=MIN_SCRAPING_SCROLL_DELAY_MS,
                    maximum=MAX_SCRAPING_SCROLL_DELAY_MS,
                    name="scroll_delay_ms",
                ),
                analysis_depth=_validated_analysis_depth(payload),
            )
        else:
            return _error_response("INPUT_SOURCE_MISSING", "Provide exactly one source: `url`, `html`, or `records`.", 400)
    except ValueError as exc:
        message = str(exc)
        return _error_response(_value_error_code(message), message, 400)
    except RuntimeError as exc:
        app.logger.exception("Runtime analysis failure")
        message = str(exc)
        error_code, status = _runtime_error_code(message)
        return _error_response(error_code, message, status)
    except Exception as exc:  # pragma: no cover
        app.logger.exception("Unexpected analysis failure")
        return _error_response("ANALYSIS_FAILED", "Analysis failed unexpectedly. Check backend logs for details.", 500)

    try:
        result, _history_record = save_analysis_report(_history_db_path(), result, source_key=source_key)
    except Exception:  # pragma: no cover
        app.logger.exception("Could not save analysis report")
        result = {
            **result,
            "history": {
                "saved": False,
                "error": "history_unavailable",
            },
        }

    return jsonify(result), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
