# 03 — Configuración `.ini`

## Ubicación y ciclo de vida

| Elemento | Ruta |
|---|---|
| Archivo activo | `%APPDATA%\MediaFormat\config.ini` |
| Copia de seguridad si está corrupto | `config.ini.bak` (mismo directorio) |
| Log | `%LOCALAPPDATA%\MediaFormat\logs\mediaformat.log` |
| Cola persistente | `%LOCALAPPDATA%\MediaFormat\queue.json` |
| Plantilla documentada | `config.example.ini` |

- Se crea en el primer arranque con los valores por defecto.
- Se guarda de forma atómica (`.tmp` + `os.replace`).
- Si el archivo no se puede crear, la app avisa pero sigue con defaults en memoria.
- Si el parseo falla, se renombra a `.bak` y se usan defaults.
- **Se reescribe completo al guardar**: los comentarios manuales se pierden. Para
  conservarlos, edita el archivo solo mientras la app está cerrada.

## Reglas de formato

- Codificación UTF-8, saltos `\n`.
- Comentarios **solo en línea completa**, con `;` o `#`.
- **No hay comentarios al final de línea**: `background = #FFFFFF` es un color.
- Rutas: admiten `%VARIABLES%` y `~`.
- Booleanos aceptados: `true/false`, `1/0`, `yes/no`, `on/off`.
- Valores fuera de rango se recortan y se anotan en `Config.warnings`.

## Referencia

### `[app]`

| Clave | Tipo | Default | Efecto |
|---|---|---|---|
| `theme` | `system\|light\|dark` | `system` | Tema de la UI |
| `accent` | `system\|blue\|red\|green\|yellow\|purple\|pink\|brown` | `blue` | Color de acento de la UI |
| `language` | `es\|en` | `es` | Idioma de la interfaz |
| `notify_on_finish` | bool | `true` | Notificación nativa al terminar un lote |
| `restore_queue` | bool | `true` | Recuperar la lista al volver a abrir |
| `version` | entero | `2` | Versión del esquema del archivo; si no coincide se repara y se avisa |

`accent` elige la paleta de acento (botones primarios, sliders, progreso,
toggles y selección) tanto en tema claro como oscuro. `system` lee el color de
acento de Windows (`ColorizationColor`) y lo aproxima al más cercano de la
paleta; un valor desconocido vuelve a `blue` y se anota en `Config.warnings`.

`language` se aplica **al reiniciar**: los textos ya construidos no se traducen
en caliente. Los textos viven en `app/i18n.py`; el motor mantiene sus mensajes
en español.

`notify_on_finish` usa `QSystemTrayIcon.showMessage`; si el sistema no tiene
bandeja disponible, se ignora sin error. `restore_queue` controla la cola de
`queue.json`: al arrancar se descartan las rutas que ya no existen y los estados
`running` se degradan a `pending`.

### `[output]`

| Clave | Tipo | Default | Efecto |
|---|---|---|---|
| `folder` | ruta | `Documents\MediaFormat` | Destino de las conversiones |
| `open_after_convert` | bool | `false` | Abrir la carpeta al terminar |
| `on_conflict` | `rename\|overwrite\|skip` | `rename` | Qué hacer si el destino existe |

`folder` por defecto se resuelve con `SHGetKnownFolderPath(FOLDERID_Documents)`,
no concatenando `%USERPROFILE%\Documents`. Eso cubre OneDrive. Una variable
`%VARIABLE%` sin definir se repara al valor por defecto y genera un aviso en el
banner; así no se crea una carpeta literal en el directorio de trabajo.

### `[format]`

| Clave | Tipo | Default | Efecto |
|---|---|---|---|
| `default` | formato | `WEBP` | Formato preseleccionado |

Valores válidos: `JPEG`, `PNG`, `WEBP`, `BMP`, `TIFF`, `GIF`, `ICO`, `TGA`,
`AVIF` (AVIF solo si `PIL.features.check("avif")` es verdadero).

