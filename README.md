# Coventry University Course Scraper

A production-quality Python web scraper that crawls the official Coventry University website (`coventry.ac.uk`), discovers course pages, and extracts structured data for **exactly 5 courses** into a clean JSON file.

---

## Project Structure

```
coventry_scraper/
├── main.py              # Entry point: CLI + logging setup
├── config.py            # All constants (URLs, timeouts, selectors, output path)
├── http_client.py       # Shared requests.Session with retry + back-off
├── crawler.py           # URL discovery: crawls seed pages → finds course URLs
├── parser.py            # HTML parser: extracts all 27 schema fields per page
├── pipeline.py          # Orchestrator: crawl → fetch → parse → deduplicate → save
├── requirements.txt     # Python dependencies
├── output/
│   └── courses_output.json   # Pre-generated output (5 course records)
└── README.md            # This file
```

---

## Architecture Overview

The scraper follows a clean **3-layer pipeline**:

```
[ Crawler ]  →  [ Parser ]  →  [ Pipeline / Data Layer ]
     |                |                  |
  Discovers       Extracts          Deduplicates
  course URLs   structured data     and saves JSON
```

| Module | Responsibility |
|---|---|
| `config.py` | Single source of truth for all constants |
| `http_client.py` | `requests.Session` + retry adapter + polite delay |
| `crawler.py` | Discovers valid `/course-structure/` URLs from seed pages |
| `parser.py` | Extracts each schema field with 2–4 fallback strategies |
| `pipeline.py` | Ties all layers together; validates + writes JSON output |
| `main.py` | CLI entry point; sets up logging; handles exit codes |

---

## Setup

### Prerequisites

- Python 3.9 or higher
- `pip`

### 1. Clone / download the project

```bash
git clone <repo-url>
cd coventry_scraper
```

### 2. (Optional) Create a virtual environment

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## How to Run

### Basic run (default output path: `output/courses_output.json`)

```bash
python main.py
```

### Override the output file path

```bash
python main.py --output results/my_courses.json
```

### Enable verbose DEBUG logging

```bash
python main.py --debug
```

### Full help

```bash
python main.py --help
```

---

## What Happens When You Run It

1. **URL Discovery** — `crawler.py` fetches the official A-Z course list and course search pages on `coventry.ac.uk`, extracts all `href` values pointing to `/course-structure/` paths, normalises them, and validates each URL against the official domain.

2. **Fetch & Parse** — `pipeline.py` iterates over the 5 discovered URLs, fetches each page via an HTTP session with automatic retries (up to 3 attempts, exponential back-off), then delegates to `parser.py`.

3. **Extraction** — `parser.py` uses 2–4 fallback CSS selectors and regex patterns per field. If a field cannot be found on the page, it is set to `"NA"` — a parse failure in one field never aborts the rest.

4. **Deduplication** — records are deduplicated by `course_website_url`; duplicates are logged and dropped.

5. **Output** — exactly 5 records are written to `output/courses_output.json` as a JSON array.

---

## Output Format

The output file is a **JSON array of 5 objects**. Each object contains the following fields:

| Field | Description |
|---|---|
| `program_course_name` | Full official course title as listed on the course page |
| `university_name` | Always `"Coventry University"` |
| `course_website_url` | Canonical URL of the official course page |
| `campus` | Campus location as shown on the page |
| `country` | Always `"United Kingdom"` |
| `address` | University postal address |
| `study_level` | `"Undergraduate"` or `"Postgraduate"` |
| `course_duration` | Duration string as listed (e.g. `"1 year full-time"`) |
| `all_intakes_available` | Start date(s) listed on the page (e.g. `"September 2026 \| January 2027"`) |
| `mandatory_documents_required` | Required application documents (raw text) |
| `yearly_tuition_fee` | Tuition fee as listed; typically international fee per year |
| `scholarship_availability` | Scholarship/funding info extracted from the page |
| `gre_gmat_mandatory_min_score` | GRE/GMAT requirement (Coventry does not require these; `"NA"`) |
| `indian_regional_institution_restrictions` | Any restrictions for Indian regional institutions |
| `class_12_boards_accepted` | Accepted Class 12 boards for English waiver eligibility |
| `gap_year_max_accepted` | Maximum gap year(s) accepted |
| `min_duolingo` | Minimum Duolingo English Test score |
| `english_waiver_class12` | English language waiver via Class 12 score |
| `english_waiver_moi` | English language waiver via Medium of Instruction |
| `min_ielts` | Minimum IELTS overall band score + component minimums |
| `kaplan_test_of_english` | Kaplan Test of English requirement |
| `min_pte` | Minimum Pearson Test of English (PTE Academic) score |
| `min_toefl` | Minimum TOEFL iBT score |
| `ug_academic_min_gpa` | Minimum undergraduate academic qualification |
| `twelfth_pass_min_cgpa` | Minimum Class 12 / Standard XII score |
| `mandatory_work_exp` | Required work experience (years/type) |
| `max_backlogs` | Maximum number of backlogs/arrears accepted |

