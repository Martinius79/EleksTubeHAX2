#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""ETF clock-face encoder / decoder (reference implementation of docs/FORMAT_ETF.md v1.0).

    python tools/etf/etf.py encode <dir> -o face.etf [--size 135x240] [--name ...]
    python tools/etf/etf.py info face.etf
    python tools/etf/etf.py decode face.etf -o outdir

Input directory: one image per glyph, named after the glyph: 0.png … 9.png (required), and
optionally blank, colon, minus, dot, am, pm (any format Pillow reads).
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

MAGIC = b"ETF\x1a"
VERSION = (1, 0)
HEADER_SIZE = 32
GLYPH_ENTRY_SIZE = 32
MAX_META = 4096
DEFLATE_WBITS = 12  # max distance 4096 bytes (spec 5.4)

RAW565, RLE565, PAL8_RLE, DEFLATE565, DEFLATE_PAL8 = range(5)
ENC_NAMES = {RAW565: "RAW565", RLE565: "RLE565", PAL8_RLE: "PAL8_RLE",
             DEFLATE565: "DEFLATE565", DEFLATE_PAL8: "DEFLATE_PAL8"}
FLAG_HAS_KEY = 0x01

GLYPH_NAMES = {**{str(d): 0x30 + d for d in range(10)},
               "blank": 0x20, "colon": 0x3A, "minus": 0x2D, "dot": 0x2E,
               "am": 0xE000, "pm": 0xE001}


class EtfError(Exception):
    pass


# --- pixel helpers ---------------------------------------------------------------------------


def rgb_to_565(rgb: np.ndarray) -> np.ndarray:
    """HxWx3 uint8 -> HxW uint16 RGB565 (rounded)."""
    c = rgb.astype(np.uint32)
    r = (c[..., 0] * 31 + 127) // 255
    g = (c[..., 1] * 63 + 127) // 255
    b = (c[..., 2] * 31 + 127) // 255
    return ((r << 11) | (g << 5) | b).astype(np.uint16)


def rgb565_to_rgb(v: np.ndarray) -> np.ndarray:
    v = v.astype(np.uint32)
    r, g, b = (v >> 11) & 0x1F, (v >> 5) & 0x3F, v & 0x1F
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)],
                    axis=-1).astype(np.uint8)


def be16(values) -> bytes:
    return np.asarray(values, dtype=">u2").tobytes()


# --- encoders --------------------------------------------------------------------------------


def _rle_rows(rows: np.ndarray, psize: int) -> bytes:
    """PackBits-style RLE, packets never cross rows. rows: HxW array of pixel values."""
    out = bytearray()
    pack = (lambda vals: be16(vals)) if psize == 2 else (lambda vals: bytes(np.asarray(vals, np.uint8)))
    for row in rows:
        row = row.tolist()
        n, i = len(row), 0
        lit: list[int] = []

        def flush():
            while lit:
                chunk = lit[:128]
                del lit[:128]
                out.append(len(chunk) - 1)
                out.extend(pack(chunk))

        while i < n:
            j = i
            while j + 1 < n and row[j + 1] == row[i] and j - i < 127:
                j += 1
            run = j - i + 1
            if run >= 2:
                flush()
                out.append(0x80 | (run - 1))
                out.extend(pack([row[i]]))
                i = j + 1
            else:
                lit.append(row[i])
                i += 1
        flush()
    return bytes(out)


def _deflate(data: bytes) -> bytes:
    c = zlib.compressobj(9, zlib.DEFLATED, -DEFLATE_WBITS, 9)
    return c.compress(data) + c.flush()


def _palette(px: np.ndarray):
    colours, idx = np.unique(px.reshape(-1), return_inverse=True)
    if len(colours) > 256:
        return None
    return colours, idx.reshape(px.shape).astype(np.uint8)


