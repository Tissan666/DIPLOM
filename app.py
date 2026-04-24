"""Flask API for suspicious review analysis and the React dashboard."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from fake_rating_detector.inference import artifacts_exist as rating_artifacts_exist
from review_scraper_detector.inference import analyze_html_document, analyze_product_url, analyze_site_rating_records, artifacts_exist
from review_scraper_detector.scraping import DEFAULT_WAIT_MS

PROJECT_ROOT = Path(__file__).resolve().parent
ARTIFACTS_DIR = Path("models")
FRONTEND_DIST_DIR = Path("frontend/dist")
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"
MAX_SCRAPING_WAIT_MS = 30000
MAX_SCRAPING_SCROLL_ROUNDS = 28
MIN_SCRAPING_SCROLL_DELAY_MS = 500
MAX_SCRAPING_SCROLL_DELAY_MS = 1500


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


def _error_response(error_code: str, message: str, status: int) -> tuple:
    """Return a stable API error contract for the frontend."""
    return jsonify({"error_code": error_code, "error": message, "message": message}), status


def _backend_scrapingbee_api_key() -> str | None:
    """Return the backend-owned ScrapingBee API key without exposing it to the client."""
    api_key = (os.getenv("SCRAPINGBEE_API_KEY") or "").strip()
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
    if "scrapingbee api key is missing" in normalized_message or "scrapingbee_api_key" in normalized_message:
        return "SCRAPINGBEE_NOT_CONFIGURED"
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
    if "scrapingbee" in normalized_message:
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
    ready = review_ready and rating_ready
    return (
        jsonify(
            {
                "status": "ok" if ready else "artifacts_missing",
                "artifacts_ready": ready,
                "review_artifacts_ready": review_ready,
                "rating_artifacts_ready": rating_ready,
                "scrapingbee_configured": _backend_scrapingbee_api_key() is not None,
                "scrapingbee_render_js": _backend_bool_env("SCRAPINGBEE_RENDER_JS", True),
                "scrapingbee_country_code": _backend_scraping_country(),
                "artifacts_dir": str(ARTIFACTS_DIR),
                "ui_url": "http://127.0.0.1:5000/",
                "frontend_dev_url": "http://127.0.0.1:5173/",
            }
        ),
        200 if ready else 503,
    )


@app.post("/predict")
@app.post("/api/predict")
def predict() -> tuple:
    """Analyze review pages or full rating datasets."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error_response("REQUEST_BODY_INVALID", "Request body must be a JSON object.", 400)

    try:
        if payload.get("records"):
            if not rating_artifacts_exist(ARTIFACTS_DIR):
                return _error_response(
                    "RATING_ARTIFACTS_MISSING",
                    "Rating anti-fraud artifacts are missing. Run training first.",
                    503,
                )
            result = analyze_site_rating_records(
                records=list(payload["records"]),
                artifacts_dir=ARTIFACTS_DIR,
            )
        elif payload.get("html"):
            if not artifacts_exist(ARTIFACTS_DIR):
                return _error_response(
                    "REVIEW_ARTIFACTS_MISSING",
                    "Review model artifacts are missing. Run training first.",
                    503,
                )
            result = analyze_html_document(
                html=str(payload["html"]),
                source_url=str(payload.get("source_url", "inline-html")),
                artifacts_dir=ARTIFACTS_DIR,
                source_type="inline_html",
            )
        elif payload.get("url"):
            if not artifacts_exist(ARTIFACTS_DIR):
                return _error_response(
                    "REVIEW_ARTIFACTS_MISSING",
                    "Review model artifacts are missing. Run training first.",
                    503,
                )
            result = analyze_product_url(
                product_url=str(payload["url"]),
                artifacts_dir=ARTIFACTS_DIR,
                api_key=_backend_scrapingbee_api_key(),
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
            )
        else:
            return _error_response("INPUT_SOURCE_MISSING", "Provide either `url`, `html`, or `records` in the request body.", 400)
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
        return _error_response("ANALYSIS_FAILED", f"Analysis failed: {exc}", 500)

    return jsonify(result), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
