"""Path helpers: known Windows folders, expansion, collisions and formatting.

The UI and the converter both depend on this module, so it must stay free of
Qt imports and of global mutable state.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

APP_NAME = "MediaFormat"

_FOLDERID_DOCUMENTS = uuid.UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")


if os.name == "nt":  # pragma: no cover - exercised on Windows only

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    _SHGetKnownFolderPath = ctypes.windll.shell32.SHGetKnownFolderPath
    _SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(_GUID),
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    _SHGetKnownFolderPath.restype = ctypes.c_long
    _CoTaskMemFree = ctypes.windll.ole32.CoTaskMemFree
    _CoTaskMemFree.argtypes = [ctypes.c_void_p]
    _CoTaskMemFree.restype = None

    def _known_folder(guid: uuid.UUID) -> Path:
        structure = _GUID(
            guid.time_low,
            guid.time_mid,
            guid.time_hi_version,
            (ctypes.c_ubyte * 8)(*guid.bytes[8:]),
        )
        buffer = ctypes.c_wchar_p()
        result = _SHGetKnownFolderPath(ctypes.byref(structure), 0, None, ctypes.byref(buffer))
        if result != 0 or not buffer.value:
            raise OSError(f"SHGetKnownFolderPath failed with 0x{result & 0xFFFFFFFF:08X}")
        try:
            return Path(buffer.value)
        finally:
            _CoTaskMemFree(buffer)

    def documents_dir() -> Path:
        """Return the real Documents folder (honours OneDrive redirection)."""
        try:
            path = _known_folder(_FOLDERID_DOCUMENTS)
        except OSError:
            path = Path.home() / "Documents"
        return path

else:  # pragma: no cover - development on other platforms

    def documents_dir() -> Path:
        candidate = Path.home() / "Documents"
        return candidate if candidate.is_dir() else Path.home()


def default_output_dir() -> Path:
    """Default destination shown in the output field."""
    return documents_dir() / APP_NAME


def _env_path(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable)
    return Path(value) if value else fallback


def config_dir() -> Path:
    """``%APPDATA%\\MediaFormat`` (Roaming)."""
    return _env_path("APPDATA", Path.home() / "AppData" / "Roaming") / APP_NAME


def data_dir() -> Path:
    """``%LOCALAPPDATA%\\MediaFormat`` (logs, caches)."""
    return _env_path("LOCALAPPDATA", Path.home() / "AppData" / "Local") / APP_NAME


def log_dir() -> Path:
    return data_dir() / "logs"


def config_path() -> Path:
    return config_dir() / "config.ini"


def expand_path(value: str | os.PathLike[str]) -> Path:
    """Expand ``%VARS%``, ``~`` and surrounding quotes, then return a Path.

    Unresolved ``%VARIABLE%`` placeholders are an error: leaving them literal
    would create an unexpected directory in the current working directory.
    """
    raw = str(value).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1]
    expanded = os.path.expandvars(os.path.expanduser(raw))
    missing = re.search(r"%([^%]+)%", expanded)
    if missing:
        raise ValueError(f"variable de entorno no definida: {missing.group(0)}")
    return Path(expanded)


def path_key(path: Path | str) -> str:
    """Case-insensitive key to compare destination paths safely."""
    candidate = Path(path)
    try:
        return str(candidate.resolve()).lower()
    except OSError:
        return str(candidate).lower()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_writable_dir(path: Path, create: bool = False) -> bool:
    """Check that ``path`` can host output files."""
    try:
        if create:
            path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            return False
        with tempfile.NamedTemporaryFile(dir=path, prefix=".mf-probe-", suffix=".tmp"):
            pass
        return True
    except OSError:
        return False


def unique_path(path: Path, reserved: set[str] | None = None) -> Path:
    """Return ``path`` or ``name_1.ext``... if it exists or is ``reserved``."""
    if not path.exists() and (reserved is None or path_key(path) not in reserved):
        return path
    stem, suffix = path.stem, path.suffix
    for index in range(1, 10_000):
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists() and (reserved is None or path_key(candidate) not in reserved):
            return candidate
    raise FileExistsError(f"no free file name for {path}")


def format_size(num_bytes: int) -> str:
    """Human readable size using decimal units (as file explorers do)."""
    size = float(max(0, num_bytes))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1000 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1000
    return f"{size:.1f} TB"


def open_folder(path: Path) -> bool:
    """Open a folder in the system file explorer. Returns success."""
    try:
        if os.name == "nt":
            os.startfile(str(path))  # noqa: S606 - intentional explorer launch
        elif sys.platform == "darwin":  # pragma: no cover
            subprocess.Popen(["open", str(path)])  # noqa: S603,S607
        else:  # pragma: no cover
            subprocess.Popen(["xdg-open", str(path)])  # noqa: S603,S607
        return True
    except OSError:
        return False
