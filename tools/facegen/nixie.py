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
                    stack_depth, stroke_mask, to_image, transform, wobble)

NAME = "nixie"
PARAMS = {
    "gas": (135, 8, 2),  # neon gas fill of the tube
    "mesh": (205, 42, 20),  # anode mesh lit by the discharge
    "cathodes": (150, 70, 105),  # unlit cathodes behind the lit one
    "ambient": (180, 12, 0),  # wide glow
    "far": (250, 35, 5),  # mid glow
    "near": (255, 85, 15),  # glow close to the wire
    "core": (255, 228, 182),  # the wire itself (hot)
    "leads": (170, 120, 255),  # violet glow points at the cathode lead-ins
    "rods": (120, 96, 88),  # support rods
    "reflection": 0.22,  # highlights on the glass
    "depth": 0.6,  # blur of the cathodes behind the lit one (px at 135 wide)
    "wobble": 0.007,  # hand-bent wire irregularity (unit box)
    "jump": 0.05,  # size difference front/back of the cathode stack
    "lead_metal": (150, 120, 110),  # lead wires from the support points to the cathode
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
    prm = {k: parse_color(v) if isinstance(PARAMS[k], tuple) else v
           for k, v in {**PARAMS, **params}.items()}
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

    def cathode(k):
        """Shape of cathode k: bent wire, scaled by its depth in the stack."""
        scale = 1 + prm["jump"] * (0.5 - stack_depth(k))
        return transform(wobble(digit_strokes(k), prm["wobble"], seed=100 + k), scale)

    lit = (stroke_mask(size, cathode(d), box, 2.8 * s) if d is not None
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
        m = stroke_mask(size, cathode(k), box, 0.8 * s)
        if prm["depth"] > 0:
            m = blur(m, prm["depth"] * s)  # behind the lit cathode: slightly out of focus
        img += (m * (0.28 + 6.0 * flood + 2.5 * ambient))[..., None] * col(prm["cathodes"])

    # support rods between the mica plates, lit by the discharge
    rods = np.zeros((h, w), np.float32)
    for x in (inner[0] + 3 * s, inner[2] - 3 * s):
        rods = np.maximum(rods, rect_mask(size, (x - 0.8 * s, tube[1] + 12 * s, x + 0.8 * s,
                                                 tube[3] - 12 * s), 0.5 * s))
    img += (rods * (0.25 + 5.0 * flood + 1.5 * ambient))[..., None] * col(prm["rods"])

    # warm orange discharge glow around the lit wire
    img += ambient[..., None] * col(prm["ambient"]) * 1.0
    img += glow_far[..., None] * col(prm["far"]) * 1.8
    img += glow_near[..., None] * col(prm["near"]) * 2.4
    img += lit[..., None] * col(prm["core"]) * 2.1

    # support points top and bottom; a lead wire connects them to the nearest point of the lit
    # cathode, the violet glow sits where the wire meets the support
    if d is not None:
        pts = [(box[0] + u * (box[2] - box[0]), box[1] + v * (box[3] - box[1]))
               for st in cathode(d) for u, v in st]
        leads = np.zeros((h, w), np.float32)
        for y in (box[1] - 7 * s, box[3] + 7 * s):
            tx, ty = min(pts, key=lambda q: (q[0] - w / 2) ** 2 + (q[1] - y) ** 2)
            leads = np.maximum(leads, stroke_mask(size, [[(0, 0), (1, 1)]],
                                                  (w / 2, y, tx, ty), 0.7 * s))
            dot = dot_mask(size, w / 2, y, 1.6 * s)
            img += blur(dot, 1.5 * s)[..., None] * col(prm["leads"]) * 2.5
            img += dot[..., None] * col((230, 210, 255))
        img += (leads * (0.4 + 3.0 * glow_far))[..., None] * col(prm["lead_metal"])

    # glass highlights: a vertical streak on the left, a short one on the right shoulder
    if prm["reflection"] > 0:
        streak = blur(rect_mask(size, (tube[0] + 6 * s, tube[1] + 16 * s, tube[0] + 8.5 * s,
                                       tube[3] - 20 * s), 1.2 * s), 1.0 * s)
        streak += 0.6 * blur(rect_mask(size, (tube[2] - 9 * s, tube[1] + 14 * s, tube[2] - 7.5 * s,
                                              tube[1] + 60 * s), 0.8 * s), 0.8 * s)
        img += (streak * prm["reflection"])[..., None] * col((240, 235, 245))

    img = 1 - np.exp(-img * 1.4)                      # soft tone mapping, no hard clipping
    return to_image(img)
