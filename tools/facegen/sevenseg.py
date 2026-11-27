# SPDX-License-Identifier: GPL-3.0-or-later
"""7-segment style: LED segments with faint unlit ghost segments, or a reflective LCD look
(dark segments with a shadow on a light background) with lcd=true."""

from __future__ import annotations

import numpy as np
from PIL import Image

from common import blur, col, glow, parse_color, polygon_mask, to_image, tonemap
from segments import SEVEN_DIGITS, seven_segments

NAME = "sevenseg"
PARAMS = {
    "color": (255, 34, 22),  # LED: lit colour, LCD: segment colour
    "background": (5, 5, 5),
    "ghost": 0.07,  # visibility of unlit segments
    "thickness": 15.0,  # segment thickness at 135 px panel width
    "gap": 2.0,
    "skew": 0.08,  # italic slant
    "glow": 0.6,
    "lcd": False,
    "shape": "hex",  # "hex" (pointed ends) or "block" (filled rectangles, old LED style)
}


def _lit_mask(size, segs, d):
    names = SEVEN_DIGITS[d] if d is not None else ""
    if not names:
        return np.zeros((size[1], size[0]), np.float32)
    return polygon_mask(size, [segs[n] for n in names])


def render(d: int | None, size=(135, 240), **params) -> Image.Image:
    p = {**PARAMS, **params}
    w, h = size
    s = w / 135.0
    box = (22 * s, 34 * s, w - 22 * s, h - 34 * s)
    segs = seven_segments(box, p["thickness"] * s, p["gap"] * s, p["skew"], p["shape"])
    color = parse_color(p["color"])
    every = polygon_mask(size, segs.values())
    lit = _lit_mask(size, segs, d)
    img = np.zeros((h, w, 3), np.float32) + col(parse_color(p["background"]))
    if p["lcd"]:
        shadow = blur(np.roll(lit, (round(3 * s), round(3 * s)), axis=(0, 1)), 1.5 * s)
        img = img * (1 - 0.35 * shadow - p["ghost"] * every)[..., None]
        img = img * (1 - lit[..., None]) + lit[..., None] * col(color)
        return to_image(img)
    img += every[..., None] * col(color) * p["ghost"]
    core = tuple(min(255, c + 45) for c in color)
    if p["glow"] <= 0:  # flat segments: exact colours, no light model
        return to_image(img * (1 - lit[..., None]) + lit[..., None] * col(color))
    img += glow(lit, s * 0.7, color, p["glow"], core=core)
    return to_image(tonemap(img))
