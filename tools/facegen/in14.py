# SPDX-License-Identifier: GPL-3.0-or-later
"""Round nixie tube, front view of the electrode cage, in the manner of Soviet IN-14 tubes.

No glass bulb (the clock's LCDs have their own glass): a cylindrical honeycomb anode in front,
the cathode stack behind it with every digit at its own depth - cathodes in front of the lit one
show as dark silhouettes against the glow, those behind it are dimly lit and slightly out of
focus, and the lit digit is a little larger or smaller depending on its depth. Broad red-orange
glow without white core, metal end plates top and bottom.

Drawn from geometry only (Soviet-style digit shapes from common.soviet_digit_strokes)."""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from common import (SS, blur, col, digit_strokes, downsample, parse_color, rect_mask,
                    soviet_digit_strokes, stack_depth, stroke_mask, to_image, tonemap, transform,
                    wobble)

NAME = "in14"
PARAMS = {
    "glow": (255, 72, 8),  # discharge colour
    "hot": (255, 128, 36),  # brightest parts of the glowing cathode
    "metal": (92, 82, 78),  # cathodes behind the lit one, end plates
    "mesh_color": (60, 44, 36),  # anode wire where it catches light
    "mesh": 0.70,  # how much the anode mesh darkens what is behind it
    "mesh_pitch": 9.0,  # honeycomb cell radius at 135 px width
    "curvature": 0.55,  # cylinder bulge of the mesh (0 = flat)
    "background": (0, 0, 0),
    "zoom": 1.0,  # digit size (1.25 = close-up)
    "stroke": 3.4,  # lit cathode width
    "jump": 0.07,  # size difference front/back of the cathode stack
    "wobble": 0.006,  # hand-bent wire irregularity
    "silhouette": 0.75,  # darkness of cathodes in front of the lit one
    "soviet_5": True,  # 5 drawn as an upside-down 2 like the real tube
}


def _warp_x(x, cx, half, curvature):
    """Cylinder projection: cells get narrower towards the left and right edge."""
    if curvature <= 0:
        return x
    a = curvature * math.pi / 2
    xn = max(-1.6, min(1.6, (x - cx) / half))
    return cx + half * math.sin(a * xn) / math.sin(a)


def _honeycomb(size, s, pitch, width, curvature):
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    dr = ImageDraw.Draw(im)
    r = pitch * s
    dx, dy = math.sqrt(3) * r, 1.5 * r
    cx, half = w / 2, w / 2
    lw = max(1, round(width * s * SS))
    for row in range(-1, int(h / dy) + 2):
        for c in range(-int(half / dx) - 3, int(half / dx) + 4):
            hx = cx + c * dx + (dx / 2 if row % 2 else 0)
            hy = row * dy
            pts = []
            for k in range(7):
                px = hx + r * math.cos(math.radians(90 + 60 * k))
                py = hy + r * math.sin(math.radians(90 + 60 * k))
                pts.append((_warp_x(px, cx, half, curvature) * SS, py * SS))
            dr.line(pts, fill=255, width=lw)
    return downsample(im, size)


def render(d: int | None, size=(135, 240), **params) -> Image.Image:
    p = {**PARAMS, **params}
    w, h = size
    s = w / 135.0
    glow_c, hot_c, metal_c = (col(parse_color(p[k])) for k in ("glow", "hot", "metal"))
    z = p["zoom"]
    bw, bh = 66 * s * z, 158 * s * z  # digit box, centred
    box = (w / 2 - bw / 2, h / 2 - bh / 2, w / 2 + bw / 2, h / 2 + bh / 2)

    def shape(k):
        base = digit_strokes(5) if (k == 5 and not p["soviet_5"]) else soviet_digit_strokes(k)
        scale = 1 + p["jump"] * (0.5 - stack_depth(k))
        return transform(wobble(base, p["wobble"], seed=200 + k), scale)

    img = np.zeros((h, w, 3), np.float32) + col(parse_color(p["background"]))
    lit = (stroke_mask(size, shape(d), box, p["stroke"] * s * z) if d is not None
           else np.zeros((h, w), np.float32))
    near, far, haze = blur(lit, 3.5 * s * z), blur(lit, 9 * s * z), blur(lit, 22 * s * z)
    fill = blur(lit, 50 * s)
    light = np.clip(0.06 + 3.5 * haze + 2.0 * far, 0, 1.6)

    # cathodes behind the lit one: dimly lit metal, more out of focus the deeper they sit
    lit_depth = stack_depth(d) if d is not None else -1.0
    front = np.zeros((h, w), np.float32)
    for k in range(10):
        if k == d:
            continue
        wire = stroke_mask(size, shape(k), box, 1.1 * s * z)
        if stack_depth(k) > lit_depth:
            wire = blur(wire, (0.3 + 1.2 * stack_depth(k)) * s)
            img += (wire * light * 0.6)[..., None] * metal_c
        else:
            front = np.maximum(front, blur(wire, 0.3 * s))

    # the discharge: broad red-orange glow, hot along the wire, no white core
    img += fill[..., None] * glow_c * 4.0
    img += haze[..., None] * glow_c * 4.0
    img += far[..., None] * glow_c * 3.0
    img += near[..., None] * (glow_c * 2.2 + hot_c * 0.8)
    img += lit[..., None] * hot_c * 1.2

    # cathodes in front of the lit one: dark silhouettes, faintly rimmed by the glow
    img *= (1 - p["silhouette"] * front)[..., None]
    img += (front * far * 0.25)[..., None] * glow_c

    # cylindrical anode mesh in front of everything
    mesh = _honeycomb(size, s, p["mesh_pitch"], 0.8, p["curvature"])
    img = img * (1 - p["mesh"] * mesh)[..., None]
    img += (mesh * (0.08 + far + haze) * 0.9)[..., None] * col(parse_color(p["mesh_color"]))

    # cylinder shading and metal end plates
    xn = (np.arange(w, dtype=np.float32) - w / 2) / (w / 2)
    img *= (0.72 + 0.28 * np.cos(np.clip(xn, -1, 1) * math.pi / 2))[None, :, None]
    plates = rect_mask(size, (0, 0, w, 10 * s), 0) + rect_mask(size, (0, h - 10 * s, w, h), 0)
    img = img * (1 - plates[..., None]) + (plates * (0.25 + light))[..., None] * metal_c * 0.6
    return to_image(tonemap(img, 1.3))