### `[jpeg]`

| Clave | Tipo | Default | Rango | Efecto |
|---|---|---|---|---|
| `quality` | entero | `95` | 1–100 | Calidad con pérdida |
| `subsampling` | `4:4:4\|4:2:2\|4:2:0` | `4:2:0` | — | Croma subsampling |
| `background` | `#RRGGBB` o `r,g,b` | `#FFFFFF` | 0–255 | Fondo al aplanar alfa |

### `[webp]`

| Clave | Tipo | Default | Efecto |
|---|---|---|---|
| `quality` | entero 1–100 | `95` | Calidad con pérdida |
| `lossless` | bool | `false` | WebP sin pérdida (ignora calidad) |

### `[png]`

| Clave | Tipo | Default | Rango | Efecto |
|---|---|---|---|---|
| `compress_level` | entero | `6` | 0–9 | 0 rápido, 9 máximo |

### `[processing]`

| Clave | Tipo | Default | Efecto |
|---|---|---|---|
| `keep_metadata` | bool | `true` | Copia EXIF e ICC cuando el destino lo permite |
| `apply_exif_orientation` | bool | `true` | Rota según orientación EXIF |
| `max_workers` | entero 1–16 | `4` | Hilos de conversión |
| `recursive_folders` | bool | `true` | Incluye subcarpetas |
| `animated_frames` | bool | `false` | Conserva animaciones si el destino lo soporta |

### `[ui]`

| Clave | Tipo | Default | Efecto |
|---|---|---|---|
| `thumbnails` | bool | `true` | Miniaturas en la lista |
| `window_geometry` | `WxH` | vacío | Tamaño recordado; vacío = 70 % de la pantalla |
| `window_x` | entero | `-1` | Obsoleto; se ignora (la ventana se abre centrada) |
| `window_y` | entero | `-1` | Obsoleto; se ignora (la ventana se abre centrada) |
| `window_maximized` | bool | `false` | Reabrir maximizada |

La ventana se abre siempre centrada en la pantalla principal cuando no está
maximizada; el tamaño sí se restaura. Si `window_geometry` está vacía o contiene
una geometría antigua (`900x640`, `1040x780`), se usa el 70 % del área útil con
un mínimo de 940×700. `window_x` y `window_y` se conservan solo por
compatibilidad con archivos antiguos y no se aplican.

### `[profiles]`

Cada clave es un perfil personalizado y su valor es un JSON de una línea:

```ini
[profiles]
mi-perfil = {"output_format": "JPEG", "quality": 85, "lossless": false}
```

Campos admitidos: `output_format`, `quality`, `lossless`, `animated`,
`jpeg_subsampling`, `png_compress_level`. Los valores fuera de rango se
recortan al cargar y un JSON inválido se ignora sin romper la app. Los cuatro
perfiles integrados (Web, Impresión, Redes, Telegram/Discord) no se guardan en
el `.ini`: viven en `app/profiles.py` y no se pueden borrar.

## Mapeo a la conversión

`Config.conversion_options(fmt)` aplica:

- `quality`: `[jpeg].quality` para JPEG; `[webp].quality` para WEBP/AVIF.
- `lossless`: solo WEBP, desde `[webp].lossless` (AVIF usa `quality`).
- `background`: `[jpeg].background` (se usa al convertir a JPEG/BMP/GIF).
- `on_conflict`, `keep_metadata`, `apply_exif_orientation`, `animated`,
  `png_compress_level` y `jpeg_subsampling` desde sus secciones.

## Diagnóstico

```powershell
.\.venv\Scripts\python.exe main.py config          # resumen
.\.venv\Scripts\python.exe main.py config --show   # todos los valores + avisos
```

## Añadir una clave nueva

1. Añádela a `default_values()` y al template de `Config.render()`.
2. Crea la propiedad tipada en `Config`.
3. Actualiza `config.example.ini`.
4. Documenta en este archivo.
5. Añade un test en `tests/test_config.py`.
