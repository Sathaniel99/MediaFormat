# Guía para agentes

Esta carpeta existe para que cualquier agente (OpenCode, Claude, Codex, Cursor,
Copilot…) pueda trabajar sin redescubrir el proyecto ni romper sus reglas.

## Orden de lectura

1. **[`../../AGENTS.md`](../../AGENTS.md)** — reglas obligatorias. Si solo lees
   un archivo, que sea ese.
2. **[`context.md`](context.md)** — estado actual, versiones, entorno y
   decisiones vigentes.
3. **[`roles.md`](roles.md)** — checklist según el tipo de tarea.
4. **`docs/01`–`docs/07`** — documento del área que vas a tocar.

## Las tres reglas que nunca se rompen

1. **Compilar tras cada fix/feature.** El agente no elige la versión: pregunta
   al usuario si es *rebuild* o *nueva versión*.
2. **El motor no importa Qt.** `app/converter.py`, `app/models.py`,
   `app/config.py`, `app/paths.py` deben poder importarse sin PySide6.
3. **Nunca se pierde un archivo.** El origen no se sobrescribe y las colisiones
   se resuelven según `on_conflict` (`rename` por defecto).

## Comandos rápidos

```powershell
$py = ".\.venv\Scripts\python.exe"

& $py -m unittest discover -s tests -t .        # tests
& $py -m ruff check app tests scripts main.py   # lint
& $py -m ruff format app tests scripts main.py  # formato
& $py main.py formats                           # CLI
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1                    # compilar
```

## Mapa mental del código

```
main.py → app/cli.py → app/config.py ─┐
                       app/converter.py ─┴→ app/models.py
                       app/paths.py
                       app/logging_setup.py
```

La UI vive en `app/ui/`, encima de `converter` y `config`; nunca al revés.

## Documentos por área

| Si tocas… | Lee y actualiza |
|---|---|
| `.ini` o defaults | `docs/03-config.md`, `config.example.ini`, `tests/test_config.py` |
| formatos, alfa, EXIF | `docs/04-conversion.md`, `tests/test_converter.py` |
| ventana, drag & drop | `docs/05-ui.md` |
| build, versión | `docs/06-build.md`, `scripts/` |
| tests | `docs/07-testing.md` |
| arquitectura | `docs/02-architecture.md` + ADR nuevo |

## Qué NO hacer

- No `git init`, ni commits, ni push sin que el usuario lo pida.
- No borrar `.venv/` ni `wheels/`: no hay red para reconstruirlos.
- No añadir dependencias que no estén en `wheels/`.
- No introducir `pytest`, `poetry`, `hatch` ni herramientas que no estén
  instaladas.
- No tocar `%APPDATA%\MediaFormat\config.ini` real desde tests.
- No cambiar `app/version.py` a mano.
- No compilar con tests rojos.
