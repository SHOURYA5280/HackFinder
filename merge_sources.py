"""
Merges the cleaned per-source JSON files into one combined dataset
for build_site.py.

Usage:
    python3 merge_sources.py wemakedevs_clean.json devpost_clean.json combined.json
"""

import json
import re
import sys


def clean_description(text):
    """Strip stray HTML markup some sources leave in (e.g. Devpost's
    '<html> <head></head> <body></body> </html>' prefix)."""
    if not text:
        return text
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 merge_sources.py <in1.json> [<in2.json> ...] <out.json>")
        sys.exit(1)

    *input_paths, output_path = sys.argv[1:]

    combined = []
    for path in input_paths:
        with open(path, encoding="utf-8") as f:
            combined.extend(json.load(f))

    for h in combined:
        h["description"] = clean_description(h.get("description", ""))

    # Soonest deadline first -- unparsed dates sort last, not first
    combined.sort(key=lambda h: h.get("event_dates") or "\uffff")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"Merged {len(combined)} hackathons from {len(input_paths)} sources -> {output_path}")


if __name__ == "__main__":
    main()
