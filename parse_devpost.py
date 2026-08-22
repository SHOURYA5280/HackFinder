"""
Parses the raw Scraper Studio CSV output for Devpost hackathons
(scraped from devpost.com/hackathons?status[]=open), flattens the
nested JSON into one row per hackathon, and adds a computed `status`
field. Closed hackathons are dropped, matching parse_wemakedevs.py.

Usage:
    python3 parse_devpost.py input.csv output.json
"""

import csv
import json
import sys

from hackathon_dates import classify_by_date


def load_raw_rows(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for row in rows:
        raw = row.get("hackathons")
        if raw:
            return json.loads(raw)
    return []


def compute_status(hackathon):
    """We already scraped only the 'open' filter on Devpost's side,
    but that can include events that have already started (Devpost's
    'open' means submissions are open, not that it hasn't begun yet).
    So we still classify by date ourselves. If a date can't be parsed
    precisely, default to 'open' -- Devpost's own filter already told
    us it's not finished."""
    status = classify_by_date(hackathon.get("event_dates", ""))
    return status or "open"


def clean(hackathon):
    return {
        "title": hackathon.get("title", "").strip(),
        "description": "",  # not available on the listing page
        "event_dates": hackathon.get("event_dates", "").strip(),
        "prize_amount": hackathon.get("prize_amount", "").strip(),
        "modes": hackathon.get("location", "").strip(),  # Devpost uses "location" for this
        "location": hackathon.get("location", "").strip(),
        "hackathon_page_url": hackathon.get("hackathon_page_url", "").strip(),
        "status": compute_status(hackathon),
        "source": "Devpost",
        "level": None,
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 parse_devpost.py input.csv output.json")
        sys.exit(1)

    input_csv, output_json = sys.argv[1], sys.argv[2]

    raw_hackathons = load_raw_rows(input_csv)
    cleaned = [clean(h) for h in raw_hackathons if h.get("title")]

    dropped = sum(1 for h in cleaned if h["status"] == "closed")
    cleaned = [h for h in cleaned if h["status"] != "closed"]

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    open_count = sum(1 for h in cleaned if h["status"] == "open")
    running_count = sum(1 for h in cleaned if h["status"] == "running")
    print(f"Parsed {len(cleaned)} hackathons -> {output_json} "
          f"(dropped {dropped} closed)")
    print(f"  open: {open_count}, running: {running_count}")


if __name__ == "__main__":
    main()
