"""Helpers for downloading HTML from product or review pages through external collectors."""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse

import requests

SCRAPINGBEE_ENDPOINT = "https://app.scrapingbee.com/api/v1/"
SCRAPEDO_ENDPOINT = "https://api.scrape.do/"
DEFAULT_TIMEOUT_SECONDS = 90
DEFAULT_WAIT_MS = 5000
PREMIUM_PROXY_HOST_HINTS = (
    "aliexpress.",
    "amazon.",
    "ebay.",
    "etsy.",
    "market.yandex.",
    "ozon.",
    "shein.",
    "temu.",
    "walmart.",
    "wildberries.",
)
BLOCKED_PAGE_MARKERS = (
    "access denied",
    "are you a robot",
    "captcha",
    "checking your browser",
    "enable javascript and cookies",
    "robot check",
    "unusual traffic",
    "verify you are human",
)


def resolve_api_key(api_key: str | None = None) -> str:
    """Resolve the ScrapingBee API key from an explicit value or environment variable."""
    resolved = (api_key or os.getenv("SCRAPINGBEE_API_KEY") or "").strip()
    if not resolved:
        raise ValueError(
            "ScrapingBee API key is missing. Set `SCRAPINGBEE_API_KEY` in the backend environment."
        )
    return resolved


def resolve_scrapedo_api_key(api_key: str | None = None) -> str:
    """Resolve the Scrape.do API key from an explicit value or environment variable."""
    resolved = (api_key or os.getenv("SCRAPEDO_API_KEY") or "").strip()
    if not resolved:
        raise ValueError(
            "Scrape.do API key is missing. Set `SCRAPEDO_API_KEY` in the backend environment."
        )
    return resolved


