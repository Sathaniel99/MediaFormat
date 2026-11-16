from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.config import Config, default_values
from app.models import ConflictPolicy, OutputFormat


class ConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.path = self.root / "config.ini"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_file_is_created_with_defaults(self) -> None:
        config = Config(self.path)
        self.assertTrue(self.path.exists())
        self.assertEqual(config.warnings, [])
        self.assertEqual(config.theme, "system")
        self.assertEqual(config.accent, "blue")
        self.assertEqual(config.default_format, OutputFormat.WEBP)
        self.assertEqual(config.jpeg_quality, 95)
        self.assertEqual(config.output_folder.name, "MediaFormat")

    def test_accent_is_normalized_on_write(self) -> None:
        config = Config(self.path)
        config.accent = "neon"
        self.assertEqual(config.accent, "blue")
        config.accent = "PINK"
        self.assertEqual(config.accent, "pink")
        config.save()
        self.assertIn("accent = pink", self.path.read_text(encoding="utf-8"))

    def test_roundtrip(self) -> None:
        config = Config(self.path)
        config.theme = "dark"
        config.accent = "green"
        config.output_folder = self.root / "salida"
        config.default_format = OutputFormat.AVIF
        config.webp_quality = 77
        config.on_conflict = ConflictPolicy.SKIP
        config.save()

        reloaded = Config(self.path)
        self.assertEqual(reloaded.theme, "dark")
        self.assertEqual(reloaded.accent, "green")
        self.assertEqual(reloaded.output_folder, self.root / "salida")
        self.assertEqual(reloaded.default_format, OutputFormat.AVIF)
        self.assertEqual(reloaded.webp_quality, 77)
        self.assertEqual(reloaded.on_conflict, ConflictPolicy.SKIP)

    def test_hex_color_is_not_treated_as_comment(self) -> None:
        config = Config(self.path)
        self.assertEqual(config.jpeg_background, (255, 255, 255))
        config.jpeg_background = (10, 11, 12)
        config.save()
        self.assertIn("background = #0A0B0C", self.path.read_text(encoding="utf-8"))
        self.assertEqual(Config(self.path).jpeg_background, (10, 11, 12))

    def test_corrupt_file_is_backed_up(self) -> None:
        self.path.write_text("theme = dark\n", encoding="utf-8")
        config = Config(self.path)
        self.assertTrue(config.warnings)
        self.assertTrue(self.path.with_suffix(".ini.bak").exists())
        self.assertEqual(config.theme, "system")

    def test_invalid_values_are_repaired(self) -> None:
        self.path.write_text(
            "\n".join(
                [
                    "[app]",
                    "theme = neon",
                    "accent = neon",
                    "[format]",
                    "default = NOPE",
                    "[jpeg]",
                    "quality = 500",
                    "[processing]",
                    "max_workers = abc",
                    "[output]",
                    "on_conflict = explode",
                ]
            ),
            encoding="utf-8",
        )
        config = Config(self.path)
        self.assertEqual(config.theme, "system")
        self.assertEqual(config.accent, "blue")
        self.assertEqual(config.default_format, OutputFormat.WEBP)
        self.assertEqual(config.jpeg_quality, 100)
        self.assertEqual(config.max_workers, 4)
        self.assertEqual(config.on_conflict, ConflictPolicy.RENAME)
        self.assertGreaterEqual(len(config.warnings), 4)

    def test_environment_variable_in_output_folder(self) -> None:
        os.environ["MF_TEST_OUT"] = str(self.root / "convertidas")
        try:
            self.path.write_text("[output]\nfolder = %MF_TEST_OUT%\n", encoding="utf-8")
            config = Config(self.path)
            self.assertEqual(config.output_folder, self.root / "convertidas")
        finally:
            os.environ.pop("MF_TEST_OUT", None)

    def test_conversion_options_follow_format(self) -> None:
        config = Config(self.path)
        jpeg = config.conversion_options(OutputFormat.JPEG)
        self.assertEqual(jpeg.output_format, OutputFormat.JPEG)
        self.assertEqual(jpeg.quality, config.jpeg_quality)
        self.assertEqual(jpeg.background, config.jpeg_background)

        webp = config.conversion_options(OutputFormat.WEBP)
        self.assertEqual(webp.output_format, OutputFormat.WEBP)
        self.assertEqual(webp.quality, config.webp_quality)

        clamped = config.conversion_options(OutputFormat.PNG, quality=999)
        self.assertEqual(clamped.quality, 100)
        self.assertEqual(clamped.output_format, OutputFormat.PNG)

    def test_default_template_contains_every_section(self) -> None:
        rendered = Config(self.path).render()
        for section in default_values():
            self.assertIn(f"[{section}]", rendered)
        self.assertIn("language = es", rendered)
        self.assertIn("[profiles]", rendered)

    def test_new_app_defaults(self) -> None:
        config = Config(self.path)
        self.assertEqual(config.language, "es")
        self.assertTrue(config.notify_on_finish)
        self.assertTrue(config.restore_queue)
        self.assertIsNone(config.window_position)
        self.assertFalse(config.window_maximized)
        self.assertEqual(config.window_geometry, "")
        self.assertEqual(config.profiles_raw, {})

    def test_system_is_a_valid_accent(self) -> None:
        config = Config(self.path)
        config.accent = "system"
        config.save()
        self.assertEqual(Config(self.path).accent, "system")

    def test_language_is_validated(self) -> None:
        config = Config(self.path)
        config.language = "fr"
        self.assertEqual(config.language, "es")
        config.language = "EN"
        self.assertEqual(config.language, "en")
        config.save()
        self.assertEqual(Config(self.path).language, "en")

    def test_window_position_and_maximized_roundtrip(self) -> None:
        config = Config(self.path)
        config.window_position = (120, 80)
        config.window_maximized = True
        config.save()

        reloaded = Config(self.path)
        self.assertEqual(reloaded.window_position, (120, 80))
        self.assertTrue(reloaded.window_maximized)

    def test_invalid_window_position_is_repaired(self) -> None:
        self.path.write_text("[ui]\nwindow_x = abc\nwindow_y = 20\n", encoding="utf-8")
        config = Config(self.path)
        self.assertIsNone(config.window_position)
        self.assertTrue(any("window_x" in warning for warning in config.warnings))

    def test_custom_profiles_roundtrip(self) -> None:
        config = Config(self.path)
        config.set_profile("mi-perfil", '{"output_format": "PNG", "quality": 88}')
        config.save()

        reloaded = Config(self.path)
        self.assertIn("mi-perfil", reloaded.profiles_raw)
        self.assertIn('"quality": 88', reloaded.profiles_raw["mi-perfil"])
        reloaded.remove_profile("mi-perfil")
        self.assertNotIn("mi-perfil", reloaded.profiles_raw)

    def test_save_is_atomic_and_leaves_no_temp_file(self) -> None:
        config = Config(self.path)
        config.theme = "light"
        config.save()
        self.assertFalse(self.path.with_suffix(".ini.tmp").exists())


if __name__ == "__main__":
    unittest.main()
