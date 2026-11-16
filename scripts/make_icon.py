"""Genera el icono definitivo de MediaFormat (variante C, multi-resolucion).

El diseno elegido es el "ciclo de conversion": tile oscuro, dos flechas
curvas cian/violeta y una foto en el centro. La logica de dibujo vive en
``scripts/make_icon_variants.py`` para poder regenerar las tres propuestas.

Uso::

    .\\.venv\\Scripts\\python.exe scripts\\make_icon.py [salida.ico]

Requiere Pillow y no usa red.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

try:  # ejecutado como ``python scripts/make_icon.py``
    from make_icon_variants import CANVAS, build_variant
except ImportError:  # importado como ``scripts.make_icon``
    from scripts.make_icon_variants import CANVAS, build_variant

ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
CHOSEN_VARIANT = "c-conversion"


def draw_icon(size: int = CANVAS) -> Image.Image:
    """Devuelve el icono elegido a ``size`` px, con transparencia fuera del tile."""
    icon = build_variant(CHOSEN_VARIANT)
    if size != CANVAS:
        icon = icon.resize((size, size), Image.Resampling.LANCZOS)
    return icon


def write_icon(path: Path) -> Path:
    """Escribe el ``.ico`` multi-resolucion y lo devuelve."""
    path.parent.mkdir(parents=True, exist_ok=True)
    draw_icon(CANVAS).save(path, format="ICO", sizes=ICON_SIZES)
    return path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parent.parent
    target = Path(args[0]) if args else root / "resources" / "icon.ico"
    write_icon(target)
    print(f"Icono escrito en {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
