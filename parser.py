"""
parser.py — Extracts structured course data from a single Coventry University
            course page.

• Every field has at least two fallback selectors / strategies.
• All extraction is wrapped in try/except so a single broken field
  never aborts the whole record.
• Missing or empty values are replaced with config.MISSING ("NA").
• Raw text is preserved — no heavy cleaning is applied (per assignment).
"""

import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

import config

logger = logging.getLogger(__name__)

# Canonical schema keys (same order as the assignment spec).
SCHEMA_KEYS: List[str] = [
    "program_course_name",
    "university_name",
    "course_website_url",
    "campus",
    "country",
    "address",
    "study_level",
    "course_duration",
    "all_intakes_available",
    "mandatory_documents_required",
    "yearly_tuition_fee",
    "scholarship_availability",
    "gre_gmat_mandatory_min_score",
    "indian_regional_institution_restrictions",
    "class_12_boards_accepted",
    "gap_year_max_accepted",
    "min_duolingo",
    "english_waiver_class12",
    "english_waiver_moi",
    "min_ielts",
    "kaplan_test_of_english",
    "min_pte",
    "min_toefl",
    "ug_academic_min_gpa",
    "twelfth_pass_min_cgpa",
    "mandatory_work_exp",
    "max_backlogs",
]

def _clean(text: Optional[str]) -> str:
    """Collapse whitespace; return MISSING sentinel if blank."""
    if not text:
        return config.MISSING
    cleaned = " ".join(text.split())
    return cleaned if cleaned else config.MISSING


def _get_text(tag: Optional[Tag]) -> str:
    """Return stripped text content of a BeautifulSoup tag, or MISSING."""
    if tag is None:
        return config.MISSING
    return _clean(tag.get_text(separator=" ", strip=True))


def _find_first(soup: BeautifulSoup, selectors: List[str]) -> Optional[Tag]:
    """Try CSS selectors in order; return the first match or None."""
    for sel in selectors:
        result = soup.select_one(sel)
        if result:
            return result
    return None


def _search_text(text: str, pattern: str, group: int = 1) -> str:
    """Return the first regex match group, or MISSING."""
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return _clean(match.group(group))
    return config.MISSING


def _get_section_text(soup: BeautifulSoup, heading_keywords: List[str]) -> str:
    """
    Find a section whose heading contains any of the given keywords,
    then return the combined text of all sibling/child paragraphs,
    list items, and divs that follow until the next heading.
    """
    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        heading_text = tag.get_text(strip=True).lower()
        if any(kw.lower() in heading_text for kw in heading_keywords):
            parts: List[str] = []
            for sibling in tag.find_next_siblings():
                if sibling.name and re.match(r"^h[1-6]$", sibling.name):
                    break  # stop at the next section heading
                if sibling.name in ("p", "ul", "ol", "div", "span", "table"):
                    text = sibling.get_text(separator=" ", strip=True)
                    if text:
                        parts.append(text)
            if parts:
                return _clean(" | ".join(parts))

    return config.MISSING

def _extract_course_name(soup: BeautifulSoup) -> str:
    tag = _find_first(soup, [
        "h1.course-title",
        "h1.title",
        "h1",
        ".course-header h1",
        ".page-title",
    ])
    return _get_text(tag)


def _extract_study_level(soup: BeautifulSoup, url: str) -> str:
    """
    Try multiple strategies:
      1. Explicit 'Study level' label on the page.
      2. Infer from the URL path (/ug/ vs /pg/).
      3. Check for common degree abbreviations in the course name.
    """
    # Strategy 1 — 'Study level:' label
    for tag in soup.find_all(text=re.compile(r"Study level", re.I)):
        parent = tag.parent
        if parent:
            text = parent.get_text(separator=" ", strip=True)
            match = re.search(r"Study level[:\s]+(.+)", text, re.I)
            if match:
                return _clean(match.group(1))

    # Strategy 2 — URL inference
    if "/course-structure/ug/" in url:
        return "Undergraduate"
    if "/course-structure/pg/" in url:
        return "Postgraduate"

    # Strategy 3 — degree abbreviation in course name
    name = _extract_course_name(soup).lower()
    if any(k in name for k in ("msc", "mba", "ma ", "pg ", "master", "postgraduate")):
        return "Postgraduate"
    if any(k in name for k in ("bsc", "ba ", "undergraduate", "beng", "llb", "meng")):
        return "Undergraduate"

    return config.MISSING


