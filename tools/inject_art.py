"""Inject the generated contour SVG into the page(s), idempotently.

Replaces whatever sits between the <!-- contours:start --> and
<!-- contours:end --> markers with the current site/_gen/contours.svg.
Run gen_contours.py first. The test suite asserts the injected fragment
matches a fresh generation, so art and generator can never drift.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAG = ROOT / "docs" / "_gen" / "contours.svg"
START = "<!-- contours:start -->"
END = "<!-- contours:end -->"


def inject(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    if START not in html:
        return False
    svg = FRAG.read_text(encoding="utf-8")
    new = re.sub(
        re.escape(START) + ".*?" + re.escape(END),
        START + svg + END,
        html,
        flags=re.S,
    )
    path.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    targets = [ROOT / "docs" / "index.html"]
    targets += sorted((ROOT / "docs" / "variants").glob("*.html")) if (ROOT / "docs" / "variants").exists() else []
    done = [t.name for t in targets if t.exists() and inject(t)]
    print(f"injected contours into: {', '.join(done) or 'nothing'}")
    if not done:
        sys.exit(1)


if __name__ == "__main__":
    main()
