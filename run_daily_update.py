"""
Triggers both Bright Data Scraper Studio collectors via the API,
waits for each to finish, and saves the results in the same CSV
shape Scraper Studio's own export uses (one 'hackathons' column
holding a JSON list) -- so parse_wemakedevs.py / parse_devpost.py
don't need to change at all.

Requires env vars: BRIGHT_DATA_API_TOKEN, WEMAKEDEVS_COLLECTOR_ID,
DEVPOST_COLLECTOR_ID.

Usage:
    python3 run_daily_update.py
"""

import csv
import json
import os
import sys
import time

import requests

BASE = "https://api.brightdata.com"
API_TOKEN = os.environ["BRIGHT_DATA_API_TOKEN"]

SOURCES = {
    "wemakedevs": {
        "collector_id": os.environ["WEMAKEDEVS_COLLECTOR_ID"],
        "target_url": "https://www.wemakedevs.org/hackathons",
        "output_csv": "raw_wemakedevs.csv",
    },
    "devpost": {
        "collector_id": os.environ["DEVPOST_COLLECTOR_ID"],
        "target_url": "https://devpost.com/hackathons?status[]=open",
        "output_csv": "raw_devpost.csv",
    },
}


def trigger(collector_id, target_url):
    resp = requests.post(
        f"{BASE}/dca/trigger",
        params={"collector": collector_id, "queue_next": 1},
        headers={
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json",
        },
        json=[{"url": target_url}],
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["collection_id"]


def poll_and_download(collection_id, max_wait=600, interval=15):
    """The same /dca/dataset endpoint returns either an in-progress
    status or the finished list of records once ready."""
    waited = 0
    while waited < max_wait:
        resp = requests.get(
            f"{BASE}/dca/dataset",
            params={"id": collection_id},
            headers={"Authorization": f"Bearer {API_TOKEN}"},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            if not (isinstance(data, dict) and data.get("status") in
                    ("running", "queued", "pending")):
                return data
        time.sleep(interval)
        waited += interval
    raise TimeoutError(f"Collection {collection_id} did not finish in time")


def save_as_csv(records, path):
    """Matches the exact shape Scraper Studio's own CSV export uses,
    so the existing parsers work unmodified."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hackathons"])
        writer.writerow([json.dumps(records, ensure_ascii=False)])


def main():
    for name, cfg in SOURCES.items():
        print(f"Triggering {name}...")
        collection_id = trigger(cfg["collector_id"], cfg["target_url"])
        print(f"  collection_id={collection_id}, polling...")
        records = poll_and_download(collection_id)

        # Some responses nest the actual list one level down
        if (isinstance(records, list) and records
                and isinstance(records[0], dict) and "hackathons" in records[0]):
            records = records[0]["hackathons"]

        save_as_csv(records, cfg["output_csv"])
        print(f"  saved {len(records)} records -> {cfg['output_csv']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Daily update failed: {e}", file=sys.stderr)
        sys.exit(1)
