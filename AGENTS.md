# AGENTS.md — Reglas para agentes

Este archivo es obligatorio para cualquier agente (OpenCode, Claude, Codex,
Cursor, Copilot...) que trabaje en este repositorio. Léelo completo antes de
tocar código y consulta `docs/agents/context.md` para el estado actual.

## 1. Contexto en 30 segundos

MediaFormat convierte imágenes entre formatos con Python + Qt + Pillow.
Fase 1 (motor, configuración, CLI, tests), Fase 2 (UI Qt estilo Windows 11),
Fase 3 (icono definitivo, metadatos del `.exe`, pulido) y Fase 4 (perfiles,
cola persistente, ajustes, i18n, notificaciones) completadas.
Hay un `.venv` funcional **sin red** y un wheelhouse en `wheels/`; no borres
ninguno de los dos.

## 2. Orden de lectura

1. `docs/agents/context.md` — estado, versiones, decisiones vigentes.
2. `docs/02-architecture.md` — capas y responsabilidades.
3. El documento del área que vas a tocar (`docs/03`–`docs/07`).
4. `docs/agents/roles.md` — checklist según tu rol.

## 3. Comandos canónicos

```powershell
$py = ".\.venv\Scripts\python.exe"

& $py -m unittest discover -s tests -t .     # tests
& $py -m ruff check app tests scripts main.py # lint
& $py -m ruff format app tests scripts main.py
& $py main.py formats                         # CLI
& $py main.py                                 # ventana Qt
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1 -Windowed    # compilar (GUI)
```

## 4. REGLA OBLIGATORIA: compilar tras cada feat/fix

**Ningún cambio funcional se considera terminado hasta que compila.**

1. Termina el fix/feature.
2. Añade o ajusta tests y ejecútalos (verde).
3. Anota el cambio en `CHANGELOG.md`.
4. **Pregunta al usuario** si el build es:
   - **Rebuild** de la versión actual, o
   - **Nueva versión** (`patch`, `minor`, `major`).
5. Si es nueva versión: `python scripts/bump_version.py <parte>`.
   Si es rebuild: no toques `app/version.py`.
6. Compila: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1 -Windowed`.
7. Verifica que existe `dist\MediaFormat-<version>.exe` y revisa
   `dist\build_info.json`.
8. Informa: versión, ruta del ejecutable y resultado de los tests.

Reglas derivadas:

- **El agente nunca decide la versión por su cuenta.** Ni siquiera para un fix
  trivial. La pregunta del paso 4 es obligatoria.
- **Nunca compilar con tests rojos.** `-SkipTests` solo si el usuario lo pide
  explícitamente y lo justifica.
- **Nunca editar `app/version.py` a mano**; usa `scripts/bump_version.py`.
- Un fix sin compilación deja la tarea **incompleta**; dilo claramente en el
  resumen final si no pudiste compilar y por qué.
- No publiques ni copies el `.exe` fuera de `dist/` sin pedirlo.

## 5. Invariantes técnicas

- `app/converter.py`, `app/models.py`, `app/config.py` y `app/paths.py`
  **no importan Qt**. La UI depende del motor, nunca al revés.
- La UI nunca bloquea el hilo principal: usa `BatchConverter` con hilos y
  actualiza widgets con señales de Qt.
- Nunca sobrescribir un archivo sin respetar `on_conflict` (`rename` por
  defecto) y nunca escribir sobre el archivo de origen.
- El `.ini` se lee con `interpolation=None` y **sin comentarios inline**:
  `#FFFFFF` es un color, no un comentario.
- Los errores por archivo se devuelven como `ConversionResult(ERROR)`, no como
  excepciones que tumben el lote.
- No añadir dependencias nuevas sin red: comprueba `wheels/` primero y avisa si
  falta algo.

## 6. Estilo

- Python 3.13+ (`StrEnum`, `dataclass(slots=True)`, type hints modernos).
- Código e identificadores en inglés; documentación y UI en español.
- Línea máxima 100, formateador `ruff format`, lint `ruff check` limpio.
- Docstrings breves en módulos y funciones públicas.
- Tests con `unittest` (stdlib); no introduzcas pytest.

## 7. Dónde documentar

| Cambio | Documento |
|---|---|
| Nuevo parámetro del `.ini` | `docs/03-config.md` + `config.example.ini` |
| Nuevo formato/regla de conversión | `docs/04-conversion.md` |
| Cambio de UI | `docs/05-ui.md` |
| Icono o identidad visual | `resources/README.md` + `docs/05-ui.md` |
| Cambio de build/versionado | `docs/06-build.md` |
| Decisión de arquitectura | `docs/adr/NNNN-titulo.md` |
| Cualquier feat/fix | `CHANGELOG.md` |

## 8. Definition of Done

- [ ] Código implementado y lint limpio.
- [ ] Tests nuevos/actualizados en verde.
- [ ] Documentación del área actualizada.
- [ ] `CHANGELOG.md` actualizado.
- [ ] Usuario preguntado: ¿nueva versión o rebuild?
- [ ] `build.ps1` ejecutado con éxito y `.exe` verificado.
