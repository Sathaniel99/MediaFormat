"""Domain models shared by the conversion engine, the config and the UI.

This module must not import Qt or touch the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

_EXTENSIONS: dict[OutputFormat, str] = {}
_QUALITY_FORMATS: frozenset[OutputFormat]
_ALPHA_FORMATS: frozenset[OutputFormat]
_ANIMATED_FORMATS: frozenset[OutputFormat]


class OutputFormat(StrEnum):
    """Formats MediaFormat can write to."""

    JPEG = "JPEG"
    PNG = "PNG"
    WEBP = "WEBP"
    BMP = "BMP"
    TIFF = "TIFF"
    GIF = "GIF"
    ICO = "ICO"
    TGA = "TGA"
    AVIF = "AVIF"

    @property
    def extension(self) -> str:
        return _EXTENSIONS[self]

    @property
    def supports_quality(self) -> bool:
        """True when the format accepts a lossy quality setting (1-100)."""
        return self in _QUALITY_FORMATS

    @property
    def supports_alpha(self) -> bool:
        return self in _ALPHA_FORMATS

    @property
    def supports_animation(self) -> bool:
        return self in _ANIMATED_FORMATS

    @classmethod
    def from_value(cls, value: object, default: OutputFormat | None = None) -> OutputFormat:
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().upper())
        except (ValueError, AttributeError):
            if default is not None:
                return default
            raise ValueError(f"unsupported output format: {value!r}") from None


class ConflictPolicy(StrEnum):
    """What to do when the output file already exists."""

    RENAME = "rename"
    OVERWRITE = "overwrite"
    SKIP = "skip"

    @classmethod
    def from_value(cls, value: object, default: ConflictPolicy | None = None) -> ConflictPolicy:
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except (ValueError, AttributeError):
            if default is not None:
                return default
            raise ValueError(f"unsupported conflict policy: {value!r}") from None


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    SKIPPED = "skipped"


def _clamped_int(value: object, default: int, minimum: int, maximum: int) -> int:
    """Coerce a value to ``int`` and clamp it, falling back on invalid input."""
    try:
        return min(maximum, max(minimum, int(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class ConversionOptions:
    """Everything needed to convert one image, independent from the UI."""

    output_format: OutputFormat = OutputFormat.WEBP
    quality: int = 90
    lossless: bool = False
    background: tuple[int, int, int] = (255, 255, 255)
    keep_metadata: bool = True
    apply_exif_orientation: bool = True
    animated: bool = False
    png_compress_level: int = 6
    jpeg_subsampling: str = "4:2:0"
    on_conflict: ConflictPolicy = ConflictPolicy.RENAME

    def normalized(self) -> ConversionOptions:
        """Return a copy with every value clamped to a safe range."""
        background = self.background
        if isinstance(background, (tuple, list)) and len(background) == 3:
            channels = tuple(_clamped_int(channel, 255, 0, 255) for channel in background)
        else:
            channels = (255, 255, 255)
        subsampling = str(self.jpeg_subsampling).strip()
        if subsampling not in ("4:4:4", "4:2:2", "4:2:0"):
            subsampling = "4:2:0"
        return ConversionOptions(
            output_format=OutputFormat.from_value(self.output_format, OutputFormat.WEBP),
            quality=_clamped_int(self.quality, 90, 1, 100),
            lossless=bool(self.lossless),
            background=channels,  # type: ignore[arg-type]
            keep_metadata=bool(self.keep_metadata),
            apply_exif_orientation=bool(self.apply_exif_orientation),
            animated=bool(self.animated),
            png_compress_level=_clamped_int(self.png_compress_level, 6, 0, 9),
            jpeg_subsampling=subsampling,
            on_conflict=ConflictPolicy.from_value(self.on_conflict, ConflictPolicy.RENAME),
        )


@dataclass(slots=True)
class ConversionResult:
    """Outcome of converting a single file."""

    source: Path
    status: JobStatus
    output: Path | None = None
    error: str | None = None
    size_in: int = 0
    size_out: int = 0
    frames: int = 1
    duration_ms: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.status in (JobStatus.DONE, JobStatus.SKIPPED)

    def summary(self) -> str:
        if self.status is JobStatus.ERROR:
            return f"ERROR {self.source.name}: {self.error}"
        if self.status is JobStatus.SKIPPED:
            return f"SKIP  {self.source.name} (ya existe)"
        return f"OK    {self.source.name} -> {self.output.name if self.output else '?'}"


@dataclass(slots=True)
class BatchProgress:
    """Progress event emitted by :class:`app.converter.BatchConverter`."""

    done: int
    total: int
    result: ConversionResult

    @property
    def percent(self) -> int:
        if self.total <= 0:
            return 0
        return int(self.done * 100 / self.total)


_EXTENSIONS = {
    OutputFormat.JPEG: ".jpg",
    OutputFormat.PNG: ".png",
    OutputFormat.WEBP: ".webp",
    OutputFormat.BMP: ".bmp",
    OutputFormat.TIFF: ".tiff",
    OutputFormat.GIF: ".gif",
    OutputFormat.ICO: ".ico",
    OutputFormat.TGA: ".tga",
    OutputFormat.AVIF: ".avif",
}
_QUALITY_FORMATS = frozenset({OutputFormat.JPEG, OutputFormat.WEBP, OutputFormat.AVIF})
_ALPHA_FORMATS = frozenset(
    {
        OutputFormat.PNG,
        OutputFormat.WEBP,
        OutputFormat.TIFF,
        OutputFormat.GIF,
        OutputFormat.ICO,
        OutputFormat.TGA,
        OutputFormat.AVIF,
    }
)
_ANIMATED_FORMATS = frozenset(
    {OutputFormat.GIF, OutputFormat.WEBP, OutputFormat.PNG, OutputFormat.TIFF}
)
