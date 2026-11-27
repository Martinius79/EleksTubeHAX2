# SPDX-License-Identifier: GPL-3.0-or-later
"""Neon sign style: bent glass tube in strong colour with a bright core and wide glow on a
dark wall; tube ends (electrodes) stay dark, the tube casts a soft shadow."""

from __future__ import annotations

import numpy as np
from PIL import Image

from common import (blur, col, digit_strokes, dot_mask, glow, parse_color, stroke_mask, to_image,
                    tonemap)

NAME = "neon"
PARAMS = {
    "color": (255, 40, 170),
    "background": (26, 22, 28),
    "stroke": 5.5,  # tube diameter at 135 px panel width
    "glow": 1.4,
    "wall": 0.10,  # wall texture strength
}


def render(d: int | None, size=(135, 240), **params) -> Image.Image:
    p = {**PARAMS, **params}
    w, h = size
    s = w / 135.0
    box = (22 * s, 36 * s, w - 22 * s, h - 36 * s)
    color = parse_color(p["color"])

    # wall: the same deterministic texture on every glyph
    rng = np.random.default_rng(20261127)
    noise = blur(rng.random((h, w), dtype=np.float32), 1.2 * s)
    img = np.zeros((h, w, 3), np.float32) + col(parse_color(p["background"]))
    img *= (1 + p["wall"] * (noise - 0.5) * 4)[..., None]
    if d is None:
        return to_image(img)

    strokes = digit_strokes(d)
    tube = stroke_mask(size, strokes, box, p["stroke"] * s)
    shadow = blur(np.roll(tube, (round(5 * s), round(3 * s)), axis=(0, 1)), 2.5 * s)
    img *= (1 - 0.6 * shadow)[..., None]
    img += blur(tube, 35 * s)[..., None] * col(color) * 1.6 * p["glow"]  # light on the wall
    img += glow(tube, s * 1.3, color, p["glow"], core=(255, 215, 240))
    # electrodes: dark glass at both tube ends
    ends = np.zeros((h, w), np.float32)
    x0, y0, x1, y1 = box
    for st in strokes:
        if abs(st[0][0] - st[-1][0]) + abs(st[0][1] - st[-1][1]) < 1e-3:
            continue  # closed loop (0, 8, ...): no tube ends
        for u, v in (st[0], st[-1]):
            ends = np.maximum(ends, dot_mask(size, x0 + u * (x1 - x0), y0 + v * (y1 - y0),
                                             p["stroke"] * 0.75 * s))
    img = img * (1 - ends[..., None]) + ends[..., None] * col((70, 62, 72))
    return to_image(tonemap(img))
