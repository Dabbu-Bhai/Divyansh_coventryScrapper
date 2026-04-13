"""
http_client.py — Shared requests.Session with retry, back-off, and
                 consistent headers.  Import build_session() wherever
                 you need an HTTP client.
"""

import logging
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

logger = logging.getLogger(__name__)


def build_session() -> requests.Session:
    """
    Return a requests.Session pre-configured with:
      • Uniform browser-like headers
      • Automatic retry with exponential back-off on transient errors
      • A reasonable timeout (enforced by the callers, not the adapter)
    """
    session = requests.Session()
    session.headers.update(config.REQUEST_HEADERS)

    retry_strategy = Retry(
        total=config.MAX_RETRIES,
        backoff_factor=config.RETRY_BACKOFF_FACTOR,
        # Retry on these HTTP status codes (server-side transient errors)
        status_forcelist=[429, 500, 502, 503, 504],
        # Retry on connection-level errors too
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def safe_get(
    session: requests.Session,
    url: str,
    timeout: int = config.REQUEST_TIMEOUT,
    delay: float = config.BETWEEN_REQUESTS_DELAY,
) -> Optional[requests.Response]:
    """
    Perform a GET request with:
      • Pre-request polite delay
      • Exception catching (network errors, timeouts, etc.)
      • HTTP-error logging (non-200 responses)

    Returns the Response object on success, or None on any failure.
    """
    time.sleep(delay)  # be polite: don't hammer the server

    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True)

        if resp.status_code == 200:
            logger.debug("GET %s → %d (%d bytes)", url, resp.status_code, len(resp.content))
            return resp

        logger.warning("GET %s → unexpected status %d", url, resp.status_code)
        return None

    except requests.exceptions.Timeout:
        logger.error("Timeout fetching %s", url)
    except requests.exceptions.TooManyRedirects:
        logger.error("Too many redirects for %s", url)
    except requests.exceptions.ConnectionError as exc:
        logger.error("Connection error for %s: %s", url, exc)
    except requests.exceptions.RequestException as exc:
        logger.error("Request failed for %s: %s", url, exc)

    return None
