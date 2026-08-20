"""
Parses the raw Scraper Studio CSV output for WeMakeDevs hackathons,
flattens the nested JSON into one row per hackathon, and adds a
computed `status` field.

Usage:
    python3 parse_wemakedevs.py input.csv output.json
"""

import csv
import json
import sys


def load_raw_rows(csv_path):
    """Scraper Studio put all hackathons as one JSON blob in a single
    cell (column 'hackathons'). This pulls that list out."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for row in rows:
        raw = row.get("hackathons")
        if raw:
            return json.loads(raw)
    return []


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

# Matches ranges like "Aug 22-30", "Aug 17-23", "Feb 23 - Mar 1".
# The end-month is optional because same-month ranges only name the
# month once (e.g. the "30" in "Aug 22-30" has no month attached).
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


def parse_date_range(text, fallback_year):
    """Returns (start_date, end_date) or (None, None) if the text
    can't be parsed precisely (e.g. 'September 2026' has no day)."""
    year_match = re.search(r"\b(20\d{2})\b", text)
    year = int(year_match.group(1)) if year_match else fallback_year

    m = RANGE_PAT.search(text)
    if m:
        start_mon, start_day, end_mon, end_day = m.groups()
        start_month = MONTHS[start_mon.lower()]
        end_month = MONTHS[end_mon.lower()] if end_mon else start_month
        start = _safe_date(year, start_month, int(start_day))
        end = _safe_date(year, end_month, int(end_day))
        return start, end

    m = SINGLE_PAT.match(text.strip())
    if m:
        mon, day = m.groups()
        d = _safe_date(year, MONTHS[mon.lower()], int(day))
        return d, d

    return None, None


def compute_status(hackathon):
    """Three states:
    - 'open'    -- hasn't started yet (registration window)
    - 'running' -- today falls inside the event's date range
    - 'closed'  -- already ended

    If an explicit year in the text is before this year, it's closed
    with no further parsing needed. Otherwise we try to parse an
    actual start/end date and compare to today. If the text can't be
    parsed at all (e.g. 'September 2026', no day given), we fall back
    to the archive-subdomain signal (WeMakeDevs moves finished
    hackathons there) -- but that fallback can only say open/closed,
    never running, since we don't know the day.
    """
    text = hackathon.get("event_dates", "")
    url = hackathon.get("hackathon_page_url", "")

    year_match = re.search(r"\b(20\d{2})\b", text)
    if year_match and int(year_match.group(1)) < TODAY.year:
        return "closed"

    start, end = parse_date_range(text, fallback_year=TODAY.year)
    if start and end:
        if TODAY < start:
            return "open"
        if start <= TODAY <= end:
            return "running"
        return "closed"

    # Couldn't parse a precise date -- fall back to the
    # archive-subdomain signal (open/closed only).
    return "closed" if "archive.wemakedevs.org" in url else "open"


def clean(hackathon):
    return {
        "title": hackathon.get("title", "").strip(),
        "description": hackathon.get("description", "").strip(),
        "event_dates": hackathon.get("event_dates", "").strip(),
        "prize_amount": hackathon.get("prize_amount", "").strip(),
        "modes": hackathon.get("modes", "").strip(),
        "location": hackathon.get("location", "").strip(),
        "hackathon_page_url": hackathon.get("hackathon_page_url", "").strip(),
        "status": compute_status(hackathon),
        "source": "WeMakeDevs",
        # level is not on the source page -- filled in later by
        # keyword-matching the description (see tag_level.py)
        "level": None,
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 parse_wemakedevs.py input.csv output.json")
        sys.exit(1)

    input_csv, output_json = sys.argv[1], sys.argv[2]

    raw_hackathons = load_raw_rows(input_csv)
    cleaned = [clean(h) for h in raw_hackathons if h.get("title")]

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    open_count = sum(1 for h in cleaned if h["status"] == "open")
    closed_count = sum(1 for h in cleaned if h["status"] == "closed")
    print(f"Parsed {len(cleaned)} hackathons -> {output_json}")
    print(f"  open: {open_count}, closed: {closed_count}")


if __name__ == "__main__":
    main()