def encode_glyph(px: np.ndarray, only: int | None = None) -> dict[int, bytes]:
    """All applicable encodings of a HxW RGB565 array -> {encoding: data}."""
    res: dict[int, bytes] = {}
    want = (lambda e: only is None or only == e)
    if want(RAW565):
        res[RAW565] = be16(px.reshape(-1))
    if want(RLE565):
        res[RLE565] = _rle_rows(px, 2)
    if want(DEFLATE565):
        res[DEFLATE565] = _deflate(be16(px.reshape(-1)))
    pal = _palette(px) if (want(PAL8_RLE) or want(DEFLATE_PAL8)) else None
    if pal is not None:
        colours, idx = pal
        head = struct.pack("<H", len(colours)) + be16(colours)
        if want(PAL8_RLE):
            res[PAL8_RLE] = head + _rle_rows(idx, 1)
        if want(DEFLATE_PAL8):
            res[DEFLATE_PAL8] = head + _deflate(idx.tobytes())
    if not res:
        raise EtfError(f"encoding {ENC_NAMES.get(only, only)} not applicable (>256 colours?)")
    return res


# --- container -------------------------------------------------------------------------------


@dataclass
class Glyph:
    code: int
    x: int
    y: int
    w: int
    h: int
    encoding: int
    data: bytes
    bg_color: int = 0
    key_color: int = 0
    flags: int = 0
    pixels: np.ndarray | None = None  # decoded HxW RGB565 (reader only)


@dataclass
class Face:
    canvas_w: int
    canvas_h: int
    glyphs: list[Glyph] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)


def _align4(n: int) -> int:
    return (n + 3) & ~3


def write_face(face: Face) -> bytes:
    glyphs = sorted(face.glyphs, key=lambda g: g.code)
    meta = "".join(f"{k}={v}\n" for k, v in face.meta.items()).encode("utf-8")
    if len(meta) > MAX_META:
        raise EtfError("metadata too large")
    table_off = HEADER_SIZE
    meta_off = table_off + GLYPH_ENTRY_SIZE * len(glyphs)
    pos = _align4(meta_off + len(meta))
    table = bytearray()
    blob = bytearray()
    for g in glyphs:
        table += struct.pack("<IHHHHBBHHHIII", g.code, g.x, g.y, g.w, g.h, g.encoding, g.flags,
                             g.key_color, g.bg_color, 0, pos + len(blob), len(g.data),
                             zlib.crc32(g.data))
        blob += g.data
        if g is not glyphs[-1]:
            blob += b"\0" * (_align4(len(blob)) - len(blob))
    head = struct.pack("<4sBBHHHHHIII", MAGIC, *VERSION, HEADER_SIZE, face.canvas_w,
                       face.canvas_h, len(glyphs), 0, table_off,
                       meta_off if meta else 0, len(meta))
    # header_crc covers header bytes 0..27, the glyph table and the metadata (spec 3)
    head += struct.pack("<I", zlib.crc32(meta, zlib.crc32(table, zlib.crc32(head))))
    body = head + table + meta
    body += b"\0" * (pos - len(body))
    return bytes(body + blob)


def _unrle(data: bytes, pos: int, w: int, h: int, psize: int) -> tuple[np.ndarray, int]:
    out = np.empty((h, w), np.uint16 if psize == 2 else np.uint8)
    for y in range(h):
        x = 0
        while x < w:
            if pos >= len(data):
                raise EtfError("RLE data truncated")
            c = data[pos]
            pos += 1
            n = (c & 0x7F) + 1
            if x + n > w:
                raise EtfError("RLE packet crosses row end")
            if c & 0x80:
                count = 1
            else:
                count = n
            raw = data[pos:pos + count * psize]
            if len(raw) != count * psize:
                raise EtfError("RLE data truncated")
            pos += count * psize
            vals = np.frombuffer(raw, ">u2" if psize == 2 else np.uint8)
            out[y, x:x + n] = vals[0] if c & 0x80 else vals
            x += n
    return out, pos


