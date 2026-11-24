"""Read/write the ``config.ini`` file with sane defaults and validation.

Design notes:

* ``configparser`` runs with ``interpolation=None`` so values like
  ``%USERPROFILE%\\Documents`` and ``#FFFFFF`` are preserved verbatim.
* Only full-line comments are supported (``;`` or ``#``). Inline comments are
  disabled on purpose, otherwise ``background = #FFFFFF`` would be truncated.
* A corrupt file is backed up as ``config.ini.bak`` and defaults are used.
* The file is fully rewritten on save, so hand comments are not preserved.
"""

from __future__ import annotations

import configparser
import contextlib
import logging
import os
from pathlib import Path

from app.accents import ACCENT_CHOICES, DEFAULT_ACCENT, normalize_accent
from app.i18n import DEFAULT_LANGUAGE, LANGUAGES
from app.models import ConflictPolicy, ConversionOptions, OutputFormat
from app.paths import config_path, default_output_dir, expand_path

LOGGER = logging.getLogger("mediaformat.config")

SCHEMA_VERSION = 2

_THEMES = ("system", "light", "dark")
_SUBSAMPLING = ("4:4:4", "4:2:2", "4:2:0")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


class ConfigError(Exception):
    """Raised when a value cannot be coerced to the expected type."""


def default_values() -> dict[str, dict[str, str]]:
    """Fresh defaults; the output folder is resolved lazily on purpose."""
    return {
        "app": {
            "version": str(SCHEMA_VERSION),
            "theme": "system",
            "accent": DEFAULT_ACCENT,
            "language": DEFAULT_LANGUAGE,
            "notify_on_finish": "true",
            "restore_queue": "true",
        },
        "output": {
            "folder": os.fspath(default_output_dir()),
            "open_after_convert": "false",
            "on_conflict": ConflictPolicy.RENAME.value,
        },
        "format": {"default": OutputFormat.WEBP.value},
        "jpeg": {"quality": "95", "subsampling": "4:2:0", "background": "#FFFFFF"},
        "webp": {"quality": "95", "lossless": "false"},
        "png": {"compress_level": "6"},
        "processing": {
            "keep_metadata": "true",
            "apply_exif_orientation": "true",
            "max_workers": "4",
            "recursive_folders": "true",
            "animated_frames": "false",
        },
        "ui": {
            "thumbnails": "true",
            "window_geometry": "",
            "window_x": "-1",
            "window_y": "-1",
            "window_maximized": "false",
        },
        "profiles": {},
    }


