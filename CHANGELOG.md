# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
La version sigue [SemVer](https://semver.org/lang/es/).

Regla: todo fix o feature anota aqui su cambio **antes** de compilar.
La decision de subir version (y con ello crear una entrada nueva) es del usuario.

## [1.0.0] - 2026-11-15

Primera versión estable de MediaFormat. Recoge todo lo publicado en 0.2.1 y el
pulido final de la interfaz.

### Changed

- La ventana se abre siempre centrada (salvo maximizada), ignorando cualquier
  posición guardada por versiones anteriores y compensando el borde nativo de
  Windows.

## [0.2.1] - 2026-11-15

### Added

- Presets de calidad en el panel de conversión: «Máxima calidad» (95, por
  defecto), «Alta» (85), «Media» (75) y «Baja» (60); un perfil con otro valor
  aparece como «Personalizada (N)».

### Changed

- Los campos de selección (perfil, formato, calidad, conflictos, tema, idioma…)
  usan `SelectComboBox` con chevron propio y estados hover/foco visibles.
- El icono de Ajustes es un engranaje estándar de ocho dientes con hueco central.
- La ventana se abre al 70 % del área útil de la pantalla (mínimo 940×700); las
  geometrías antiguas `900x640`/`1040x780` se sustituyen por ese tamaño.
- Las calidades por defecto pasan a 95 para JPEG y WebP/AVIF.
- «Guardar en» es de solo lectura y se cambia únicamente con «Elegir carpeta»,
  tanto en la ventana principal como en Ajustes.
- La calidad deja de editarse en Ajustes: solo vive en el panel de conversión.

### Removed

- El campo independiente de drag & drop (`app/ui/drop_zone.py`): la cola es el
  destino de arrastre y, vacía, pinta la tarjeta punteada con clic para explorar.

### Fixed

- La ventana se abre siempre centrada (salvo maximizada): ignora cualquier
  posición guardada por versiones anteriores y centra el marco nativo —incluido
  el borde invisible de Windows—, por lo que ya no aparece desplazada.
- El arrastre a la cola añade siempre al final y conserva el resaltado de borde
  mientras dura el arrastre.

## [0.2.0] - 2026-11-15

### Added

- Perfiles de conversión: cuatro integrados (Web, Impresión, Redes,
  Telegram/Discord) y perfiles personalizados guardados como JSON en
  `[profiles]` del `.ini`.
- Cola persistente en `%LOCALAPPDATA%\MediaFormat\queue.json`: al reabrir se
  recuperan las rutas existentes y los estados `running` vuelven a `pending`.
- Reintento de archivos fallidos (botón y menú contextual) sin relanzar todo el
  lote.
- Cancelación por archivo: los seleccionados que aún no han empezado se omiten;
  el que ya está convirtiendo termina.
- Reordenación de filas arrastrando y multiselección con acciones por lote.
- Diálogo de ajustes (`Ctrl+,`) para apariencia, conversión, salida y
  comportamiento.
- Banner de avisos cuando el `.ini` trae valores inválidos reparados al cargar.
- Acento `system`: lee `ColorizationColor` de Windows y lo aproxima a la paleta.
- La ventana recuerda posición, tamaño y estado maximizado.
- Interfaz en español e inglés (`[app].language`), aplicada al reiniciar.
- Notificación nativa al terminar un lote (`QSystemTrayIcon`), configurable.
- Tres propuestas de icono definitivo en `resources/icon-variants/` y script
  `scripts/make_icon_variants.py` para regenerarlas. Se adopta la variante C
  («ciclo de conversión») como `resources/icon.ico`.
- `-Onedir` en `scripts/build.ps1` para comparar tamaño y arranque con
  `--onefile`.
- Tests de perfiles, cola, i18n, cancelación por archivo y nuevas acciones de
  UI (115 en total).

### Changed

- `scripts/build.ps1` excluye módulos Qt/Pillow no usados y usa
  `--optimize 1`; `build_info.json` incluye `mode`, `size_mb` y `bundle_mb`.
- `config.ini` sube a esquema 2 con `language`, `notify_on_finish`,
  `restore_queue`, `window_x`, `window_y` y `window_maximized`.
- La lista y los diálogos usan textos de `app/i18n.py`; `STATUS_LABELS` se
  sustituye por `status_label()` para respetar el idioma activo.

### Fixed

- Los marcadores de posición ausentes en una traducción ya no rompen el texto:
  se conservan tal cual (`{size}`) y el resto sí se sustituye.

## [0.1.3] - 2026-11-15

### Added

- Selector de color de acento junto al botón de tema: azul, rojo, verde,
  amarillo, morado, rosado y marrón. Se aplica a botones primarios, sliders,
  progreso, toggles y selección, con paleta propia para tema claro y oscuro.
- `[app].accent` persistido en `config.ini` (`blue` por defecto); valores
  inválidos vuelven a azul con aviso.
- `app/accents.py` (sin Qt) y paletas `AccentColors` en `app/ui/theme.py`.

## [0.1.2] - 2026-11-15

### Added

- Fase 3: icono provisional `resources/icon.ico` multi-resolucion (16-256 px),
  generado de forma reproducible con `scripts/make_icon.py`.
- `app/ui/branding.py`: carga del icono en runtime, `AppUserModelID` de Windows
  y barra de titulo oscura acorde al tema.
- Metadatos del `.exe` (nombre, version, descripcion) generados por
  `scripts/make_version_info.py` e incrustados con `--version-file`.
- El icono viaja dentro del ejecutable (`--add-data`) para que la ventana lo use
  tambien en el build `--onefile`.
- Tests de recursos de build e identidad visual (59 en total).

## [0.1.1] - 2026-11-15

### Added

- Fase 1: estructura del proyecto, motor de conversion (Pillow), configuracion `.ini`,
  utilidades de rutas, CLI de prueba y documentacion para agentes.
- Fase 2: UI Qt completa con estetica Windows 11 (`app/ui/`): ventana unica,
  drop zone con arrastre de archivos y carpetas, lista con miniaturas y estados,
  selector de formato/calidad, modo sin perdida, politica de conflictos, carpeta
  de salida editable, progreso, cancelacion y resumen final.
- Tema claro/oscuro/sistema con `QSS` propio y boton de cambio rapido; iconos
  vectoriales dibujados con `QPainter` (sin assets externos).
- Miniaturas generadas con Pillow en un `QThreadPool`, sin bloquear la UI.
- `app/ui/convert_worker.py`: puente `QThread` + `BatchConverter` con senales de
  progreso y cancelacion segura.
- `main.py` sin argumentos abre la UI; cualquier subcomando sigue usando la CLI.
- Tests de UI en modo `offscreen`: 10 pruebas nuevas (50 en total).
- `build.ps1 -Windowed` documentado para compilar sin consola.

## [0.1.0] - 2026-11-15

### Added

- Entorno virtual con PySide6-Essentials 6.12.0 y Pillow 12.3.0.
- Repositorio offline de wheels en `wheels/`.
- Politica de build y scripts `scripts/build.ps1` y `scripts/bump_version.py`.
- Primer build validado: `dist/MediaFormat-0.1.0.exe` (15.9 MB) con smoke test de
  `formats` y una conversion real PNG -> JPEG desde el ejecutable.
