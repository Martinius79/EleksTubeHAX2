#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the ETF fixtures shared by the Python reference and the C decoder host tests.

    python test/host/fixtures/generate.py [outdir]   (default: this directory)

Writes small .etf files, a .expect file per valid face (all glyphs rendered on the full canvas,
RGB565 big-endian, in glyph-table order) and manifest.txt with the expected outcome per file:
  ok            opens, every glyph verifies and decodes to the .expect pixels
  open_error    etf_open() must fail
  crc_error     opens, but at least one glyph's data CRC check fails
  decode_error  opens, CRCs match, but decoding at least one glyph fails
The output is deterministic; test/tools checks that the committed files are up to date.
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "etf"))
import etf  # noqa: E402

W, H = 12, 16


def pat_details(d: int) -> np.ndarray:
    px = np.zeros((H, W), np.uint16)
    px[2:14:3, 1 + d] = 0xFFFF
    px[6, 1:11] = 0xF800
    px[3 + d, 6] = 0x07E0
    return px


def pat_few(d: int) -> np.ndarray:
    rng = np.random.default_rng(100 + d)
    pal = rng.integers(0, 0x10000, 6, dtype=np.uint16)
    px = pal[rng.integers(0, 6, (H, W))]
    px[:, 4:8] = pal[0]  # runs inside rows and one run over a full row
    px[10] = pal[1]
    return px


def pat_noise(d: int) -> np.ndarray:
    return np.random.default_rng(200 + d).integers(0, 0x10000, (H, W), dtype=np.uint16)


def pat_wide_runs(d: int) -> np.ndarray:
    """Rows wider than one 128-pixel packet need two packets per row."""
    px = np.full((4, 140), 0x1111 * (d + 1) & 0xFFFF, np.uint16)
    px[::2, 130:] = 0xF81F
    return px


def build(gen, encoding, crop=True, extra_colon=False):
    face = None
    glyphs = [(0x30 + d, gen(d)) for d in range(10)]
    if extra_colon:
        glyphs.append((0x3A, gen(3)[::-1].copy()))
    for code, full in glyphs:
        h, w = full.shape
        face = face or etf.Face(w, h, meta={"name": "fixture", "license": "CC0-1.0"})
        bg = etf._corner_bg(full)
        x, y, px = etf.crop_uniform(full, bg) if crop else (0, 0, full)
        variants = etf.encode_glyph(px, encoding)
        enc = encoding if encoding is not None else min(variants, key=lambda e: (len(variants[e]), e))
        face.glyphs.append(etf.Glyph(code, x, y, px.shape[1], px.shape[0], enc, variants[enc],
                                     bg_color=bg))
    return face


def expect_bytes(face: etf.Face) -> bytes:
    out = bytearray()
    for g in sorted(face.glyphs, key=lambda g: g.code):
        g.pixels = etf.decode_glyph(g)
        out += etf.be16(etf.render_canvas(face, g).reshape(-1))
    return bytes(out)


def refresh_crcs(buf: bytearray) -> bytearray:
    """Recompute all CRCs after a deliberate modification."""
    count = struct.unpack_from("<H", buf, 12)[0]
    toff, moff, msize = struct.unpack_from("<III", buf, 16)
    for i in range(count):
        e = toff + i * 32
        doff, dsize = struct.unpack_from("<II", buf, e + 20)
        if doff + dsize <= len(buf):
            struct.pack_into("<I", buf, e + 28, zlib.crc32(buf[doff:doff + dsize]))
    crc = zlib.crc32(bytes(buf[:28]))
    crc = zlib.crc32(bytes(buf[toff:toff + 32 * count]), crc)
    if moff:
        crc = zlib.crc32(bytes(buf[moff:moff + msize]), crc)
    struct.pack_into("<I", buf, 28, crc)
    return buf


