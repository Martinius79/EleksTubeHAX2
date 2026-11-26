#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Clock-face generator: renders the built-in faces and encodes them as .etf.

    python tools/facegen/facegen.py render nixie -o out/nixie [--size 80x160] [--montage]
    python tools/facegen/facegen.py build -o out/faces [--update-fallback]

`build` renders every built-in face in every display size, encodes it (smallest lossless
encoding per glyph), prints a size report per encoding (Markdown) and with --update-fallback
refreshes the fallback faces embedded in the firmware (components/faces/*.etf).
All generated images are CC0-1.0 (D-019).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PIL import Image

import minimal
import nixie

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "etf"))
import etf  # noqa: E402

STYLES = {"nixie": nixie.render, "minimal": minimal.render}
SIZES = [(135, 240), (80, 160)]
FALLBACK_DIR = ROOT / "components" / "faces"

# name -> (style, metadata)
FACES = {
    "nixie-glow": ("nixie", {"name": "Nixie Glow"}),
    "minimal": ("minimal", {"name": "Minimal Amber"}),
}
FALLBACK_FACE = "minimal"
COMMON_META = {"author": "EleksTubeHAX2 facegen", "license": "CC0-1.0",
               "generator": "tools/facegen/facegen.py"}


def render_style(style: str, out: Path, size: tuple[int, int], montage: bool = False) -> None:
    """Write 0.png ... 9.png and blank.png."""
    out.mkdir(parents=True, exist_ok=True)
    render = STYLES[style]
    frames = [render(d, size) for d in range(10)]
    for d, im in enumerate(frames):
        im.save(out / f"{d}.png")
    render(None, size).save(out / "blank.png")
    if montage:
        w, h = size
        m = Image.new("RGB", (w * 5, h * 2))
        for d, im in enumerate(frames):
            m.paste(im, ((d % 5) * w, (d // 5) * h))
        m.save(out / "montage.png")


def encode_face(name: str, size: tuple[int, int]) -> tuple[bytes, dict[str, int | None], int]:
    """Render + encode one face. Returns (file, total bytes per encoding, glyph count)."""
    style, meta = FACES[name]
    with tempfile.TemporaryDirectory() as tmp:
        render_style(style, Path(tmp), size)
        report: list = []
        face = etf.build_face(Path(tmp), None, {**meta, **COMMON_META}, report=report)
    data = etf.write_face(face)
    etf.read_face(data)  # self-check
    totals: dict[str, int | None] = {}
    for enc in etf.ENC_NAMES.values():
        sizes = [r[2].get(enc) for r in report]
        totals[enc] = None if None in sizes else sum(sizes)
    return data, totals, len(face.glyphs)


def cmd_render(a) -> int:
    w, h = (int(x) for x in a.size.lower().split("x"))
    render_style(a.style, Path(a.out), (w, h), a.montage)
    return 0


def cmd_build(a) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    encs = list(etf.ENC_NAMES.values())
    print("| Face | Size | Glyphs | " + " | ".join(encs) + " | **.etf file** |")
    print("|---" * (len(encs) + 4) + "|")
    for name in FACES:
        for size in SIZES:
            data, totals, count = encode_face(name, size)
            fname = f"{name}_{size[0]}x{size[1]}.etf"
            (out / fname).write_bytes(data)
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
    r = sub.add_parser("render", help="render one style as PNGs")
    r.add_argument("style", choices=sorted(STYLES))
    r.add_argument("-o", "--out", required=True)
    r.add_argument("--size", default="135x240")
    r.add_argument("--montage", action="store_true")
    r.set_defaults(fn=cmd_render)
    b = sub.add_parser("build", help="render + encode all built-in faces, print size report")
    b.add_argument("-o", "--out", required=True)
    b.add_argument("--update-fallback", action="store_true",
                   help=f"also write the '{FALLBACK_FACE}' face to {FALLBACK_DIR.relative_to(ROOT)}")
    b.set_defaults(fn=cmd_build)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
