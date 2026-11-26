# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal flat clock face: amber digits with anti-aliased strokes on black.

Small and fast to decode - used as the fallback face embedded in the firmware, so the clock
can always show the time even with an empty or damaged face storage.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from common import col, digit_strokes, stroke_mask, to_image

COLOR = (255, 176, 64)  # warm amber


def render(d: int | None, size=(135, 240)) -> Image.Image:
    """Digit d, or d=None for a blank (black) glyph."""
    w, h = size
    s = w / 135.0
    box = (18 * s, 28 * s, w - 18 * s, h - 28 * s)
    img = np.zeros((h, w, 3), np.float32)
    if d is not None:
        mask = stroke_mask(size, digit_strokes(d), box, 7.0 * s)
        img += mask[..., None] * col(COLOR)
    return to_image(img)