def fetch_html_with_fallback(
    url: str,
    scrapingbee_api_key: str | None = None,
    scrapedo_api_key: str | None = None,
    render_js: bool = True,
    country_code: str | None = None,
    wait_ms: int = DEFAULT_WAIT_MS,
    scroll_rounds: int = 0,
    scroll_delay_ms: int = 1200,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Try ScrapingBee first, then Scrape.do when live page collection fails."""
    first_error: Exception | None = None
    has_scrapingbee = bool((scrapingbee_api_key or os.getenv("SCRAPINGBEE_API_KEY") or "").strip())
    has_scrapedo = bool((scrapedo_api_key or os.getenv("SCRAPEDO_API_KEY") or "").strip())

    if has_scrapingbee:
        try:
            return fetch_html_via_scrapingbee(
                url=url,
                api_key=scrapingbee_api_key,
                render_js=render_js,
                country_code=country_code,
                wait_ms=wait_ms,
                scroll_rounds=scroll_rounds,
                scroll_delay_ms=scroll_delay_ms,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            first_error = exc

    if has_scrapedo:
        try:
            return fetch_html_via_scrapedo(
                url=url,
                api_key=scrapedo_api_key,
                render_js=render_js,
                country_code=country_code,
                wait_ms=wait_ms,
                scroll_rounds=scroll_rounds,
                scroll_delay_ms=scroll_delay_ms,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            if first_error is not None:
                raise RuntimeError(
                    "Both scraping providers failed. "
                    f"ScrapingBee: {_compact_error(first_error)}; Scrape.do: {_compact_error(exc)}"
                ) from exc
            raise

    if first_error is not None:
        raise first_error

    raise ValueError(
        "Scraping service API key is missing. Set `SCRAPINGBEE_API_KEY` or `SCRAPEDO_API_KEY` in the backend environment."
    )


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
        premium_proxy = any(domain in hostname for domain in PREMIUM_PROXY_HOST_HINTS)

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
        raise RuntimeError(_scrapingbee_error_message(exc)) from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach ScrapingBee: {exc}") from exc

    if _looks_like_blocked_page(response.text):
        raise RuntimeError(
            "ScrapingBee fetched a bot-protection page instead of the marketplace reviews. "
            "Use HTML snapshot mode or try a lower analysis depth."
        )

    return response.text


def fetch_html_via_scrapedo(
    url: str,
    api_key: str | None = None,
    render_js: bool = True,
    country_code: str | None = None,
    wait_ms: int = DEFAULT_WAIT_MS,
    scroll_rounds: int = 0,
    scroll_delay_ms: int = 1200,
    super_proxy: bool | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Download HTML for the given page through Scrape.do as a fallback collector."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("The provided URL must start with http:// or https://")

    hostname = (parsed.hostname or "").lower()
    if super_proxy is None:
        super_proxy = any(domain in hostname for domain in PREMIUM_PROXY_HOST_HINTS)

    params: dict[str, str | int] = {
        "token": resolve_scrapedo_api_key(api_key),
        "url": url,
        "render": "true" if render_js else "false",
        "blockResources": "false",
        "customWait": max(0, min(int(wait_ms), 30000)),
        "timeout": max(1000, min(int(timeout_seconds * 1000), 120000)),
        "waitUntil": "networkidle2" if render_js else "domcontentloaded",
    }
    if super_proxy:
        params["super"] = "true"
    if country_code:
        params["geoCode"] = country_code
    if scroll_rounds > 0:
        params["playWithBrowser"] = json.dumps(_scrapedo_scroll_instructions(wait_ms, scroll_rounds, scroll_delay_ms))

    try:
        response = requests.get(
            SCRAPEDO_ENDPOINT,
            params=params,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(_scrapedo_error_message(exc)) from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach Scrape.do: {exc}") from exc

    if _looks_like_blocked_page(response.text):
        raise RuntimeError(
            "Scrape.do fetched a bot-protection page instead of the marketplace reviews. "
            "Use HTML snapshot mode or try a lower analysis depth."
        )

    return response.text


def _scrapedo_scroll_instructions(wait_ms: int, scroll_rounds: int, scroll_delay_ms: int) -> list[dict[str, int | str]]:
    bounded_rounds = max(1, min(int(scroll_rounds), 28))
    bounded_delay = max(500, min(int(scroll_delay_ms), 1500))
    instructions: list[dict[str, int | str]] = [{"Action": "Wait", "Timeout": max(1000, min(int(wait_ms), 8000))}]
    for _index in range(bounded_rounds):
        instructions.append({"Action": "ScrollY", "Value": 900})
        instructions.append({"Action": "Wait", "Timeout": bounded_delay})
    instructions.append({"Action": "Wait", "Timeout": 1500})
    return instructions


def _scrapingbee_error_message(exc: requests.HTTPError) -> str:
    response = exc.response
    status_code = response.status_code if response is not None else 0
    details = response.text[:300] if response is not None and response.text else str(exc)
    compact_details = " ".join(details.split())

    if status_code in {401, 403}:
        return (
            f"ScrapingBee request was blocked or rejected by the upstream service (HTTP {status_code}). "
            f"Details: {compact_details}"
        )
    if status_code in {402, 429}:
        return (
            f"ScrapingBee rate limit or credits issue prevented collection (HTTP {status_code}). "
            f"Details: {compact_details}"
        )
    if status_code in {500, 502, 503, 504}:
        return (
            f"ScrapingBee upstream fetch failed while collecting the marketplace page (HTTP {status_code}). "
            f"Details: {compact_details}"
        )
    return f"ScrapingBee request failed (HTTP {status_code}). Details: {compact_details}"


def _scrapedo_error_message(exc: requests.HTTPError) -> str:
    response = exc.response
    status_code = response.status_code if response is not None else 0
    details = response.text[:300] if response is not None and response.text else str(exc)
    compact_details = " ".join(details.split())

    if status_code in {401, 403}:
        return (
            f"Scrape.do request was blocked or rejected by the upstream service (HTTP {status_code}). "
            f"Details: {compact_details}"
        )
    if status_code in {402, 429}:
        return (
            f"Scrape.do rate limit or credits issue prevented collection (HTTP {status_code}). "
            f"Details: {compact_details}"
        )
    if status_code in {500, 502, 503, 504}:
        return (
            f"Scrape.do upstream fetch failed while collecting the marketplace page (HTTP {status_code}). "
            f"Details: {compact_details}"
        )
    return f"Scrape.do request failed (HTTP {status_code}). Details: {compact_details}"


def _compact_error(exc: Exception) -> str:
    return " ".join(str(exc).split())[:300]


def _looks_like_blocked_page(html: str) -> bool:
    sample = (html or "")[:12000].lower()
    return any(marker in sample for marker in BLOCKED_PAGE_MARKERS)
