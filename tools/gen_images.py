"""Generate favicon set + og image from the same design system as the page.

Outputs (all in site/):
  favicon.svg          - dark tile, Space Grotesk 'A' glyph as a real path
  favicon-32.png       - PNG fallback
  apple-touch-icon.png - 180x180
  og.png               - 1200x630 link-preview card (same contour art math)

Deterministic given the same font + gen_contours settings.
"""

import math
import random
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageDraw, ImageFont

import gen_contours

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs"
VF = SITE / "fonts" / "SpaceGrotesk-VF.ttf"
BOLD_TTF = SITE / "fonts" / "_sg-bold-full.ttf"  # temp, for PIL rendering

CARD = (12, 13, 18)        # #0c0d12
INK = (244, 245, 249)      # #f4f5f9
DIM = (143, 147, 168)      # #8f93a8
INDIGO = (67, 83, 255)     # #4353ff
VIOLET = (139, 92, 246)    # #8b5cf6
PINK = (244, 114, 182)     # #f472b6


def ensure_bold_ttf() -> Path:
    if not BOLD_TTF.exists():
        font = TTFont(VF)
        instantiateVariableFont(font, {"wght": 700}, inplace=True)
        font.save(BOLD_TTF)
        font.close()
    return BOLD_TTF


def glyph_a_path() -> tuple[str, float, float]:
    """The 'A' glyph outline from Space Grotesk Bold as an SVG path string."""
    font = TTFont(ensure_bold_ttf())
    glyph_set = font.getGlyphSet()
    glyph = glyph_set["A"]
    upm = font["head"].unitsPerEm
    # flip y (font coords are y-up), scale to a 100-unit box
    scale = 100.0 / upm
    pen = SVGPathPen(glyph_set)
    tpen = TransformPen(pen, (scale, 0, 0, -scale, 0, 100 * 0.78))
    glyph.draw(tpen)
    return pen.getCommands(), glyph.width * scale, 100.0


def make_favicon_svg() -> None:
    d, gw, _ = glyph_a_path()
    # center the glyph in a 128 tile (glyph box is ~100 tall after scaling)
    ox = (128 - gw) / 2
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
        '<rect width="128" height="128" rx="28" fill="#0c0d12"/>'
        f'<path d="{d}" transform="translate({ox:.1f},16)" fill="#f4f5f9"/>'
        "</svg>"
    )
    (SITE / "favicon.svg").write_text(svg, encoding="utf-8")
    print("favicon.svg written")


def make_favicon_pngs() -> None:
    for size, name in ((32, "favicon-32.png"), (180, "apple-touch-icon.png")):
        s = 8  # supersample
        img = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        r = int(size * s * 0.22)
        dr.rounded_rectangle([0, 0, size * s - 1, size * s - 1], radius=r, fill=CARD)
        fnt = ImageFont.truetype(str(ensure_bold_ttf()), int(size * s * 0.72))
        bbox = dr.textbbox((0, 0), "A", font=fnt)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        dr.text(
            ((size * s - w) / 2 - bbox[0], (size * s - h) / 2 - bbox[1]),
            "A", font=fnt, fill=INK,
        )
        img = img.resize((size, size), Image.LANCZOS)
        img.save(SITE / name)
        print(f"{name} written")


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ring_color(t: float):
    """indigo -> violet -> pink across the ring family, like the CSS gradient."""
    if t < 0.55:
        return lerp(INDIGO, VIOLET, t / 0.55)
    return lerp(VIOLET, PINK, (t - 0.55) / 0.45)


def make_og() -> None:
    W, H, S = 1200, 630, 2  # render 2x then downsample
    img = Image.new("RGB", (W * S, H * S), CARD)
    dr = ImageDraw.Draw(img)

    # contour rings, right side, same math as the page art
    rng = random.Random(gen_contours.SEED)
    freqs = [1, 2, 3, 5, 7]
    amps = [0.06, 0.09, 0.055, 0.026, 0.011]
    phases = [rng.uniform(0, 2 * math.pi) for _ in freqs]
    cx, cy = 1050 * S, 315 * S
    for i in range(18):
        r0 = (30 + 19.5 * i) * S
        drift = i * 0.085
        pts = []
        for k in range(192):
            theta = 2 * math.pi * k / 192
            wob = sum(a * math.sin(f * theta + p + drift * f)
                      for a, f, p in zip(amps, freqs, phases))
            r = r0 * (1 + wob)
            pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta) * 0.92))
        t = i / 17
        col = ring_color(t)
        fade = 1.0 - 0.62 * t
        col = lerp(CARD, col, fade)
        dr.line(pts + [pts[0]], fill=col, width=2 * S, joint="curve")

    bold = ImageFont.truetype(str(ensure_bold_ttf()), 92 * S)
    dr.text((80 * S, 200 * S), "The phone gets\nanswered.", font=bold, fill=INK)
    reg = ImageFont.truetype(str(ensure_bold_ttf()), 32 * S)
    dr.text((84 * S, 452 * S), "AVXT · AI receptionist for Ontario home service shops",
            font=reg, fill=DIM)

    img = img.resize((W, H), Image.LANCZOS)
    img.save(SITE / "og.png", optimize=True)
    print(f"og.png written ({(SITE / 'og.png').stat().st_size:,} bytes)")


def main() -> None:
    make_favicon_svg()
    make_favicon_pngs()
    make_og()


if __name__ == "__main__":
    main()
