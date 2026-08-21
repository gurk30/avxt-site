"""Fetch Space Grotesk (OFL) from the official google/fonts repository.

Owner-approved download (chat, 2026-08-20). Source of truth:
https://github.com/google/fonts/tree/main/ofl/spacegrotesk

The variable TTF is kept out of git (see .gitignore); the checked-in artifacts
are the subset woff2 files produced by tools/build_fonts.py.
"""

import urllib.request
from pathlib import Path

URL = "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf"
DEST = Path(__file__).resolve().parent.parent / "docs" / "fonts" / "SpaceGrotesk-VF.ttf"


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"fetching {URL}")
    with urllib.request.urlopen(URL) as resp:
        data = resp.read()
    DEST.write_bytes(data)
    print(f"wrote {DEST} ({len(data):,} bytes)")


if __name__ == "__main__":
    main()
