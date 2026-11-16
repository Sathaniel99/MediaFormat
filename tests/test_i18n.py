"""Pruebas del sistema de traducciones español/inglés."""

from __future__ import annotations

import unittest

from app.i18n import (
    _EN,
    _ES,
    DEFAULT_LANGUAGE,
    LANGUAGES,
    current_language,
    set_language,
    tr,
)


class I18nTest(unittest.TestCase):
    def tearDown(self) -> None:
        set_language(DEFAULT_LANGUAGE)

    def test_default_language_is_spanish(self) -> None:
        set_language("es")
        self.assertEqual(current_language(), "es")
        self.assertEqual(tr("button.convert"), "Convertir")

    def test_english_translation(self) -> None:
        set_language("en")
        self.assertEqual(current_language(), "en")
        self.assertEqual(tr("button.convert"), "Convert")

    def test_unknown_language_falls_back_to_spanish(self) -> None:
        self.assertEqual(set_language("fr"), "es")
        self.assertEqual(current_language(), "es")

    def test_placeholders_are_replaced(self) -> None:
        set_language("es")
        self.assertEqual(tr("status.images", count=3, size="1.2 MB"), "3 imágenes · 1.2 MB")

    def test_unknown_key_returns_the_key(self) -> None:
        self.assertEqual(tr("no.existe"), "no.existe")

    def test_missing_placeholder_does_not_raise(self) -> None:
        self.assertEqual(tr("status.images", count=2), "2 imágenes · {size}")

    def test_both_dictionaries_have_the_same_keys(self) -> None:
        self.assertEqual(set(_ES), set(_EN))
        for source in (_ES, _EN):
            for key, value in source.items():
                if key == "header.preview":
                    self.assertEqual(value, "")
                    continue
                self.assertTrue(value, f"traducción vacía: {key}")

    def test_every_supported_language_has_a_dictionary(self) -> None:
        for language in LANGUAGES:
            with self.subTest(language=language):
                set_language(language)
                self.assertTrue(tr("settings.title"))


if __name__ == "__main__":
    unittest.main()
