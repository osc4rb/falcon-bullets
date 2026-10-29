"""Build "Falcon Sans": Source Sans 3 at a chosen weight with a straight lowercase l.

The 715A's entries are set in Myriad Pro, which can't be redistributed. Source Sans 3
(Adobe, SIL OFL 1.1) is its open sibling; two tweaks make it match the form:
  * weight: picked by measuring ink against Acrobat's render of a real 715A
  * the default "l" has a tail; Myriad's is a straight stroke, so l -> l.a
OFL requires a modified font to drop the reserved name "Source", hence "Falcon Sans".

Usage:  python build_font.py <SourceSans3VF-Upright.ttf> <weight> <out.ttf>
"""
import sys

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

STRAIGHT = {"l": "l.a", "lslash": "lslash.a"}
# Characters a 715A realistically needs: Latin-1 plus common punctuation and dashes.
UNICODES = list(range(0x20, 0x7F)) + list(range(0xA0, 0x100)) + [
    0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x20AC, 0x2122]


def build(vf_path, weight, out_path):
    font = instancer.instantiateVariableFont(TTFont(vf_path), {"wght": float(weight)})
    for table in font["cmap"].tables:
        if table.isUnicode():
            for cp, glyph in list(table.cmap.items()):
                if glyph in STRAIGHT:
                    table.cmap[cp] = STRAIGHT[glyph]
    for rec in font["name"].names:
        s = rec.toUnicode()
        if rec.nameID in (1, 4, 16, 21):
            rec.string = "Falcon Sans" if rec.nameID in (1, 16, 21) else "Falcon Sans Regular"
        elif rec.nameID == 6:
            rec.string = "FalconSans-Regular"
        elif rec.nameID == 3:
            rec.string = "FalconSans-Regular;Falcon Bullets"
        elif rec.nameID == 2 and s:
            rec.string = "Regular"
    if "DSIG" in font:
        del font["DSIG"]
    opts = subset.Options()
    opts.layout_features = []      # pdf-lib doesn't apply OpenType features; keep the cmap mapping
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=UNICODES)
    sub.subset(font)
    font.save(out_path)
    print(f"wrote {out_path} (weight {weight})")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], sys.argv[3])
