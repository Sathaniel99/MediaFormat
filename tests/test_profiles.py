"""Pruebas de los perfiles de conversión (integrados y personalizados)."""

from __future__ import annotations

import unittest

from app.models import OutputFormat
from app.profiles import (
    BUILTIN_PROFILES,
    Profile,
    all_profiles,
    custom_profile_key,
    profile_from_json,
    profile_label,
    profile_to_json,
    slugify,
)


class BuiltinProfilesTest(unittest.TestCase):
    def test_expected_builtin_keys(self) -> None:
        keys = [profile.key for profile in BUILTIN_PROFILES]
        self.assertEqual(keys, ["web", "print", "social", "chat"])
        self.assertTrue(all(profile.builtin for profile in BUILTIN_PROFILES))

    def test_print_profile_is_lossless_ready(self) -> None:
        print_profile = next(profile for profile in BUILTIN_PROFILES if profile.key == "print")
        self.assertEqual(print_profile.output_format, OutputFormat.PNG)
        self.assertEqual(print_profile.png_compress_level, 9)
        self.assertEqual(print_profile.jpeg_subsampling, "4:4:4")

    def test_labels_are_translated(self) -> None:
        profile = BUILTIN_PROFILES[0]
        self.assertEqual(profile_label(profile, lambda key: f"<{key}>"), "<profile.builtin.web>")


class CustomProfilesTest(unittest.TestCase):
    def test_slugify(self) -> None:
        self.assertEqual(slugify("Mi Perfil Web"), "mi-perfil-web")
        self.assertEqual(slugify("  --  "), "perfil")

    def test_custom_key_avoids_collisions(self) -> None:
        self.assertEqual(custom_profile_key("web", {"web"}), "web-2")
        self.assertEqual(custom_profile_key("web", {"web", "web-2"}), "web-3")

    def test_json_roundtrip(self) -> None:
        original = Profile(
            key="mi-perfil",
            label_key="profile.custom.Mi perfil",
            output_format=OutputFormat.JPEG,
            quality=81,
            jpeg_subsampling="4:4:4",
            builtin=False,
        )
        restored = profile_from_json("mi-perfil", profile_to_json(original))
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.output_format, OutputFormat.JPEG)
        self.assertEqual(restored.quality, 81)
        self.assertEqual(restored.jpeg_subsampling, "4:4:4")
        self.assertFalse(restored.builtin)
        self.assertEqual(profile_label(restored), "Mi perfil")

    def test_invalid_json_is_ignored(self) -> None:
        self.assertIsNone(profile_from_json("roto", "no es json"))
        self.assertIsNone(profile_from_json("lista", "[1, 2]"))

    def test_out_of_range_values_are_clamped(self) -> None:
        restored = profile_from_json(
            "raro",
            '{"output_format": "WEBP", "quality": 900, "png_compress_level": -4}',
        )
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.quality, 100)
        self.assertEqual(restored.png_compress_level, 0)

    def test_all_profiles_appends_valid_custom_entries(self) -> None:
        raw = {
            "custom-a": '{"output_format": "PNG", "quality": 70}',
            "custom-b": "roto",
        }
        profiles = all_profiles(raw)
        self.assertEqual(len(profiles), len(BUILTIN_PROFILES) + 1)
        self.assertEqual(profiles[-1].key, "custom-a")


if __name__ == "__main__":
    unittest.main()
