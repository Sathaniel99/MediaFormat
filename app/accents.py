"""Nombres, etiquetas y deteccion del acento de color (sin Qt).

Vive fuera de la UI para que ``app.config`` pueda validar el valor sin importar
PySide6, y para que ``app.ui.theme`` comparta la misma lista.
"""

from __future__ import annotations

import logging
import os
from typing import Final

LOGGER = logging.getLogger("mediaformat.accents")

ACCENT_NAMES: tuple[str, ...] = ("blue", "red", "green", "yellow", "purple", "pink", "brown")

ACCENT_CHOICES: tuple[str, ...] = ("system", *ACCENT_NAMES)

ACCENT_LABELS: dict[str, str] = {
    "system": "Sistema (Windows)",
    "blue": "Azul",
    "red": "Rojo",
    "green": "Verde",
    "yellow": "Amarillo",
    "purple": "Morado",
    "pink": "Rosado",
    "brown": "Marrón",
}

DEFAULT_ACCENT = "blue"

# Color de referencia (tema claro) de cada acento, usado para acercar el color
# de Windows al nombre mas parecido.
ACCENT_PREVIEW: dict[str, tuple[int, int, int]] = {
    "blue": (0x00, 0x67, 0xC0),
    "red": (0xC4, 0x2B, 0x1C),
    "green": (0x10, 0x7C, 0x10),
    "yellow": (0x9D, 0x5D, 0x00),
    "purple": (0x6B, 0x21, 0xA8),
    "pink": (0xC2, 0x18, 0x5B),
    "brown": (0x8B, 0x5A, 0x2B),
}


def normalize_accent(value: object) -> str:
    """Devuelve un acento valido (incluido ``system``); si no, azul."""
    candidate = str(value).strip().lower()
    return candidate if candidate in ACCENT_CHOICES else DEFAULT_ACCENT


def _nearest_accent(red: int, green: int, blue: int) -> str:
    """Nombre de acento cuya muestra clara esta mas cerca del color dado."""
    return min(
        ACCENT_NAMES,
        key=lambda name: sum(
            (channel - target) ** 2
            for channel, target in zip(ACCENT_PREVIEW[name], (red, green, blue), strict=True)
        ),
    )


def _read_windows_colorization() -> int | None:
    """Lee ``ColorizationColor`` (ARGB) del registro de Windows."""
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
            value, _kind = winreg.QueryValueEx(key, "ColorizationColor")
    except (OSError, ImportError) as exc:
        LOGGER.debug("no se pudo leer el acento de Windows: %s", exc)
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def system_accent() -> str:
    """Acento configurado en Windows, aproximado a uno de los siete nombres."""
    raw = _read_windows_colorization()
    if raw is None:
        return DEFAULT_ACCENT
    red = (raw >> 16) & 0xFF
    green = (raw >> 8) & 0xFF
    blue = raw & 0xFF
    return _nearest_accent(red, green, blue)


def resolve_accent(value: object) -> str:
    """Convierte una preferencia (``system`` incluido) en un acento concreto."""
    name = normalize_accent(value)
    return system_accent() if name == "system" else name


def accent_label(value: object) -> str:
    return ACCENT_LABELS[normalize_accent(value)]


#: Lista usada por la UI para construir menus y pruebas.
ACCENT_ORDER: Final = ACCENT_CHOICES