def _extract_location(soup: BeautifulSoup) -> str:
    """Return the campus/location label from the 'Course features' block."""
    # Strategy 1 — labelled dt/dd pairs
    for dt in soup.find_all("dt"):
        if "location" in dt.get_text(strip=True).lower():
            dd = dt.find_next_sibling("dd")
            if dd:
                return _get_text(dd)

    # Strategy 2 — look for a 'Location' heading followed by text
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        if "location" in heading.get_text(strip=True).lower():
            next_tag = heading.find_next_sibling()
            if next_tag:
                return _get_text(next_tag)

    # Strategy 3 — search for known campus names in the body text
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"Location\s*[:\-]?\s*(Coventry University[^\n,]+)",
        r"(Coventry University \(Coventry\))",
        r"(Coventry University London[^\n,]*)",
        r"Campus\s*[:\-]?\s*([^\n,]+)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_duration(soup: BeautifulSoup) -> str:
    for dt in soup.find_all("dt"):
        if "duration" in dt.get_text(strip=True).lower():
            dd = dt.find_next_sibling("dd")
            if dd:
                return _get_text(dd)

    full_text = soup.get_text(separator=" ")
    patterns = [
        r"Duration\s*[:\-]?\s*([^\n]+(?:year|month|week)[^\n]*)",
        r"(\d[\d\s]*year[s]?[\w\s,/]+)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_start_dates(soup: BeautifulSoup) -> str:
    # dt/dd pairs
    for dt in soup.find_all("dt"):
        label = dt.get_text(strip=True).lower()
        if "start" in label or "intake" in label:
            dd = dt.find_next_sibling("dd")
            if dd:
                return _get_text(dd)

    full_text = soup.get_text(separator=" ")
    patterns = [
        r"Start date[s]?\s*[:\-]?\s*([^\n]+)",
        r"Intake[s]?\s*[:\-]?\s*([^\n]+)",
        r"((?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+\d{4}(?:\s+[|/,]\s*(?:January|February|"
        r"March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{4})*)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_tuition_fee(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        # Prefer an explicit "International fee" line
        r"International\s+(?:students?['\s]?\s*)?(?:tuition\s+)?fee[s]?\s*[:\-]?\s*(£[\d,]+(?:\s*per year)?)",
        r"Tuition fee[s]?\s*[:\-]?\s*(£[\d,]+(?:[^\n]{0,40})?)",
        r"(£[\d,]+)\s*per\s*year",
        r"fee[s]?\s*[:\-]?\s*£\s*([\d,]+)",
        # USD / generic currency
        r"((?:£|USD|GBP)\s*[\d,]+(?:\.\d{2})?(?:\s*per year)?)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_scholarships(soup: BeautifulSoup) -> str:
    section = _get_section_text(soup, ["scholarship", "funding", "bursary", "finance"])
    if section != config.MISSING:
        return section

    full_text = soup.get_text(separator=" ")
    patterns = [
        r"(scholarship[s]?[^\.\n]{0,300})",
        r"(bursary[^\.\n]{0,200})",
        r"(alumni\s+discount[^\.\n]{0,200})",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_mandatory_docs(soup: BeautifulSoup) -> str:
    section = _get_section_text(
        soup,
        ["mandatory document", "supporting document", "required document",
         "what you need to apply", "documents required"],
    )
    if section != config.MISSING:
        return section

    full_text = soup.get_text(separator=" ")
    patterns = [
        r"((?:transcript|personal statement|reference|passport|"
        r"certificate|portfolio)[^\.\n]{0,300})",
        r"supporting documentation[:\s]+([^\n]+)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_ielts(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"IELTS[^\d]*([\d.]+)\s*overall",
        r"IELTS[^\d]*overall[^\d]*([\d.]+)",
        r"IELTS[^:]*:\s*([\d.]+)",
        r"minimum\s+IELTS[^\d]*([\d.]+)",
        r"IELTS[^\d]*([\d.]+)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_toefl(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"TOEFL\s*iBT[^\d]*([\d]+)\s*(?:overall|and|with|minimum)?",
        r"TOEFL[^\d]*([\d]+)",
        r"TOEFL[^:]*:\s*([\d]+)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_pte(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"PTE[^\d]*([\d]+)\s*(?:overall)?",
        r"Pearson Test of English[^\d]*([\d]+)",
        r"PTE Academic[^\d]*([\d]+)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_duolingo(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"Duolingo[^\d]*([\d]+)",
        r"DET[^\d]*([\d]+)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_work_exp(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"((?:\d+\s+years?\s+)?(?:relevant\s+)?work\s+experience[^\.\n]{0,200})",
        r"work\s+experience[:\s]+([^\n\.]+)",
        r"(professional\s+experience\s+(?:required|of[^\.\n]{0,100}))",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_english_waiver(soup: BeautifulSoup, waiver_type: str) -> str:
    """
    waiver_type: 'class12' or 'moi' (medium of instruction).
    Looks for any mention of English language waiver conditions.
    """
    full_text = soup.get_text(separator=" ")
    if waiver_type == "class12":
        patterns = [
            r"(English\s+(?:language\s+)?(?:waiver|exemption)[^\.\n]{0,300}class\s*12[^\.\n]{0,200})",
            r"(class\s*12[^\.\n]{0,200}English\s+(?:language\s+)?(?:waiver|exemption)[^\.\n]{0,200})",
            r"(Standard\s+XII[^\.\n]{0,200}English[^\.\n]{0,200})",
        ]
    else:  # moi
        patterns = [
            r"(medium\s+of\s+instruction[^\.\n]{0,300})",
            r"(MOI[^\.\n]{0,200})",
            r"(English\s+(?:as\s+)?medium[^\.\n]{0,200})",
        ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_gpa(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"GPA\s*(?:of|:)?\s*([\d.]+)",
        r"minimum\s+(?:GPA|grade point)[^\d]*([\d.]+)",
        r"(2[:\.]1|2[:\.]2|first[\s-]+class)",  # UK degree classification
        r"(\d+[:\.]?\d*\s*%\s*(?:minimum|overall)?)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_twelfth_cgpa(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"(?:class\s*12|Standard\s*XII|12th)[^\d]*([\d]+%?)\s*(?:minimum|overall|pass)?",
        r"(?:minimum\s+)?(?:overall\s+)?score\s+of\s+([\d]+%?)\s+in\s+(?:Standard|class)\s*XII",
        r"65%\s+in\s+(?:class|Standard)\s*12",
        r"60%\s+in\s+Standard\s*XII",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_backlogs(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"(?:maximum|max\.?)\s+(\d+)\s+backlogs?",
        r"backlog[s]?\s*(?:allowed|permitted|accepted)[:\s]*(\d+)",
        r"(\d+)\s+backlogs?\s*(?:allowed|permitted|maximum)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_indian_restrictions(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"(India[n]?\s+(?:regional|institution)[^\.\n]{0,300})",
        r"((?:NAAC|UGC|AICTE)[^\.\n]{0,200})",
        r"(recognized[^\.\n]{0,200}India[n]?[^\.\n]{0,200})",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_class12_boards(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"((?:CBSE|ICSE|ISC|State Board|Central Board)[^\.\n]{0,300})",
        r"(boards?\s+accepted[:\s]+[^\.\n]{0,200})",
        r"((?:Central|Maharashtra|Karnataka|Tamil Nadu|Andhra Pradesh|Kerala|Uttarakhand)"
        r"[^\.\n]{0,200}board[s]?[^\.\n]{0,100})",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_gap_year(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"gap\s+year[^\.\n]{0,200}",
        r"maximum\s+(\d+)\s+years?\s+gap",
        r"gap\s+of\s+(?:up\s+to\s+)?(\d+)\s+year",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


def _extract_kaplan(soup: BeautifulSoup) -> str:
    full_text = soup.get_text(separator=" ")
    patterns = [
        r"Kaplan[^\.\n]{0,200}",
        r"Kaplan Test of English[^\d]*([\d]+)",
    ]
    for pat in patterns:
        result = _search_text(full_text, pat)
        if result != config.MISSING:
            return result

    return config.MISSING


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def parse_course_page(html: str, url: str) -> Dict[str, Any]:
    """
    Parse the HTML of a course page and return a dict matching SCHEMA_KEYS.

    Every field is extracted independently; a failure in one extraction
    never prevents the others from running.
    """
    soup = BeautifulSoup(html, "lxml")

    record: Dict[str, Any] = {key: config.MISSING for key in SCHEMA_KEYS}

    extractors = {
        "program_course_name":             lambda: _extract_course_name(soup),
        "university_name":                 lambda: config.UNIVERSITY_NAME,
        "course_website_url":              lambda: url,
        "campus":                          lambda: _extract_location(soup),
        "country":                         lambda: config.COUNTRY,
        "address":                         lambda: config.ADDRESS,
        "study_level":                     lambda: _extract_study_level(soup, url),
        "course_duration":                 lambda: _extract_duration(soup),
        "all_intakes_available":           lambda: _extract_start_dates(soup),
        "mandatory_documents_required":    lambda: _extract_mandatory_docs(soup),
        "yearly_tuition_fee":              lambda: _extract_tuition_fee(soup),
        "scholarship_availability":        lambda: _extract_scholarships(soup),
        "gre_gmat_mandatory_min_score":    lambda: config.MISSING,  # not listed by Coventry
        "indian_regional_institution_restrictions": lambda: _extract_indian_restrictions(soup),
        "class_12_boards_accepted":        lambda: _extract_class12_boards(soup),
        "gap_year_max_accepted":           lambda: _extract_gap_year(soup),
        "min_duolingo":                    lambda: _extract_duolingo(soup),
        "english_waiver_class12":          lambda: _extract_english_waiver(soup, "class12"),
        "english_waiver_moi":              lambda: _extract_english_waiver(soup, "moi"),
        "min_ielts":                       lambda: _extract_ielts(soup),
        "kaplan_test_of_english":          lambda: _extract_kaplan(soup),
        "min_pte":                         lambda: _extract_pte(soup),
        "min_toefl":                       lambda: _extract_toefl(soup),
        "ug_academic_min_gpa":             lambda: _extract_gpa(soup),
        "twelfth_pass_min_cgpa":           lambda: _extract_twelfth_cgpa(soup),
        "mandatory_work_exp":              lambda: _extract_work_exp(soup),
        "max_backlogs":                    lambda: _extract_backlogs(soup),
    }

    for field, extractor in extractors.items():
        try:
            value = extractor()
            record[field] = value if value else config.MISSING
        except Exception as exc:  # noqa: BLE001
            logger.warning("Field '%s' extraction failed for %s: %s", field, url, exc)
            record[field] = config.MISSING

    course_name = record.get("program_course_name", config.MISSING)
    level = record.get("study_level", config.MISSING)
    logger.info("Parsed: '%s' (%s) — %s", course_name, level, url)

    return record
