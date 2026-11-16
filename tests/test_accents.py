"""Pruebas del selector de acento: normalizacion y paletas por tema."""

from __future__ import annotations

import unittest
from unittest import mock

from app.accents import (
    ACCENT_CHOICES,
    ACCENT_LABELS,
    ACCENT_NAMES,
    DEFAULT_ACCENT,
    _nearest_accent,
    normalize_accent,
    resolve_accent,
)
from app.ui.theme import build_stylesheet, resolve_colors


class AccentNamesTest(unittest.TestCase):
    def test_every_accent_has_a_spanish_label(self) -> None:
        self.assertEqual(set(ACCENT_LABELS), set(ACCENT_CHOICES))
        self.assertTrue(all(ACCENT_LABELS[name].strip() for name in ACCENT_CHOICES))
        self.assertIn("system", ACCENT_CHOICES)

    def test_system_is_accepted_but_not_a_palette(self) -> None:
        self.assertEqual(normalize_accent("system"), "system")
        self.assertNotIn("system", ACCENT_NAMES)

    def test_default_is_blue(self) -> None:
        self.assertEqual(DEFAULT_ACCENT, "blue")
        self.assertIn(DEFAULT_ACCENT, ACCENT_NAMES)

    def test_normalize_accepts_known_names_case_insensitively(self) -> None:
        for name in ACCENT_NAMES:
            with self.subTest(name=name):
                self.assertEqual(normalize_accent(name.upper()), name)
                self.assertEqual(normalize_accent(f"  {name}  "), name)

    def test_normalize_falls_back_to_blue(self) -> None:
        for value in ("", "neon", None, 42, "rojo"):
            with self.subTest(value=value):
                self.assertEqual(normalize_accent(value), DEFAULT_ACCENT)


class AccentPaletteTest(unittest.TestCase):
    def test_system_resolves_to_the_detected_accent(self) -> None:
        with mock.patch("app.accents.system_accent", return_value="green"):
            self.assertEqual(resolve_accent("system"), "green")

    def test_system_resolution_falls_back_to_blue_when_unknown(self) -> None:
        with mock.patch("app.accents._read_windows_colorization", return_value=None):
            self.assertEqual(resolve_accent("system"), DEFAULT_ACCENT)

    def test_nearest_accent_maps_windows_blue(self) -> None:
        self.assertEqual(_nearest_accent(0x00, 0x67, 0xC0), "blue")

    def test_light_and_dark_use_different_accent_tones(self) -> None:
        for name in ACCENT_NAMES:
            with self.subTest(name=name):
                light = resolve_colors("light", name)
                dark = resolve_colors("dark", name)
                self.assertFalse(light.dark)
                self.assertTrue(dark.dark)
                self.assertNotEqual(light.accent, dark.accent)

    def test_accent_changes_button_and_selection_colors(self) -> None:
        blue = resolve_colors("light", "blue")
        red = resolve_colors("light", "red")
        self.assertNotEqual(blue.accent, red.accent)
        self.assertNotEqual(blue.selection, red.selection)
        self.assertNotEqual(blue.accent_soft, red.accent_soft)

    def test_invalid_accent_falls_back_to_blue(self) -> None:
        self.assertEqual(
            resolve_colors("dark", "neon").accent,
            resolve_colors("dark", "blue").accent,
        )

    def test_stylesheet_embeds_the_chosen_accent(self) -> None:
        colors = resolve_colors("light", "purple")
        stylesheet = build_stylesheet(colors)
        self.assertIn(colors.accent, stylesheet)
        self.assertIn(colors.selection, stylesheet)


if __name__ == "__main__":
    unittest.main()
