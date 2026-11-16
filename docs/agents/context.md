# Contexto del proyecto (para agentes)

> Actualízalo al cerrar cada fase o cuando cambie el entorno. Es la primera cosa
> que un agente debe leer después de `AGENTS.md`.

## Snapshot

| Dato | Valor |
|---|---|
| Proyecto | MediaFormat — conversor de imágenes de escritorio |
| Fase actual | **Fases 1–4 completadas** |
| Versión | `1.0.0` (`app/version.py`) |
| Python | 3.14.2 (`.venv` local) |
| Qt | PySide6-Essentials 6.12.0 |
| Imagen | Pillow 12.3.0 (WebP ✅, AVIF ✅) |
| Empaquetado | PyInstaller 6.22.3 (build 1.0.0 onefile validado, 43.5 MB) |
| Lint | ruff 0.17.4 |
| Tests | 126, `unittest`, verdes, ~14 s (34 de UI en `offscreen`) |
| Red | **No disponible** (`pypi.org:443` no responde) |
| Git | Repositorio `Sathaniel99/MediaFormat`, rama `main`, remoto `origin` |

## Rutas reales en este equipo

| Elemento | Ruta |
|---|---|
| Proyecto | `C:\Users\Sathaniel\Cosas\PROGRAMACION\MediaFormat` |
| Config | `%APPDATA%\MediaFormat\config.ini` |
| Cola | `%LOCALAPPDATA%\MediaFormat\queue.json` |
| Log | `%LOCALAPPDATA%\MediaFormat\logs\mediaformat.log` |
| Salida por defecto | `C:\Users\Sathaniel\Documents\MediaFormat` |
| Wheels | `wheels/` (7 wheels, ~100 MB, no versionado) |

## Qué está hecho

- Estructura de carpetas, `.gitignore`, `pyproject.toml`, requirements.
- `.venv` reparado (venía clonado de otro proyecto): metadata, scripts de
  activación y ejecutables regenerados. Se quitaron Addons/WebEngine/Pdf.
- `app/models.py`, `app/paths.py`, `app/config.py`, `app/converter.py`,
  `app/logging_setup.py`, `app/cli.py`.
- 50 tests iniciales (`unittest`), lint y formato limpios. Los de UI corren con
  `QT_QPA_PLATFORM=offscreen`.
- Smoke test real: 3 PNG → WEBP por CLI.
- Fase 2: UI Qt completa en `app/ui/` (ventana, cola con miniaturas,
  delegados, worker, tema claro/oscuro/sistema, iconos vectoriales).
- `main.py` sin argumentos abre la ventana; con subcomando ejecuta la CLI.
- `scripts/build.ps1` y `scripts/bump_version.py`.
- Primer build validado: `dist/MediaFormat-0.1.0.exe` (15.9 MB, consola).
- Build 0.1.1 windowed validado: `dist/MediaFormat-0.1.1.exe` (44.1 MB) con
  ventana real y conversión PNG → WebP desde el ejecutable.
- Fase 3: icono multi-resolución (`resources/icon.ico`), identidad de taskbar +
  barra de título oscura (`app/ui/branding.py`) y metadatos de versión incrustados
  en el `.exe` (`scripts/make_version_info.py`).
- Build 0.1.2 validado: icono dentro del ejecutable, propiedades del `.exe`
  correctas y CLI/ventana funcionando.
- Selector de acento (7 colores) junto al botón de tema, persistido en
  `[app].accent`; paletas claro/oscuro por acento en `app/ui/theme.py`.
- Build 0.1.3 validado: selector de acento empaquetado, CLI PNG → JPEG y
  ventana real funcionando.
- Fase 4: perfiles integrados + personalizados, cola persistente, reintento de
  fallidos, cancelación por archivo, reordenación y multiselección, diálogo de
  ajustes, banner del `.ini`, acento de Windows, geometría/maximizado,
  i18n es/en, notificación nativa y `-Onedir` en el build.