def with_glyph_data(face: etf.Face, code: int, data: bytes) -> bytes:
    for g in face.glyphs:
        if g.code == code:
            g.data = data
    return etf.write_face(face)


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, tuple[bytes, str]] = {}

    valid = {
        "raw565": build(pat_details, etf.RAW565, crop=False),
        "rle565": build(pat_few, etf.RLE565),
        "rle565_wide": build(pat_wide_runs, etf.RLE565, crop=False),
        "pal8_rle": build(pat_few, etf.PAL8_RLE),
        "deflate565": build(pat_noise, etf.DEFLATE565),
        "deflate_pal8": build(pat_few, etf.DEFLATE_PAL8),
        "auto_cropped": build(pat_details, None, extra_colon=True),
    }
    for name, face in valid.items():
        files[name] = (etf.write_face(face), "ok")
        (out / f"{name}.expect").write_bytes(expect_bytes(face))

    good = files["rle565"][0]
    b = bytearray(good)
    b[0] = ord("X")
    files["bad_magic"] = (bytes(b), "open_error")
    b = bytearray(good)
    b[4] = 2
    files["bad_version"] = (bytes(refresh_crcs(b)), "open_error")
    b = bytearray(good)
    b[32 + 4] ^= 0x01  # glyph x changes, header CRC not updated
    files["bad_header_crc"] = (bytes(b), "open_error")
    files["truncated"] = (good[:-10], "open_error")
    b = bytearray(good)
    struct.pack_into("<H", b, 32 + 8, W + 1)  # glyph wider than the canvas
    files["glyph_outside_canvas"] = (bytes(refresh_crcs(b)), "open_error")
    nine = build(pat_few, etf.RLE565)
    nine.glyphs = nine.glyphs[:9]
    files["missing_digit"] = (etf.write_face(nine), "open_error")

    b = bytearray(good)
    doff = struct.unpack_from("<I", b, 32 + 20)[0]
    b[doff + 3] ^= 0x40  # pixel data changes, data CRC not updated
    files["bad_data_crc"] = (bytes(b), "crc_error")

    def rle_face():
        return build(pat_few, etf.RLE565, crop=False)

    row_cross = bytes([0x80 | 120, 0x12, 0x34])  # run of 121 pixels in a 12-pixel row
    files["rle_row_cross"] = (with_glyph_data(rle_face(), 0x35, row_cross), "decode_error")
    trailing = etf.encode_glyph(pat_few(1), etf.RLE565)[etf.RLE565] + bytes([0x80, 0, 0])
    files["rle_trailing"] = (with_glyph_data(rle_face(), 0x31, trailing), "decode_error")
    short = etf.encode_glyph(pat_few(2), etf.RLE565)[etf.RLE565][:-5]
    files["rle_short"] = (with_glyph_data(rle_face(), 0x32, short), "decode_error")

    pal = build(pat_few, etf.PAL8_RLE, crop=False)
    bad_idx = struct.pack("<H", 2) + etf.be16([0x1234, 0x5678]) + bytes([0x80 | (W - 1), 5]) * H
    files["pal_index"] = (with_glyph_data(pal, 0x37, bad_idx), "decode_error")
    files["pal_zero_count"] = (with_glyph_data(build(pat_few, etf.PAL8_RLE, crop=False), 0x30,
                                               struct.pack("<H", 0)), "decode_error")

    def defl(data: bytes) -> bytes:
        c = zlib.compressobj(9, zlib.DEFLATED, -12, 9)
        return c.compress(data) + c.flush()

    px = etf.be16(pat_noise(4).reshape(-1))
    files["deflate_short"] = (with_glyph_data(build(pat_noise, etf.DEFLATE565, crop=False), 0x34,
                                              defl(px[:-2])), "decode_error")
    files["deflate_long"] = (with_glyph_data(build(pat_noise, etf.DEFLATE565, crop=False), 0x34,
                                             defl(px + b"\0\0")), "decode_error")
    files["deflate_trailing"] = (with_glyph_data(build(pat_noise, etf.DEFLATE565, crop=False),
                                                 0x34, defl(px) + b"\x00\x00\x00"), "decode_error")
    files["deflate_garbage"] = (with_glyph_data(build(pat_noise, etf.DEFLATE565, crop=False), 0x36,
                                                bytes([0xFF]) * 64), "decode_error")
    files["unknown_encoding"] = (with_glyph_data(build(pat_few, etf.RLE565, crop=False), 0x30,
                                                 b"\0" * 4), "decode_error")
    b = bytearray(files["unknown_encoding"][0])
    b[32 + 12] = 9  # encoding of glyph '0'
    files["unknown_encoding"] = (bytes(refresh_crcs(b)), "decode_error")

    lines = []
    for name, (data, outcome) in files.items():
        (out / f"{name}.etf").write_bytes(data)
        lines.append(f"{name} {outcome}")
    (out / "manifest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
