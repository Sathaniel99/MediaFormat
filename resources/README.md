# resources/

Iconos y otros recursos empaquetados con la aplicacion.

## `icon.ico`

- Icono **definitivo**: variante **C — Ciclo de conversión** (tile oscuro con dos
  flechas cian/violeta y una foto en el centro).
- Formato: `.ico` multi-resolucion (16, 24, 32, 48, 64, 128 y 256 px).
- Lo genera `scripts/make_icon.py` (Pillow, sin red), que reutiliza el dibujo de
  `scripts/make_icon_variants.py`:

```powershell
.\.venv\Scripts\python.exe scripts\make_icon.py
```

- `scripts/build.ps1` lo usa como icono del `.exe` (`--icon`) y lo embebe para
  que la ventana lo cargue en tiempo de ejecucion (`--add-data`).

Para cambiar de variante, edita `CHOSEN_VARIANT` en `scripts/make_icon.py`,
regenera el `.ico` y recompila.

## `icon-variants/`

Las tres propuestas que se evaluaron, generadas por
`scripts/make_icon_variants.py`:

| Variante | Archivo | Idea | Estado |
|---|---|---|---|
| A | `a-clasico.png` | Tile azul con marco de foto, sol y montanas | Descartada |
| B | `b-capas.png` | Tres fotos apiladas y giradas, sin tile | Descartada |
| C | `c-conversion.png` | Tile oscuro con ciclo de conversion y foto central | **Elegida** |

Cada una tiene su `.png` (vista previa 512 px) y su `.ico` multi-resolucion. Se
conservan como referencia y para poder volver a generar cualquiera de ellas.
