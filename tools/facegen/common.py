# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared geometry and drawing helpers for the clock-face generators (tools/facegen).

Digit shapes are defined here once and used by every style, so all built-in faces share the
same original glyph geometry.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SS = 4  # supersampling factor

# --- digit geometry -------------------------------------------------------------------------
# Units: digit box u (0 = left, 1 = right), v (0 = top, 1 = bottom). Each digit is a list of
# strokes; each stroke is a list of (u, v) points. Angles in degrees, 0 = right, 90 = down.


def arc(cx, cy, rx, ry, a0, a1, n=64):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


R = 0.5  # horizontal radius of round parts


def digit_strokes(d: int) -> list[list[tuple[float, float]]]:
    if d == 0:
        top, bot = R * 0.95, 1 - R * 0.95
        return [arc(0.5, top, R, R * 0.95, 180, 360) + arc(0.5, bot, R, R * 0.95, 0, 180)
                + [(0.0, top)]]
    if d == 1:
        return [[(0.27, 0.16), (0.55, 0.0), (0.55, 1.0)], [(0.32, 1.0), (0.78, 1.0)]]
    if d == 2:
        return [arc(0.5, 0.25, R, 0.25, 180, 360 + 40) + [(0.0, 1.0), (1.0, 1.0)]]
    if d == 3:
        return [arc(0.5, 0.245, 0.43, 0.235, 200, 450) + [(0.34, 0.48)],
                arc(0.5, 0.74, R, 0.26, 270, 520)]
    if d == 4:
        return [[(0.74, 1.0), (0.74, 0.0), (0.0, 0.68), (1.0, 0.68)]]
    if d == 5:
        bowl = arc(0.5, 0.69, R, 0.31, 215, 520)
        return [[(0.92, 0.0), (0.12, 0.0)] + bowl]  # stem runs straight into the bowl
    if d == 6:
        return [arc(0.5, 0.69, R, 0.31, 0, 360), arc(1.1, 0.69, 1.1, 0.69, 180, 255)]
    if d == 7:
        return [[(0.0, 0.0), (1.0, 0.0), (0.3, 1.0)]]
    if d == 8:
        return [arc(0.5, 0.215, 0.41, 0.215, 90, 450), arc(0.5, 0.715, R, 0.285, -90, 270)]
    if d == 9:
        return [arc(0.5, 0.31, R, 0.31, 0, 360), arc(-0.1, 0.31, 1.1, 0.69, 0, 75)]
    raise ValueError(d)


# --- rendering ------------------------------------------------------------------------------


def to_px(pts, box):
    x0, y0, x1, y1 = box
    return [((x0 + u * (x1 - x0)) * SS, (y0 + v * (y1 - y0)) * SS) for u, v in pts]


def downsample(im, size):
    return np.asarray(im.resize(size, Image.LANCZOS), dtype=np.float32) / 255.0


def stroke_mask(size, strokes, box, width):
    """Anti-aliased stroke mask as float array in [0, 1] at final resolution."""
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    dr = ImageDraw.Draw(im)
    lw = max(1, round(width * SS))
    for s in strokes:
        pts = to_px(s, box)
        dr.line(pts, fill=255, width=lw, joint="curve")
        r = lw / 2
        for x, y in (pts[0], pts[-1]):
            dr.ellipse((x - r, y - r, x + r, y + r), fill=255)
    return downsample(im, size)


def dot_mask(size, x, y, r):
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(im).ellipse(((x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS), fill=255)
    return downsample(im, size)


def blur(a, radius):
    im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.0


def rect_mask(size, rect, radius):
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    x0, y0, x1, y1 = rect
    ImageDraw.Draw(im).rounded_rectangle((x0 * SS, y0 * SS, x1 * SS, y1 * SS),
                                         radius=radius * SS, fill=255)
    return downsample(im, size)


def col(rgb):
    return np.array(rgb, dtype=np.float32)[None, None, :] / 255.0


def to_image(img: np.ndarray) -> Image.Image:
    """Float RGB array in [0, 1] -> 8-bit PIL image."""
    return Image.fromarray(np.clip(img * 255 + 0.5, 0, 255).astype(np.uint8), "RGB")
