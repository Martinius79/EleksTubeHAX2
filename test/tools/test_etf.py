# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the ETF reference encoder/decoder (tools/etf/etf.py).

Run: python -m unittest discover -s test/tools -v
"""

from __future__ import annotations

import random
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "etf"))
import etf  # noqa: E402

W, H = 135, 240


# --- deterministic test images (P1.4) ---------------------------------------------------------


def img_solid(seed: int) -> np.ndarray:
    return np.full((H, W), 0x1234 + seed, np.uint16)


def img_gradient(seed: int) -> np.ndarray:
    y, x = np.mgrid[0:H, 0:W]
    return (((x * 31 // W) << 11) | (((y + seed) * 63 // H % 64) << 5) | (x * 31 // W)).astype(
        np.uint16)


def img_noise(seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 0x10000, (H, W), dtype=np.uint16)


def img_few_colours(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    pal = rng.integers(0, 0x10000, 7, dtype=np.uint16)
    return pal[rng.integers(0, 7, (H, W))]


def img_details(seed: int) -> np.ndarray:
    """1-pixel lines and dots on black, with a black border to exercise cropping."""
    px = np.zeros((H, W), np.uint16)
    px[20:220:3, 30 + seed] = 0xFFFF
    px[100, 10:125] = 0xF800
    px[50 + seed, 60] = 0x07E0
    return px


def img_256(seed: int) -> np.ndarray:
    """Exactly 256 colours - the PAL8 limit."""
    return (np.arange(H * W, dtype=np.uint32).reshape(H, W) * 7 + seed) % 256 * 0x101 % 0x10000


IMAGES = {"solid": img_solid, "gradient": img_gradient, "noise": img_noise,
          "few_colours": img_few_colours, "details": img_details, "exact_256": img_256}


def make_face(gen, encoding=None, crop=True) -> etf.Face:
    face = etf.Face(W, H, meta={"name": "test", "license": "CC0-1.0"})
    for d in range(10):
        full = gen(d).astype(np.uint16)
        bg = etf._corner_bg(full)
        x, y, px = etf.crop_uniform(full, bg) if crop else (0, 0, full)
        variants = etf.encode_glyph(px, encoding)
        enc = min(variants, key=lambda e: (len(variants[e]), e))
        face.glyphs.append(etf.Glyph(0x30 + d, x, y, px.shape[1], px.shape[0], enc,
                                     variants[enc], bg_color=bg))
    return face


def canvases(face: etf.Face) -> list[np.ndarray]:
    return [etf.render_canvas(face, g) for g in sorted(face.glyphs, key=lambda g: g.code)]


# --- tests -----------------------------------------------------------------------------------


class RoundTrip(unittest.TestCase):
    def check(self, gen, encoding=None, crop=True):
        face = make_face(gen, encoding, crop)
        out = etf.read_face(etf.write_face(face))
        for d, canvas in enumerate(canvases(out)):
            np.testing.assert_array_equal(canvas, gen(d).astype(np.uint16),
                                          err_msg=f"digit {d}")
        return out

    def test_auto_encoding_all_images(self):
        for name, gen in IMAGES.items():
            with self.subTest(image=name):
                self.check(gen)

    def test_every_encoding_forced(self):
        for enc, ename in etf.ENC_NAMES.items():
            for name, gen in IMAGES.items():
                if enc in (etf.PAL8_RLE, etf.DEFLATE_PAL8) and len(np.unique(gen(0))) > 256:
                    continue  # palette encodings need <= 256 colours
                with self.subTest(encoding=ename, image=name):
                    out = self.check(gen, enc, crop=False)
                    self.assertTrue(all(g.encoding == enc for g in out.glyphs))

    def test_palette_rejects_too_many_colours(self):
        with self.assertRaises(etf.EtfError):
            etf.encode_glyph(img_noise(0), etf.PAL8_RLE)

    def test_crop_keeps_details(self):
        out = self.check(img_details)
        g = out.glyphs[0]
        self.assertLess(g.w * g.h, W * H, "uniform border should be cropped")

    def test_rle_packets_do_not_cross_rows(self):
        px = np.full((3, 200), 0x0001, np.uint16)  # 200 > 128: needs two runs per row
        data = etf._rle_rows(px, 2)
        self.assertEqual(len(data), 3 * 2 * 3)  # per row: two run packets of 3 bytes

    def test_deflate_window_limit(self):
        # repeated pattern with period 6000 bytes: only matches > 4096 would help
        rng = np.random.default_rng(1)
        block = rng.integers(0, 0x10000, 3000, dtype=np.uint16)
        px = np.tile(block, 10)[: 135 * 200].reshape(200, 135)
        data = etf.encode_glyph(px, etf.DEFLATE565)[etf.DEFLATE565]
        self.assertGreater(len(data), 0.9 * px.size * 2, "encoder must not use far matches")
        d = zlib.decompressobj(-etf.DEFLATE_WBITS)  # decoder with a 4 KB window must work
        self.assertEqual(d.decompress(data), etf.be16(px.reshape(-1)))

    def test_pixel_byte_order_is_big_endian(self):
        g = etf.encode_glyph(np.array([[0xF800]], np.uint16), etf.RAW565)[etf.RAW565]
        self.assertEqual(g, b"\xf8\x00")

    def test_metadata_and_alignment(self):
        face = make_face(img_few_colours)
        buf = etf.write_face(face)
        out = etf.read_face(buf)
        self.assertEqual(out.meta, {"name": "test", "license": "CC0-1.0"})
        for i in range(10):
            doff = struct.unpack_from("<I", buf, 32 + i * 32 + 20)[0]
            self.assertEqual(doff % 4, 0)


class Corruption(unittest.TestCase):
    """A corrupt file must raise EtfError - never another exception, never garbage."""

    @classmethod
    def setUpClass(cls):
        faces = [make_face(img_few_colours), make_face(img_gradient, etf.RLE565, crop=False),
                 make_face(img_noise, etf.DEFLATE565), make_face(img_details, etf.PAL8_RLE)]
        cls.files = [etf.write_face(f) for f in faces]

    def expect_error(self, buf, verify_crc=True):
        with self.assertRaises(etf.EtfError):
            etf.read_face(buf, verify_crc)

    def test_truncated(self):
        for buf in self.files:
            for n in (0, 10, 31, 32, 100, 320, len(buf) // 2, len(buf) - 1):
                with self.subTest(n=n):
                    self.expect_error(buf[:n])

    def test_bad_magic_and_version(self):
        buf = bytearray(self.files[0])
        buf[0] = ord("X")
        self.expect_error(bytes(buf))
        buf = bytearray(self.files[0])
        buf[4] = 2
        self.expect_error(bytes(buf))

    def test_random_bit_flips_detected_by_crc(self):
        rng = random.Random(42)
        for buf in self.files:
            for _ in range(60):
                b = bytearray(buf)
                pos = rng.randrange(len(b))
                b[pos] ^= 1 << rng.randrange(8)
                try:
                    etf.read_face(bytes(b))
                except etf.EtfError:
                    continue
                # only padding bytes may change without detection
                self.assertTrue(self._is_padding(buf, pos), f"undetected flip at {pos}")

    def test_random_flips_without_crc_never_crash(self):
        """With CRC checks off, the decoder's own bounds checks must still hold."""
        rng = random.Random(7)
        for buf in self.files:
            count = struct.unpack_from("<H", buf, 12)[0]
            data_start = min(struct.unpack_from("<I", buf, 32 + i * 32 + 20)[0]
                             for i in range(count))
            for _ in range(60):
                b = bytearray(buf)
                for _ in range(rng.randrange(1, 4)):  # corrupt pixel streams only
                    b[rng.randrange(data_start, len(b))] = rng.randrange(256)
                try:
                    etf.read_face(bytes(b), verify_crc=False)
                except etf.EtfError:
                    pass

    def test_missing_digit(self):
        face = make_face(img_solid)
        face.glyphs = face.glyphs[:9]
        self.expect_error(etf.write_face(face))

    @staticmethod
    def _is_padding(buf: bytes, pos: int) -> bool:
        count = struct.unpack_from("<H", buf, 12)[0]
        moff, msize = struct.unpack_from("<II", buf, 20)
        used = [(0, 32 + 32 * count)]
        if moff:
            used.append((moff, moff + msize))
        for i in range(count):
            doff, dsize = struct.unpack_from("<II", buf, 32 + i * 32 + 20)
            used.append((doff, doff + dsize))
        return not any(a <= pos < b for a, b in used)


