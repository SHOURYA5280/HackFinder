"""
Triggers Bright Data Scraper Studio collectors via the API, waits for
each to finish, and saves the results as flat CSV files consumed by
the source-specific parsers.

Requires env vars: BRIGHT_DATA_API_TOKEN, WEMAKEDEVS_COLLECTOR_ID,
DEVPOST_COLLECTOR_ID, DEVFOLIO_COLLECTOR_ID.

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
    "devfolio": {
        "collector_id": os.environ["DEVFOLIO_COLLECTOR_ID"],
        "target_url": "https://devfolio.co/hackathons",
        "output_csv": "raw_devfolio.csv",
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


def parse_brightdata_response(text):
    """
    Parse Bright Data responses that may contain:
    - normal JSON
    - a JSON array
    - NDJSON / JSON Lines
    - multiple JSON values concatenated together

    Returns either:
    - a status dict
    - a list of records
    """

    text = text.strip()

    if not text:
        raise ValueError("Bright Data returned an empty response")

    # ---------------------------------------------------------
    # First try normal JSON.
    # This is the format documented by Bright Data.
    # ---------------------------------------------------------
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # ---------------------------------------------------------
    # If normal JSON fails, the response may contain multiple
    # JSON values / JSON Lines.
    #
    # Example:
    # {"title": "..."}
    # {"title": "..."}
    # ---------------------------------------------------------
    decoder = json.JSONDecoder()
    values = []
    position = 0
    length = len(text)

    while position < length:
        # Skip whitespace between JSON values
        while position < length and text[position].isspace():
            position += 1

        if position >= length:
            break

        try:
            value, next_position = decoder.raw_decode(text, position)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Bright Data returned malformed JSON/NDJSON. "
                f"Could not parse near character {position}: "
                f"{text[position:position + 500]!r}"
            ) from exc

        values.append(value)
        position = next_position

    if not values:
        raise ValueError("Bright Data returned no JSON values")

    # If there was one JSON value, return it directly.
    if len(values) == 1:
        return values[0]

    # Multiple JSON values:
    #
    # If one of them is already a list, use that list.
    for value in values:
        if isinstance(value, list):
            return value

    # Otherwise treat multiple JSON objects as records.
    if all(isinstance(value, dict) for value in values):
        return values

    raise ValueError(
        "Bright Data returned multiple JSON values, but they "
        "could not be interpreted as records."
    )


def poll_and_download(collection_id, max_wait=600, interval=15):
    """
    Poll Bright Data until the collection is complete.

    Handles:
    - normal JSON responses
    - Bright Data status objects
    - JSON arrays
    - wrapped result dictionaries
    - NDJSON / multiple JSON values
    """

    waited = 0

    while waited < max_wait:

        resp = requests.get(
            f"{BASE}/dca/dataset",
            params={"id": collection_id},
            headers={
                "Authorization": f"Bearer {API_TOKEN}"
            },
            timeout=30,
        )

        # -----------------------------------------------------
        # Don't hide HTTP errors.
        # -----------------------------------------------------
        if resp.status_code not in (200, 202):
    raise RuntimeError(
        f"Bright Data returned HTTP {resp.status_code}: "
        f"{resp.text[:1000]}"
    )

        # -----------------------------------------------------
        # Parse the response ourselves instead of using
        # resp.json(), because DevPost is currently returning
        # more than one JSON value.
        # -----------------------------------------------------
        try:
            data = parse_brightdata_response(resp.text)

        except Exception as exc:
            print("Failed to parse Bright Data response.")
            print(f"Collection ID: {collection_id}")
            print(f"Content-Type: {resp.headers.get('Content-Type')}")
            print(f"Response length: {len(resp.text)}")
            print("Response preview:")
            print(resp.text[:2000])
            print("Response ending:")
            print(resp.text[-1000:])

            raise exc

        # -----------------------------------------------------
        # Normal ready response:
        #
        # [
        #     {...},
        #     {...}
        # ]
        # -----------------------------------------------------
        if isinstance(data, list):
            return data

        # -----------------------------------------------------
        # Status / wrapped responses.
        # -----------------------------------------------------
        if isinstance(data, dict):

            status = str(data.get("status", "")).lower()

            if status in (
                "running",
                "queued",
                "pending",
                "building",
                "collecting"
                "processing",
            ):
                print(f" collection still {status}...")
                time.sleep(interval)
                waited += interval
                continue

            # -------------------------------------------------
            # Some response shapes wrap the records.
            # -------------------------------------------------
            for key in (
                "data",
                "result",
                "results",
                "records",
                "hackathons",
            ):
                value = data.get(key)

                if isinstance(value, list):
                    return value

            # -------------------------------------------------
            # If this looks like one actual record rather than
            # a status object, accept it as a single record.
            # -------------------------------------------------
            if "status" not in data:
                return [data]

            print("Unexpected Bright Data response:")
            print(json.dumps(data, indent=2)[:3000])

            raise ValueError(
                "Bright Data returned an unexpected response shape."
            )

        raise ValueError(
            f"Unexpected Bright Data response type: "
            f"{type(data).__name__}"
        )

    raise TimeoutError(
        f"Collection {collection_id} did not finish "
        f"within {max_wait} seconds"
    )

def save_as_csv(records, path):
    """Save flat records so every source parser gets ordinary CSV fields."""
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("Collector response must be a list of object records")

    fieldnames = list(dict.fromkeys(
        key for record in records for key in record
    ))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


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
