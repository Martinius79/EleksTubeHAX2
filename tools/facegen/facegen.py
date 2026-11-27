#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Clock-face generator: renders the built-in faces and encodes them as .etf.

    python tools/facegen/facegen.py list
    python tools/facegen/facegen.py render <preset|style> -o out/x [--size 80x160] [--montage]
                                    [--set key=value ...]
    python tools/facegen/facegen.py build -o out/faces [--update-fallback]

A preset is a style plus parameter values (PRESETS below); `--set` overrides single parameters,
e.g. --set color=#40c0ff --set stroke=5. `build` renders every preset in every display size,
encodes it (smallest lossless encoding per glyph), prints a size report (Markdown) and with
--update-fallback refreshes the fallback faces embedded in the firmware (components/faces).
All generated images are CC0-1.0 (D-019).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PIL import Image

import in14
import minimal
import neon
import nixie
import sevenseg
import varisymbol
import vfd
from common import parse_color

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "etf"))
import etf  # noqa: E402

STYLES = {m.NAME: m for m in (minimal, nixie, in14, sevenseg, vfd, varisymbol, neon)}
SIZES = [(135, 240), (80, 160)]
FALLBACK_DIR = ROOT / "components" / "faces"
FALLBACK_FACE = "minimal"

# old LED look: filled block segments, thick, narrow gaps, no glow
_BLOCK = {"shape": "block", "thickness": 24.0, "gap": 1.0, "skew": 0.0, "glow": 0.0,
          "ghost": 0.2, "color": "#ff1a12", "background": "#000000"}

# preset -> (style, parameter overrides, display name)
PRESETS: dict[str, tuple[str, dict, str]] = {
    "minimal": ("minimal", {}, "Minimal Amber"),
    "minimal-ice": ("minimal", {"color": "#7fd8ff"}, "Minimal Ice"),
    "minimal-paper": ("minimal", {"color": "#202020", "background": "#e8e4d8", "stroke": 9.0},
                      "Minimal Paper"),
    "nixie-glow": ("nixie", {}, "Nixie Glow"),
    "in14": ("in14", {}, "IN-14 Tube"),
    "nixie-mesh": ("in14", {"zoom": 1.22, "stroke": 5.0, "mesh_pitch": 11.0, "jump": 0.09,
                            "glow": "#ff3c00", "hot": "#ffc040", "soviet_5": False},
                   "Nixie Mesh Close-up"),
    "seg7-red": ("sevenseg", {}, "7-Segment Red"),
    "seg7-green": ("sevenseg", {"color": "#30ff50"}, "7-Segment Green"),
    "seg7-lcd": ("sevenseg", {"lcd": True, "color": "#1c201c", "background": "#b4bca8",
                              "ghost": 0.05, "skew": 0.05}, "7-Segment LCD"),
    "seg7-block-red": ("sevenseg", _BLOCK, "7-Segment Block Red"),
    "seg7-block-green": ("sevenseg", {**_BLOCK, "color": "#2ee84a"}, "7-Segment Block Green"),
    "seg7-block-gray": ("sevenseg", {**_BLOCK, "color": "#c8c8c8", "background": "#202020"},
                        "7-Segment Block Gray"),
    "seg7-block-bw": ("sevenseg", {**_BLOCK, "color": "#ffffff", "ghost": 0.12},
                      "7-Segment Block Black-White"),
    "vfd": ("vfd", {}, "VFD Turquoise"),
    "varisymbol": ("varisymbol", {}, "Varisymbol"),
    "neon-pink": ("neon", {}, "Neon Pink"),
    "neon-blue": ("neon", {"color": "#3a8cff"}, "Neon Blue"),
    "neon-retro": ("neon", {"shapes": "retro", "rainbow": True, "background": "#0c0a0e",
                            "wall": 0.04, "gloss": 0.3}, "Neon Retro Rainbow"),
}
COMMON_META = {"author": "EleksTubeHAX2 facegen", "license": "CC0-1.0",
               "generator": "tools/facegen/facegen.py"}


def _coerce(default, value: str):
    """Convert a --set string to the type of the parameter's default."""
    if isinstance(default, bool):
        if value.lower() in ("1", "true", "yes", "on"):
            return True
        if value.lower() in ("0", "false", "no", "off"):
            return False
        raise ValueError(f"expected true/false, got {value!r}")
    if isinstance(default, tuple):
        return parse_color(value)
    return type(default)(value)


