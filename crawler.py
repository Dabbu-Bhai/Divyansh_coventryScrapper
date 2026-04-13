"""
crawler.py — Discovers course page URLs from Coventry University's website.

1. Fetch each seed URL (A-Z course list, course search results, etc.).
2. Extract every href that points to a /course-structure/ path.
3. Normalise and validate each candidate URL.
4. Stop after TARGET_COURSES unique valid URLs have been collected
   (or MAX_CRAWL_PAGES pages have been visited — whichever comes first).

The crawler deliberately does NOT follow arbitrary links; it stays within
the /course-structure/ tree to avoid crawling unrelated sections.
"""

import logging
from typing import List, Set
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

import config
from http_client import build_session, safe_get

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _normalise_url(raw: str, base: str = config.UNIVERSITY_BASE_URL) -> str:
    """
    Convert a potentially relative URL to an absolute, canonical URL:
      • Remove fragments (#section)
      • Ensure trailing slash
      • Strip query strings (course detail pages don't need them)
    """
    absolute = urljoin(base, raw.strip())
    parsed = urlparse(absolute)

    # Drop the fragment and query string — we want the canonical page
    clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    # Ensure a trailing slash for consistency
    if not clean.endswith("/"):
        clean += "/"

    return clean


def _is_valid_course_url(url: str) -> bool:
    """
    Return True only if the URL:
      • belongs to the official Coventry domain
      • contains the expected course-structure path prefix
      • does not match any excluded fragment
    """
    parsed = urlparse(url)

    # Must be on the official domain
    if "coventry.ac.uk" not in parsed.netloc:
        return False

    # Must start with the course-structure prefix
    if not parsed.path.startswith(config.COURSE_URL_PREFIX):
        return False

    # Must not be a bare /course-structure/ root (no slug → not a real course)
    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) < 3:
        return False

    # Must not match any excluded fragments
    for fragment in config.EXCLUDED_URL_FRAGMENTS:
        if fragment in url:
            return False

    return True


def _extract_course_links(html: str, page_url: str) -> List[str]:
    """
    Parse the HTML of a discovery page and return all href values that
    look like course-structure URLs.
    """
    soup = BeautifulSoup(html, "lxml")
    found: List[str] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()

        # Quick pre-filter before full normalisation
        if config.COURSE_URL_PREFIX not in href and "/course-structure/" not in href:
            continue

        normalised = _normalise_url(href, base=page_url)
        if _is_valid_course_url(normalised):
            found.append(normalised)

    logger.debug("Found %d candidate course links on %s", len(found), page_url)
    return found


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def discover_course_urls() -> List[str]:
    """
    Crawl the seed pages and return exactly TARGET_COURSES unique,
    validated course page URLs.

    Raises RuntimeError if fewer than TARGET_COURSES URLs were found.
    """
    session = build_session()
    visited_pages: Set[str] = set()
    collected_urls: Set[str] = set()
    pages_crawled = 0

    logger.info(
        "Starting URL discovery — target: %d courses, page cap: %d",
        config.TARGET_COURSES,
        config.MAX_CRAWL_PAGES,
    )

    # ── Phase 1: harvest from seed pages ────────────────────────────────────
    for seed in config.SEED_URLS:
        if len(collected_urls) >= config.TARGET_COURSES:
            break
        if pages_crawled >= config.MAX_CRAWL_PAGES:
            break
        if seed in visited_pages:
            continue

        logger.info("Fetching seed page: %s", seed)
        resp = safe_get(session, seed)
        visited_pages.add(seed)
        pages_crawled += 1

        if resp is None:
            logger.warning("Skipping unreachable seed: %s", seed)
            continue

        new_links = _extract_course_links(resp.text, seed)
        before = len(collected_urls)
        collected_urls.update(new_links)
        logger.info(
            "Seed %s → %d new course URLs (total: %d)",
            seed, len(collected_urls) - before, len(collected_urls),
        )

    # ── Phase 2: follow discovered course-structure pages to find more ───────
    # The /course-structure/ug/ or /course-structure/pg/ listing pages
    # sometimes contain additional course links not on the seed pages.
    if len(collected_urls) < config.TARGET_COURSES:
        listing_seeds = [
            f"{config.UNIVERSITY_BASE_URL}/course-structure/ug/",
            f"{config.UNIVERSITY_BASE_URL}/course-structure/pg/",
        ]
        for listing in listing_seeds:
            if len(collected_urls) >= config.TARGET_COURSES:
                break
            if pages_crawled >= config.MAX_CRAWL_PAGES:
                break
            if listing in visited_pages:
                continue

            logger.info("Fetching listing page: %s", listing)
            resp = safe_get(session, listing)
            visited_pages.add(listing)
            pages_crawled += 1

            if resp is None:
                continue

            new_links = _extract_course_links(resp.text, listing)
            collected_urls.update(new_links)

    final_urls = list(collected_urls)[: config.TARGET_COURSES]

    logger.info(
        "Discovery complete — %d unique course URLs found (pages crawled: %d)",
        len(final_urls), pages_crawled,
    )

    if len(final_urls) < config.TARGET_COURSES:
        raise RuntimeError(
            f"Only {len(final_urls)} course URLs found; "
            f"need {config.TARGET_COURSES}. "
            "Check seed URLs or COURSE_URL_PREFIX in config.py."
        )

    return final_urls
