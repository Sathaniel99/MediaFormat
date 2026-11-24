from __future__ import annotations

import unittest

from app.models import ConflictPolicy, ConversionOptions, JobStatus, OutputFormat


class ModelsTest(unittest.TestCase):
    def test_extension_mapping(self) -> None:
        self.assertEqual(OutputFormat.JPEG.extension, ".jpg")
        self.assertEqual(OutputFormat.TIFF.extension, ".tiff")
        self.assertEqual(OutputFormat.WEBP.extension, ".webp")

    def test_capabilities(self) -> None:
        self.assertTrue(OutputFormat.JPEG.supports_quality)
        self.assertFalse(OutputFormat.JPEG.supports_alpha)
        self.assertTrue(OutputFormat.PNG.supports_alpha)
        self.assertTrue(OutputFormat.WEBP.supports_animation)

    def test_from_value_accepts_enum_and_string(self) -> None:
        self.assertIs(OutputFormat.from_value(OutputFormat.PNG), OutputFormat.PNG)
        self.assertIs(OutputFormat.from_value("webp"), OutputFormat.WEBP)
        self.assertIs(OutputFormat.from_value("basura", OutputFormat.JPEG), OutputFormat.JPEG)

    def test_normalized_keeps_enum_format_and_clamps(self) -> None:
        raw = ConversionOptions(
            output_format=OutputFormat.AVIF,
            quality=999,
            png_compress_level=42,
            background=(-5, 300, 128),
            jpeg_subsampling="nope",
            on_conflict=ConflictPolicy.SKIP,
        ).normalized()

        self.assertIs(raw.output_format, OutputFormat.AVIF)
        self.assertEqual(raw.quality, 100)
        self.assertEqual(raw.png_compress_level, 9)
        self.assertEqual(raw.background, (0, 255, 128))
        self.assertEqual(raw.jpeg_subsampling, "4:2:0")
        self.assertIs(raw.on_conflict, ConflictPolicy.SKIP)

    def test_normalized_tolerates_invalid_types(self) -> None:
        raw = ConversionOptions(
            output_format="no-es-un-formato",  # type: ignore[arg-type]
            quality="abc",  # type: ignore[arg-type]
            png_compress_level=None,  # type: ignore[arg-type]
            background="rojo",  # type: ignore[arg-type]
            jpeg_subsampling=None,  # type: ignore[arg-type]
            on_conflict="explode",  # type: ignore[arg-type]
        ).normalized()

        self.assertIs(raw.output_format, OutputFormat.WEBP)
        self.assertEqual(raw.quality, 90)
        self.assertEqual(raw.png_compress_level, 6)
        self.assertEqual(raw.background, (255, 255, 255))
        self.assertEqual(raw.jpeg_subsampling, "4:2:0")
        self.assertIs(raw.on_conflict, ConflictPolicy.RENAME)

    def test_result_ok_flag(self) -> None:
        from pathlib import Path

        from app.models import ConversionResult

        self.assertTrue(ConversionResult(Path("a.png"), JobStatus.DONE).ok)
        self.assertTrue(ConversionResult(Path("a.png"), JobStatus.SKIPPED).ok)
        self.assertFalse(ConversionResult(Path("a.png"), JobStatus.ERROR).ok)


if __name__ == "__main__":
    unittest.main()
