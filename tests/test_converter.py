from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.converter import (
    BatchConverter,
    available_formats,
    build_output_path,
    collect_sources,
    convert_file,
)
from app.models import (
    BatchProgress,
    ConflictPolicy,
    ConversionOptions,
    JobStatus,
    OutputFormat,
)
from PIL import Image


class ConverterTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.inbox = self.root / "in"
        self.outbox = self.root / "out"
        self.inbox.mkdir()
        self.outbox.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ------------------------------------------------------------- fixtures
    def make_image(
        self,
        name: str = "image.png",
        size: tuple[int, int] = (64, 48),
        mode: str = "RGB",
        color: tuple[int, ...] = (200, 30, 30),
    ) -> Path:
        path = self.inbox / name
        Image.new(mode, size, color).save(path)
        return path

    def options(self, fmt: OutputFormat = OutputFormat.WEBP, **kwargs: object) -> ConversionOptions:
        return ConversionOptions(output_format=fmt, **kwargs).normalized()  # type: ignore[arg-type]

    # ---------------------------------------------------------------- tests
    def test_available_formats_contains_core_formats(self) -> None:
        formats = available_formats()
        for expected in (OutputFormat.JPEG, OutputFormat.PNG, OutputFormat.WEBP, OutputFormat.TIFF):
            self.assertIn(expected, formats)

    def test_collect_sources_expands_folders_and_skips_noise(self) -> None:
        nested = self.inbox / "sub"
        nested.mkdir()
        self.make_image("a.png")
        self.make_image("sub/b.jpg")
        (self.inbox / "notas.txt").write_text("hola", encoding="utf-8")

        collected = collect_sources([self.inbox, self.inbox / "a.png"])

        names = sorted(path.name for path in collected)
        self.assertEqual(names, ["a.png", "b.jpg"])

    def test_convert_png_to_webp(self) -> None:
        source = self.make_image()
        result = convert_file(source, self.outbox, self.options(OutputFormat.WEBP))

        self.assertEqual(result.status, JobStatus.DONE, result.error)
        self.assertIsNotNone(result.output)
        assert result.output is not None
        self.assertTrue(result.output.exists())
        self.assertGreater(result.size_out, 0)
        with Image.open(result.output) as converted:
            self.assertEqual(converted.format, "WEBP")

    def test_alpha_is_flattened_for_jpeg(self) -> None:
        source = self.inbox / "alpha.png"
        Image.new("RGBA", (64, 48), (255, 0, 0, 128)).save(source)

        result = convert_file(source, self.outbox, self.options(OutputFormat.JPEG))

        self.assertEqual(result.status, JobStatus.DONE, result.error)
        with Image.open(result.output) as converted:  # type: ignore[arg-type]
            self.assertEqual(converted.mode, "RGB")
            red, green, blue = converted.getpixel((32, 24))
        self.assertEqual(red, 255)
        self.assertTrue(100 <= green <= 155, green)
        self.assertTrue(100 <= blue <= 155, blue)

    def test_exif_orientation_is_applied(self) -> None:
        source = self.inbox / "rotada.jpg"
        image = Image.new("RGB", (10, 20), (0, 128, 0))
        exif = Image.Exif()
        exif[0x0112] = 6  # rotate 90 CW
        image.save(source, "JPEG", exif=exif)

        result = convert_file(source, self.outbox, self.options(OutputFormat.PNG))

        self.assertEqual(result.status, JobStatus.DONE, result.error)
        with Image.open(result.output) as converted:  # type: ignore[arg-type]
            self.assertEqual(converted.size, (20, 10))

    def test_orientation_can_be_disabled(self) -> None:
        source = self.inbox / "rotada.jpg"
        image = Image.new("RGB", (10, 20), (0, 128, 0))
        exif = Image.Exif()
        exif[0x0112] = 6
        image.save(source, "JPEG", exif=exif)

        options = self.options(OutputFormat.PNG, apply_exif_orientation=False)
        result = convert_file(source, self.outbox, options)

        with Image.open(result.output) as converted:  # type: ignore[arg-type]
            self.assertEqual(converted.size, (10, 20))

    def test_conflict_rename(self) -> None:
        source = self.make_image()
        first = convert_file(source, self.outbox, self.options(OutputFormat.PNG))
        second = convert_file(source, self.outbox, self.options(OutputFormat.PNG))

        self.assertEqual(first.output.name, "image.png")
        self.assertEqual(second.output.name, "image_1.png")
        self.assertEqual(second.status, JobStatus.DONE)

    def test_conflict_skip(self) -> None:
        source = self.make_image()
        options = self.options(OutputFormat.PNG, on_conflict=ConflictPolicy.SKIP)
        convert_file(source, self.outbox, options)
        second = convert_file(source, self.outbox, options)

        self.assertEqual(second.status, JobStatus.SKIPPED)
        self.assertEqual(second.output.name, "image.png")

    def test_conflict_overwrite(self) -> None:
        source = self.make_image()
        options = self.options(OutputFormat.PNG, on_conflict=ConflictPolicy.OVERWRITE)
        first = convert_file(source, self.outbox, options)
        second = convert_file(source, self.outbox, options)

        self.assertEqual(second.status, JobStatus.DONE)
        self.assertEqual(first.output, second.output)

    def test_same_format_same_folder_does_not_overwrite_source(self) -> None:
        source = self.make_image("misma.png")
        before = source.read_bytes()

        result = convert_file(source, self.inbox, self.options(OutputFormat.PNG))

        self.assertEqual(result.status, JobStatus.DONE, result.error)
        self.assertNotEqual(result.output, source)
        self.assertEqual(source.read_bytes(), before)
        self.assertTrue((self.inbox / "misma_converted.png").exists())

    def test_invalid_file_returns_error(self) -> None:
        source = self.inbox / "falsa.png"
        source.write_text("esto no es una imagen", encoding="utf-8")

        result = convert_file(source, self.outbox, self.options(OutputFormat.WEBP))

        self.assertEqual(result.status, JobStatus.ERROR)
        self.assertIn("no reconocido", result.error or "")
        self.assertEqual(list(self.outbox.iterdir()), [])

    def test_missing_file_returns_error(self) -> None:
        result = convert_file(self.inbox / "no-existe.png", self.outbox, self.options())
        self.assertEqual(result.status, JobStatus.ERROR)
        self.assertIsNotNone(result.error)

    def test_lossless_webp(self) -> None:
        source = self.make_image()
        result = convert_file(source, self.outbox, self.options(OutputFormat.WEBP, lossless=True))
        self.assertEqual(result.status, JobStatus.DONE, result.error)
        self.assertTrue(result.output.exists())  # type: ignore[union-attr]

    def test_animated_gif_to_webp_keeps_frames(self) -> None:
        source = self.inbox / "anim.gif"
        frames = [Image.new("RGB", (32, 32), (value, 0, 0)) for value in (255, 120, 0)]
        frames[0].save(source, save_all=True, append_images=frames[1:], duration=80, loop=0)

        options = self.options(OutputFormat.WEBP, animated=True)
        result = convert_file(source, self.outbox, options)

        self.assertEqual(result.status, JobStatus.DONE, result.error)
        self.assertEqual(result.frames, 3)
        with Image.open(result.output) as converted:  # type: ignore[arg-type]
            self.assertEqual(converted.n_frames, 3)

    def test_animated_without_option_keeps_first_frame(self) -> None:
        source = self.inbox / "anim.gif"
        frames = [Image.new("RGB", (16, 16), (value, 0, 0)) for value in (255, 0)]
        frames[0].save(source, save_all=True, append_images=frames[1:], duration=100)

        result = convert_file(source, self.outbox, self.options(OutputFormat.PNG))

        self.assertEqual(result.status, JobStatus.DONE, result.error)
        self.assertEqual(result.frames, 1)
        self.assertTrue(any("primer fotograma" in note for note in result.notes))

    def test_batch_reports_progress_and_isolates_errors(self) -> None:
        good_one = self.make_image("uno.png")
        bad = self.inbox / "malo.png"
        bad.write_bytes(b"no soy una imagen")
        good_two = self.make_image("dos.png", color=(0, 200, 0))

        events: list[BatchProgress] = []
        converter = BatchConverter(self.outbox, self.options(OutputFormat.WEBP), max_workers=2)
        results = converter.run([good_one, bad, good_two], on_progress=events.append)

        self.assertEqual(len(events), 3)
        self.assertEqual([event.done for event in events], [1, 2, 3])
        self.assertEqual([result.source for result in results], [good_one, bad, good_two])
        self.assertEqual(results[0].status, JobStatus.DONE)
        self.assertEqual(results[1].status, JobStatus.ERROR)
        self.assertEqual(results[2].status, JobStatus.DONE)

    def test_batch_can_be_cancelled_before_start(self) -> None:
        converter = BatchConverter(self.outbox, self.options())
        converter.cancel()

        results = converter.run([self.make_image("a.png"), self.make_image("b.png")])

        self.assertTrue(all(result.status is JobStatus.SKIPPED for result in results))

    def test_batch_cancels_one_file_without_stopping_the_rest(self) -> None:
        first = self.make_image("a.png")
        second = self.make_image("b.png")
        converter = BatchConverter(self.outbox, self.options())
        converter.cancel_file(second)

        results = converter.run([first, second])

        self.assertEqual(results[0].status, JobStatus.DONE)
        self.assertEqual(results[1].status, JobStatus.SKIPPED)
        self.assertTrue(converter.is_file_cancelled(second))
        self.assertFalse(converter.is_file_cancelled(first))

    def test_cancel_files_accepts_several_paths(self) -> None:
        sources = [self.make_image("a.png"), self.make_image("b.png")]
        converter = BatchConverter(self.outbox, self.options())
        converter.cancel_files(sources)

        results = converter.run(sources)

        self.assertTrue(all(result.status is JobStatus.SKIPPED for result in results))

    def test_build_output_path_protects_source(self) -> None:
        source = self.make_image("doble.png")
        target, skip = build_output_path(
            source, self.inbox, OutputFormat.PNG, ConflictPolicy.RENAME
        )
        self.assertFalse(skip)
        self.assertNotEqual(target, source)
        self.assertEqual(target.name, "doble_converted.png")

    def test_batch_empty_input(self) -> None:
        self.assertEqual(BatchConverter(self.outbox, self.options()).run([]), [])


if __name__ == "__main__":
    unittest.main()
