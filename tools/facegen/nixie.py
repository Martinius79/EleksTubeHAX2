# SPDX-License-Identifier: GPL-3.0-or-later
"""Procedural nixie-tube clock face generator.

Renders digits 0-9 as glowing cathode wires inside a tube with a hexagonal anode mesh and dim
unlit cathodes behind. Everything is drawn from geometry in this file - no source images - so
the output is an original work.

    python tools/facegen/facegen.py render nixie -o out/nixie [--size 80x160] [--montage]
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from common import (SS, blur, col, digit_strokes, dot_mask, downsample, parse_color, rect_mask,
                    stroke_mask, to_image)

NAME = "nixie"
PARAMS = {
    "gas": (135, 8, 2),  # neon gas fill of the tube
    "mesh": (205, 42, 20),  # anode mesh lit by the discharge
    "cathodes": (150, 70, 105),  # unlit cathodes behind the lit one
    "ambient": (180, 12, 0),  # wide glow
    "far": (250, 35, 5),  # mid glow
    "near": (255, 85, 15),  # glow close to the wire
    "core": (255, 210, 145),  # the wire itself
    "leads": (170, 120, 255),  # violet glow points at the cathode lead-ins
}


def hex_mesh(size, cell, line, region):
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    dr = ImageDraw.Draw(im)
    r = cell * SS
    dx, dy = math.sqrt(3) * r, 1.5 * r
    rows, cols = int(h * SS / dy) + 3, int(w * SS / dx) + 3
    for row in range(-1, rows):
        for c in range(-1, cols):
            cx = c * dx + (dx / 2 if row % 2 else 0)
            cy = row * dy
            pts = [(cx + r * math.cos(math.radians(30 + 60 * k)),
                    cy + r * math.sin(math.radians(30 + 60 * k))) for k in range(7)]
            dr.line(pts, fill=255, width=max(1, round(line * SS)))
    return downsample(im, size) * rect_mask(size, region, 6)


def render(d: int | None, size=(135, 240), **params) -> Image.Image:
    """Digit d lit, or d=None for a blank (unlit) tube."""
    prm = {k: parse_color(v) for k, v in {**PARAMS, **params}.items()}
    w, h = size
    s = w / 135.0                                     # scale relative to the reference size
    tube = (4 * s, 6 * s, w - 4 * s, h - 6 * s)
    inner = (12 * s, 20 * s, w - 12 * s, h - 20 * s)
    box = (19 * s, 32 * s, w - 19 * s, h - 32 * s)    # digit box

    img = np.zeros((h, w, 3), np.float32)

    # glass body: very dark warm gradient, brighter rim
    body = rect_mask(size, tube, 12 * s)
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    img += body[..., None] * (col((14, 6, 5)) + col((10, 3, 2)) * (1 - abs(yy - 0.5) * 2))
    rim = body - rect_mask(size, (tube[0] + 1.5 * s, tube[1] + 1.5 * s,
                                  tube[2] - 1.5 * s, tube[3] - 1.5 * s), 11 * s)
    img += np.clip(rim, 0, 1)[..., None] * col((55, 35, 32))

    # top / bottom mica plates
    for y0 in (tube[1] + 3 * s, tube[3] - 13 * s):
        plate = rect_mask(size, (inner[0] - 2 * s, y0, inner[2] + 2 * s, y0 + 10 * s), 2 * s)
        img = img * (1 - plate[..., None]) + plate[..., None] * col((38, 30, 30))

    lit = (stroke_mask(size, digit_strokes(d), box, 2.8 * s) if d is not None
           else np.zeros((h, w), np.float32))
    glow_near = blur(lit, 2.0 * s)
    glow_far = blur(lit, 9.0 * s)
    ambient = blur(lit, 28.0 * s)
    flood = blur(lit, 60.0 * s)

    # neon gas fill: the whole tube interior is washed in red light
    interior = rect_mask(size, inner, 6 * s)
    img += (interior * (0.30 + 9.0 * flood))[..., None] * col(prm["gas"])

    # anode mesh, lit by the digit
    mesh = hex_mesh(size, 4.2 * s, 0.7 * s, inner)
    mesh_light = 0.35 + 8.0 * flood + 3.0 * ambient + 3.0 * glow_far
    img += (mesh * np.clip(mesh_light, 0, 2.2))[..., None] * col(prm["mesh"])

    # unlit cathodes stacked behind, slightly offset, dim and lit by the active digit
    for k in range(10):
        if k == d:
            continue
        off = ((k % 3) - 1) * 0.8 * s
        b = (box[0] + off, box[1] + off * 0.5, box[2] + off, box[3] + off * 0.5)
        m = stroke_mask(size, digit_strokes(k), b, 0.8 * s)
        img += (m * (0.15 + 4.0 * flood + 1.5 * ambient))[..., None] * col(prm["cathodes"])

    # warm orange discharge glow around the lit wire
    img += ambient[..., None] * col(prm["ambient"]) * 1.0
    img += glow_far[..., None] * col(prm["far"]) * 1.8
    img += glow_near[..., None] * col(prm["near"]) * 2.4
    img += lit[..., None] * col(prm["core"]) * 1.7

    # cathode lead-ins: small violet glow points top and bottom
    for y in (box[1] - 7 * s, box[3] + 7 * s):
        p = dot_mask(size, w / 2, y, 1.6 * s)
        img += blur(p, 1.5 * s)[..., None] * col(prm["leads"]) * 2.5
        img += p[..., None] * col((230, 210, 255))

    img = 1 - np.exp(-img * 1.4)                      # soft tone mapping, no hard clipping
    return to_image(img)
