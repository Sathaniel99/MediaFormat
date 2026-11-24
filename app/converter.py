"""Image conversion engine (Pillow only, no Qt).

Public API
----------
* :func:`available_formats` - formats this Pillow build can actually write.
* :func:`collect_sources` - expand files/folders into a clean list of paths.
* :func:`convert_file` - convert one image, never raises for user errors.
* :class:`BatchConverter` - threaded batch conversion with progress callbacks.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError, features

from app.models import (
    BatchProgress,
    ConflictPolicy,
    ConversionOptions,
    ConversionResult,
    JobStatus,
    OutputFormat,
)
from app.paths import ensure_dir, path_key, unique_path

LOGGER = logging.getLogger("mediaformat.converter")

_SUBSAMPLING = {"4:4:4": 0, "4:2:2": 1, "4:2:0": 2}
_METADATA_FORMATS = frozenset(
    {OutputFormat.JPEG, OutputFormat.PNG, OutputFormat.WEBP, OutputFormat.AVIF}
)
_ICC_FORMATS = frozenset(
    {OutputFormat.JPEG, OutputFormat.PNG, OutputFormat.WEBP, OutputFormat.TIFF, OutputFormat.AVIF}
)


class ConversionError(Exception):
    """Raised for invalid calls, not for per-file failures."""


def available_formats() -> list[OutputFormat]:
    """Formats writable by the current Pillow build, in enum order."""
    Image.init()  # populate Image.SAVE before inspecting it
    available: list[OutputFormat] = []
    for fmt in OutputFormat:
        if fmt.value not in Image.SAVE:
            continue
        if fmt is OutputFormat.AVIF and not features.check("avif"):
            continue
        available.append(fmt)
    return available


def supported_extensions() -> set[str]:
    """Lowercase extensions Pillow can read, including the leading dot."""
    return {str(extension).lower() for extension in Image.registered_extensions()}


def collect_sources(inputs: Iterable[Path | str], recursive: bool = True) -> list[Path]:
    """Expand folders into image files, keeping explicit files untouched.

    Order is preserved and duplicates (case-insensitive on Windows) removed.
    """
    seen: set[str] = set()
    collected: list[Path] = []
    extensions = supported_extensions()

    def add(candidate: Path) -> None:
        key = str(candidate.resolve()).lower()
        if key not in seen:
            seen.add(key)
            collected.append(candidate)

    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            iterator = path.rglob("*") if recursive else path.glob("*")
            for candidate in sorted(iterator):
                if candidate.is_file() and candidate.suffix.lower() in extensions:
                    add(candidate)
        elif path.is_file():
            add(path)

    return collected


def build_output_path(
    source: Path,
    output_dir: Path,
    output_format: OutputFormat,
    policy: ConflictPolicy,
    reserved: set[str] | None = None,
) -> tuple[Path, bool]:
    """Return ``(target, should_skip)`` for a single conversion.

    ``reserved`` holds destinations already claimed by other jobs in the same
    batch; it prevents two workers from choosing the same file name.
    """
    target = output_dir / f"{source.stem}{output_format.extension}"
    try:
        same_file = target.resolve() == source.resolve()
    except OSError:
        same_file = target == source
    if same_file:
        target = output_dir / f"{source.stem}_converted{output_format.extension}"

    if reserved is not None and path_key(target) in reserved:
        if policy is ConflictPolicy.SKIP:
            return target, True
        target = unique_path(target, reserved)
    elif policy is ConflictPolicy.SKIP and target.exists():
        return target, True
    elif policy is ConflictPolicy.RENAME and target.exists():
        target = unique_path(target, reserved)

    if reserved is not None:
        reserved.add(path_key(target))
    return target, False


def convert_file(
    source: Path | str,
    output_dir: Path | str,
    options: ConversionOptions,
    skip_check: Callable[[Path], bool] | None = None,
    reserve_path: Callable[[Path], tuple[Path, bool]] | None = None,
) -> ConversionResult:
    """Convert ``source`` into ``output_dir``.

    ``skip_check`` lets the batch cancel a file that has not started yet: it is
    evaluated at the very beginning, so files already running finish normally.
    ``reserve_path`` atomically claims the destination inside a batch. File-level
    problems are returned as an ``ERROR`` result with a readable message; only
    programming mistakes raise.
    """
    source = Path(source)
    output_dir = Path(output_dir)
    options = options.normalized()
    fmt = options.output_format
    started = time.perf_counter()
    size_in = 0
    target: Path | None = None
    target_existed = False
    notes: list[str] = []

    if skip_check is not None and skip_check(source):
        return _cancelled_result(source)

    def finish(
        status: JobStatus,
        *,
        output: Path | None = None,
        error: str | None = None,
        size_out: int = 0,
        frames: int = 1,
    ) -> ConversionResult:
        return ConversionResult(
            source=source,
            status=status,
            output=output,
            error=error,
            size_in=size_in,
            size_out=size_out,
            frames=frames,
            duration_ms=int((time.perf_counter() - started) * 1000),
            notes=tuple(notes),
        )

    try:
        if not source.is_file():
            raise FileNotFoundError(f"no existe: {source}")
        size_in = source.stat().st_size

        if reserve_path is not None:
            target, should_skip = reserve_path(source)
        else:
            target, should_skip = build_output_path(source, output_dir, fmt, options.on_conflict)
        target_existed = target.exists()
        if should_skip:
            notes.append("el archivo de salida ya existe")
            return finish(JobStatus.SKIPPED, output=target)

        ensure_dir(output_dir)

        with Image.open(source) as opened:
            frame_count = int(getattr(opened, "n_frames", 1) or 1)
            icc_profile = opened.info.get("icc_profile") if options.keep_metadata else None
            source_exif = opened.info.get("exif") if options.keep_metadata else None

            if frame_count > 1 and options.animated and fmt.supports_animation:
                frames_saved = _save_animated(
                    opened, target, fmt, options, source_exif, icc_profile, frame_count, notes
                )
            else:
                if frame_count > 1:
                    notes.append("solo se convirtio el primer fotograma")
                    frames_saved = 1
                else:
                    frames_saved = 1
                image, static_exif = _load_static(opened, options, notes)
                _save_static(image, target, fmt, options, static_exif, icc_profile, notes)

        size_out = target.stat().st_size
        LOGGER.info("convertido %s -> %s (%s -> %s)", source.name, target.name, size_in, size_out)
        return finish(JobStatus.DONE, output=target, size_out=size_out, frames=frames_saved)

    except Exception as exc:  # noqa: BLE001 - per-file isolation is a feature
        if target is not None and not target_existed:
            with contextlib.suppress(OSError):
                target.unlink(missing_ok=True)
        LOGGER.warning("fallo al convertir %s: %s", source, exc)
        return finish(JobStatus.ERROR, error=_friendly_error(exc))


class BatchConverter:
    """Convert many files in parallel while reporting progress."""

    def __init__(
        self,
        output_dir: Path | str,
        options: ConversionOptions,
        max_workers: int = 4,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.options = options.normalized()
        self.max_workers = max(1, min(16, int(max_workers)))
        self.cancel_event = cancel_event or threading.Event()
        self._cancelled_files: set[str] = set()
        self._cancel_lock = threading.Lock()

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def cancel(self) -> None:
        self.cancel_event.set()

    def cancel_file(self, source: Path | str) -> None:
        """Cancel one file if it has not started yet (thread-safe)."""
        with self._cancel_lock:
            self._cancelled_files.add(_source_key(source))

    def cancel_files(self, sources: Iterable[Path | str]) -> None:
        with self._cancel_lock:
            self._cancelled_files.update(_source_key(source) for source in sources)

    def is_file_cancelled(self, source: Path | str) -> bool:
        if self.cancelled:
            return True
        with self._cancel_lock:
            return _source_key(source) in self._cancelled_files

    def run(
        self,
        sources: Sequence[Path | str],
        on_progress: Callable[[BatchProgress], None] | None = None,
    ) -> list[ConversionResult]:
        items = [Path(source) for source in sources]
        total = len(items)
        results: dict[int, ConversionResult] = {}
        if total == 0:
            return []

        reserved: set[str] = set()
        reservation_lock = threading.Lock()
        completed = 0

        def reserve(source: Path) -> tuple[Path, bool]:
            with reservation_lock:
                return build_output_path(
                    source,
                    self.output_dir,
                    self.options.output_format,
                    self.options.on_conflict,
                    reserved,
                )

        def report(result: ConversionResult) -> None:
            nonlocal completed
            completed += 1
            if on_progress is not None:
                on_progress(BatchProgress(completed, total, result))

        workers = min(self.max_workers, total)
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="mf-convert") as pool:
            futures = {}
            for index, item in enumerate(items):
                if self.is_file_cancelled(item):
                    result = _cancelled_result(item)
                    results[index] = result
                    report(result)
                    continue
                futures[
                    pool.submit(
                        convert_file,
                        item,
                        self.output_dir,
                        self.options,
                        self.is_file_cancelled,
                        reserve,
                    )
                ] = index

            for future in as_completed(futures):
                index = futures[future]
                try:
                    result = future.result()
                except CancelledError:
                    result = _cancelled_result(items[index])
                results[index] = result
                report(result)
                if self.cancelled:
                    for pending in futures:
                        pending.cancel()

        for index, item in enumerate(items):
            if index not in results:
                result = _cancelled_result(item)
                results[index] = result
                report(result)
        return [results[index] for index in range(total)]


def _source_key(source: Path | str) -> str:
    path = Path(source)
    try:
        return str(path.resolve()).lower()
    except OSError:
        return str(path).lower()


def _cancelled_result(source: Path) -> ConversionResult:
    return ConversionResult(
        source=source,
        status=JobStatus.SKIPPED,
        error="cancelado",
        notes=("cancelado por el usuario",),
    )


def _load_static(
    opened: Image.Image, options: ConversionOptions, notes: list[str]
) -> tuple[Image.Image, bytes | None]:
    image = opened
    try:
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"no se pudo leer la imagen: {exc}") from exc

    if options.apply_exif_orientation:
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:  # noqa: BLE001 - bad EXIF must not abort the conversion
            notes.append("orientacion EXIF no aplicable")

    # exif_transpose already removes the Orientation tag from the returned
    # image; reusing the original bytes would rotate the pixels twice.
    exif_bytes: bytes | None = None
    if options.keep_metadata:
        try:
            exif = image.getexif()
            if exif:
                exif_bytes = exif.tobytes()
        except Exception:  # noqa: BLE001 - metadata must not abort conversion
            notes.append("EXIF no aplicable")

    return _prepare_image(image, options.output_format, options), exif_bytes


def _prepare_image(
    image: Image.Image, fmt: OutputFormat, options: ConversionOptions
) -> Image.Image:
    if fmt in (OutputFormat.JPEG, OutputFormat.BMP) or fmt is OutputFormat.GIF:
        return _flatten_alpha(image, options.background)

    if fmt is OutputFormat.ICO:
        return image.convert("RGBA")

    if image.mode == "P":
        if "transparency" in image.info and fmt.supports_alpha:
            return image.convert("RGBA")
        return image.convert("RGB")

    if image.mode in ("RGBA", "RGB", "L"):
        return image
    if image.mode == "LA":
        return image.convert("RGBA")
    if "A" in image.getbands():
        return image.convert("RGBA")
    return image.convert("RGB")


def _flatten_alpha(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, background)
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return canvas
    if image.mode in ("RGB", "L"):
        return image
    return image.convert("RGB")


def _save_static(
    image: Image.Image,
    target: Path,
    fmt: OutputFormat,
    options: ConversionOptions,
    exif: bytes | None,
    icc_profile: bytes | None,
    notes: list[str],
) -> None:
    kwargs: dict[str, object] = _format_kwargs(fmt, options)

    if options.keep_metadata:
        if exif and fmt in _METADATA_FORMATS:
            kwargs["exif"] = exif
        if icc_profile and fmt in _ICC_FORMATS:
            kwargs["icc_profile"] = icc_profile

    try:
        image.save(target, fmt.value, **kwargs)
    except (TypeError, ValueError) as exc:
        dropped = [key for key in ("exif", "icc_profile") if key in kwargs]
        if not dropped:
            raise
        for key in dropped:
            kwargs.pop(key, None)
        image.save(target, fmt.value, **kwargs)
        notes.append(f"metadatos omitidos ({exc})")


def _save_animated(
    opened: Image.Image,
    target: Path,
    fmt: OutputFormat,
    options: ConversionOptions,
    exif: bytes | None,
    icc_profile: bytes | None,
    frame_count: int,
    notes: list[str],
) -> int:
    frames: list[Image.Image] = []
    durations: list[int] = []
    mode = "RGBA" if fmt.supports_alpha else "RGB"
    for index in range(frame_count):
        opened.seek(index)
        frames.append(opened.convert(mode))
        durations.append(int(opened.info.get("duration", 100) or 100))

    kwargs: dict[str, object] = _format_kwargs(fmt, options)
    kwargs.update(
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=int(opened.info.get("loop", 0) or 0),
    )
    if fmt is OutputFormat.GIF:
        kwargs["optimize"] = False
        kwargs["disposal"] = 2
    if options.keep_metadata:
        if exif and fmt in _METADATA_FORMATS:
            kwargs["exif"] = exif
        if icc_profile and fmt in _ICC_FORMATS:
            kwargs["icc_profile"] = icc_profile

    try:
        frames[0].save(target, fmt.value, **kwargs)
    except (TypeError, ValueError) as exc:
        dropped = [key for key in ("exif", "icc_profile") if key in kwargs]
        for key in dropped:
            kwargs.pop(key, None)
        if not dropped:
            raise
        frames[0].save(target, fmt.value, **kwargs)
        notes.append(f"metadatos omitidos ({exc})")

    notes.append(f"{frame_count} fotogramas")
    return frame_count


def _format_kwargs(fmt: OutputFormat, options: ConversionOptions) -> dict[str, object]:
    if fmt is OutputFormat.JPEG:
        return {
            "quality": options.quality,
            "subsampling": _SUBSAMPLING.get(options.jpeg_subsampling, 2),
            "optimize": True,
            "progressive": True,
        }
    if fmt is OutputFormat.WEBP:
        if options.lossless:
            return {"lossless": True, "method": 4}
        return {"quality": options.quality, "method": 4}
    if fmt is OutputFormat.AVIF:
        return {"quality": options.quality}
    if fmt is OutputFormat.PNG:
        return {"compress_level": options.png_compress_level}
    if fmt is OutputFormat.TIFF:
        return {"compression": "tiff_lzw"}
    return {}


def _friendly_error(exc: Exception) -> str:
    if isinstance(exc, ConversionError):
        return str(exc)
    if isinstance(exc, FileNotFoundError):
        return "el archivo no existe"
    if isinstance(exc, UnidentifiedImageError):
        return "formato de imagen no reconocido o archivo danado"
    if isinstance(exc, Image.DecompressionBombError):
        return "imagen demasiado grande (proteccion anti-bomba de Pillow)"
    if isinstance(exc, PermissionError):
        return "sin permisos para leer o escribir el archivo"
    if isinstance(exc, MemoryError):
        return "memoria insuficiente para procesar la imagen"
    if isinstance(exc, OSError):
        return f"error de disco: {exc}"
    return f"{type(exc).__name__}: {exc}"
