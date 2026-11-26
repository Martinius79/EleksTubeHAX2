#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Procedural nixie-tube clock face generator.

Renders digits 0-9 as glowing cathode wires inside a tube with a hexagonal anode mesh and dim
unlit cathodes behind. Everything is drawn from geometry in this file - no source images - so
the output is an original work.

    python tools/facegen/nixie.py -o out/nixie --size 135x240 [--montage]
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

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
        return [[(0.92, 0.0), (0.12, 0.0), (0.05, 0.44)] + arc(0.5, 0.69, R, 0.31, 215, 520)]
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


def _down(im, size):
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
    return _down(im, size)


def dot_mask(size, x, y, r):
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    ImageDraw.Draw(im).ellipse(((x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS), fill=255)
    return _down(im, size)


def blur(a, radius):
    im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.0


def rect_mask(size, rect, radius):
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    x0, y0, x1, y1 = rect
    ImageDraw.Draw(im).rounded_rectangle((x0 * SS, y0 * SS, x1 * SS, y1 * SS),
                                         radius=radius * SS, fill=255)
    return _down(im, size)


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
    return _down(im, size) * rect_mask(size, region, 6)


def col(rgb):
    return np.array(rgb, dtype=np.float32)[None, None, :] / 255.0


def render(d: int, size=(135, 240)) -> Image.Image:
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

    lit = stroke_mask(size, digit_strokes(d), box, 2.8 * s)
    glow_near = blur(lit, 2.0 * s)
    glow_far = blur(lit, 9.0 * s)
    ambient = blur(lit, 28.0 * s)
    flood = blur(lit, 60.0 * s)

    # neon gas fill: the whole tube interior is washed in red light
    interior = rect_mask(size, inner, 6 * s)
    img += (interior * (0.30 + 9.0 * flood))[..., None] * col((135, 8, 2))

    # anode mesh, lit by the digit
    mesh = hex_mesh(size, 4.2 * s, 0.7 * s, inner)
    mesh_light = 0.35 + 8.0 * flood + 3.0 * ambient + 3.0 * glow_far
    img += (mesh * np.clip(mesh_light, 0, 2.2))[..., None] * col((205, 42, 20))

    # unlit cathodes stacked behind, slightly offset, dim and lit by the active digit
    for k in range(10):
        if k == d:
            continue
        off = ((k % 3) - 1) * 0.8 * s
        b = (box[0] + off, box[1] + off * 0.5, box[2] + off, box[3] + off * 0.5)
        m = stroke_mask(size, digit_strokes(k), b, 0.8 * s)
        img += (m * (0.15 + 4.0 * flood + 1.5 * ambient))[..., None] * col((150, 70, 105))

    # warm orange discharge glow around the lit wire
    img += ambient[..., None] * col((180, 12, 0)) * 1.0
    img += glow_far[..., None] * col((250, 35, 5)) * 1.8
    img += glow_near[..., None] * col((255, 85, 15)) * 2.4
    img += lit[..., None] * col((255, 210, 145)) * 1.7

    # cathode lead-ins: small violet glow points top and bottom
    for y in (box[1] - 7 * s, box[3] + 7 * s):
        p = dot_mask(size, w / 2, y, 1.6 * s)
        img += blur(p, 1.5 * s)[..., None] * col((170, 120, 255)) * 2.5
        img += p[..., None] * col((230, 210, 255))

    img = 1 - np.exp(-img * 1.4)                      # soft tone mapping, no hard clipping
    return Image.fromarray(np.clip(img * 255 + 0.5, 0, 255).astype(np.uint8), "RGB")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", type=Path, required=True, help="output directory")
    ap.add_argument("--size", default="135x240", help="WxH, default 135x240")
    ap.add_argument("--montage", action="store_true", help="also write montage.png")
    a = ap.parse_args()
    w, h = (int(x) for x in a.size.lower().split("x"))
    a.out.mkdir(parents=True, exist_ok=True)
    frames = [render(d, (w, h)) for d in range(10)]
    for d, im in enumerate(frames):
        im.save(a.out / f"{d}.png")
    if a.montage:
        m = Image.new("RGB", (w * 5, h * 2))
        for d, im in enumerate(frames):
            m.paste(im, ((d % 5) * w, (d // 5) * h))
        m.save(a.out / "montage.png")


if __name__ == "__main__":
    main()
