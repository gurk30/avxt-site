"""Build the deployed font files from the Space Grotesk variable TTF.

Produces three static-weight, latin-subset woff2 files. Run after
tools/fetch_font.py. Deterministic: same input TTF -> same outputs.
"""

from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "docs" / "fonts"
VF = FONTS / "SpaceGrotesk-VF.ttf"

WEIGHTS = {400: "regular", 500: "medium", 700: "bold"}

# Every character the page is allowed to render in Space Grotesk. The copy
# tests keep page text inside this set, so a missing glyph can't ship.
UNICODES = (
    "U+0020-007E,"  # printable ASCII
    "U+2018-2019,"  # curly single quotes / apostrophe
    "U+201C-201D,"  # curly double quotes
    "U+00A9,"       # (c)
    "U+00B7"        # middle dot separator
)


def main() -> None:
    for weight, name in WEIGHTS.items():
        font = TTFont(VF)
        instantiateVariableFont(font, {"wght": weight}, inplace=True)
        tmp = FONTS / f"_sg-{name}.ttf"
        font.save(tmp)

        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = ["kern", "liga", "calt"]
        options.drop_tables += ["DSIG"]
        ss = subset.Subsetter(options=options)
        ss.populate(unicodes=subset.parse_unicodes(UNICODES))
        out_font = subset.load_font(str(tmp), options)
        ss.subset(out_font)
        out = FONTS / f"space-grotesk-{name}.woff2"
        out_font.flavor = "woff2"  # save() alone would emit raw TTF bytes
        out_font.save(str(out))
        out_font.close()  # release the Windows file handle before unlink
        tmp.unlink()
        print(f"{out.name}: {out.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
