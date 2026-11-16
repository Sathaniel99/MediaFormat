"""Perfiles de conversion integrados y personalizados (sin Qt).

Los perfiles integrados cubren los casos habituales. Los personalizados se
guardan como JSON en la seccion ``[profiles]`` de ``config.ini``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from app.models import OutputFormat

_SUBSAMPLING = ("4:4:4", "4:2:2", "4:2:0")


@dataclass(frozen=True, slots=True)
class Profile:
    """Ajustes de conversion que puede aplicar un perfil."""

    key: str
    label_key: str
    output_format: OutputFormat
    quality: int = 90
    lossless: bool = False
    animated: bool = False
    jpeg_subsampling: str = "4:2:0"
    png_compress_level: int = 6
    builtin: bool = True

    def normalized(self) -> Profile:
        subsampling = self.jpeg_subsampling if self.jpeg_subsampling in _SUBSAMPLING else "4:2:0"
        return Profile(
            key=self.key,
            label_key=self.label_key,
            output_format=OutputFormat.from_value(self.output_format, OutputFormat.WEBP),
            quality=min(100, max(1, int(self.quality))),
            lossless=bool(self.lossless),
            animated=bool(self.animated),
            jpeg_subsampling=subsampling,
            png_compress_level=min(9, max(0, int(self.png_compress_level))),
            builtin=self.builtin,
        )


BUILTIN_PROFILES: tuple[Profile, ...] = (
    Profile("web", "profile.builtin.web", OutputFormat.WEBP, 82),
    Profile(
        "print",
        "profile.builtin.print",
        OutputFormat.PNG,
        90,
        jpeg_subsampling="4:4:4",
        png_compress_level=9,
    ),
    Profile(
        "social",
        "profile.builtin.social",
        OutputFormat.JPEG,
        90,
        jpeg_subsampling="4:4:4",
    ),
    Profile("chat", "profile.builtin.chat", OutputFormat.WEBP, 85),
)

_SLUG = re.compile(r"[^a-z0-9_-]+")


def slugify(value: str) -> str:
    """Nombre estable para usar como clave en el ``.ini``."""
    slug = _SLUG.sub("-", value.strip().lower()).strip("-")
    return slug or "perfil"


def custom_profile_key(name: str, existing: set[str]) -> str:
    """Evita colisiones anadiendo ``-2``, ``-3``... al slug."""
    base = slugify(name)
    candidate = base
    index = 2
    while candidate in existing:
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def profile_to_json(profile: Profile) -> str:
    data = asdict(profile)
    data["output_format"] = profile.output_format.value
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def profile_from_json(key: str, raw: str) -> Profile | None:
    """Reconstruye un perfil personalizado; ``None`` si el JSON no es valido."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        profile = Profile(
            key=key,
            label_key=str(data.get("label_key") or f"profile.custom.{key}"),
            output_format=OutputFormat.from_value(data.get("output_format"), OutputFormat.WEBP),
            quality=int(data.get("quality", 90)),
            lossless=bool(data.get("lossless", False)),
            animated=bool(data.get("animated", False)),
            jpeg_subsampling=str(data.get("jpeg_subsampling", "4:2:0")),
            png_compress_level=int(data.get("png_compress_level", 6)),
            builtin=False,
        )
    except (TypeError, ValueError):
        return None
    return profile.normalized()


def all_profiles(raw_profiles: dict[str, str] | None = None) -> list[Profile]:
    """Integrados primero y luego los personalizados validos."""
    profiles = list(BUILTIN_PROFILES)
    for key, raw in sorted((raw_profiles or {}).items()):
        profile = profile_from_json(key, raw)
        if profile is not None:
            profiles.append(profile)
    return profiles


def profile_label(profile: Profile, translate: object | None = None) -> str:
    """Etiqueta visible; los personalizados guardan su nombre en ``label_key``."""
    if profile.label_key.startswith("profile.custom."):
        return profile.label_key.removeprefix("profile.custom.")
    if callable(translate):
        return str(translate(profile.label_key))
    return profile.label_key
