"""
Parses the raw Scraper Studio CSV for Devpost hackathons (scraped from
devpost.com/hackathons?status[]=open&status[]=upcoming, listing +
description combined in one pass). Deduplicates by page URL -- the
crawler can revisit the same hackathon multiple times -- and drops
anything that turns out to be closed once we check the actual dates.

Usage:
    python3 parse_devpost.py input.csv output.json
"""

import sys

from hackathon_dates import classify_by_date, normalize_mode
from parser_utils import (
    build_hackathon,
    load_export_rows,
    print_parse_summary,
    unique_rows_by_url,
    write_active_hackathons,
)


def compute_status(row):
    """Use Devpost's open/upcoming listing as the fallback for vague dates."""
    status = classify_by_date(row.get("event_dates", ""))
    return status or "open"


def clean(row):
    """Normalize a Devpost row for the shared frontend schema."""
    return build_hackathon(
        row, "Devpost", compute_status(row), normalize_mode(row.get("location", ""))
    )


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 parse_devpost.py input.csv output.json")
        sys.exit(1)

    input_csv, output_json = sys.argv[1], sys.argv[2]

    rows = load_export_rows(input_csv)
    unique_rows = unique_rows_by_url(rows)
    hackathons = [clean(row) for row in unique_rows if row.get("title", "").strip()]
    active_hackathons, dropped_count = write_active_hackathons(hackathons, output_json)
    print_parse_summary(
        len(rows), len(unique_rows), active_hackathons, dropped_count, output_json
    )


if __name__ == "__main__":
    main()
