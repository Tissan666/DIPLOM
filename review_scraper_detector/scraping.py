"""Helpers for downloading HTML from product or review pages through ScrapingBee."""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import requests

SCRAPINGBEE_ENDPOINT = "https://app.scrapingbee.com/api/v1/"
DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_WAIT_MS = 5000


def resolve_api_key(api_key: str | None = None) -> str:
    """Resolve the ScrapingBee API key from an explicit value or environment variable."""
    resolved = (api_key or os.getenv("SCRAPINGBEE_API_KEY") or "").strip()
    if not resolved:
        raise ValueError(
            "ScrapingBee API key is missing. Set `SCRAPINGBEE_API_KEY` in the backend environment."
        )
    return resolved


def fetch_html_via_scrapingbee(
    url: str,
    api_key: str | None = None,
    render_js: bool = True,
    country_code: str | None = None,
    wait_ms: int = DEFAULT_WAIT_MS,
    scroll_rounds: int = 0,
    scroll_delay_ms: int = 1200,
    premium_proxy: bool | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Download HTML for the given page through the external ScrapingBee API."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("The provided URL must start with http:// or https://")

    hostname = (parsed.hostname or "").lower()
    if premium_proxy is None:
        premium_proxy = any(domain in hostname for domain in ["amazon.", "ebay.", "walmart."])

    params: dict[str, str | int] = {
        "api_key": resolve_api_key(api_key),
        "url": url,
        "render_js": "true" if render_js else "false",
        "wait": int(wait_ms),
        "block_resources": "false",
        "json_response": "false",
    }
    if premium_proxy:
        params["premium_proxy"] = "true"
    if country_code:
        params["country_code"] = country_code
    if scroll_rounds > 0:
        # ScrapingBee scenarios have their own execution timeout, so keep the
        # fallback deep-scroll useful but bounded.
        bounded_rounds = max(1, min(int(scroll_rounds), 28))
        bounded_delay = max(500, min(int(scroll_delay_ms), 1500))
        params["js_scenario"] = json.dumps(
            {
                "strict": False,
                "instructions": [
                    {"wait": max(1000, min(int(wait_ms), 8000))},
                    {
                        "infinite_scroll": {
                            "max_count": bounded_rounds,
                            "delay": bounded_delay,
                        }
                    },
                    {"wait": 1500},
                ],
            }
        )

    try:
        response = requests.get(
            SCRAPINGBEE_ENDPOINT,
            params=params,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        details = exc.response.text[:300] if exc.response is not None else str(exc)
        raise RuntimeError(f"ScrapingBee request failed: {details}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach ScrapingBee: {exc}") from exc

    return response.text
