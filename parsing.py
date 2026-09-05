"""Text parsing helpers, kept free of Playwright so they can be unit tested."""

import re
from typing import List, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

BASE_URL = "https://www.upwork.com"

# Upwork job URLs carry a job id like ~021968676050348026869
JOB_ID_RE = re.compile(r"~([0-9a-zA-Z]{6,})")


def clean_text(value: Optional[str]) -> str:
    """Collapse whitespace and strip, tolerating None."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def absolute_url(href: Optional[str]) -> str:
    """Turn a relative job href into a full URL and drop tracking query args."""
    if not href:
        return ""
    full = urljoin(BASE_URL, href.strip())
    parts = urlsplit(full)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def extract_job_id(url: str) -> str:
    """Pull the ~0... id out of a job URL, falling back to the path slug."""
    if not url:
        return ""
    match = JOB_ID_RE.search(url)
    if match:
        return match.group(1)
    path = urlsplit(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def parse_posted_age_hours(text: str) -> Optional[float]:
    """Convert Upwork's relative posted text into an age in hours.

    Handles the shapes Upwork actually renders, for example:
      "Posted 27 minutes ago", "yesterday", "3 days ago", "last week",
      "2 weeks ago", "last month".
    Returns None when nothing recognisable is found.
    """
    if not text:
        return None
    low = clean_text(text).lower()

    if "just now" in low or "less than a minute" in low:
        return 0.0
    if "yesterday" in low:
        return 24.0
    if "today" in low:
        return 1.0

    unit_hours = {
        "second": 1 / 3600,
        "minute": 1 / 60,
        "hour": 1.0,
        "day": 24.0,
        "week": 24.0 * 7,
        "month": 24.0 * 30,
        "year": 24.0 * 365,
    }

    # "last week" / "a day ago" have no digits, treat the article as 1.
    match = re.search(
        r"(\d+|a|an|last)\s*"
        r"(second|minute|min|hour|hr|day|week|month|year)s?",
        low,
    )
    if not match:
        return None

    raw_amount, raw_unit = match.group(1), match.group(2)
    amount = 1.0 if raw_amount in ("a", "an", "last") else float(raw_amount)
    unit = {"min": "minute", "hr": "hour"}.get(raw_unit, raw_unit)
    return amount * unit_hours[unit]


def parse_proposal_count(text: str) -> Optional[int]:
    """Turn a proposals label into a comparable number.

    Upwork shows bands ("Proposals: 5 to 10", "Less than 5", "50+"). The lower
    bound of the band is used, since that is what the competition penalty and
    the search filters are keyed on.
    """
    if not text:
        return None
    low = clean_text(text).lower()

    if "less than" in low:
        numbers = re.findall(r"\d+", low)
        return 0 if numbers else None

    numbers = [int(n) for n in re.findall(r"\d+", low)]
    if not numbers:
        return None
    return min(numbers)


def parse_price(job_type_text: str, budget_text: str = "") -> tuple:
    """Work out (price_type, rate) from the job type and budget labels.

    Examples of what Upwork renders:
      "Hourly: $15.00 - $30.00"  -> ("Hourly", "$15.00 - $30.00")
      "Fixed price" + "$250.00"  -> ("Fixed", "$250.00")
    """
    job_type_text = clean_text(job_type_text)
    budget_text = clean_text(budget_text)
    # Upwork prefixes the amount with a label, for example "Est. Budget: $250".
    budget_text = re.sub(
        r"^(est\.?\s*budget|budget|fixed[- ]price)\s*:?\s*", "",
        budget_text, flags=re.I,
    ).strip()
    low = job_type_text.lower()

    if "hourly" in low:
        rate = job_type_text.split(":", 1)[1].strip() if ":" in job_type_text else ""
        return "Hourly", rate or budget_text or "Rate not shown"
    if "fixed" in low:
        return "Fixed", budget_text or "Budget not shown"
    if budget_text:
        return "Fixed", budget_text
    return clean_text(job_type_text) or "Unknown", budget_text or ""


def dedupe_skills(skills: List[str], limit: int = 12) -> List[str]:
    """Drop blanks, UI noise and duplicates while keeping the original order."""
    seen = set()
    result = []
    for skill in skills:
        cleaned = clean_text(skill)
        if not cleaned:
            continue
        # "+3" style overflow chips carry no information.
        if re.fullmatch(r"\+\s*\d+", cleaned):
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result