class Cli(unittest.TestCase):
    def test_encode_info_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            for d in range(10):
                Image.fromarray(etf.rgb565_to_rgb(img_details(d)), "RGB").save(src / f"{d}.png")
            Image.fromarray(etf.rgb565_to_rgb(img_solid(0)), "RGB").save(src / "colon.png")
            out = Path(tmp) / "face.etf"
            self.assertEqual(etf.main(["encode", str(src), "-o", str(out), "-q",
                                       "--name", "cli", "--license", "CC0-1.0"]), 0)
            face = etf.read_face(out.read_bytes())
            self.assertEqual(len(face.glyphs), 11)
            self.assertEqual(etf.main(["decode", str(out), "-o", str(Path(tmp) / "dec")]), 0)
            back = np.asarray(Image.open(Path(tmp) / "dec" / "7.png").convert("RGB"))
            np.testing.assert_array_equal(etf.rgb_to_565(back), img_details(7))

    def test_missing_digits_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            Image.new("RGB", (W, H)).save(Path(tmp) / "0.png")
            self.assertEqual(etf.main(["encode", tmp, "-o", str(Path(tmp) / "x.etf"), "-q"]), 1)


if __name__ == "__main__":
    unittest.main()


class Fixtures(unittest.TestCase):
    """Shared fixtures for the C decoder (test/host/fixtures) must be current and agree with the
    Python reference."""

    DIR = Path(__file__).resolve().parents[2] / "test" / "host" / "fixtures"

    def test_fixtures_up_to_date(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(self.DIR / "generate.py"), tmp], check=True)
            fresh = sorted(p.name for p in Path(tmp).iterdir())
            committed = sorted(p.name for p in self.DIR.iterdir()
                               if p.suffix in (".etf", ".expect", ".txt"))
            self.assertEqual(fresh, committed, "run test/host/fixtures/generate.py")
            for name in fresh:
                new, old = (Path(tmp) / name).read_bytes(), (self.DIR / name).read_bytes()
                if new == old:
                    continue
                # DEFLATE output differs between zlib implementations (CPython on Windows ships
                # zlib-ng): .etf files must then still be equivalent, pixel data and manifest
                # must match exactly.
                self.assertTrue(name.endswith(".etf"),
                                f"{name} outdated - run test/host/fixtures/generate.py")
                self.assertEqual(self._digest(new), self._digest(old),
                                 f"{name} outdated - run test/host/fixtures/generate.py")

    @staticmethod
    def _digest(buf: bytes):
        """Outcome and decoded pixels of an .etf file, independent of the DEFLATE byte stream."""
        try:
            face = etf.read_face(buf)
        except etf.EtfError as ex:
            try:
                face = etf.read_face(buf, verify_crc=False)
                return ("crc_error",)
            except etf.EtfError:
                return ("error", str(ex).split(":")[0])
        return ("ok", face.canvas_w, face.canvas_h, tuple(
            (g.code, g.x, g.y, g.w, g.h, g.encoding, g.bg_color, g.pixels.tobytes())
            for g in face.glyphs))

    def test_python_reference_agrees_with_manifest(self):
        for line in (self.DIR / "manifest.txt").read_text(encoding="utf-8").splitlines():
            name, outcome = line.split()
            buf = (self.DIR / f"{name}.etf").read_bytes()
            with self.subTest(fixture=name, expected=outcome):
                if outcome == "ok":
                    face = etf.read_face(buf)
                    got = b"".join(etf.be16(etf.render_canvas(face, g).reshape(-1))
                                   for g in face.glyphs)
                    self.assertEqual(got, (self.DIR / f"{name}.expect").read_bytes())
                else:
                    with self.assertRaises(etf.EtfError):
                        etf.read_face(buf)
