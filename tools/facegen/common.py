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


def _rot180(strokes):
    return [[(1 - u, 1 - v) for u, v in st] for st in strokes]


def soviet_digit_strokes(d: int) -> list[list[tuple[float, float]]]:
    """Digit shapes in the manner of Soviet nixie tubes (IN-14 family): flat-topped 3, and the
    tube's economy of reusing cathode shapes - 5 is an upside-down 2, 9 an upside-down 6."""
    if d == 0:
        return [arc(0.5, 0.5, 0.5, 0.5, 0, 360)]
    if d == 1:
        return [[(0.30, 0.14), (0.58, 0.0), (0.58, 1.0)]]
    if d == 2:
        return [arc(0.5, 0.26, 0.48, 0.26, 190, 360 + 35) + [(0.02, 1.0), (1.0, 1.0)]]
    if d == 3:
        return [[(0.04, 0.0), (0.96, 0.0), (0.42, 0.40)] + arc(0.5, 0.70, 0.5, 0.30, 252, 515)]
    if d == 4:
        return [[(0.76, 1.0), (0.76, 0.0), (0.0, 0.70), (1.0, 0.70)]]
    if d == 5:
        return _rot180(soviet_digit_strokes(2))
    if d == 6:
        return [arc(0.5, 0.70, 0.48, 0.30, 0, 360), [(0.08, 0.62), (0.70, 0.0)]]
    if d == 7:
        return [[(0.0, 0.0), (1.0, 0.0), (0.28, 1.0)]]
    if d == 8:
        return [arc(0.5, 0.22, 0.40, 0.22, 90, 450), arc(0.5, 0.72, 0.48, 0.28, -90, 270)]
    if d == 9:
        return _rot180(soviet_digit_strokes(6))
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


def polygon_mask(size, polygons) -> np.ndarray:
    """Anti-aliased mask of filled polygons given in final pixel coordinates."""
    w, h = size
    im = Image.new("L", (w * SS, h * SS), 0)
    dr = ImageDraw.Draw(im)
    for pts in polygons:
        dr.polygon([(x * SS, y * SS) for x, y in pts], fill=255)
    return downsample(im, size)


def parse_color(value) -> tuple[int, int, int]:
    """'#rrggbb', 'rrggbb' or an (r, g, b) tuple -> (r, g, b)."""
    if isinstance(value, (tuple, list)):
        r, g, b = (int(c) for c in value)
    else:
        v = str(value).lstrip("#")
        if len(v) != 6:
            raise ValueError(f"colour must be #rrggbb, got {value!r}")
        r, g, b = (int(v[i:i + 2], 16) for i in (0, 2, 4))
    return r, g, b


def glow(mask: np.ndarray, s: float, color, strength: float = 1.0,
         core=(255, 240, 220)) -> np.ndarray:
    """Light emitted by a lit mask: white-hot core, coloured near and far glow (linear RGB)."""
    near = blur(mask, 1.8 * s)
    far = blur(mask, 7.0 * s)
    wide = blur(mask, 22.0 * s)
    c = col(color)
    img = wide[..., None] * c * 0.9 * strength
    img = img + far[..., None] * c * 1.5 * strength
    img = img + near[..., None] * c * 2.0
    img = img + mask[..., None] * (c * 0.6 + col(core) * 0.9)
    return img


def tonemap(img: np.ndarray, exposure: float = 1.4) -> np.ndarray:
    """Soft saturation instead of hard clipping for additive light."""
    return 1 - np.exp(-img * exposure)


# --- hand-made look --------------------------------------------------------------------------

# Cathode stack order of IN-14 style tubes, front to back.
NIXIE_STACK = (1, 6, 2, 7, 5, 0, 4, 9, 8, 3)


def stack_depth(d: int) -> float:
    """Position of digit d in the cathode stack: 0.0 = front, 1.0 = back."""
    return NIXIE_STACK.index(d) / (len(NIXIE_STACK) - 1)


def wobble(strokes, amount: float, seed: int):
    """Bend strokes slightly like hand-formed wire: smooth, deterministic displacement along the
    path (amount in unit-box coordinates, e.g. 0.006)."""
    if amount <= 0:
        return strokes
    rng = np.random.default_rng(seed)
    out = []
    for st in strokes:
        pts = np.asarray(st, dtype=np.float64)
        seg = np.r_[0.0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
        t = seg / seg[-1] if seg[-1] > 0 else seg
        disp = np.zeros_like(pts)
        for axis in (0, 1):
            for freq in (1.3, 2.9, 5.1):
                phase = rng.uniform(0, 2 * np.pi)
                disp[:, axis] += np.sin(2 * np.pi * freq * t + phase) / freq
        closed = np.allclose(pts[0], pts[-1])
        if closed:  # keep loops closed
            disp -= np.outer(t, disp[-1] - disp[0]) + disp[0]
        out.append([tuple(p) for p in pts + disp * amount])
    return out


def transform(strokes, scale: float = 1.0, dx: float = 0.0, dy: float = 0.0,
              angle_deg: float = 0.0):
    """Scale/rotate strokes around the unit-box centre, then shift (unit coordinates)."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for st in strokes:
        pts = []
        for u, v in st:
            x, y = (u - 0.5) * scale, (v - 0.5) * scale
            pts.append((0.5 + x * ca - y * sa + dx, 0.5 + x * sa + y * ca + dy))
        out.append(pts)
    return out


def rounded_path(points, radius: float, n: int = 6):
    """Polyline with rounded inner corners (radius in unit coordinates)."""
    pts = [np.asarray(p, dtype=np.float64) for p in points]
    if len(pts) < 3 or radius <= 0:
        return [tuple(p) for p in pts]
    out = [tuple(pts[0])]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        u1, u2 = (a - b), (c - b)
        l1, l2 = np.linalg.norm(u1), np.linalg.norm(u2)
        if l1 == 0 or l2 == 0:
            continue
        r = min(radius, l1 / 2, l2 / 2)
        p1, p2 = b + u1 / l1 * r, b + u2 / l2 * r
        for k in range(n + 1):  # quadratic Bezier from p1 via b to p2
            t = k / n
            q = (1 - t) ** 2 * p1 + 2 * (1 - t) * t * b + t ** 2 * p2
            out.append(tuple(q))
    out.append(tuple(pts[-1]))
    return out
