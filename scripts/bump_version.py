"""Bump the project version in app/version.py and pyproject.toml.

Usage:
    python scripts/bump_version.py patch
    python scripts/bump_version.py minor
    python scripts/bump_version.py major
    python scripts/bump_version.py 2.0.0
    python scripts/bump_version.py --dry-run patch

The user decides when a change deserves a new version. Agents must ask first.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "app" / "version.py"
PYPROJECT_FILE = ROOT / "pyproject.toml"

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
VERSION_SOURCE = re.compile(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"')
VERSION_PYPROJECT = re.compile(r'(?m)^version\s*=\s*"(\d+\.\d+\.\d+)"')


def read_current() -> str:
    match = VERSION_SOURCE.search(VERSION_FILE.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"No se encontro __version__ en {VERSION_FILE}")
    return match.group(1)


def compute(current: str, target: str) -> str:
    major, minor, patch = (int(part) for part in SEMVER.match(current).groups())  # type: ignore[union-attr]
    normalized = target.strip().lower()
    if normalized == "major":
        return f"{major + 1}.0.0"
    if normalized == "minor":
        return f"{major}.{minor + 1}.0"
    if normalized == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if SEMVER.match(normalized):
        return normalized
    raise SystemExit(f"Objetivo invalido: {target!r}. Usa patch|minor|major|x.y.z")


def write_version(new_version: str) -> None:
    content = VERSION_FILE.read_text(encoding="utf-8")
    updated, replacements = VERSION_SOURCE.subn(f'__version__ = "{new_version}"', content, count=1)
    if replacements != 1:
        raise SystemExit("No se pudo actualizar app/version.py")
    VERSION_FILE.write_text(updated, encoding="utf-8", newline="\n")

    if PYPROJECT_FILE.exists():
        project = PYPROJECT_FILE.read_text(encoding="utf-8")
        project_updated, found = VERSION_PYPROJECT.subn(
            f'version = "{new_version}"', project, count=1
        )
        if found:
            PYPROJECT_FILE.write_text(project_updated, encoding="utf-8", newline="\n")
        else:
            print("Aviso: no se encontro [project] version en pyproject.toml", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sube la version de MediaFormat.")
    parser.add_argument("target", help="patch | minor | major | x.y.z")
    parser.add_argument("--dry-run", action="store_true", help="solo muestra el resultado")
    args = parser.parse_args(argv)

    current = read_current()
    new_version = compute(current, args.target)

    if args.dry_run:
        print(f"{current} -> {new_version} (dry run)")
        return 0

    write_version(new_version)
    print(f"Version: {current} -> {new_version}")
    print("Siguiente paso: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
