"""
Parses the raw Scraper Studio CSV for Devfolio hackathons (listing +
description combined in one pass, from devfolio.co/hackathons).

Usage:
    python3 parse_devfolio.py input.csv output.json
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
    return classify_by_date(row.get("event_dates", "")) or "open"


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
        "source": "Devfolio",
        "level": None,
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 parse_devfolio.py input.csv output.json")
        sys.exit(1)

    input_csv, output_json = sys.argv[1], sys.argv[2]

    rows = load_rows(input_csv)

    seen = set()
    deduped = []
    for row in rows:
        url = row.get("hackathon_page_url", "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(row)

    cleaned = [clean(r) for r in deduped if r.get("title", "").strip()]

    dropped = sum(1 for h in cleaned if h["status"] == "closed")
    cleaned = [h for h in cleaned if h["status"] != "closed"]

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    open_count = sum(1 for h in cleaned if h["status"] == "open")
    running_count = sum(1 for h in cleaned if h["status"] == "running")
    print(f"Parsed {len(rows)} raw rows -> {len(deduped)} unique -> "
          f"{len(cleaned)} kept -> {output_json} (dropped {dropped} closed)")
    print(f"  open: {open_count}, running: {running_count}")


if __name__ == "__main__":
    main()
