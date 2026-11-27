# SPDX-License-Identifier: GPL-3.0-or-later
"""Round nixie tube seen from the front, in the manner of Soviet IN-14 tubes: glass cylinder with
shoulder and exhaust tip, mica disc with support rods, a coarse honeycomb anode IN FRONT of the
digit, a broad diffuse orange glow without white core, dim cathode stack behind, pins in the
base and optionally coloured light from below (clocks with LED underlighting).

Drawn from geometry only (Soviet-style digit shapes from common.soviet_digit_strokes)."""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from common import (SS, blur, col, digit_strokes, downsample, parse_color, soviet_digit_strokes,
                    stroke_mask, to_image, tonemap)

NAME = "in14"
PARAMS = {
    "glow": (255, 72, 8),  # discharge colour
    "hot": (255, 128, 36),  # brightest parts of the glowing cathode
    "mesh": 0.78,  # how much the anode mesh darkens the glow
    "metal": (92, 82, 78),  # unlit cathodes, rods, mica
    "background": (0, 0, 0),
    "base": (170, 60, 255),  # underlight colour
    "base_glow": 0.0,  # underlight strength (0 = off)
    "reflection": 0.30,  # glass highlights
    "soviet_5": True,  # 5 drawn as an upside-down 2 like the real tube
}


def _tube_mask(size, s):
    """Glass outline: cylinder with rounded shoulder, slightly rounded bottom."""
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    dr = ImageDraw.Draw(im)
    x0, x1 = 9 * s, w - 9 * s
    top, bottom = 30 * s, h - 8 * s
    r = (x1 - x0) * 0.42
    dr.rounded_rectangle((x0 * SS, top * SS, x1 * SS, (top + 3 * r) * SS), radius=r * SS,
                         fill=255, corners=(True, True, False, False))
    dr.rounded_rectangle((x0 * SS, (top + r) * SS, x1 * SS, bottom * SS), radius=6 * s * SS,
                         fill=255, corners=(False, False, True, True))
    # exhaust tip
    cx = w / 2
    dr.rounded_rectangle(((cx - 3.2 * s) * SS, 12 * s * SS, (cx + 3.2 * s) * SS,
                          (top + 4 * s) * SS), radius=2 * s * SS, fill=255)
    dr.ellipse(((cx - 3.0 * s) * SS, 8 * s * SS, (cx + 3.0 * s) * SS, 14 * s * SS), fill=255)
    return downsample(im, size)


def _honeycomb(size, s, region):
    """Coarse hexagonal anode mesh (pointy-top cells), clipped to region."""
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    dr = ImageDraw.Draw(im)
    r = 9.0 * s * SS
    dx, dy = math.sqrt(3) * r, 1.5 * r
    lw = max(1, round(1.0 * s * SS))
    for row in range(-1, int(h * SS / dy) + 2):
        for c in range(-1, int(w * SS / dx) + 2):
            cx = c * dx + (dx / 2 if row % 2 else 0)
            cy = row * dy
            pts = [(cx + r * math.cos(math.radians(90 + 60 * k)),
                    cy + r * math.sin(math.radians(90 + 60 * k))) for k in range(7)]
            dr.line(pts, fill=255, width=lw)
    clip = Image.new("L", im.size, 0)
    x0, y0, x1, y1 = region
    ImageDraw.Draw(clip).rectangle((x0 * SS, y0 * SS, x1 * SS, y1 * SS), fill=255)
    return downsample(Image.composite(im, Image.new("L", im.size, 0), clip), size)


def _lines(size, segments, width):
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    dr = ImageDraw.Draw(im)
    for (xa, ya), (xb, yb) in segments:
        dr.line([(xa * SS, ya * SS), (xb * SS, yb * SS)], fill=255,
                width=max(1, round(width * SS)))
    return downsample(im, size)


def _ellipse(size, box, width):
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    x0, y0, x1, y1 = box
    ImageDraw.Draw(im).ellipse((x0 * SS, y0 * SS, x1 * SS, y1 * SS), outline=255,
                               width=max(1, round(width * SS)))
    return downsample(im, size)


