# 06 — Build y versionado

## La regla del proyecto

> **Todo fix o feature termina con una compilación.** El agente no decide la
> versión: el usuario elige entre *rebuild* de la versión actual o *nueva
> versión*.

Esta regla está en `AGENTS.md` porque no es una sugerencia: un cambio sin
ejecutable actualizado se considera **incompleto**.

## Flujo obligatorio

```powershell
# 1. Tests y lint en verde
& .\.venv\Scripts\python.exe -m unittest discover -s tests -t .
& .\.venv\Scripts\ruff.exe check app tests scripts main.py

# 2. CHANGELOG.md actualizado (sección Unreleased o versión nueva)

# 3. Preguntar al usuario: ¿rebuild o nueva versión?
#    Rebuild  -> seguir al paso 5
#    Nueva    -> paso 4

# 4. Subir versión (solo si el usuario lo pidió)
& .\.venv\Scripts\python.exe scripts\bump_version.py patch   # o minor / major / x.y.z

# 5. Compilar (la UI actual usa -Windowed: sin consola)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1 -Windowed
# 6. Verificar
Get-Content dist\build_info.json
```

Si los tests fallan, **no se compila**. `-SkipTests` existe solo para una
emergencia autorizada explícitamente por el usuario.

## Versión: fuente única

- `app/version.py` → `__version__` es la fuente de verdad.
- `pyproject.toml` → `[project].version` se actualiza en el mismo comando.
- `scripts/bump_version.py patch|minor|major|x.y.z` mantiene ambos sincronizados.
- **Nunca** editar `app/version.py` a mano.
- `scripts/build.ps1 -Version x.y.z` falla si no coincide con la fuente: el
  nombre del ejecutable nunca miente.

SemVer aplicado a este proyecto:

| Cambio | Salto |
|---|---|
| Fix de comportamiento sin API nueva | `patch` |
| Feature nueva compatible | `minor` |
| Cambio incompatible (formato de `.ini`, CLI) | `major` |

## Qué hace `scripts/build.ps1`

1. Comprueba que existe `.venv` (si no, aborta).
2. Lee la versión de `app/version.py` y valida `-Version` si se pasó.
3. `-Clean` opcional: borra `build/` y `dist/`.
4. Ejecuta los tests (`unittest`) salvo `-SkipTests`.
5. Ejecuta PyInstaller:
   - `--onefile` por defecto; `-Onedir` cambia a carpeta `--onedir`.
   - `--console` por defecto; `-Windowed` para la app gráfica.
   - `--icon resources\icon.ico` si existe.
   - `--add-data resources\icon.ico;resources` para que la UI lo cargue en
     tiempo de ejecución.
   - `--exclude-module` para Qt no usado (`QtNetwork`, `QtQml`, `QtQuick`,
     `QtSql`, `QtOpenGL`, `QtSvg`, `QtPdf`, `QtWebEngine*`…) y `tkinter`.
   - `--version-file build\version_info.txt`, generado por
     `scripts/make_version_info.py` con la versión de `app/version.py`.
   - `--workpath build/`, `--specpath build/`, `--optimize 1`.