def _inflate(data: bytes, expect: int) -> bytes:
    d = zlib.decompressobj(-DEFLATE_WBITS)  # strict: distances > 4096 are an error
    try:
        raw = d.decompress(data, expect + 1)
    except zlib.error as ex:
        raise EtfError(f"DEFLATE error: {ex}") from None
    if len(raw) != expect or not d.eof or d.unused_data:
        raise EtfError("DEFLATE size mismatch")
    return raw


def decode_glyph(g: Glyph) -> np.ndarray:
    d, w, h = g.data, g.w, g.h
    if g.encoding == RAW565:
        if len(d) != 2 * w * h:
            raise EtfError("RAW565 size mismatch")
        return np.frombuffer(d, ">u2").reshape(h, w).astype(np.uint16)
    if g.encoding == RLE565:
        px, end = _unrle(d, 0, w, h, 2)
        if end != len(d):
            raise EtfError("RLE565 trailing data")
        return px
    if g.encoding in (PAL8_RLE, DEFLATE_PAL8):
        if len(d) < 2:
            raise EtfError("palette truncated")
        (n,) = struct.unpack_from("<H", d, 0)
        if not 1 <= n <= 256 or len(d) < 2 + 2 * n:
            raise EtfError("bad palette")
        pal = np.frombuffer(d[2:2 + 2 * n], ">u2").astype(np.uint16)
        if g.encoding == PAL8_RLE:
            idx, end = _unrle(d, 2 + 2 * n, w, h, 1)
            if end != len(d):
                raise EtfError("PAL8_RLE trailing data")
        else:
            idx = np.frombuffer(_inflate(d[2 + 2 * n:], w * h), np.uint8).reshape(h, w)
        if idx.max(initial=0) >= n:
            raise EtfError("palette index out of range")
        return pal[idx]
    if g.encoding == DEFLATE565:
        return np.frombuffer(_inflate(d, 2 * w * h), ">u2").reshape(h, w).astype(np.uint16)
    raise EtfError(f"unknown encoding {g.encoding}")


def read_face(buf: bytes, verify_crc: bool = True) -> Face:
    if len(buf) < HEADER_SIZE:
        raise EtfError("file too small")
    (magic, vmaj, _vmin, hsize, cw, ch, count, _flags, toff, moff, msize, hcrc) = \
        struct.unpack_from("<4sBBHHHHHIIII", buf, 0)
    if magic != MAGIC:
        raise EtfError("bad magic")
    if vmaj != VERSION[0]:
        raise EtfError(f"unsupported major version {vmaj}")
    if hsize < HEADER_SIZE or hsize > len(buf):
        raise EtfError("bad header size")
    if not (1 <= cw <= 1024 and 1 <= ch <= 1024 and 1 <= count <= 256):
        raise EtfError("canvas or glyph count out of range")
    tend = toff + count * GLYPH_ENTRY_SIZE
    if toff % 4 or toff < hsize or tend > len(buf):
        raise EtfError("glyph table outside file")
    if moff and (msize > MAX_META or moff < hsize or moff + msize > len(buf)):
        raise EtfError("metadata outside file")
    if not moff and msize:
        raise EtfError("metadata size without offset")
    meta_raw = buf[moff:moff + msize] if moff else b""
    if zlib.crc32(meta_raw, zlib.crc32(buf[toff:tend], zlib.crc32(buf[:28]))) != hcrc:
        raise EtfError("header CRC mismatch")
    meta: dict[str, str] = {}
    if meta_raw:
        try:
            text = meta_raw.decode("utf-8")
        except UnicodeDecodeError:
            raise EtfError("metadata is not UTF-8") from None
        for line in text.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                meta[k] = v
    face = Face(cw, ch, meta=meta)
    last = -1
    for i in range(count):
        (code, x, y, w, h, enc, gflags, key, bg, _r, doff, dsize, dcrc) = \
            struct.unpack_from("<IHHHHBBHHHIII", buf, toff + i * GLYPH_ENTRY_SIZE)
        if code <= last:
            raise EtfError("glyph codes not strictly ascending")
        last = code
        if w < 1 or h < 1 or x + w > cw or y + h > ch:
            raise EtfError(f"glyph U+{code:04X} outside canvas")
        if enc not in ENC_NAMES:
            raise EtfError(f"glyph U+{code:04X}: unknown encoding {enc}")
        if doff % 4 or doff < hsize or doff + dsize > len(buf):
            raise EtfError(f"glyph U+{code:04X}: data outside file")
        if dsize and ((doff < tend and toff < doff + dsize) or
                      (moff and msize and doff < moff + msize and moff < doff + dsize)):
            raise EtfError(f"glyph U+{code:04X}: data overlaps glyph table or metadata")
        data = buf[doff:doff + dsize]
        if verify_crc and zlib.crc32(data) != dcrc:
            raise EtfError(f"glyph U+{code:04X}: data CRC mismatch")
        g = Glyph(code, x, y, w, h, enc, data, bg, key, gflags)
        g.pixels = decode_glyph(g)
        face.glyphs.append(g)
    codes = {g.code for g in face.glyphs}
    missing = [d for d in range(10) if 0x30 + d not in codes]
    if missing:
        raise EtfError(f"missing digit glyphs: {missing}")
    return face