def resolve(name: str, overrides: dict[str, str] | None = None) -> tuple[str, dict]:
    """Preset or style name + --set overrides -> (style, parameters)."""
    if name in PRESETS:
        style, params, _ = PRESETS[name]
        params = dict(params)
    elif name in STYLES:
        style, params = name, {}
    else:
        raise ValueError(f"unknown preset or style {name!r} (see 'facegen.py list')")
    defaults = STYLES[style].PARAMS
    for key, value in (overrides or {}).items():
        if key not in defaults:
            raise ValueError(f"style {style!r} has no parameter {key!r} "
                             f"(has: {', '.join(defaults)})")
        params[key] = _coerce(defaults[key], value)
    return style, params


def render_style(name: str, out: Path, size: tuple[int, int], montage: bool = False,
                 overrides: dict[str, str] | None = None) -> None:
    """Write 0.png ... 9.png and blank.png for a preset or style."""
    style, params = resolve(name, overrides)
    out.mkdir(parents=True, exist_ok=True)
    render = STYLES[style].render
    frames = [render(d, size, **params) for d in range(10)]
    for d, im in enumerate(frames):
        im.save(out / f"{d}.png")
    render(None, size, **params).save(out / "blank.png")
    if montage:
        w, h = size
        m = Image.new("RGB", (w * 5, h * 2))
        for d, im in enumerate(frames):
            m.paste(im, ((d % 5) * w, (d // 5) * h))
        m.save(out / "montage.png")


def encode_face(name: str, size: tuple[int, int]) -> tuple[bytes, dict[str, int | None], int]:
    """Render + encode one preset. Returns (file, total bytes per encoding, glyph count)."""
    meta = {"name": PRESETS[name][2], **COMMON_META}
    with tempfile.TemporaryDirectory() as tmp:
        render_style(name, Path(tmp), size)
        report: list = []
        face = etf.build_face(Path(tmp), None, meta, report=report)
    data = etf.write_face(face)
    etf.read_face(data)  # self-check
    totals: dict[str, int | None] = {}
    for enc in etf.ENC_NAMES.values():
        sizes = [r[2].get(enc) for r in report]
        totals[enc] = None if None in sizes else sum(sizes)
    return data, totals, len(face.glyphs)


def _parse_sets(items: list[str] | None) -> dict[str, str]:
    out = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"--set expects key=value, got {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def cmd_list(a) -> int:
    print("Presets:")
    for name, (style, params, title) in PRESETS.items():
        extra = ", ".join(f"{k}={v}" for k, v in params.items())
        print(f"  {name:15} {title:18} style={style}" + (f"  ({extra})" if extra else ""))
    print("\nStyles and parameters (defaults):")
    for name, mod in STYLES.items():
        print(f"  {name}: " + ", ".join(f"{k}={v}" for k, v in mod.PARAMS.items()))
    return 0


def cmd_render(a) -> int:
    w, h = (int(x) for x in a.size.lower().split("x"))
    render_style(a.name, Path(a.out), (w, h), a.montage, _parse_sets(a.set))
    return 0


def cmd_build(a) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    encs = list(etf.ENC_NAMES.values())
    print("| Face | Size | Glyphs | " + " | ".join(encs) + " | **.etf file** |")
    print("|---" * (len(encs) + 4) + "|")
    for name in PRESETS:
        for size in SIZES:
            data, totals, count = encode_face(name, size)
            (out / f"{name}_{size[0]}x{size[1]}.etf").write_bytes(data)
            if a.update_fallback and name == FALLBACK_FACE:
                (FALLBACK_DIR / f"fallback_{size[0]}x{size[1]}.etf").write_bytes(data)
            cols = " | ".join("n/a" if totals[e] is None else f"{totals[e] / 1024:.1f} KB"
                              for e in encs)
            print(f"| {name} | {size[0]}x{size[1]} | {count} | {cols} | "
                  f"**{len(data) / 1024:.1f} KB** |")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list presets, styles and parameters").set_defaults(fn=cmd_list)
    r = sub.add_parser("render", help="render a preset or style as PNGs")
    r.add_argument("name", help="preset or style")
    r.add_argument("-o", "--out", required=True)
    r.add_argument("--size", default="135x240")
    r.add_argument("--montage", action="store_true")
    r.add_argument("--set", action="append", metavar="KEY=VALUE",
                   help="override a style parameter (repeatable)")
    r.set_defaults(fn=cmd_render)
    b = sub.add_parser("build", help="render + encode all presets, print size report")
    b.add_argument("-o", "--out", required=True)
    b.add_argument("--update-fallback", action="store_true",
                   help=f"also write the '{FALLBACK_FACE}' face to {FALLBACK_DIR.relative_to(ROOT)}")
    b.set_defaults(fn=cmd_build)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except ValueError as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