def render(d: int | None, size=(135, 240), **params) -> Image.Image:
    p = {**PARAMS, **params}
    w, h = size
    s = w / 135.0
    glow_c, hot_c, metal_c = (col(parse_color(p[k])) for k in ("glow", "hot", "metal"))

    tube = _tube_mask(size, s)
    anode = (22 * s, 66 * s, w - 22 * s, h - 46 * s)  # the mesh cage
    box = (36 * s, 78 * s, w - 36 * s, h - 60 * s)  # digit box

    img = np.zeros((h, w, 3), np.float32) + col(parse_color(p["background"]))
    img += tube[..., None] * col((9, 7, 8))  # faint glass body

    def shape(k):
        if k == 5 and not p["soviet_5"]:
            return digit_strokes(5)
        return soviet_digit_strokes(k)

    lit = (stroke_mask(size, shape(d), box, 3.4 * s) if d is not None
           else np.zeros((h, w), np.float32))
    near, far, haze = blur(lit, 3.5 * s), blur(lit, 9 * s), blur(lit, 22 * s)
    fill = blur(lit, 50 * s) * tube

    # structure behind the mesh: cathode stack, rods, mica disc - lit by the glow
    light = np.clip(0.10 + 3.5 * haze + 2.0 * far, 0, 1.6)
    for k in range(10):
        if k == d:
            continue
        off = ((k % 3) - 1) * 1.0 * s
        b = (box[0] + off, box[1] + off * 0.4, box[2] + off, box[3] + off * 0.4)
        wire = blur(stroke_mask(size, shape(k), b, 1.0 * s), 0.6 * s)
        img += (wire * light * 0.55)[..., None] * metal_c
    rods = _lines(size, [((anode[0] + 2 * s, 52 * s), (anode[0] + 2 * s, h - 34 * s)),
                         ((anode[2] - 2 * s, 52 * s), (anode[2] - 2 * s, h - 34 * s))], 1.4 * s)
    img += (rods * (0.35 + light))[..., None] * metal_c * 0.6
    mica = _ellipse(size, (anode[0] - 4 * s, 50 * s, anode[2] + 4 * s, 60 * s), 1.1 * s)
    img += (mica * (0.45 + light))[..., None] * metal_c * 0.7

    # the discharge: broad orange glow, hot along the wire, no white core
    img += fill[..., None] * glow_c * 4.0  # gas glow filling the cage
    img += haze[..., None] * glow_c * 4.0
    img += far[..., None] * glow_c * 3.0
    img += near[..., None] * (glow_c * 2.2 + hot_c * 0.8)
    img += lit[..., None] * hot_c * 1.2

    # honeycomb anode in front: dark wires that catch a little of the light
    mesh = _honeycomb(size, s, anode)
    img = img * (1 - p["mesh"] * mesh)[..., None] + (mesh * (far + haze) * 0.9)[..., None] * glow_c

    # base: pins and optional underlight
    pins = _lines(size, [((w / 2 + i * 9 * s, h - 34 * s), (w / 2 + i * 9 * s, h - 9 * s))
                         for i in (-3, -2, -1, 0, 1, 2, 3)], 1.0 * s)
    img += pins[..., None] * metal_c * 0.5
    if p["base_glow"] > 0:
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        under = np.clip((yy - 0.72) / 0.28, 0, 1) ** 2 * tube
        img += (under * p["base_glow"])[..., None] * col(parse_color(p["base"])) * 1.6
        img += (pins * p["base_glow"])[..., None] * col(parse_color(p["base"]))

    # glass highlights: vertical streaks near both edges, a soft arc on the shoulder
    refl = _lines(size, [((15 * s, 70 * s), (15 * s, h - 20 * s)),
                         ((w - 18 * s, 80 * s), (w - 18 * s, h - 30 * s))], 2.2 * s)
    refl = blur(refl, 1.0 * s) + 0.5 * blur(_ellipse(size, (14 * s, 32 * s, w - 14 * s,
                                                          90 * s), 1.5 * s), 1.2 * s)
    img += (refl * tube * p["reflection"])[..., None] * col((235, 230, 240))
    img += (blur(tube, 0.8 * s) - blur(tube, 2.5 * s)).clip(0, 1)[..., None] * col((90, 85, 95))
    return to_image(tonemap(img, 1.3))
