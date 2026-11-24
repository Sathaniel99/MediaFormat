from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
    ConversionResult,
    JobStatus,
    OutputFormat,
)
from app.paths import path_key
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

    def test_exif_orientation_is_not_applied_twice(self) -> None:
        source = self.inbox / "rotada.jpg"
        image = Image.new("RGB", (10, 20), (0, 128, 0))
        exif = Image.Exif()
        exif[0x0112] = 6
        image.save(source, "JPEG", exif=exif)

        result = convert_file(source, self.outbox, self.options(OutputFormat.JPEG))

        self.assertEqual(result.status, JobStatus.DONE, result.error)
        with Image.open(result.output) as converted:  # type: ignore[arg-type]
            self.assertEqual(converted.size, (20, 10))
            self.assertIsNone(converted.getexif().get(0x0112))

    def test_reserved_destination_forces_a_renamed_target(self) -> None:
        first = self.make_image("uno.png")
        second = self.inbox / "uno.jpg"
        Image.new("RGB", (32, 16), (10, 20, 30)).save(second)
        reserved: set[str] = set()

        first_target, first_skip = build_output_path(
            first, self.outbox, OutputFormat.WEBP, ConflictPolicy.RENAME, reserved
        )
        second_target, second_skip = build_output_path(
            second, self.outbox, OutputFormat.WEBP, ConflictPolicy.RENAME, reserved
        )

        self.assertEqual((first_target.name, first_skip), ("uno.webp", False))
        self.assertEqual((second_target.name, second_skip), ("uno_1.webp", False))

    def test_reserved_destination_is_skipped_with_the_skip_policy(self) -> None:
        source = self.make_image("uno.png")
        reserved = {path_key(self.outbox / "uno.webp")}
        _, skip = build_output_path(
            source, self.outbox, OutputFormat.WEBP, ConflictPolicy.SKIP, reserved
        )
        self.assertTrue(skip)

    def test_batch_does_not_lose_concurrent_destinations(self) -> None:
        png = self.make_image("igual.png")
        jpg = self.inbox / "igual.jpg"
        Image.new("RGB", (32, 16), (10, 20, 30)).save(jpg)

        converter = BatchConverter(self.outbox, self.options(OutputFormat.WEBP), max_workers=2)
        results = converter.run([png, jpg])

        names = {result.output.name for result in results if result.status is JobStatus.DONE}
        self.assertEqual(names, {"igual.webp", "igual_1.webp"})
        self.assertEqual(len(list(self.outbox.glob("*.webp"))), 2)

    def test_batch_reports_progress_for_precancelled_files(self) -> None:
        sources = [self.make_image("a.png"), self.make_image("b.png")]
        converter = BatchConverter(self.outbox, self.options())
        converter.cancel()
        events: list[BatchProgress] = []

        results = converter.run(sources, on_progress=events.append)

        self.assertTrue(all(result.status is JobStatus.SKIPPED for result in results))
        self.assertEqual([event.done for event in events], [1, 2])
        self.assertEqual([event.total for event in events], [2, 2])

    def test_cancelling_mid_batch_returns_results_without_raising(self) -> None:
        sources = [self.make_image(f"{index}.png") for index in range(3)]
        converter = BatchConverter(self.outbox, self.options(), max_workers=1)
        events: list[BatchProgress] = []

        def cancel_on_first_file(*_args: object, **_kwargs: object) -> ConversionResult:
            converter.cancel()
            return ConversionResult(source=sources[0], status=JobStatus.DONE)

        with mock.patch("app.converter.convert_file", side_effect=cancel_on_first_file):
            results = converter.run(sources, on_progress=events.append)

        self.assertEqual(len(results), 3)
        self.assertEqual([event.done for event in events], [1, 2, 3])
        self.assertEqual(results[0].status, JobStatus.DONE)
        self.assertEqual(results[1].status, JobStatus.SKIPPED)
        self.assertEqual(results[2].status, JobStatus.SKIPPED)

    def test_failed_save_removes_the_partial_output(self) -> None:
        source = self.make_image("parcial.png")

        def broken_save(_image: Image.Image, fp: object, *_args: object, **_kwargs: object) -> None:
            Path(fp).write_bytes(b"parcial")  # type: ignore[arg-type]
            raise OSError("disco lleno")

        with mock.patch.object(Image.Image, "save", broken_save):
            result = convert_file(source, self.outbox, self.options(OutputFormat.PNG))

        self.assertEqual(result.status, JobStatus.ERROR)
        self.assertFalse((self.outbox / "parcial.png").exists())

    def test_animated_conversion_keeps_exif(self) -> None:
        source = self.inbox / "anim.webp"
        frames = [Image.new("RGB", (16, 16), (value, 0, 0)) for value in (255, 120)]
        exif = Image.Exif()
        exif[0x010E] = "origen"
        frames[0].save(source, "WEBP", save_all=True, append_images=frames[1:], exif=exif)

        result = convert_file(source, self.outbox, self.options(OutputFormat.WEBP, animated=True))

        self.assertEqual(result.status, JobStatus.DONE, result.error)
        with Image.open(result.output) as converted:  # type: ignore[arg-type]
            self.assertEqual(converted.n_frames, 2)
            self.assertEqual(converted.getexif().get(0x010E), "origen")


if __name__ == "__main__":
    unittest.main()
