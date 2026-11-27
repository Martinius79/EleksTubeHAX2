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
        for name in facegen.PRESETS:
            for size in facegen.SIZES:
                with self.subTest(face=name, size=size):
                    data, _totals, count = facegen.encode_face(name, size)
                    face = etf.read_face(data)
                    self.assertEqual((face.canvas_w, face.canvas_h), size)
                    self.assertEqual(count, 11)
                    self.assertEqual(face.meta["license"], "CC0-1.0")

    def test_presets_reference_existing_styles_and_params(self):
        for name, (style, params, title) in facegen.PRESETS.items():
            with self.subTest(preset=name):
                self.assertIn(style, facegen.STYLES)
                self.assertTrue(title)
                for key in params:
                    self.assertIn(key, facegen.STYLES[style].PARAMS)

    def test_set_overrides_are_typed_and_checked(self):
        style, params = facegen.resolve("minimal", {"color": "#102030", "stroke": "3.5"})
        self.assertEqual(style, "minimal")
        self.assertEqual(params["color"], (0x10, 0x20, 0x30))
        self.assertEqual(params["stroke"], 3.5)
        _, params = facegen.resolve("sevenseg", {"lcd": "true"})
        self.assertIs(params["lcd"], True)
        with self.assertRaises(ValueError):
            facegen.resolve("minimal", {"no_such_param": "1"})
        with self.assertRaises(ValueError):
            facegen.resolve("minimal", {"color": "#12"})
        with self.assertRaises(ValueError):
            facegen.resolve("no_such_preset")

    def test_override_changes_pixels(self):
        base = facegen.STYLES["minimal"].render(8, (80, 160))
        _, params = facegen.resolve("minimal", {"color": "#00ff00"})
        green = facegen.STYLES["minimal"].render(8, (80, 160), **params)
        self.assertNotEqual(base.tobytes(), green.tobytes())

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
