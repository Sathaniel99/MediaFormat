"""Genera el archivo de metadatos que PyInstaller incrusta en el ``.exe``.

Asi las propiedades del ejecutable muestran nombre, version y descripcion en
lugar de los datos genericos de Python.

Uso::

    python scripts\\make_version_info.py build\\version_info.txt
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

APP_NAME = "MediaFormat"
APP_DESCRIPTION = "MediaFormat - conversor de imagenes"
COMPANY = "MediaFormat"

_TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', '{company}'),
          StringStruct('FileDescription', '{description}'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', '{name}'),
          StringStruct('OriginalFilename', '{name}.exe'),
          StringStruct('ProductName', '{name}'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1252])])
  ]
)
"""


def parse_version(version: str) -> tuple[int, int, int]:
    """Convierte ``x.y.z`` en una tupla de enteros; falla si no encaja."""
    parts = version.strip().split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"version invalida: {version!r} (se espera x.y.z)")
    major, minor, patch = (int(part) for part in parts)
    return major, minor, patch


def current_version() -> str:
    """Lee la version desde ``app/version.py`` sin importar el proyecto."""
    root = Path(__file__).resolve().parent.parent
    text = (root / "app" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if not match:
        raise ValueError("no se encontro __version__ en app/version.py")
    return match.group(1)


def build_version_info(version: str = "") -> str:
    """Devuelve el contenido del archivo de version para ``version``."""
    version = version or current_version()
    major, minor, patch = parse_version(version)
    return _TEMPLATE.format(
        major=major,
        minor=minor,
        patch=patch,
        version=version,
        name=APP_NAME,
        company=COMPANY,
        description=APP_DESCRIPTION,
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parent.parent
    target = Path(args[0]) if args else root / "build" / "version_info.txt"
    version = args[1] if len(args) > 1 else current_version()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_version_info(version), encoding="utf-8")
    print(f"Metadatos de version {version} escritos en {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
