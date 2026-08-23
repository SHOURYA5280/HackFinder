"""
Shared date-parsing helpers used by every source-specific parser
(parse_wemakedevs.py, parse_devpost.py, ...). Pulled out here so the
same regex and status logic isn't duplicated per source -- one place
to fix if a date format shows up that we haven't seen before.
"""

import re
from datetime import date

# Always the real current date -- NEVER hardcode this, or the status
# logic quietly goes stale the next day (this happened once already).
TODAY = date.today()

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
MONTH_PAT = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"

# Matches ranges like "Aug 22-30", "Aug 17-23", "Feb 23 - Mar 1",
# "Jul 31 - Oct 01, 2026". The end-month is optional because
# same-month ranges only name the month once (e.g. the "30" in
# "Aug 22-30" has no month attached). Handles both a plain hyphen
# and an en-dash, since different sites use different characters.
RANGE_PAT = re.compile(
    rf"{MONTH_PAT}\s+(\d{{1,2}})\s*[\u2013\u2010-]\s*(?:{MONTH_PAT}\s+)?(\d{{1,2}})"
)
# Matches a single date like "Aug 22" with nothing else around it.
SINGLE_PAT = re.compile(rf"^\s*{MONTH_PAT}\s+(\d{{1,2}})\s*$")


def _safe_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date_range(text, fallback_year=None):
    """Returns (start_date, end_date), or (None, None) if the text
    can't be parsed precisely (e.g. 'September 2026' has no day)."""
    fallback_year = fallback_year or TODAY.year
    year_match = re.search(r"\b(20\d{2})\b", text)
    year = int(year_match.group(1)) if year_match else fallback_year

    m = RANGE_PAT.search(text)
    if m:
        start_mon, start_day, end_mon, end_day = m.groups()
        start_month = MONTHS[start_mon.lower()]
        end_month = MONTHS[end_mon.lower()] if end_mon else start_month
        start = _safe_date(year, start_month, int(start_day))
        # A range such as "Dec 30 - Jan 2" crosses into the following year.
        end_year = year + 1 if end_month < start_month else year
        end = _safe_date(end_year, end_month, int(end_day))
        return start, end

    m = SINGLE_PAT.match(text.strip())
    if m:
        mon, day = m.groups()
        d = _safe_date(year, MONTHS[mon.lower()], int(day))
        return d, d

    return None, None


def classify_by_date(text):
    """Pure date-based classification: 'open' (hasn't started),
    'running' (today's inside the range), 'closed' (already ended),
    or None if the text couldn't be parsed precisely enough to say.
    Source-specific parsers supply their own fallback for the None
    case (e.g. a domain heuristic)."""
    year_match = re.search(r"\b(20\d{2})\b", text)
    if year_match and int(year_match.group(1)) < TODAY.year:
        return "closed"

    start, end = parse_date_range(text)
    if start and end:
        if TODAY < start:
            return "open"
        if start <= TODAY <= end:
            return "running"
        return "closed"

    return None


def normalize_mode(location_text):
    """Maps a free-text location (e.g. 'Online', 'Kalyani, India',
    'Hybrid - San Francisco') to the fixed vocabulary the site's mode
    filter expects: 'remote', 'in-person', or 'hybrid'. None of the
    sources give us this directly anymore -- only a location string --
    so we infer it."""
    text = (location_text or "").strip().lower()
    if not text or "online" in text or "remote" in text or "virtual" in text:
        return "remote"
    if "hybrid" in text:
        return "hybrid"
    return "in-person"
