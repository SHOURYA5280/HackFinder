"""Build the deployable HTML and JavaScript files from the combined dataset.

Usage:
    python3 build_site.py hackathons_combined.json
"""

import json
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).parent
INDEX_TEMPLATE = ROOT / "index_template.html"
SCRIPT_TEMPLATE = ROOT / "script_template.js"
INDEX_OUTPUT = ROOT / "index.html"
SCRIPT_OUTPUT = ROOT / "script.js"


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 build_site.py <hackathons.json>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        hackathons = json.load(f)

    data = json.dumps(hackathons, indent=2, ensure_ascii=False)
    last_checked = f"{date.today():%b} {date.today().day}, {date.today():%Y}"
    script = SCRIPT_TEMPLATE.read_text(encoding="utf-8")
    script = script.replace("__HACKATHON_DATA__", data, 1)
    script = script.replace("__LAST_CHECKED__", last_checked, 1)
    if "__HACKATHON_DATA__" in script or "__LAST_CHECKED__" in script:
        raise ValueError("Unreplaced placeholder in script template")

    index = INDEX_TEMPLATE.read_text(encoding="utf-8")
    index = index.replace('src="script_template.js"', 'src="script.js"', 1)

    SCRIPT_OUTPUT.write_text(script, encoding="utf-8")
    INDEX_OUTPUT.write_text(index, encoding="utf-8")
    print(f"Built {INDEX_OUTPUT.name} and {SCRIPT_OUTPUT.name} from {len(hackathons)} hackathons")


if __name__ == "__main__":
    main()
