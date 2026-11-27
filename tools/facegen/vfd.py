# SPDX-License-Identifier: GPL-3.0-or-later
"""VFD style: vacuum fluorescent display - turquoise phosphor segments behind a fine control
grid, unlit segments faintly visible, thin filament wires across the cell."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from common import SS, col, downsample, glow, parse_color, polygon_mask, to_image, tonemap
from segments import SEVEN_DIGITS, seven_segments

NAME = "vfd"
PARAMS = {
    "color": (80, 255, 205),
    "unlit": (20, 48, 50),
    "background": (5, 10, 12),
    "thickness": 11.0,
    "gap": 3.0,
    "skew": 0.0,
    "glow": 0.7,
    "grid": 0.35,  # darkening by the control grid
}


def _grid(size, pitch, width):
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    dr = ImageDraw.Draw(im)
    step = pitch * SS
    lw = max(1, round(width * SS))
    for i in range(int(w * SS / step) + 2):
        dr.line([(i * step, 0), (i * step, h * SS)], fill=255, width=lw)
    for j in range(int(h * SS / step) + 2):
        dr.line([(0, j * step), (w * SS, j * step)], fill=255, width=lw)
    return downsample(im, size)


def _filaments(size, s):
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    dr = ImageDraw.Draw(im)
    for y in (h * 0.12, h * 0.5, h * 0.88):
        dr.line([(4 * s * SS, y * SS), ((w - 4 * s) * SS, (y + 2 * s) * SS)], fill=255,
                width=max(1, round(0.5 * s * SS)))
    return downsample(im, size)


def render(d: int | None, size=(135, 240), **params) -> Image.Image:
    p = {**PARAMS, **params}
    w, h = size
    s = w / 135.0
    box = (24 * s, 36 * s, w - 24 * s, h - 36 * s)
    segs = seven_segments(box, p["thickness"] * s, p["gap"] * s, p["skew"])
    color = parse_color(p["color"])
    every = polygon_mask(size, segs.values())
    names = SEVEN_DIGITS[d] if d is not None else ""
    lit = polygon_mask(size, [segs[n] for n in names]) if names else np.zeros((h, w), np.float32)

    img = np.zeros((h, w, 3), np.float32) + col(parse_color(p["background"]))
    img += every[..., None] * col(parse_color(p["unlit"]))
    img += lit[..., None] * col(color) * 1.2
    img += glow(lit, s * 0.8, color, p["glow"], core=(140, 255, 220))
    img *= (1 - p["grid"] * _grid(size, 3.2 * s, 0.6 * s))[..., None]
    img += _filaments(size, s)[..., None] * col((60, 80, 80)) * 0.5
    return to_image(tonemap(img))
