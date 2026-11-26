# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the clock-face generator (tools/facegen) and the embedded fallback faces.

Run: python -m unittest discover -s test/tools -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "facegen"))
sys.path.insert(0, str(ROOT / "tools" / "etf"))
import etf  # noqa: E402
import facegen  # noqa: E402


class Facegen(unittest.TestCase):
    def test_render_writes_digits_and_blank(self):
        with tempfile.TemporaryDirectory() as tmp:
            facegen.render_style("minimal", Path(tmp), (80, 160))
            names = sorted(p.stem for p in Path(tmp).iterdir())
            self.assertEqual(names, sorted([str(d) for d in range(10)] + ["blank"]))

    def test_every_face_encodes_in_every_size(self):
        for name in facegen.FACES:
            for size in facegen.SIZES:
                with self.subTest(face=name, size=size):
                    data, _totals, count = facegen.encode_face(name, size)
                    face = etf.read_face(data)
                    self.assertEqual((face.canvas_w, face.canvas_h), size)
                    self.assertEqual(count, 11)
                    self.assertEqual(face.meta["license"], "CC0-1.0")

    def test_embedded_fallback_faces_up_to_date(self):
        """components/faces/*.etf must match the generator; refresh with
        python tools/facegen/facegen.py build -o out/faces --update-fallback"""
        for size in facegen.SIZES:
            path = facegen.FALLBACK_DIR / f"fallback_{size[0]}x{size[1]}.etf"
            with self.subTest(file=path.name):
                fresh, _totals, _count = facegen.encode_face(facegen.FALLBACK_FACE, size)
                self.assertEqual(etf.face_digest(fresh), etf.face_digest(path.read_bytes()),
                                 f"{path.name} outdated - run facegen.py build --update-fallback")


if __name__ == "__main__":
    unittest.main()
