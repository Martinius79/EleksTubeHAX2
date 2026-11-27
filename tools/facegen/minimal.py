# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal flat clock face: digits with anti-aliased strokes on a plain background.

Small and fast to decode - the amber preset is the fallback face embedded in the firmware, so
the clock can always show the time even with an empty or damaged face storage.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from common import col, digit_strokes, parse_color, stroke_mask, to_image

NAME = "minimal"
PARAMS = {
    "color": (255, 176, 64),  # warm amber
    "background": (0, 0, 0),
    "stroke": 7.0,  # stroke width at 135 px panel width
}


def render(d: int | None, size=(135, 240), **params) -> Image.Image:
    """Digit d, or d=None for a blank glyph."""
    p = {**PARAMS, **params}
    w, h = size
    s = w / 135.0
    box = (18 * s, 28 * s, w - 18 * s, h - 28 * s)
    bg = col(parse_color(p["background"]))
    img = np.zeros((h, w, 3), np.float32) + bg
    if d is not None:
        mask = stroke_mask(size, digit_strokes(d), box, p["stroke"] * s)[..., None]
        img = img * (1 - mask) + mask * col(parse_color(p["color"]))
    return to_image(img)
