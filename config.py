"""
config.py — Central configuration for the Coventry University scraper.
All tuneable constants live here so callers never need magic numbers.
"""

UNIVERSITY_NAME = "Coventry University"
UNIVERSITY_BASE_URL = "https://www.coventry.ac.uk"
COUNTRY = "United Kingdom"
ADDRESS = "Priory Street, Coventry, CV1 5FB, United Kingdom"

# ── Seed discovery URLs ───────────────────────────────────────────────────────
# These pages list course links that the crawler will follow.
SEED_URLS = [
    "https://www.coventry.ac.uk/study-at-coventry/postgraduate-study/az-course-list/",
    "https://www.coventry.ac.uk/study-at-coventry/undergraduate-study/course-finder/",
    "https://www.coventry.ac.uk/study-at-coventry/course-finder-search-results/?startdate=1082",
]

# ── URL patterns ──────────────────────────────────────────────────────────────
# A valid course page must match this path prefix.
COURSE_URL_PREFIX = "/course-structure/"

# Segments that indicate noise / non-course pages (skip them).
EXCLUDED_URL_FRAGMENTS = [
    "/blog/", "/news/", "/events/", "/research/", "/business/",
    "/jobs/", "/life-on-campus/", "/the-university/", "/unibuddy/",
    "/clearing/", "/nite/", "/online/", "/cuc/", "/cul/", "/cus/",
    "/wroclaw/", "/london/", "#", "javascript:", "mailto:",
]

# ── Crawl limits ──────────────────────────────────────────────────────────────
TARGET_COURSES = 5          # stop once this many unique courses are collected
MAX_CRAWL_PAGES = 40        # hard ceiling on pages visited during discovery

# ── HTTP settings ─────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 20        # seconds
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 1.5  # exponential back-off multiplier
BETWEEN_REQUESTS_DELAY = 1.2  # polite delay (seconds) between fetches

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_FILE = "output/courses_output.json"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"          # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ── Fallback / missing-value sentinel ────────────────────────────────────────
MISSING = "NA"
