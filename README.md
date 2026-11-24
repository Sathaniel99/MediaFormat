# MediaFormat

Conversor de imágenes de escritorio para Windows: arrastra archivos o carpetas,
elige el formato de salida y convierte en lote sin perder calidad ni bloquearte
la interfaz.

- **Stack**: Python 3.14, PySide6-Essentials 6.12, Pillow 12.3, PyInstaller 6.22.
- **Configuración**: un `config.ini` legible y editable a mano.
- **Salida por defecto**: `Documents\MediaFormat` (resuelto con la API de Windows,
  así que funciona aunque Documents esté redirigido a OneDrive).

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Estructura, configuración, motor de conversión, CLI, tests | ✅ Completada |
| 2 | UI Qt (drag & drop, lista, progreso, temas) | ✅ Completada |
| 3 | Pulido visual, icono, empaquetado final | ✅ Completada |
| 4 | Perfiles, cola persistente, ajustes, i18n, notificaciones | ✅ Completada |

Sin argumentos, `main.py` abre la ventana; con un subcomando funciona la CLI.

## Descargar

La [release 1.0.0](https://github.com/Sathaniel99/MediaFormat/releases/tag/v1.0.0)
publica `MediaFormat-V1.0.0.exe`. Es el mismo binario que
`dist\MediaFormat-1.0.0.exe` (la `V` del asset es solo el nombre de subida):
SHA-256 `6BC1C68A2A73FC0A0FB01BC00B1B0B09CECBF28B4E59E6C3A9EF057AAF85BBF5`.

La versión `1.0.1` (28 arreglos, 154 tests verdes) ya compila como build local
en `dist\MediaFormat-1.0.1.exe` (SHA-256
`6C58CF5E4CFA06058C1B3C5A1EE1B1353CD9402D0FC0ED44D6245345E2FA76BE`), pero aún
no tiene release pública.

## Instalación

El proyecto ya incluye un `.venv` preparado y un repositorio local de wheels en
`wheels/`, por lo que **no hace falta conexión** para reconstruir el entorno.
Si hay red, también puedes clonar
[`Sathaniel99/MediaFormat`](https://github.com/Sathaniel99/MediaFormat):

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links wheels -r requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-index --find-links wheels -r requirements-dev.txt
```

Comprobación rápida:

```powershell
.\.venv\Scripts\python.exe -c "import PIL, PySide6; print(PIL.__version__, PySide6.__version__)"
```

## Uso

### Ventana (recomendado)

```powershell
.\.venv\Scripts\python.exe main.py
```

Arrastra archivos o carpetas a la cola (o usa **Añadir archivos**), elige
formato y calidad en el panel inferior, revisa la carpeta de destino y pulsa
**Convertir**. Con la cola vacía, la propia zona punteada abre el selector al
hacer clic.
Puedes reordenar arrastrando filas, seleccionar varias con Ctrl/Mayús y usar el
menú contextual para convertir, reintentar o cancelar solo lo seleccionado.

- **Perfiles**: Web, Impresión, Redes y Telegram/Discord, más los que guardes tú.
- **Cola persistente**: al reabrir se recupera la lista (rutas existentes).
- **Calidad**: presets «Máxima» (por defecto), «Alta», «Media» y «Baja» en el
  panel de conversión; la carpeta de salida solo se cambia con **Elegir carpeta**.
- **Ajustes** (`Ctrl+,`): tema, acento, idioma, hilos, metadatos, carpeta de
  salida y notificaciones.
- **Banner**: avisa si el `.ini` tenía valores inválidos y se repararon.
- **Acento de Windows**: la opción `system` lee el color real del sistema.
- El botón de tema de la cabecera alterna sistema → claro → oscuro. A su lado,
  el botón de acento abre un menú con los colores disponibles.

### CLI

```powershell
# formatos disponibles en este Pillow
.\.venv\Scripts\python.exe main.py formats

# configuración efectiva
.\.venv\Scripts\python.exe main.py config --show

# convertir una carpeta completa a WebP
.\.venv\Scripts\python.exe main.py convert .\fotos --format webp --quality 85

# convertir archivos sueltos a PNG en una carpeta concreta
.\.venv\Scripts\python.exe main.py convert .\a.jpg .\b.webp --format png --out .\salida
```

Opciones útiles: `--lossless`, `--animated`, `--conflict rename|overwrite|skip`,
`--no-metadata`, `--no-orientation`, `--workers N`, `--no-recursive`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

6 de modelos + 9 de rutas + 20 de configuración + 29 del motor + 3 de CLI +
1 de logging + 12 de acentos + 9 de perfiles + 7 de cola + 8 de i18n +
7 de recursos de build + 43 de UI en modo `offscreen` (154 en total).
Ver `docs/07-testing.md`.

## Compilar

Política del proyecto: **todo fix o feature termina con una compilación**. El
agente no decide la versión; la eliges tú.

```powershell
# rebuild de la versión actual (GUI sin consola)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1 -Windowed

# nueva versión (tú decides el salto) + build
.\.venv\Scripts\python.exe scripts\bump_version.py patch
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1 -Windowed
```

Salida: `dist\MediaFormat-<version>.exe` + `dist\build_info.json`.
Detalles en `docs/06-build.md`.

## Estructura

```
MediaFormat/
├── AGENTS.md              reglas obligatorias para agentes
├── CLAUDE.md              atajo para Claude → AGENTS.md
├── .opencode/             configuración de OpenCode (instructions)
├── app/
│   ├── config.py          lectura/escritura y validación del .ini
│   ├── converter.py       motor Pillow + BatchConverter con hilos
│   ├── models.py          formatos, opciones, resultados
│   ├── paths.py           Documents real, expansión, colisiones
│   ├── accents.py         acentos y lectura del acento de Windows
│   ├── i18n.py            textos español/inglés
│   ├── profiles.py        perfiles integrados y personalizados
│   ├── queue_state.py     cola persistente en %LOCALAPPDATA%
│   ├── logging_setup.py   log rotativo
│   ├── cli.py             CLI
│   └── ui/                ventana Qt, ajustes, modelo, delegados, tema, iconos
├── docs/                  documentación, ADRs y guía de agentes
├── resources/             icon.ico + propuestas en icon-variants/
├── scripts/               build.ps1, bump_version.py, make_icon*.py, make_version_info.py
├── tests/                 unittest (154 tests)
├── wheels/                wheels offline (100 MB, no versionado)
├── CHANGELOG.md
├── config.example.ini
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── main.py
```

## Funciones de pago

La app es gratuita y completa en su alcance actual. Las ideas reservadas para
una futura edición de pago están en un archivo local (`De_pago.txt`, ignorado
por git y por eso no publicado): marca de agua, redimensionado por presets,
edición previa, perfiles en la nube, IA y exportación profesional. Nada de eso
está implementado ni bloquea funciones actuales.

## Documentación

- [Visión y alcance](docs/01-vision.md)
- [Arquitectura](docs/02-architecture.md)
- [Configuración `.ini`](docs/03-config.md)
- [Conversión y formatos](docs/04-conversion.md)
- [Especificación de la UI](docs/05-ui.md)
- [Build y versionado](docs/06-build.md)
- [Testing](docs/07-testing.md)
- [Guía para agentes](docs/agents/README.md)
- [Contexto para agentes](docs/agents/context.md)
- ADRs: [0001 stack](docs/adr/0001-stack-pyside6.md) ·
  [0002 config](docs/adr/0002-config-ini.md) ·
  [0003 hilos](docs/adr/0003-hilos-y-ui.md)
