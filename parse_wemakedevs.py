"""
Parses the raw Scraper Studio CSV for WeMakeDevs hackathons (listing +
description combined in one pass). Rows for archived/closed hackathons
often fail extraction (blank title) since old pages have a different
layout -- those are dropped along with anything closed by date.

Usage:
    python3 parse_wemakedevs.py input.csv output.json
"""

import csv
import json
import sys

from hackathon_dates import classify_by_date, normalize_mode


def load_rows(csv_path):
    """Load either Bright Data's flat CSV export or its legacy
    one-cell ``hackathons`` JSON export."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    flattened = []
    for row in rows:
        raw = row.get("hackathons")
        if raw:
            try:
                nested = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid hackathons JSON in {csv_path}") from exc
            if not isinstance(nested, list):
                raise ValueError(f"Expected a list in the hackathons column of {csv_path}")
            flattened.extend(nested)
        else:
            flattened.append(row)
    return flattened


def compute_status(row):
    """Fallback for unparseable dates: use the archive-subdomain
    signal (WeMakeDevs moves finished hackathons there)."""
    status = classify_by_date(row.get("event_dates", ""))
    if status:
        return status
    url = row.get("hackathon_page_url", "")
    return "closed" if "archive.wemakedevs.org" in url else "open"


def clean(row):
    return {
        "title": row.get("title", "").strip(),
        "description": row.get("description", "").strip(),
        "event_dates": row.get("event_dates", "").strip(),
        "prize_amount": row.get("prize", "").strip(),
        "modes": normalize_mode(row.get("location", "")),
        "location": row.get("location", "").strip(),
        "hackathon_page_url": row.get("hackathon_page_url", "").strip(),
        "status": compute_status(row),
        "source": "WeMakeDevs",
        "level": None,
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 parse_wemakedevs.py input.csv output.json")
        sys.exit(1)

    input_csv, output_json = sys.argv[1], sys.argv[2]

    rows = load_rows(input_csv)
    cleaned = [clean(r) for r in rows if r.get("title", "").strip()]

    dropped = sum(1 for h in cleaned if h["status"] == "closed")
    cleaned = [h for h in cleaned if h["status"] != "closed"]

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    open_count = sum(1 for h in cleaned if h["status"] == "open")
    running_count = sum(1 for h in cleaned if h["status"] == "running")
    print(f"Parsed {len(rows)} raw rows -> {len(cleaned)} kept -> "
          f"{output_json} (dropped {dropped} closed)")
    print(f"  open: {open_count}, running: {running_count}")


if __name__ == "__main__":
    main()
