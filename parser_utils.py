"""Reusable helpers for turning Bright Data CSV exports into site records."""

import csv
import json
from pathlib import Path


def load_export_rows(csv_path: str) -> list[dict]:
    """Load a flat CSV export or unpack the legacy ``hackathons`` JSON column."""
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8") as file:
        source_rows = list(csv.DictReader(file))

    rows = []
    for source_row in source_rows:
        nested_json = source_row.get("hackathons")
        if not nested_json:
            rows.append(source_row)
            continue

        try:
            nested_rows = json.loads(nested_json)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid hackathons JSON in {path}") from error

        if not isinstance(nested_rows, list):
            raise ValueError(f"Expected a list in the hackathons column of {path}")
        rows.extend(nested_rows)

    return rows


def unique_rows_by_url(rows: list[dict]) -> list[dict]:
    """Keep the first row for each page URL and discard unusable records."""
    seen_urls = set()
    unique_rows = []
    for row in rows:
        url = row.get("hackathon_page_url", "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique_rows.append(row)
    return unique_rows


def build_hackathon(row: dict, source: str, status: str, mode: str) -> dict:
    """Map an untrusted scraper row to the public site's stable data shape."""
    return {
        "title": row.get("title", "").strip(),
        "description": row.get("description", "").strip(),
        "event_dates": row.get("event_dates", "").strip(),
        "prize_amount": row.get("prize", "").strip(),
        "modes": mode,
        "location": row.get("location", "").strip(),
        "hackathon_page_url": row.get("hackathon_page_url", "").strip(),
        "status": status,
        "source": source,
        "level": None,
    }


def write_active_hackathons(hackathons: list[dict], output_path: str) -> tuple[list[dict], int]:
    """Exclude closed events, write the JSON dataset, and return the active records."""
    active_hackathons = [item for item in hackathons if item["status"] != "closed"]
    dropped_count = len(hackathons) - len(active_hackathons)

    with Path(output_path).open("w", encoding="utf-8") as file:
        json.dump(active_hackathons, file, indent=2, ensure_ascii=False)

    return active_hackathons, dropped_count


def print_parse_summary(raw_count: int, unique_count: int, active_hackathons: list[dict],
                        dropped_count: int, output_path: str) -> None:
    """Print a consistent, concise summary for local runs and GitHub Actions logs."""
    open_count = sum(item["status"] == "open" for item in active_hackathons)
    running_count = sum(item["status"] == "running" for item in active_hackathons)
    print(
        f"Parsed {raw_count} raw rows -> {unique_count} unique -> "
        f"{len(active_hackathons)} kept -> {output_path} "
        f"(dropped {dropped_count} closed)"
    )
    print(f"  open: {open_count}, running: {running_count}")
