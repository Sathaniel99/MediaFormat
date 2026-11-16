"""Identidad de la aplicacion: icono, taskbar y barra de titulo de Windows.

Todo lo nativo se hace con ``ctypes`` y con guardas: en otro sistema o en un
entorno sin ventana (tests ``offscreen``) las funciones no lanzan.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon

from app.ui.icons import app_logo

LOGGER = logging.getLogger("mediaformat.ui.branding")

# Identificador estable para que Windows agrupe la app en la taskbar y use su
# icono en lugar del icono generico de Python.
APP_USER_MODEL_ID = "MediaFormat.Desktop"

# DWMWA_USE_IMMERSIVE_DARK_MODE (Windows 10 20H1+)
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20


def resources_dir() -> Path:
    """Carpeta de recursos, tanto en desarrollo como dentro del ``.exe``."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / "resources"
    return Path(__file__).resolve().parent.parent.parent / "resources"


def icon_path() -> Path:
    return resources_dir() / "icon.ico"


def app_icon() -> QIcon:
    """Icono de la app: el ``.ico`` si existe, si no el logo vectorial."""
    path = icon_path()
    if path.is_file():
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    return QIcon(app_logo(256))


def set_taskbar_identity(app_id: str = APP_USER_MODEL_ID) -> None:
    """Fija el AppUserModelID para que la taskbar muestre el icono correcto."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError) as exc:
        LOGGER.debug("AppUserModelID no disponible: %s", exc)


def apply_dark_titlebar(window: object, dark: bool) -> None:
    """Pinta la barra de titulo nativa en claro u oscuro (Windows 11)."""
    if os.name != "nt":
        return
    try:
        handle = int(window.winId())  # type: ignore[attr-defined]
        value = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            handle,
            _DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except (AttributeError, OSError, ValueError) as exc:
        LOGGER.debug("barra de titulo nativa no disponible: %s", exc)