def render_canvas(face: Face, g: Glyph) -> np.ndarray:
    """Full-canvas RGB565 image of a glyph (area outside the rectangle = bg_color)."""
    canvas = np.full((face.canvas_h, face.canvas_w), g.bg_color, np.uint16)
    canvas[g.y:g.y + g.h, g.x:g.x + g.w] = g.pixels
    return canvas


# --- image preparation -----------------------------------------------------------------------


def _corner_bg(px: np.ndarray) -> int:
    corners = [int(px[0, 0]), int(px[0, -1]), int(px[-1, 0]), int(px[-1, -1])]
    return max(set(corners), key=corners.count)


def crop_uniform(px: np.ndarray, bg: int) -> tuple[int, int, np.ndarray]:
    """Crop rows/columns consisting only of bg. Returns x, y, cropped (at least 1x1)."""
    mask = px != bg
    if not mask.any():
        return 0, 0, px[:1, :1]
    ys, xs = np.where(mask.any(axis=1))[0], np.where(mask.any(axis=0))[0]
    y0, y1, x0, x1 = ys[0], ys[-1] + 1, xs[0], xs[-1] + 1
    return int(x0), int(y0), px[y0:y1, x0:x1]


def load_image(path: Path, size: tuple[int, int] | None) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    if size and im.size != size:
        im.thumbnail(size, Image.LANCZOS)
        bg = Image.new("RGB", size, im.getpixel((0, 0)))
        bg.paste(im, ((size[0] - im.width) // 2, (size[1] - im.height) // 2))
        im = bg
    return rgb_to_565(np.asarray(im))


def find_glyph_files(src: Path) -> dict[int, Path]:
    files: dict[int, Path] = {}
    for p in sorted(src.iterdir()):
        code = GLYPH_NAMES.get(p.stem.lower())
        if code is not None and p.is_file() and p.suffix.lower() in (".png", ".bmp", ".jpg",
                                                                     ".jpeg", ".gif", ".webp"):
            files[code] = p
    return files


def build_face(src: Path, size: tuple[int, int] | None, meta: dict[str, str],
               only: int | None = None, crop: bool = True,
               report: list | None = None) -> Face:
    files = find_glyph_files(src)
    missing = [d for d in range(10) if 0x30 + d not in files]
    if missing:
        raise EtfError(f"{src}: missing digit images {missing}")
    face = None
    for code, path in sorted(files.items()):
        full = load_image(path, size)
        h, w = full.shape
        if face is None:
            face = Face(w, h, meta=meta)
        elif (w, h) != (face.canvas_w, face.canvas_h):
            raise EtfError(f"{path.name}: size {w}x{h} differs (use --size)")
        bg = _corner_bg(full)
        x, y, px = crop_uniform(full, bg) if crop else (0, 0, full)
        variants = encode_glyph(px, only)
        enc = min(variants, key=lambda e: (len(variants[e]), e))
        face.glyphs.append(Glyph(code, x, y, px.shape[1], px.shape[0], enc, variants[enc],
                                 bg_color=bg))
        if report is not None:
            report.append((code, px.shape, {ENC_NAMES[e]: len(v) for e, v in variants.items()},
                           ENC_NAMES[enc]))
    return face


# --- CLI -------------------------------------------------------------------------------------


def _size(s: str) -> tuple[int, int]:
    w, h = s.lower().split("x")
    return int(w), int(h)


def _glyph_label(code: int) -> str:
    return chr(code) if 0x20 < code < 0x7F else f"U+{code:04X}"


def cmd_encode(a) -> int:
    meta = {k: v for k, v in (("name", a.name), ("author", a.author), ("license", a.license),
                              ("generator", "tools/etf/etf.py")) if v}
    only = {v: k for k, v in ENC_NAMES.items()}[a.encoding] if a.encoding else None
    report: list = []
    face = build_face(Path(a.src), _size(a.size) if a.size else None, meta, only,
                      crop=not a.no_crop, report=report)
    data = write_face(face)
    read_face(data)  # self-check: decodes and validates
    Path(a.out).write_bytes(data)
    if not a.quiet:
        print(f"{a.out}: {face.canvas_w}x{face.canvas_h}, {len(face.glyphs)} glyphs, "
              f"{len(data)} bytes")
        for code, shape, sizes, chosen in report:
            cols = "  ".join(f"{k}={v}" for k, v in sizes.items())
            print(f"  {_glyph_label(code):>6} {shape[1]}x{shape[0]}  -> {chosen:12}  {cols}")
    return 0


def cmd_info(a) -> int:
    buf = Path(a.file).read_bytes()
    face = read_face(buf)
    print(f"{a.file}: {face.canvas_w}x{face.canvas_h}, {len(face.glyphs)} glyphs, {len(buf)} bytes")
    for k, v in face.meta.items():
        print(f"  {k}: {v}")
    for g in face.glyphs:
        print(f"  {_glyph_label(g.code):>6} rect {g.x},{g.y} {g.w}x{g.h}  "
              f"{ENC_NAMES[g.encoding]:12} {len(g.data):7} bytes  bg=0x{g.bg_color:04X}")
    return 0


def cmd_decode(a) -> int:
    face = read_face(Path(a.file).read_bytes())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    names = {v: k for k, v in GLYPH_NAMES.items()}
    for g in face.glyphs:
        name = names.get(g.code, f"u{g.code:04x}")
        Image.fromarray(rgb565_to_rgb(render_canvas(face, g)), "RGB").save(out / f"{name}.png")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("encode", help="images -> .etf")
    e.add_argument("src", help="directory with 0.png … 9.png (+ optional extra glyphs)")
    e.add_argument("-o", "--out", required=True)
    e.add_argument("--size", help="target canvas WxH (fit + centre), e.g. 135x240")
    e.add_argument("--encoding", choices=list(ENC_NAMES.values()), help="force one encoding")
    e.add_argument("--no-crop", action="store_true", help="do not crop uniform borders")
    e.add_argument("--name")
    e.add_argument("--author")
    e.add_argument("--license", help="SPDX identifier, e.g. CC0-1.0")
    e.add_argument("-q", "--quiet", action="store_true")
    e.set_defaults(fn=cmd_encode)
    i = sub.add_parser("info", help="show header and glyph table")
    i.add_argument("file")
    i.set_defaults(fn=cmd_info)
    d = sub.add_parser("decode", help=".etf -> PNG per glyph")
    d.add_argument("file")
    d.add_argument("-o", "--out", required=True)
    d.set_defaults(fn=cmd_decode)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except EtfError as ex:
        print(f"error: {ex}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
