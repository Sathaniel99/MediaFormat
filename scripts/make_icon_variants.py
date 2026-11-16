"""Genera tres propuestas de icono definitivo para MediaFormat.

Cada propuesta se guarda como PNG (vista previa) y como ``.ico`` multi-resolucion
en ``resources/icon-variants/``. El usuario elige una y despues se copia a
``resources/icon.ico`` con ``scripts/make_icon.py --use <variante>``.

Uso::

    .\\.venv\\Scripts\\python.exe scripts\\make_icon_variants.py

Requiere Pillow y no usa red.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

CANVAS = 1024
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

VARIANT_NAMES = {
    "a-clasico": "Clásico refinado",
    "b-capas": "Fotos apiladas",
    "c-conversion": "Ciclo de conversión",
}


def _lerp(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(start, end, strict=True))  # type: ignore[return-value]


def _diagonal_gradient(
    size: int,
    start: tuple[int, int, int],
    end: tuple[int, int, int],
) -> Image.Image:
    """Degradado diagonal de la esquina superior izquierda a la inferior derecha."""
    image = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(image)
    span = size * 2 - 1
    for index in range(span):
        draw.line(
            [(index, 0), (0, index)],
            fill=_lerp(start, end, index / span),
        )
    return image


def _vertical_gradient(
    size: tuple[int, int],
    start: tuple[int, int, int],
    end: tuple[int, int, int],
) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        draw.line([(0, y), (width, y)], fill=_lerp(start, end, y / max(1, height - 1)))
    return image


def _tile(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    radius_ratio: float = 0.225,
) -> Image.Image:
    """Cuadrado redondeado con degradado y fondo transparente."""
    mask = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, CANVAS - 1, CANVAS - 1),
        radius=int(CANVAS * radius_ratio),
        fill=255,
    )
    tile = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    tile.paste(_diagonal_gradient(CANVAS, start, end), (0, 0), mask)
    return tile


def _highlight(tile: Image.Image, inset: float = 0.035) -> None:
    """Brillo sutil en el borde superior, como el cristal de Windows 11."""
    layer = Image.new("RGBA", tile.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    margin = int(CANVAS * inset)
    draw.rounded_rectangle(
        (margin, margin, CANVAS - margin, int(CANVAS * 0.46)),
        radius=int(CANVAS * 0.19),
        fill=(255, 255, 255, 26),
    )
    tile.alpha_composite(layer)


def _mountain(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    fill: tuple[int, int, int, int],
    width: int,
) -> None:
    draw.line(points, fill=fill, width=width, joint="curve")


def _variant_a() -> Image.Image:
    """Tile azul con marco de foto, sol y montanas (evolucion del provisional)."""
    tile = _tile((64, 156, 255), (0, 84, 166))
    _highlight(tile)
    draw = ImageDraw.Draw(tile)

    white = (255, 255, 255, 255)
    soft = (255, 255, 255, 120)
    stroke = int(CANVAS * 0.056)

    draw.rounded_rectangle(
        (int(CANVAS * 0.165), int(CANVAS * 0.205), int(CANVAS * 0.835), int(CANVAS * 0.795)),
        radius=int(CANVAS * 0.075),
        outline=white,
        width=stroke,
    )
    draw.rounded_rectangle(
        (int(CANVAS * 0.255), int(CANVAS * 0.315), int(CANVAS * 0.745), int(CANVAS * 0.685)),
        radius=int(CANVAS * 0.035),
        outline=soft,
        width=int(CANVAS * 0.018),
    )

    sun_x, sun_y, sun_r = CANVAS * 0.345, CANVAS * 0.400, CANVAS * 0.052
    draw.ellipse(
        (sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r),
        fill=white,
    )

    _mountain(
        draw,
        [
            (CANVAS * 0.225, CANVAS * 0.725),
            (CANVAS * 0.400, CANVAS * 0.505),
            (CANVAS * 0.520, CANVAS * 0.625),
            (CANVAS * 0.625, CANVAS * 0.505),
            (CANVAS * 0.775, CANVAS * 0.725),
        ],
        white,
        stroke,
    )
    return tile


def _rotated_card(
    body: tuple[int, int, int, int],
    image_color: tuple[int, int, int, int],
    angle: float,
    center: tuple[int, int],
    scale: float = 1.0,
) -> Image.Image:
    """Tarjeta de foto redondeada con un paisaje simple, rotada."""
    width, height = int(620 * scale), int(500 * scale)
    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    radius = int(58 * scale)
    draw.rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=radius,
        fill=body,
        outline=(255, 255, 255, 235),
        width=max(2, int(10 * scale)),
    )
    inner = (
        int(38 * scale),
        int(38 * scale),
        width - int(38 * scale),
        height - int(38 * scale),
    )
    draw.rounded_rectangle(inner, radius=int(32 * scale), fill=image_color)

    white = (255, 255, 255, 230)
    sun_r = int(30 * scale)
    sun_x, sun_y = int(150 * scale), int(155 * scale)
    draw.ellipse(
        (sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r),
        fill=white,
    )
    _mountain(
        draw,
        [
            (int(70 * scale), int(height * 0.80)),
            (int(220 * scale), int(height * 0.46)),
            (int(300 * scale), int(height * 0.62)),
            (int(370 * scale), int(height * 0.46)),
            (int(545 * scale), int(height * 0.80)),
        ],
        white,
        max(3, int(18 * scale)),
    )
    rotated = card.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    canvas.alpha_composite(
        rotated,
        (center[0] - rotated.width // 2, center[1] - rotated.height // 2),
    )
    return canvas


def _variant_b() -> Image.Image:
    """Tres fotos apiladas y ligeramente giradas, sin tile de fondo."""
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))

    shadow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (CANVAS * 0.20, CANVAS * 0.24, CANVAS * 0.80, CANVAS * 0.84),
        radius=int(CANVAS * 0.10),
        fill=(6, 20, 40, 95),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    canvas.alpha_composite(shadow)

    canvas.alpha_composite(
        _rotated_card(
            (124, 92, 255, 255),
            (196, 178, 255, 255),
            16.0,
            (int(CANVAS * 0.43), int(CANVAS * 0.47)),
            scale=0.86,
        )
    )
    canvas.alpha_composite(
        _rotated_card(
            (255, 116, 84, 255),
            (255, 190, 170, 255),
            -11.0,
            (int(CANVAS * 0.57), int(CANVAS * 0.50)),
            scale=0.90,
        )
    )
    canvas.alpha_composite(
        _rotated_card(
            (0, 120, 212, 255),
            (43, 136, 216, 255),
            4.0,
            (int(CANVAS * 0.50), int(CANVAS * 0.54)),
            scale=0.96,
        )
    )
    return canvas


def _polar(center: tuple[float, float], radius: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(degrees)
    return (
        center[0] + radius * math.cos(radians),
        center[1] + radius * math.sin(radians),
    )


def _arrow_head(
    draw: ImageDraw.ImageDraw,
    tip: tuple[float, float],
    tangent_degrees: float,
    size: float,
    color: tuple[int, int, int, int],
) -> None:
    """Triangulo solido que apunta en la direccion tangente."""
    left = math.radians(tangent_degrees + 145)
    right = math.radians(tangent_degrees - 145)
    points = [
        tip,
        (tip[0] + size * math.cos(left), tip[1] + size * math.sin(left)),
        (tip[0] + size * math.cos(right), tip[1] + size * math.sin(right)),
    ]
    draw.polygon(points, fill=color)


def _variant_c() -> Image.Image:
    """Tile oscuro con un ciclo de conversion y una foto en el centro."""
    tile = _tile((22, 34, 58), (9, 16, 31), radius_ratio=0.225)
    _highlight(tile)
    draw = ImageDraw.Draw(tile)

    center = (CANVAS / 2, CANVAS / 2)
    radius = CANVAS * 0.315
    box = (
        center[0] - radius,
        center[1] - radius,
        center[0] + radius,
        center[1] + radius,
    )
    width = int(CANVAS * 0.055)
    cyan = (56, 217, 255, 255)
    violet = (167, 139, 250, 255)
    draw.arc(box, start=205, end=335, fill=cyan, width=width)
    draw.arc(box, start=25, end=155, fill=violet, width=width)

    _arrow_head(
        draw,
        _polar(center, radius, 335),
        335 + 90,
        CANVAS * 0.085,
        cyan,
    )
    _arrow_head(
        draw,
        _polar(center, radius, 155),
        155 + 90,
        CANVAS * 0.085,
        violet,
    )

    card_w, card_h = CANVAS * 0.42, CANVAS * 0.34
    card = (
        center[0] - card_w / 2,
        center[1] - card_h / 2,
        center[0] + card_w / 2,
        center[1] + card_h / 2,
    )
    draw.rounded_rectangle(card, radius=int(CANVAS * 0.045), fill=(255, 255, 255, 255))
    inner = (
        card[0] + CANVAS * 0.035,
        card[1] + CANVAS * 0.035,
        card[2] - CANVAS * 0.035,
        card[3] - CANVAS * 0.035,
    )
    draw.rounded_rectangle(inner, radius=int(CANVAS * 0.028), fill=(0, 120, 212, 255))

    sun_x, sun_y, sun_r = CANVAS * 0.425, CANVAS * 0.435, CANVAS * 0.028
    draw.ellipse(
        (sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r),
        fill=(255, 255, 255, 235),
    )
    _mountain(
        draw,
        [
            (CANVAS * 0.375, CANVAS * 0.590),
            (CANVAS * 0.460, CANVAS * 0.485),
            (CANVAS * 0.525, CANVAS * 0.545),
            (CANVAS * 0.575, CANVAS * 0.485),
            (CANVAS * 0.650, CANVAS * 0.590),
        ],
        (255, 255, 255, 235),
        int(CANVAS * 0.030),
    )
    return tile


def build_variant(name: str) -> Image.Image:
    builders = {
        "a-clasico": _variant_a,
        "b-capas": _variant_b,
        "c-conversion": _variant_c,
    }
    return builders[name]()


def write_variants(root: Path) -> list[Path]:
    """Escribe PNG de vista previa y ``.ico`` de cada propuesta."""
    out_dir = root / "resources" / "icon-variants"
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in VARIANT_NAMES:
        image = build_variant(name)
        preview = out_dir / f"{name}.png"
        image.resize((512, 512), Image.Resampling.LANCZOS).save(preview, format="PNG")
        icon = out_dir / f"{name}.ico"
        image.save(icon, format="ICO", sizes=ICON_SIZES)
        written.extend([preview, icon])
    return written


def main(argv: list[str] | None = None) -> int:
    _ = argv
    root = Path(__file__).resolve().parent.parent
    written = write_variants(root)
    for path in written:
        print(f"Escrito {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
