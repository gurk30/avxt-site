"""Generate the hero's topographic contour-ring art as an inline SVG fragment.

Deterministic (seeded); the test suite regenerates this and asserts the
fragment embedded in site/index.html matches byte-for-byte, so the art in
production is always reproducible from this file.

Design intent (owner's 2026-08-15 reference): thin-line topographic /
fingerprint wave rings, blue -> violet -> pink gradient, sitting on the right
side of the dark hero card and overlapping its edge.
"""

import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "_gen" / "contours.svg"

SEED = 47
RINGS = 20
BASE_R = 26.0
STEP = 18.5
CX, CY = 520.0, 300.0
VIEW = (0, 0, 1040, 640)
POINTS = 192  # samples per ring


def ring_path(rng: random.Random, ring_index: int, phases, amps, freqs) -> str:
    """One closed wobbling ring as an SVG path (Catmull-Rom-ish via line segs).

    Per-ring phase drift keeps neighbouring rings roughly parallel, which is
    what reads as topography instead of noise.
    """
    r0 = BASE_R + STEP * ring_index
    drift = ring_index * 0.085
    pts = []
    for i in range(POINTS):
        theta = 2 * math.pi * i / POINTS
        wobble = 0.0
        for a, f, p in zip(amps, freqs, phases):
            wobble += a * math.sin(f * theta + p + drift * f)
        r = r0 * (1.0 + wobble)
        x = CX + r * math.cos(theta)
        y = CY + r * math.sin(theta) * 0.92  # slight vertical squash
        pts.append((x, y))
    # integer coordinates: invisible at 1.3px strokes, ~30% smaller output
    d = f"M{pts[0][0]:.0f} {pts[0][1]:.0f}"
    for x, y in pts[1:]:
        d += f"L{x:.0f} {y:.0f}"
    return d + "Z"


def build() -> str:
    rng = random.Random(SEED)
    # f=1 skews the whole ring family off-round (egg-shaped asymmetry);
    # the higher frequencies carry the fingerprint wobble
    freqs = [1, 2, 3, 5, 7]
    amps = [0.06, 0.09, 0.055, 0.026, 0.011]
    phases = [rng.uniform(0, 2 * math.pi) for _ in freqs]

    x0, y0, w, h = VIEW
    parts = [
        f'<svg class="contours" viewBox="{x0} {y0} {w} {h}" fill="none" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">',
        "<defs>",
        '<linearGradient id="cg" x1="0" y1="1" x2="1" y2="0">',
        '<stop offset="0" stop-color="#4353ff"/>',
        '<stop offset=".55" stop-color="#8b5cf6"/>',
        '<stop offset="1" stop-color="#f472b6"/>',
        "</linearGradient>",
        "</defs>",
    ]
    for i in range(RINGS):
        # outer rings fade so the art dissolves into the card edge
        opacity = 0.95 - 0.6 * (i / (RINGS - 1))
        d = ring_path(rng, i, phases, amps, freqs)
        parts.append(
            f'<path d="{d}" stroke="url(#cg)" stroke-width="1.4" '
            f'opacity="{opacity:.2f}"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    svg = build()
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT} ({len(svg):,} chars, {RINGS} rings)")


if __name__ == "__main__":
    main()