- 126 tests (`unittest`), lint y formato limpios.
- Icono definitivo: variante **C — Ciclo de conversión** (tile oscuro, flechas
  cian/violeta y foto central), generada por `scripts/make_icon.py`; las
  propuestas quedan en `resources/icon-variants/`.
- Build 0.2.0 onefile validado: `dist\MediaFormat-0.2.0.exe` (43.5 MB), ventana,
  icono, metadatos y conversión PNG → JPEG verificados. Comparación con
  `-Onedir` anotada en `docs/06-build.md`.
- Build 0.2.1 validado (`dist\MediaFormat-0.2.1.exe`, 43.5 MB): selects con
  hover/foco, engranaje, ventana al 70 %, calidad con presets en el panel de
  conversión, salida de solo lectura y cola como drop target. La ventana se abre
  siempre centrada (salvo maximizada): la posición guardada se ignora y el
  centrado compensa el borde invisible de Windows.
- Build **1.0.0** validado (`dist\MediaFormat-1.0.0.exe`, 43.5 MB, onefile):
  primera versión estable, centrado real medido (0,5 px en X y 0 px en Y) y
  release publicado en GitHub con el ejecutable adjunto.
- Documentación `docs/01`–`docs/07`, ADRs 0001–0003 y esta guía.

## Qué falta

| Tarea | Dónde |
|---|---|
| Revisión visual fina (espaciados, contraste) | `app/ui/theme.py`, `docs/05-ui.md` |
| `git init` + primer commit | Solo si el usuario lo pide |
| HEIC/HEIF | Requiere `pillow-heif` (no disponible offline) |
| Funciones de pago | `De_pago.txt` (solo ideas, nada implementado) |

## Decisiones vigentes

- Motor sin Qt; UI encima (`ADR 0001`, `ADR 0003`).
- `.ini` en `%APPDATA%`, sin interpolación, sin comentarios inline
  (`ADR 0002`).
- La cola es caché de sesión en `%LOCALAPPDATA%`, separada del `.ini`.
- Textos de UI en `app/i18n.py`; el motor sigue en español.
- Perfiles integrados en código; los personalizados son JSON en `[profiles]`.
- La calidad se elige en el panel de conversión (presets; «Máxima» por defecto); Ajustes no la edita.
- La cola es el único destino de drag & drop; vacía imita la antigua drop zone.
- Documents vía `SHGetKnownFolderPath` (OneDrive-safe).
- Tests con `unittest`, no pytest (offline).
- Versión la decide el usuario; el agente pregunta siempre.

## Trampas conocidas

- **PowerShell**: no soporta heredocs (`<<'PY'`). Usa archivos temporales o la
  herramienta de escritura.
- **`%APPDATA%` en tests**: siempre pasar `Config(path_temporal)`.
- **`#FFFFFF`**: es un color; no activar comentarios inline en `configparser`.
- **`Image.SAVE`**: hay que llamar a `Image.init()` antes de consultarlo
  (`available_formats()` ya lo hace).
- **Nombres de wheel**: los de `F:\...\Librerias python` son `cp313`; este venv
  es `cp314`. Usar `wheels/`.
- **PySide6 meta-package**: desinstalarlo elimina `PySide6/__init__.py`; si se
  reinstala Essentials, usar `--force-reinstall --no-deps`.
- **`ruff format` y `line-ending`**: el proyecto usa LF; no mezclar CRLF.

## Cómo verificar que el entorno sigue sano

```powershell
$py = ".\.venv\Scripts\python.exe"

& $py -c "import sys, PIL, PySide6; from PIL import features; print(sys.version.split()[0], PIL.__version__, PySide6.__version__, features.check('webp'), features.check('avif'))"
& $py -m unittest discover -s tests -t .
& $py -m ruff check app tests scripts main.py
```

Salida esperada: `3.14.2 12.3.0 6.12.0 True True`, `OK`, `All checks passed!`.