6. Verifica que existe el ejecutable (en `dist\` o en la carpeta `--onedir`).
7. Escribe `dist\build_info.json`.

### `build_info.json`

```json
{
  "app": "MediaFormat",
  "version": "0.2.0",
  "built_at": "2026-11-15T12:55:34-05:00",
  "python": "3.14.2",
  "commit": "n/a",
  "windowed": true,
  "mode": "onefile",
  "exe": "dist/MediaFormat-0.2.0.exe",
  "size_mb": 43.5,
  "bundle_mb": 43.5,
  "sha256": "…"
}
```

`size_mb` es el `.exe`; `bundle_mb` suma toda la carpeta en modo `onedir`.
`commit` queda en `n/a` hasta que el proyecto sea un repo git.

## Parámetros

| Parámetro | Efecto |
|---|---|
| `-Version x.y.z` | Falla si no coincide con `app/version.py` |
| `-Windowed` | Sin consola (UI final). Un `.exe` windowed no imprime en terminal: usa un build `--console` para depurar la CLI |
| `-SkipTests` | Omite tests (solo emergencia autorizada) |
| `-Clean` | Borra `build/` y `dist/` antes de compilar |
| `-Onedir` | Carpeta `--onedir` en vez de `--onefile`; sirve para comparar tamaño y arranque |

## Tamaño y arranque

- `--onefile` descomprime en `%TEMP%` al arrancar: primer inicio más lento que
  `--onedir`, pero distribución de un solo archivo.
- `--onedir` arranca antes (no descomprime), pero distribuye una carpeta con
  DLLs y plugins. Se mide con `-Onedir` y se comparan `size_mb`/`bundle_mb` y el
  tiempo hasta que aparece la ventana.
- Los `--exclude-module` recortan los módulos Qt que la app no importa. No se
  excluyen `QtCore`, `QtGui`, `QtWidgets`, los plugins de plataforma ni los
  formatos de imagen.
- Cualquier exclusión nueva debe probarse con un build `-Windowed` real: la
  ventana debe abrir y convertir una imagen antes de darla por buena.

### Comparación medida (0.2.0)

Medición en este equipo, con `Start-Process` y sondeo de `MainWindowTitle` hasta
que la ventana existe. En `--onefile` el título lo publica el proceso hijo que
crea el bootloader, no el proceso lanzado.

| Modo | `.exe` | Bundle | Arranque (2.ª/3.ª ejecución) | Primer arranque |
|---|---|---|---|---|
| `onefile` (por defecto) | 43.5 MB | 43.5 MB | ~10.8–11.7 s | ~11.7 s |
| `onedir` (`-Onedir`) | 3.2 MB | 105.7 MB | ~4.8–5.0 s | ~8.0 s |

- `onefile` tarda más porque extrae el bundle en `%TEMP%`; sigue siendo el modo
  de distribución por ser un solo archivo.
- `onedir` arranca casi al doble de velocidad, pero ocupa 105.7 MB en carpeta.
- Los tiempos incluyen el escaneo de Defender; varían entre equipos y no son
  una medida objetiva de rendimiento del código.

## Entorno

- **Sin red**: todas las dependencias están en `wheels/` y ya instaladas en
  `.venv`. Reconstruir el entorno:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links wheels -r requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-index --find-links wheels -r requirements-dev.txt
```

- PyInstaller 6.22.3 + `pyinstaller-hooks-contrib` 2026.10 ya cubren Pillow y
  PySide6; no hace falta hook propio.

- Los metadatos del `.exe` (nombre, versión, descripción) salen de
  `scripts/make_version_info.py`; no se editan a mano.

> En este equipo **no está instalado `pwsh`**. Usa siempre
> `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1`.

## Estado de los builds

| Versión | Fecha | Ejecutable | Tamaño | Modo | Contenido / smoke test |
|---|---|---|---|---|---|
| `0.1.0` | 2026-11-15 | `dist\MediaFormat-0.1.0.exe` | 15.9 MB | consola | solo CLI; `formats` + PNG → JPEG |
| `0.1.1` | 2026-11-15 | `dist\MediaFormat-0.1.1.exe` | 44.1 MB | ventana | UI Qt + CLI; ventana real y PNG → WebP |
| `0.1.2` | 2026-11-15 | `dist\MediaFormat-0.1.2.exe` | 44.1 MB | ventana | icono provisional, metadatos del `.exe`, barra de titulo oscura; CLI y ventana verificadas |
| `0.1.3` | 2026-11-15 | `dist\MediaFormat-0.1.3.exe` | 44.1 MB | ventana | selector de acento (7 colores) persistido en el `.ini`; CLI y ventana verificadas |
| `0.2.0` | 2026-11-15 | `dist\MediaFormat-0.2.0.exe` | 43.5 MB | ventana | Fase 4 completa, icono definitivo (variante C); ventana, icono, metadatos y PNG → JPEG verificados |
| `0.2.0` (`-Onedir`) | 2026-11-15 | `dist\MediaFormat-0.2.0\MediaFormat-0.2.0.exe` | 3.2 MB (105.7 MB bundle) | ventana | build de comparación; ventana verificada |
| `0.2.1` | 2026-11-15 | `dist\MediaFormat-0.2.1.exe` | 43.5 MB | ventana | fixes de UI: selects, engranaje, ventana al 70 %, calidad en el panel de conversión, salida de solo lectura y cola como drop target; arranque verificado |
| `1.0.0` | 2026-11-15 | `dist\MediaFormat-1.0.0.exe` | 43.5 MB | ventana | primera versión estable: ventana centrada con borde nativo compensado; arranque verificado (delta de centro 0,5 px en X, 0 px en Y); SHA-256 `6BC1C68A…85BBF5` |

`dist\build_info.json` se genera con el hash SHA-256 del ejecutable. `build/` y
`dist/` están en `.gitignore`; el `.exe` se regenera, no se versiona.

## Antes de publicar (checklist)

- [ ] `CHANGELOG.md` con la versión y fecha.
- [ ] Tests verdes y lint limpio.
- [ ] `build_info.json` con la versión correcta.
- [ ] Ejecutable probado a doble clic en una carpeta limpia.
- [ ] Conversión real de al menos 5 archivos desde el `.exe`.
- [ ] El `.exe` **no** se copia fuera de `dist/` sin pedirlo al usuario.
