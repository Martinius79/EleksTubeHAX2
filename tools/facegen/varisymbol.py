# SPDX-License-Identifier: GPL-3.0-or-later
"""Varisymbol style: 14-segment gas-discharge display in the manner of the Telefunken
Varisymbol - glowing orange bars, unlit segments visible as thin lines, warm light filling
the cell. Rendered from segment geometry only (segments.py)."""

from __future__ import annotations

import numpy as np
from PIL import Image

from common import blur, col, glow, parse_color, stroke_mask, to_image, tonemap
from segments import FOURTEEN_DIGITS, FOURTEEN_SEGMENTS, fourteen_strokes

NAME = "varisymbol"
PARAMS = {
    "color": (255, 118, 18),  # discharge colour
    "unlit": (120, 104, 98),  # thin lines of the unlit segments
    "background": (7, 4, 3),
    "stroke": 6.0,  # lit segment width at 135 px panel width
    "glow": 1.0,  # glow strength
    "core": (255, 196, 120),  # hottest part of the bars
}


def render(d: int | None, size=(135, 240), **params) -> Image.Image:
    p = {**PARAMS, **params}
    w, h = size
    s = w / 135.0
    box = (17 * s, 24 * s, w - 17 * s, h - 32 * s)
    color = parse_color(p["color"])

    img = np.zeros((h, w, 3), np.float32) + col(parse_color(p["background"]))
    lines = stroke_mask(size, fourteen_strokes(FOURTEEN_SEGMENTS), box, 0.9 * s)
    if d is None:
        lit = np.zeros((h, w), np.float32)
    else:
        lit = stroke_mask(size, fourteen_strokes(FOURTEEN_DIGITS[d]), box, p["stroke"] * s)
    fill = blur(lit, 45 * s)  # light reflected inside the cell
    img += fill[..., None] * col(color) * 2.2 * p["glow"]
    near_light = blur(lit, 10 * s)
    img += (lines * (0.22 + 2.5 * near_light))[..., None] * col(parse_color(p["unlit"]))
    img += glow(lit, s, color, p["glow"], core=parse_color(p["core"]))
    return to_image(tonemap(img))
