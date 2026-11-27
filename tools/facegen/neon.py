# SPDX-License-Identifier: GPL-3.0-or-later
"""Neon sign style: hand-bent glass tube in strong colour on a dark wall.

Two shape sets:
  * "classic": the shared curved digit shapes, slightly irregular like hand-bent glass, with a
    glossy highlight, uneven brightness along the tube, metal clips and a soft shadow.
  * "retro": playful angular tube paths with rounded bends, small rings at the tube ends, every
    digit a little tilted, optionally each digit in its own rainbow colour.
Tube ends (electrodes) stay dark."""

from __future__ import annotations

import colorsys

import numpy as np
from PIL import Image

from common import (blur, col, digit_strokes, dot_mask, glow, parse_color, rect_mask,
                    rounded_path, stroke_mask, to_image, tonemap, transform, wobble)

NAME = "neon"
PARAMS = {
    "color": (255, 40, 170),
    "background": (26, 22, 28),
    "stroke": 5.5,  # tube diameter at 135 px panel width
    "glow": 1.4,
    "wall": 0.10,  # wall texture strength
    "shapes": "classic",  # "classic" or "retro"
    "rainbow": False,  # every digit in its own colour (overrides color)
    "wobble": 0.008,  # hand-bent irregularity
    "gloss": 0.55,  # highlight on the glass
    "clips": True,  # metal clips holding the tube
}

# Retro tube paths in unit coordinates (angular, rounded by rounded_path). Open ends get rings.
_RETRO = {
    0: [[(0.82, 0.62), (0.82, 0.06), (0.16, 0.06), (0.16, 0.94), (0.82, 0.94), (0.82, 0.76)],
        [(0.40, 0.30), (0.60, 0.30), (0.60, 0.70), (0.40, 0.70), (0.40, 0.30)]],
    1: [[(0.30, 0.22), (0.54, 0.06), (0.54, 0.94)], [(0.30, 0.94), (0.78, 0.94)]],
    2: [[(0.16, 0.18), (0.16, 0.06), (0.84, 0.06), (0.84, 0.50), (0.16, 0.50), (0.16, 0.94),
         (0.86, 0.94)]],
    3: [[(0.14, 0.06), (0.84, 0.06), (0.84, 0.94), (0.14, 0.94)], [(0.38, 0.50), (0.84, 0.50)]],
    4: [[(0.16, 0.06), (0.16, 0.62), (0.88, 0.62)], [(0.68, 0.30), (0.68, 0.94)]],
    5: [[(0.86, 0.06), (0.16, 0.06), (0.16, 0.48), (0.84, 0.48), (0.84, 0.94), (0.14, 0.94)]],
    6: [[(0.80, 0.06), (0.16, 0.06), (0.16, 0.94), (0.84, 0.94), (0.84, 0.50), (0.32, 0.50)]],
    7: [[(0.14, 0.06), (0.86, 0.06), (0.50, 0.94)], [(0.34, 0.52), (0.66, 0.52)]],
    8: [[(0.16, 0.06), (0.84, 0.06), (0.84, 0.94), (0.16, 0.94), (0.16, 0.06)],
        [(0.16, 0.48), (0.84, 0.48)]],
    9: [[(0.84, 0.50), (0.16, 0.50), (0.16, 0.06), (0.84, 0.06), (0.84, 0.94), (0.20, 0.94)]],
}
_TILT = (-3.0, 2.5, -1.5, 3.0, -2.5, 1.5, -3.5, 2.0, -1.0, 2.5)  # degrees per digit (retro)


def _is_closed(st):
    return abs(st[0][0] - st[-1][0]) + abs(st[0][1] - st[-1][1]) < 1e-3


def _shapes(d, p):
    if p["shapes"] == "retro":
        strokes = [rounded_path(st, 0.07) for st in _RETRO[d]]
        strokes = transform(strokes, 1.0 - 0.03 * (d % 3), angle_deg=_TILT[d])
    else:
        strokes = digit_strokes(d)
    return wobble(strokes, p["wobble"], seed=300 + d)