class Config:
    """Typed view over ``config.ini``."""

    def __init__(self, path: Path | str | None = None, autoload: bool = True) -> None:
        self.path = Path(path) if path is not None else config_path()
        self.warnings: list[str] = []
        self._data = default_values()
        if autoload:
            self.load()

    # ------------------------------------------------------------------ load
    def load(self) -> Config:
        self._data = default_values()
        self.warnings = []

        if not self.path.exists():
            try:
                self.save()
            except OSError as exc:  # read-only locations
                self.warnings.append(f"No se pudo crear {self.path}: {exc}")
            return self

        parser = configparser.ConfigParser(
            interpolation=None,
            comment_prefixes=(";", "#"),
            inline_comment_prefixes=None,
            strict=False,
        )
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                parser.read_file(handle)
        except (configparser.Error, UnicodeDecodeError, OSError) as exc:
            self._backup_corrupt()
            self.warnings.append(f"config.ini corrupto ({exc}); se usan valores por defecto")
            return self

        for section in parser.sections():
            target = self._data.setdefault(section, {})
            for key, value in parser.items(section):
                target[key] = value.strip()

        self._validate()
        return self

    def _backup_corrupt(self) -> None:
        backup = self.path.with_suffix(self.path.suffix + ".bak")
        try:
            os.replace(self.path, backup)
            LOGGER.warning("config.ini corrupto movido a %s", backup)
        except OSError:
            LOGGER.warning("No se pudo respaldar el config.ini corrupto")

    # --------------------------------------------------------------- getters
    def get(self, section: str, key: str, fallback: str = "") -> str:
        return self._data.get(section, {}).get(key, fallback)

    def get_int(
        self,
        section: str,
        key: str,
        fallback: int,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        try:
            value = int(str(self.get(section, key, str(fallback))).strip())
        except (TypeError, ValueError):
            return fallback
        if minimum is not None and value < minimum:
            return minimum
        if maximum is not None and value > maximum:
            return maximum
        return value

    def get_bool(self, section: str, key: str, fallback: bool) -> bool:
        raw = str(self.get(section, key, "")).strip().lower()
        if raw in _TRUE_VALUES:
            return True
        if raw in _FALSE_VALUES:
            return False
        return fallback

    def get_choice(self, section: str, key: str, choices: tuple[str, ...], fallback: str) -> str:
        raw = str(self.get(section, key, "")).strip().lower()
        return raw if raw in choices else fallback

    def set_value(self, section: str, key: str, value: object) -> None:
        rendered = ("true" if value else "false") if isinstance(value, bool) else str(value)
        self._data.setdefault(section, {})[key] = rendered

    def remove_value(self, section: str, key: str) -> None:
        self._data.get(section, {}).pop(key, None)

    # -------------------------------------------------------------- settings
    @property
    def theme(self) -> str:
        return self.get_choice("app", "theme", _THEMES, "system")

    @theme.setter
    def theme(self, value: str) -> None:
        self.set_value("app", "theme", value)

    @property
    def accent(self) -> str:
        return self.get_choice("app", "accent", ACCENT_CHOICES, DEFAULT_ACCENT)

    @accent.setter
    def accent(self, value: str) -> None:
        self.set_value("app", "accent", normalize_accent(value))

    @property
    def language(self) -> str:
        return self.get_choice("app", "language", LANGUAGES, DEFAULT_LANGUAGE)

    @language.setter
    def language(self, value: str) -> None:
        selected = str(value).strip().lower()
        self.set_value("app", "language", selected if selected in LANGUAGES else DEFAULT_LANGUAGE)

    @property
    def notify_on_finish(self) -> bool:
        return self.get_bool("app", "notify_on_finish", True)

    @notify_on_finish.setter
    def notify_on_finish(self, value: bool) -> None:
        self.set_value("app", "notify_on_finish", value)

    @property
    def restore_queue(self) -> bool:
        return self.get_bool("app", "restore_queue", True)

    @restore_queue.setter
    def restore_queue(self, value: bool) -> None:
        self.set_value("app", "restore_queue", value)

    @property
    def output_folder(self) -> Path:
        raw = self.get("output", "folder").strip()
        if not raw:
            return default_output_dir()
        return expand_path(raw)

    @output_folder.setter
    def output_folder(self, value: Path | str) -> None:
        self.set_value("output", "folder", os.fspath(value))

    @property
    def open_after_convert(self) -> bool:
        return self.get_bool("output", "open_after_convert", False)

    @open_after_convert.setter
    def open_after_convert(self, value: bool) -> None:
        self.set_value("output", "open_after_convert", value)

    @property
    def on_conflict(self) -> ConflictPolicy:
        return ConflictPolicy.from_value(self.get("output", "on_conflict"), ConflictPolicy.RENAME)

    @on_conflict.setter
    def on_conflict(self, value: ConflictPolicy) -> None:
        self.set_value("output", "on_conflict", ConflictPolicy.from_value(value).value)

    @property
    def default_format(self) -> OutputFormat:
        return OutputFormat.from_value(self.get("format", "default"), OutputFormat.WEBP)

    @default_format.setter
    def default_format(self, value: OutputFormat) -> None:
        self.set_value("format", "default", OutputFormat.from_value(value).value)

    @property
    def jpeg_quality(self) -> int:
        return self.get_int("jpeg", "quality", 95, 1, 100)

    @jpeg_quality.setter
    def jpeg_quality(self, value: int) -> None:
        self.set_value("jpeg", "quality", min(100, max(1, int(value))))

    @property
    def jpeg_subsampling(self) -> str:
        return self.get_choice("jpeg", "subsampling", _SUBSAMPLING, "4:2:0")

    @jpeg_subsampling.setter
    def jpeg_subsampling(self, value: str) -> None:
        if value not in _SUBSAMPLING:
            raise ValueError(f"subsampling invalido: {value!r}")
        self.set_value("jpeg", "subsampling", value)

    @property
    def jpeg_background(self) -> tuple[int, int, int]:
        return _parse_color(self.get("jpeg", "background", "#FFFFFF"))

    @jpeg_background.setter
    def jpeg_background(self, value: tuple[int, int, int]) -> None:
        red, green, blue = (min(255, max(0, int(channel))) for channel in value)
        self.set_value("jpeg", "background", f"#{red:02X}{green:02X}{blue:02X}")

    @property
    def webp_quality(self) -> int:
        return self.get_int("webp", "quality", 95, 1, 100)

    @webp_quality.setter
    def webp_quality(self, value: int) -> None:
        self.set_value("webp", "quality", min(100, max(1, int(value))))

    @property
    def webp_lossless(self) -> bool:
        return self.get_bool("webp", "lossless", False)

    @webp_lossless.setter
    def webp_lossless(self, value: bool) -> None:
        self.set_value("webp", "lossless", value)

    @property
    def png_compress_level(self) -> int:
        return self.get_int("png", "compress_level", 6, 0, 9)

    @png_compress_level.setter
    def png_compress_level(self, value: int) -> None:
        self.set_value("png", "compress_level", min(9, max(0, int(value))))

    @property
    def keep_metadata(self) -> bool:
        return self.get_bool("processing", "keep_metadata", True)

    @keep_metadata.setter
    def keep_metadata(self, value: bool) -> None:
        self.set_value("processing", "keep_metadata", value)

    @property
    def apply_exif_orientation(self) -> bool:
        return self.get_bool("processing", "apply_exif_orientation", True)

    @apply_exif_orientation.setter
    def apply_exif_orientation(self, value: bool) -> None:
        self.set_value("processing", "apply_exif_orientation", value)

    @property
    def max_workers(self) -> int:
        return self.get_int("processing", "max_workers", 4, 1, 16)

    @max_workers.setter
    def max_workers(self, value: int) -> None:
        self.set_value("processing", "max_workers", min(16, max(1, int(value))))

    @property
    def recursive_folders(self) -> bool:
        return self.get_bool("processing", "recursive_folders", True)

    @recursive_folders.setter
    def recursive_folders(self, value: bool) -> None:
        self.set_value("processing", "recursive_folders", value)

    @property
    def animated_frames(self) -> bool:
        return self.get_bool("processing", "animated_frames", False)

    @animated_frames.setter
    def animated_frames(self, value: bool) -> None:
        self.set_value("processing", "animated_frames", value)

    @property
    def thumbnails(self) -> bool:
        return self.get_bool("ui", "thumbnails", True)

    @thumbnails.setter
    def thumbnails(self, value: bool) -> None:
        self.set_value("ui", "thumbnails", value)

    @property
    def window_geometry(self) -> str:
        return self.get("ui", "window_geometry", "").strip()

    @window_geometry.setter
    def window_geometry(self, value: str) -> None:
        self.set_value("ui", "window_geometry", value)

    @property
    def window_position(self) -> tuple[int, int] | None:
        """Posicion recordada, o ``None`` si aun no se guardo."""
        try:
            x = int(self.get("ui", "window_x", "-1"))
            y = int(self.get("ui", "window_y", "-1"))
        except ValueError:
            return None
        return None if x < 0 or y < 0 else (x, y)

    @window_position.setter
    def window_position(self, value: tuple[int, int] | None) -> None:
        if value is None:
            self.set_value("ui", "window_x", -1)
            self.set_value("ui", "window_y", -1)
            return
        self.set_value("ui", "window_x", int(value[0]))
        self.set_value("ui", "window_y", int(value[1]))

    @property
    def window_maximized(self) -> bool:
        return self.get_bool("ui", "window_maximized", False)

    @window_maximized.setter
    def window_maximized(self, value: bool) -> None:
        self.set_value("ui", "window_maximized", value)

    @property
    def profiles_raw(self) -> dict[str, str]:
        return dict(self._data.get("profiles", {}))

    def set_profile(self, key: str, payload: str) -> None:
        self.set_value("profiles", key, payload)

    def remove_profile(self, key: str) -> None:
        self.remove_value("profiles", key)

    # ------------------------------------------------------------- behaviour
    def conversion_options(
        self,
        output_format: OutputFormat | str | None = None,
        *,
        quality: int | None = None,
        lossless: bool | None = None,
    ) -> ConversionOptions:
        """Build conversion options from the current configuration."""
        fmt = (
            OutputFormat.from_value(output_format)
            if output_format is not None
            else self.default_format
        )
        if quality is None:
            quality = self.jpeg_quality if fmt is OutputFormat.JPEG else self.webp_quality
        if lossless is None:
            lossless = self.webp_lossless and fmt is OutputFormat.WEBP
        return ConversionOptions(
            output_format=fmt,
            quality=quality,
            lossless=lossless,
            background=self.jpeg_background,
            keep_metadata=self.keep_metadata,
            apply_exif_orientation=self.apply_exif_orientation,
            animated=self.animated_frames,
            png_compress_level=self.png_compress_level,
            jpeg_subsampling=self.jpeg_subsampling,
            on_conflict=self.on_conflict,
        ).normalized()

    def _validate(self) -> None:
        checks = (
            ("app", "theme", _THEMES, "system"),
            ("app", "accent", ACCENT_CHOICES, DEFAULT_ACCENT),
            ("app", "language", LANGUAGES, DEFAULT_LANGUAGE),
            ("output", "on_conflict", tuple(p.value for p in ConflictPolicy), "rename"),
            ("jpeg", "subsampling", _SUBSAMPLING, "4:2:0"),
        )
        for section, key, choices, fallback in checks:
            raw = self.get(section, key).strip().lower()
            if raw not in choices:
                self.warnings.append(f"[{section}] {key}={raw!r} invalido; se usa {fallback!r}")
                self.set_value(section, key, fallback)

        raw_format = self.get("format", "default").strip().upper()
        if raw_format not in {fmt.value for fmt in OutputFormat}:
            self.warnings.append(
                f"[format] default={raw_format!r} invalido; se usa {OutputFormat.WEBP.value!r}"
            )
            self.set_value("format", "default", OutputFormat.WEBP.value)

        numeric = (
            ("jpeg", "quality", 95, 1, 100),
            ("webp", "quality", 95, 1, 100),
            ("png", "compress_level", 6, 0, 9),
            ("processing", "max_workers", 4, 1, 16),
        )
        for section, key, fallback, minimum, maximum in numeric:
            raw = self.get(section, key, str(fallback)).strip()
            try:
                value = int(raw)
            except ValueError:
                self.warnings.append(f"[{section}] {key}={raw!r} no numerico; se usa {fallback}")
                self.set_value(section, key, fallback)
                continue
            if value < minimum or value > maximum:
                clamped = min(maximum, max(minimum, value))
                self.warnings.append(
                    f"[{section}] {key}={value} fuera de rango; se ajusta a {clamped}"
                )
                self.set_value(section, key, clamped)

        for section, key in (
            ("output", "open_after_convert"),
            ("webp", "lossless"),
            ("processing", "keep_metadata"),
            ("processing", "apply_exif_orientation"),
            ("processing", "recursive_folders"),
            ("processing", "animated_frames"),
            ("ui", "thumbnails"),
            ("ui", "window_maximized"),
            ("app", "notify_on_finish"),
            ("app", "restore_queue"),
        ):
            raw = self.get(section, key, "").strip().lower()
            if raw not in _TRUE_VALUES | _FALSE_VALUES:
                self.warnings.append(f"[{section}] {key}={raw!r} no booleano; se usa el default")
                self.set_value(section, key, default_values()[section][key])

        for key in ("window_x", "window_y"):
            raw = self.get("ui", key, "-1").strip()
            try:
                int(raw)
            except ValueError:
                self.warnings.append(f"[ui] {key}={raw!r} no numerico; se usa -1")
                self.set_value("ui", key, -1)

        raw_version = self.get("app", "version", str(SCHEMA_VERSION)).strip()
        try:
            version = int(raw_version)
        except ValueError:
            version = -1
        if version != SCHEMA_VERSION:
            self.warnings.append(
                f"[app] version={raw_version!r} no compatible; se escribe {SCHEMA_VERSION}"
            )
            self.set_value("app", "version", SCHEMA_VERSION)

        raw_folder = self.get("output", "folder").strip()
        if raw_folder:
            try:
                expand_path(raw_folder)
            except ValueError as exc:
                self.warnings.append(
                    f"[output] folder={raw_folder!r} invalido: {exc}; se usa el default"
                )
                self.output_folder = default_output_dir()
        if not self.get("output", "folder").strip():
            self.output_folder = default_output_dir()

    # ----------------------------------------------------------------- save
    def _render_profiles(self) -> str:
        lines = [
            f"{key} = {value}"
            for key, value in sorted(self._data.get("profiles", {}).items())
            if value.strip()
        ]
        return "\n".join(lines) if lines else "; (sin perfiles personalizados)"

    def render(self) -> str:
        """Serialize the effective configuration (comments included)."""
        background = self.jpeg_background
        return f"""; MediaFormat - configuracion
; Este archivo lo gestiona la aplicacion. Los comentarios deben ir en su propia linea.
; Rutas: admite variables de entorno (%USERPROFILE%) y ~.
; Compatible con OneDrive: la carpeta por defecto se resuelve con la API de Windows.

[app]
; system | light | dark
theme = {self.theme}
; system | blue | red | green | yellow | purple | pink | brown
accent = {self.accent}
; es | en
language = {self.language}
; Notificacion nativa al terminar un lote
notify_on_finish = {_as_bool(self.notify_on_finish)}
; Recuperar la lista al volver a abrir
restore_queue = {_as_bool(self.restore_queue)}
version = {SCHEMA_VERSION}

[output]
; Carpeta donde se guardan las conversiones
folder = {os.fspath(self.output_folder)}
; true para abrir la carpeta al terminar un lote
open_after_convert = {_as_bool(self.open_after_convert)}
; rename | overwrite | skip
on_conflict = {self.on_conflict.value}

[format]
; Formato por defecto: JPEG, PNG, WEBP, BMP, TIFF, GIF, ICO, TGA, AVIF
default = {self.default_format.value}

[jpeg]
quality = {self.jpeg_quality}
; 4:4:4 | 4:2:2 | 4:2:0
subsampling = {self.jpeg_subsampling}
; Color de fondo al aplanar transparencia (#RRGGBB)
background = #{background[0]:02X}{background[1]:02X}{background[2]:02X}

[webp]
quality = {self.webp_quality}
lossless = {_as_bool(self.webp_lossless)}

[png]
; 0 (rapido) - 9 (maxima compresion)
compress_level = {self.png_compress_level}

[processing]
keep_metadata = {_as_bool(self.keep_metadata)}
apply_exif_orientation = {_as_bool(self.apply_exif_orientation)}
max_workers = {self.max_workers}
recursive_folders = {_as_bool(self.recursive_folders)}
animated_frames = {_as_bool(self.animated_frames)}

[ui]
thumbnails = {_as_bool(self.thumbnails)}
window_geometry = {self.window_geometry}
window_x = {self.window_position[0] if self.window_position else -1}
window_y = {self.window_position[1] if self.window_position else -1}
window_maximized = {_as_bool(self.window_maximized)}

[profiles]
; Perfiles personalizados: clave = JSON generado por la aplicacion
{self._render_profiles()}
"""

    def save(self) -> Path:
        """Atomically write the configuration and return its path."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        nonce = f"{os.getpid()}.{os.urandom(4).hex()}"
        temporary = self.path.with_name(f"{self.path.name}.{nonce}.tmp")
        try:
            temporary.write_text(self.render(), encoding="utf-8", newline="\n")
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                with contextlib.suppress(OSError):
                    temporary.unlink()
        return self.path


def _as_bool(value: bool) -> str:
    return "true" if value else "false"


def _parse_color(raw: str) -> tuple[int, int, int]:
    value = raw.strip()
    try:
        if value.startswith("#") and len(value) == 7:
            return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]
        parts = [int(part.strip()) for part in value.split(",")]
        if len(parts) == 3:
            return tuple(min(255, max(0, part)) for part in parts)  # type: ignore[return-value]
    except (ValueError, TypeError):
        pass
    return (255, 255, 255)
