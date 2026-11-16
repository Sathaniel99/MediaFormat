"""Pruebas de los recursos de build: icono definitivo y metadatos del .exe."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image
from scripts.make_icon import ICON_SIZES, draw_icon, write_icon
from scripts.make_version_info import build_version_info, current_version, parse_version

ROOT = Path(__file__).resolve().parent.parent


class IconAssetTest(unittest.TestCase):
    def test_committed_icon_is_multi_size(self) -> None:
        path = ROOT / "resources" / "icon.ico"
        self.assertTrue(path.is_file(), "falta resources/icon.ico")
        with Image.open(path) as image:
            self.assertEqual(image.format, "ICO")
            sizes = set(image.ico.sizes())
        self.assertIn((256, 256), sizes)
        self.assertIn((16, 16), sizes)
        self.assertIn((32, 32), sizes)

    def test_drawn_icon_has_transparent_corners(self) -> None:
        icon = draw_icon(128).convert("RGBA")
        self.assertEqual(icon.size, (128, 128))
        self.assertEqual(icon.getpixel((1, 1))[3], 0)
        # El centro lleva el detalle (sol, montanas); el remuestreo suaviza el
        # alfa, asi que se exige opaco, no un valor exacto.
        self.assertGreaterEqual(icon.getpixel((64, 64))[3], 200)

    def test_write_icon_regenerates_the_same_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = write_icon(Path(tmp) / "icon.ico")
            with Image.open(target) as image:
                self.assertEqual(set(image.ico.sizes()), set(ICON_SIZES))


class VersionInfoTest(unittest.TestCase):
    def test_version_is_split_into_numeric_tuple(self) -> None:
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version(" 0.1.1 "), (0, 1, 1))

    def test_current_version_is_read_from_the_source(self) -> None:
        version = current_version()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertIn(f"filevers=({', '.join(version.split('.'))}, 0)", build_version_info())

    def test_invalid_version_is_rejected(self) -> None:
        for value in ("1.2", "1.2.x", "", "1.2.3.4"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_version(value)

    def test_rendered_metadata_contains_version_and_app(self) -> None:
        text = build_version_info("1.2.3")
        self.assertIn("filevers=(1, 2, 3, 0)", text)
        self.assertIn("prodvers=(1, 2, 3, 0)", text)
        self.assertIn("'ProductVersion', '1.2.3'", text)
        self.assertIn("'ProductName', 'MediaFormat'", text)


if __name__ == "__main__":
    unittest.main()