def _color(d, p):
    if p["rainbow"]:
        r, g, b = colorsys.hsv_to_rgb((d / 10 + 0.95) % 1.0, 0.85, 1.0)
        return int(r * 255), int(g * 255), int(b * 255)
    return parse_color(p["color"])


def render(d: int | None, size=(135, 240), **params) -> Image.Image:
    p = {**PARAMS, **params}
    w, h = size
    s = w / 135.0
    box = (22 * s, 36 * s, w - 22 * s, h - 36 * s)

    # wall: the same deterministic texture on every glyph
    rng = np.random.default_rng(20261127)
    noise = blur(rng.random((h, w), dtype=np.float32), 1.2 * s)
    img = np.zeros((h, w, 3), np.float32) + col(parse_color(p["background"]))
    img *= (1 + p["wall"] * (noise - 0.5) * 4)[..., None]
    if d is None:
        return to_image(img)

    color = _color(d, p)
    strokes = _shapes(d, p)
    stroke = p["stroke"] * s * (0.8 if p["shapes"] == "retro" else 1.0)
    tube = stroke_mask(size, strokes, box, stroke)
    shadow = blur(np.roll(tube, (round(5 * s), round(3 * s)), axis=(0, 1)), 2.5 * s)
    img *= (1 - 0.6 * shadow)[..., None]

    # gas brightness is never perfectly even along a hand-made tube
    uneven = 0.82 + 0.18 * blur(np.random.default_rng(400 + d).random((h, w),
                                                                     dtype=np.float32), 9 * s) * 2
    lit = tube * np.clip(uneven, 0.7, 1.05)
    img += blur(lit, 35 * s)[..., None] * col(color) * 1.6 * p["glow"]  # light on the wall
    img += glow(lit, s * 1.3, color, p["glow"], core=(255, 215, 240))

    # glossy highlight: a thin bright line along the upper-left side of the tube
    if p["gloss"] > 0:
        inner = stroke_mask(size, strokes, box, stroke * 0.28)
        hi = np.roll(inner, (-round(stroke * 0.22), -round(stroke * 0.22)), axis=(0, 1)) * tube
        img += (blur(hi, 0.4 * s) * p["gloss"])[..., None] * col((255, 255, 255))

    x0, y0, x1, y1 = box
    to_px = (lambda u, v: (x0 + u * (x1 - x0), y0 + v * (y1 - y0)))
    # electrodes: dark glass at open tube ends; retro tubes end in small rings
    ends = np.zeros((h, w), np.float32)
    rings = np.zeros((h, w), np.float32)
    for st in strokes:
        if _is_closed(st):
            continue
        for u, v in (st[0], st[-1]):
            x, y = to_px(u, v)
            if p["shapes"] == "retro":
                ring = dot_mask(size, x, y, stroke * 1.25) - dot_mask(size, x, y, stroke * 0.6)
                rings = np.maximum(rings, np.clip(ring, 0, 1))
            else:
                ends = np.maximum(ends, dot_mask(size, x, y, stroke * 0.75))
    img = img * (1 - ends[..., None]) + ends[..., None] * col((70, 62, 72))
    img += glow(rings, s * 0.8, color, 0.5, core=(255, 230, 245)) * 0.8

    # clips: small metal brackets across the tube at two points of the longest stroke
    if p["clips"] and p["shapes"] != "retro":
        longest = max(strokes, key=len)
        for t in (0.3, 0.72):
            u, v = longest[int(t * (len(longest) - 1))]
            x, y = to_px(u, v)
            clip = rect_mask(size, (x - 1.2 * s, y - stroke * 0.9, x + 1.2 * s, y + stroke * 0.9),
                             0.5 * s)
            img = img * (1 - clip[..., None]) + clip[..., None] * col((110, 105, 112))
    return to_image(tonemap(img))
