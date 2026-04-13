"""
pipeline.py — Data pipeline that ties the crawler and parser together.

• Drive URL discovery (via crawler.py).
• Fetch each course page (via http_client.py).
• Parse the HTML into a structured record (via parser.py).
• Deduplicate records by URL.
• Validate that exactly TARGET_COURSES records were produced.
• Write the final JSON output file.
"""

import json
import logging
import os
from typing import List, Dict, Any

import config
from crawler import discover_course_urls
from http_client import build_session, safe_get
from parser import parse_course_page

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deduplicate(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove records with duplicate course_website_url values."""
    seen_urls: set = set()
    unique: List[Dict[str, Any]] = []

    for record in records:
        url = record.get("course_website_url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(record)
        else:
            logger.warning("Dropping duplicate record for URL: %s", url)

    return unique


def _save_json(records: List[Dict[str, Any]], path: str) -> None:
    """Write records to a JSON file, creating parent directories if needed."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)

    logger.info("Output written → %s (%d records)", path, len(records))


def _print_summary(records: List[Dict[str, Any]]) -> None:
    """Log a human-readable summary of each scraped record."""
    separator = "─" * 60
    logger.info(separator)
    logger.info("SCRAPE SUMMARY — %d records", len(records))
    logger.info(separator)

    for i, rec in enumerate(records, start=1):
        logger.info(
            "[%d] %s | %s | Duration: %s | IELTS: %s | Fee: %s",
            i,
            rec.get("program_course_name", "?"),
            rec.get("study_level", "?"),
            rec.get("course_duration", "?"),
            rec.get("min_ielts", "?"),
            rec.get("yearly_tuition_fee", "?"),
        )

    logger.info(separator)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def run() -> List[Dict[str, Any]]:
    """
    Execute the full scraping pipeline:
      1. Discover TARGET_COURSES course URLs.
      2. Fetch and parse each course page.
      3. Deduplicate and validate the result set.
      4. Save to the configured JSON output file.

    Returns the list of course record dicts.
    Raises RuntimeError if fewer than TARGET_COURSES unique records result.
    """
    logger.info("═" * 60)
    logger.info("Coventry University Scraper — pipeline start")
    logger.info("Target: %d courses  |  Output: %s", config.TARGET_COURSES, config.OUTPUT_FILE)
    logger.info("═" * 60)

    # ── Step 1: Discover course URLs ─────────────────────────────────────────
    logger.info("STEP 1/3 — Discovering course URLs …")
    course_urls = discover_course_urls()
    logger.info("Discovered %d course URLs.", len(course_urls))

    # ── Step 2: Fetch and parse each course page ──────────────────────────────
    logger.info("STEP 2/3 — Fetching and parsing course pages …")
    session = build_session()
    records: List[Dict[str, Any]] = []

    for idx, url in enumerate(course_urls, start=1):
        logger.info("  [%d/%d] %s", idx, len(course_urls), url)

        resp = safe_get(session, url)
        if resp is None:
            logger.warning("  → Could not fetch page; skipping.")
            continue

        try:
            record = parse_course_page(resp.text, url)
            records.append(record)
        except Exception as exc:  # noqa: BLE001
            logger.error("  → Parser crashed for %s: %s", url, exc, exc_info=True)

    # ── Step 3: Deduplicate, validate, save ───────────────────────────────────
    logger.info("STEP 3/3 — Deduplicating and saving …")
    records = _deduplicate(records)

    if len(records) < config.TARGET_COURSES:
        raise RuntimeError(
            f"Pipeline produced only {len(records)} valid records "
            f"(need {config.TARGET_COURSES}). "
            "Inspect the logs above for fetch/parse errors."
        )

    # Truncate to exactly TARGET_COURSES (in case we got more)
    records = records[: config.TARGET_COURSES]

    _save_json(records, config.OUTPUT_FILE)
    _print_summary(records)

    logger.info("Pipeline complete. ✓")
    return records
