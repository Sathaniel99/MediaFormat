# 04 — Conversión y formatos

## Matriz de soporte

Se calcula en runtime con `available_formats()` y `Image.SAVE`, así que una
versión de Pillow sin AVIF simplemente no lo muestra.

| Formato | Extensión | Calidad | Alfa | Animación |
|---|---|---|---|---|
| JPEG | `.jpg` | ✅ | ❌ (se aplana) | ❌ |
| PNG | `.png` | — | ✅ | ✅ |
| WEBP | `.webp` | ✅ | ✅ | ✅ |
| BMP | `.bmp` | — | ❌ | ❌ |
| TIFF | `.tiff` | — | ✅ | ✅ |
| GIF | `.gif` | — | ✅ (1 bit) | ✅ |
| ICO | `.ico` | — | ✅ | ❌ |
| TGA | `.tga` | — | ✅ | ❌ |
| AVIF | `.avif` | ✅ | ✅ | ❌ |

Lectura: cualquier formato registrado en Pillow (incluye `jpg/jpeg, png, webp,
bmp, tiff, gif, ico, tga, ppm/pgm/pbm, avif`). La extensión no decide nada: se
detecta el formato real al abrir.

## Pipeline

1. **Validación**: existe, es archivo, se puede leer.
2. **Destino**: `carpeta / nombre + extensión`; si coincide con el origen se usa
   `nombre_converted`; luego se aplica `on_conflict`.
3. **Apertura**: `Image.open` + `load()`; se registra `n_frames`, EXIF e ICC.
4. **Orientación**: `ImageOps.exif_transpose` solo en imágenes estáticas.
5. **Modo**:
   - JPEG/BMP/GIF: se aplana alfa sobre el color de fondo.
   - ICO: RGBA.
   - PNG/WEBP/TIFF/TGA/AVIF: conserva alfa si existe.
   - `P` con transparencia → `RGBA`; sin transparencia → `RGB`.
   - `CMYK` → `RGB`; `LA` → `RGBA`.
6. **Guardado** con parámetros por formato (ver abajo).
7. **Resultado**: `ConversionResult` con tamaños, duración, fotogramas y notas.

## Parámetros de guardado

| Formato | Opciones |
|---|---|
| JPEG | `quality`, `subsampling`, `optimize=True`, `progressive=True` |
| WEBP | `quality` o `lossless=True`; `method=4` |
| AVIF | `quality` |
| PNG | `compress_level` 0–9 |
| TIFF | `compression="tiff_lzw"` |
| GIF/BMP/ICO/TGA | valores por defecto de Pillow |

Metadatos: EXIF se pasa a JPEG/PNG/WEBP/AVIF (también en animaciones); ICC a
JPEG/PNG/WEBP/TIFF/AVIF. Al aplicar orientación se eliminan los bytes EXIF
originales antes de reinyectarlos, para que los visores no roten dos veces. Si
Pillow rechaza los metadatos, se reintenta sin ellos y se añade una nota al
resultado (nunca se pierde la conversión por un EXIF raro).

## Animaciones

- `animated_frames = false` (default): se convierte el **primer fotograma** y se
  anota "solo se convirtio el primer fotograma".
- `animated_frames = true` y destino con animación: se copian todos los
  fotogramas con sus duraciones y el `loop` original.
- Destino sin animación (JPEG, ICO...): primer fotograma.
- La orientación EXIF no se aplica a animaciones (evita desincronizar frames).

## Nombres y colisiones

| Política | Comportamiento |
|---|---|
| `rename` (default) | `foto.webp`, `foto_1.webp`, `foto_2.webp`… |
| `overwrite` | Reemplaza el destino existente |
| `skip` | No hace nada y devuelve `SKIPPED` |

Nunca se escribe sobre el archivo de origen, ni siquiera con `overwrite`. En un
lote, los destinos se reservan con un bloqueo antes de escribir: dos archivos
con el mismo nombre no pueden acabar en el mismo destino. Si falla una escritura
ya iniciada, se borra el archivo parcial para no dejar una salida corrupta.

## Errores y notas

| Mensaje | Causa |
|---|---|
| `formato de imagen no reconocido o archivo danado` | Bytes inválidos / truncados |
| `imagen demasiado grande...` | `DecompressionBombError` de Pillow |
| `sin permisos para leer o escribir el archivo` | ACL / archivo bloqueado |
| `error de disco: ...` | Ruta inexistente, disco lleno |
| `memoria insuficiente...` | Imagen que no cabe en RAM |

Notas posibles: `solo se convirtio el primer fotograma`,
`orientacion EXIF no aplicable`, `metadatos omitidos (...)`, `N fotogramas`.

## Rendimiento

- La conversión se paraleliza con hilos (`max_workers`), pero el cuello real
  suele ser el disco.
- Imágenes > 100 MP pueden tardar y consumir mucha RAM; el límite de Pillow
  (`Image.MAX_IMAGE_PIXELS`) protege contra bombas de descompresión.
- El formato de salida más lento por defecto es TIFF LZW por el tamaño de los
  buffers; para lotes grandes, WebP suele ser el mejor equilibrio.

## Añadir un formato nuevo

1. Añade el valor a `OutputFormat` y sus capacidades en `models.py`.
2. Define extensión y kwargs en `converter._format_kwargs`.
3. Añade metadatos (EXIF/ICC) si aplica.
4. Añade el formato a `config.example.ini` y a `docs/03`.
5. Test de ida y vuelta en `tests/test_converter.py`.
