# Roles y checklists

Un agente puede actuar en varios roles durante una misma sesión. Usa la lista
del rol que corresponda a la tarea **antes** de dar el trabajo por terminado.

## Regla común a todos los roles

Toda tarea funcional termina con:

1. Tests verdes.
2. Lint y formato limpios.
3. `CHANGELOG.md` actualizado.
4. Pregunta al usuario: **¿rebuild o nueva versión?**
5. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1` ejecutado y `.exe` verificado.

Si no puedes compilar, dilo explícitamente y explica por qué. Nunca des una
tarea por completa sin build.

---

## 1. Implementador (feature/fix)

- [ ] Leí `AGENTS.md` y el doc del área.
- [ ] Reproduje el bug o entendí el requisito.
- [ ] El cambio respeta las capas (motor sin Qt).
- [ ] Añadí o ajusté tests; los ejecuté.
- [ ] `ruff check` y `ruff format --check` limpios.
- [ ] Actualicé la documentación del área.
- [ ] Anoté el cambio en `CHANGELOG.md`.
- [ ] Pregunté por la versión y compilé.

## 2. Revisor de código

- [ ] No hay `import PySide6` fuera de `app/ui/` y `main.py`.
- [ ] Ningún camino escribe sobre el archivo de origen.
- [ ] Los errores por archivo no abortan el lote.
- [ ] `ConversionOptions.normalized()` se aplica antes de guardar.
- [ ] Las rutas nuevas del `.ini` tienen default, validación, template y test.
- [ ] No se añadieron dependencias fuera de `wheels/`.
- [ ] Los mensajes de usuario están en español; identificadores en inglés.

## 3. Documentador

- [ ] El doc describe el comportamiento **real**, no el deseado.
- [ ] Las tablas de claves/rangos coinciden con `app/config.py`.
- [ ] Los enlaces relativos resuelven (`docs/README.md` es el índice).
- [ ] Si hubo una decisión de arquitectura, hay un ADR nuevo.
- [ ] `docs/agents/context.md` refleja el estado actual.

## 4. Responsable de build/release

- [ ] `app/version.py` y `pyproject.toml` coinciden.
- [ ] La versión la eligió el usuario (no el agente).
- [ ] `CHANGELOG.md` tiene la entrada con fecha.
- [ ] `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1` terminó en verde.
- [ ] `dist\MediaFormat-<version>.exe` existe.
- [ ] `dist\build_info.json` tiene versión, hash y fecha correctos.
- [ ] Probé el `.exe` a doble clic en una carpeta limpia.

## 5. Diseñador de UI

- [ ] La ventana sigue `docs/05-ui.md` (o actualicé el doc).
- [ ] Drag & drop de archivos y carpetas funciona.
- [ ] La conversión corre fuera del hilo principal.
- [ ] Cancelar deja un estado consistente.
- [ ] Los estados de fila (pendiente/listo/omitido/error) son visibles.
- [ ] La geometría y preferencias persisten en el `.ini`.
- [ ] Probé con 50 imágenes y con un archivo corrupto.

## 6. Explorador (sin cambios)

- [ ] No modifiqué archivos.
- [ ] Respondí con rutas y números de línea.
- [ ] Distinguí lo comprobado de lo supuesto.
