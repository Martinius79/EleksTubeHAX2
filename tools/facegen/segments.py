# SPDX-License-Identifier: GPL-3.0-or-later
"""Segment display geometry shared by the segment styles (7-segment, VFD, Varisymbol).

Two layouts:
  * 7 segments (a-g) as hexagonal polygons with pointed ends, optional italic skew.
  * 14 segments as stroke lines (frame, centre cross and four diagonals), the layout of the
    Telefunken Varisymbol gas-discharge display; its top and bottom segments are not split.
"""

from __future__ import annotations

# --- 7 segments ------------------------------------------------------------------------------
#  aaa
# f   b
#  ggg
# e   c
#  ddd
SEVEN_DIGITS = {
    0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc",
    5: "afgcd", 6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abcdfg",
}


def seven_segments(box, thickness: float, gap: float, skew: float = 0.0, shape: str = "hex"):
    """Polygons (pixel coordinates) for segments a-g inside box (x0, y0, x1, y1).

    thickness: segment width in pixels, gap: space between segment ends,
    skew: italic slant as x shift per pixel above the box centre (0.1 = mild italic).
    shape: "hex" (pointed ends) or "block" (rectangles with small chamfers, old LED style).
    """
    x0, y0, x1, y1 = box
    h = thickness / 2
    xl, xr = x0 + h, x1 - h
    yt, ym, yb = y0 + h, (y0 + y1) / 2, y1 - h
    cy = (y0 + y1) / 2

    c = h * 0.35  # chamfer of block segments

    def horiz(y):
        a, b = xl + gap, xr - gap
        if shape == "block":
            a, b = a - h + gap, b + h - gap
            return [(a + c, y - h), (b - c, y - h), (b, y - h + c), (b, y + h - c), (b - c, y + h),
                    (a + c, y + h), (a, y + h - c), (a, y - h + c)]
        return [(a, y), (a + h, y - h), (b - h, y - h), (b, y), (b - h, y + h), (a + h, y + h)]

    def vert(x, ya, yb_):
        a, b = ya + gap, yb_ - gap
        if shape == "block":
            a, b = a + h, b - h
            return [(x - h + c, a), (x + h - c, a), (x + h, a + c), (x + h, b - c), (x + h - c, b),
                    (x - h + c, b), (x - h, b - c), (x - h, a + c)]
        return [(x, a), (x + h, a + h), (x + h, b - h), (x, b), (x - h, b - h), (x - h, a + h)]

    segs = {
        "a": horiz(yt), "g": horiz(ym), "d": horiz(yb),
        "f": vert(xl, yt, ym), "b": vert(xr, yt, ym),
        "e": vert(xl, ym, yb), "c": vert(xr, ym, yb),
    }
    if skew:
        segs = {k: [(x + skew * (cy - y), y) for x, y in pts] for k, pts in segs.items()}
    return segs


# --- 14 segments (Varisymbol layout) ---------------------------------------------------------
# Unit box: (0, 0) top left, (1, 1) bottom right; C = centre.
_P = {"TL": (0, 0), "TR": (1, 0), "BL": (0, 1), "BR": (1, 1), "ML": (0, .5), "MR": (1, .5),
      "C": (.5, .5), "TC": (.5, 0), "BC": (.5, 1)}

FOURTEEN_SEGMENTS = {
    "top": ("TL", "TR"), "bottom": ("BL", "BR"),
    "ul": ("TL", "ML"), "ll": ("ML", "BL"), "ur": ("TR", "MR"), "lr": ("MR", "BR"),
    "ml": ("ML", "C"), "mr": ("C", "MR"), "cu": ("TC", "C"), "cl": ("C", "BC"),
    "d_tl": ("C", "TL"), "d_tr": ("C", "TR"), "d_bl": ("C", "BL"), "d_br": ("C", "BR"),
}

# Digit -> lit segments, as the Varisymbol shows them.
FOURTEEN_DIGITS = {
    0: {"top", "bottom", "ul", "ll", "ur", "lr", "d_tr", "d_bl"},
    1: {"d_tr", "ur", "lr"},
    2: {"top", "ur", "ml", "mr", "ll", "bottom"},
    3: {"top", "d_tr", "mr", "lr", "bottom"},
    4: {"ul", "ml", "mr", "ur", "lr"},
    5: {"top", "ul", "ml", "mr", "lr", "bottom"},
    6: {"top", "ul", "ll", "ml", "mr", "lr", "bottom"},
    7: {"top", "d_tr", "cl"},
    8: {"top", "bottom", "ul", "ll", "ur", "lr", "ml", "mr"},
    9: {"top", "ul", "ur", "ml", "mr", "lr", "bottom"},
}


def fourteen_strokes(names) -> list[list[tuple[float, float]]]:
    """Strokes in unit coordinates (as used by common.stroke_mask) for the given segments."""
    return [[_P[a], _P[b]] for a, b in (FOURTEEN_SEGMENTS[n] for n in sorted(names))]