> **Missing values:** any field not found on the page is returned as `"NA"`.  
> **Raw text is preserved:** no heavy normalisation is applied — field values may be sentences or paragraphs directly from the page, exactly as required.

### Example record

```json
{
  "program_course_name": "Computer Science MSc",
  "university_name": "Coventry University",
  "course_website_url": "https://www.coventry.ac.uk/course-structure/pg/ees/computer-science-msc/",
  "campus": "Coventry University (Coventry)",
  "country": "United Kingdom",
  "address": "Priory Street, Coventry, CV1 5FB, United Kingdom",
  "study_level": "Postgraduate",
  "course_duration": "1 year full-time | Up to 2 years full-time with professional placement",
  "all_intakes_available": "May 2026 | July 2026",
  "mandatory_documents_required": "Copies of degree/diploma certificates and academic transcripts ...",
  "yearly_tuition_fee": "£20,050 per year (international students, 2025/26)",
  "scholarship_availability": "25% alumni discount available from September 2025 ...",
  "gre_gmat_mandatory_min_score": "NA",
  "min_ielts": "6.5 overall with a minimum of 5.5 in each component",
  "min_toefl": "88 (iBT) with a minimum component score of 19",
  "ug_academic_min_gpa": "An honours degree 2:2 or above (or international equivalent) ...",
  "..."  : "..."
}
```

---

## Technical Details

### Scraping approach

- **HTTP client:** `requests.Session` with an `HTTPAdapter` configured for up to 3 retries on status codes `429, 500, 502, 503, 504` with exponential back-off (`factor = 1.5`).
- **Politeness:** 1.2-second delay between all requests — no hammering.
- **URL validation:** Only `coventry.ac.uk` URLs matching `/course-structure/` with at least 3 path segments are accepted.
- **Parser:** `BeautifulSoup` with the `lxml` back-end (faster and more tolerant than the built-in HTML parser).
- **Fallback strategy:** Every field has 2–4 independent extraction strategies (CSS selector → regex → section heading search → URL inference). If all fail, `"NA"` is returned.
- **Deduplication:** Records are deduplicated on `course_website_url` before the final JSON is written.

### Configuration

All tuneable values live in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `TARGET_COURSES` | `5` | Number of courses to scrape |
| `MAX_CRAWL_PAGES` | `40` | Hard ceiling on pages visited during discovery |
| `MAX_RETRIES` | `3` | HTTP retry attempts per request |
| `RETRY_BACKOFF_FACTOR` | `1.5` | Exponential back-off multiplier |
| `REQUEST_TIMEOUT` | `20` | Seconds before a request times out |
| `BETWEEN_REQUESTS_DELAY` | `1.2` | Polite delay between requests (seconds) |
| `OUTPUT_FILE` | `output/courses_output.json` | Output path |

---

## Important Notes

- **Official sources only.** The scraper only crawls `www.coventry.ac.uk`. Third-party aggregators (Shiksha, Yocket, etc.) are never contacted.
- **Dynamic content limitation.** Some Coventry course pages load fee/entry data via JavaScript. The scraper uses `requests` (no browser). Where dynamic content is absent in the raw HTML, fields are populated with `"NA"` and can be supplemented by fetching the international entry requirements page (`/international-students-hub/entry-requirements/`) which provides country-level data in static HTML.
- **Page layout changes.** If Coventry redesigns their course pages, update the CSS selectors in `parser.py` and the seed URLs in `config.py`.

---

## Dependencies

| Library | Version | Purpose |
|---|---|---|
| `requests` | 2.32.3 | HTTP client |
| `beautifulsoup4` | 4.12.3 | HTML parsing |
| `lxml` | 5.2.2 | Fast, tolerant HTML parser back-end for BS4 |
| `urllib3` | 2.2.1 | Retry adapter (bundled with requests) |

All are standard, widely-used libraries with no exotic dependencies.

---

## Extending the Scraper

- **More courses:** increase `TARGET_COURSES` in `config.py`.
- **Different fields:** add a new extractor lambda in `parser.py`'s `extractors` dict.
- **New seed pages:** append URLs to `SEED_URLS` in `config.py`.
- **JavaScript-rendered pages:** swap `http_client.py` for a `playwright` or `selenium` session; the rest of the pipeline is unchanged.

---

## License

For assignment/educational purposes only. All scraped data belongs to Coventry University.
