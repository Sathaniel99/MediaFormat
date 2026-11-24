# 07 — Testing

## Principios

- **Sin red**: los tests corren con `unittest` de la stdlib. Los del motor no
  necesitan Qt; los de UI fuerzan `QT_QPA_PLATFORM=offscreen`.
- **Rápidos salvo la UI**: el motor acaba en ~2 s; la suite completa tarda
  ~2 min porque 43 pruebas de UI corren en `offscreen`.
- **Deterministas**: cada test usa su propio `TemporaryDirectory`.
- **Aislados del usuario**: nunca leen ni escriben el `config.ini` real; siempre
  pasan una ruta temporal a `Config(path)`.
- **Un fallo por archivo no tumba el lote**: eso también se prueba.

> `pytest` no está disponible offline. Si en el futuro se instala, se puede
> añadir como runner, pero los tests deben seguir siendo `unittest` válidos.

## Ejecución

```powershell
$py = ".\.venv\Scripts\python.exe"

# toda la suite
& $py -m unittest discover -s tests -t .

# un módulo
& $py -m unittest tests.test_converter -v

# un test concreto
& $py -m unittest tests.test_converter.ConverterTest.test_alpha_is_flattened_for_jpeg -v
```

Salida esperada: `Ran 154 tests ... OK`.

## Mapa de la suite

| Archivo | Tests | Cubre |
|---|---|---|
| `tests/test_models.py` | 6 | Extensiones, capacidades, `from_value`, `normalized()` (incluidos tipos inválidos) y `ConversionResult.ok` |
| `tests/test_paths.py` | 9 | `unique_path` con destinos reservados, `%VARS%` (incluida variable sin definir), comillas, tamaños, escritura y Documents |
| `tests/test_config.py` | 20 | Creación, roundtrip, `#RRGGBB`, corrupción → `.bak`, esquema, rutas inválidas, valores reparados, acento/idioma, perfiles JSON y guardado atómico |
| `tests/test_converter.py` | 29 | Formatos, conversión real, alfa, EXIF sin doble rotación, reserva de destinos, limpieza de parciales, progreso al cancelar, errores, animaciones y lotes |
| `tests/test_cli.py` | 3 | `--conflict`, `recursive_folders` y `--no-recursive` sobre la configuración temporal |
| `tests/test_logging.py` | 1 | El nivel se actualiza en llamadas repetidas sin duplicar handlers |
| `tests/test_accents.py` | 12 | Nombres y etiquetas, normalización, acento `system`, paletas claro/oscuro y QSS resultante |
| `tests/test_profiles.py` | 9 | Perfiles integrados, slugs, JSON, valores fuera de rango y perfiles personalizados |
| `tests/test_queue_state.py` | 7 | Cola persistente, `RUNNING` → `PENDING`, archivos corruptos y guardado atómico |
| `tests/test_i18n.py` | 8 | Diccionarios es/en, marcadores, idioma desconocido y paridad de claves |
| `tests/test_ui.py` | 43 | Modelo de lista, worker, ventana en `offscreen`, resumen por lote, estado `RUNNING`, liberación de `QThread`, miniaturas, perfiles, ajustes, calidad de sesión, accesibilidad, geometría y tema |
| `tests/test_build_assets.py` | 7 | Icono multi-resolución y metadatos de versión del `.exe` |

## Qué debe cubrir un cambio nuevo

| Tipo de cambio | Test obligatorio |
|---|---|
| Nueva clave del `.ini` | Default + roundtrip + valor inválido |
| Nuevo formato de salida | Conversión real y reapertura con Pillow |
| Nueva regla de nombres | Caso sin colisión y con colisión |
| Nuevo mensaje de error | Entrada que lo provoque |
| Cambio en lotes/hilos | Orden de resultados y aislamiento de errores |
| Cancelación o reintento | Archivo cancelado antes de empezar y lote que sigue vivo |
| Cola persistente | Roundtrip, estado degradado y archivo corrupto |
| Texto nuevo de UI | Clave en `_ES` y `_EN` + prueba de `tr` |
| UI | `test_ui.py`: modelo, worker y ventana en `offscreen` |
| Acento o paleta | `test_accents.py`: normalización y contraste por tema |

## Reglas para escribir tests

1. Usar `tempfile.TemporaryDirectory()` en `setUp` y limpiarlo en `tearDown`.
2. Crear imágenes reales con Pillow, no mocks: el objetivo es probar I/O.
3. No depender del orden de finalización en lotes: comparar por índice.
4. Evitar `assertAlmostEqual` en colores; usar rangos porque JPEG es con
   pérdida.
5. No tocar `%APPDATA%`: `Config(path)` siempre con ruta temporal.
6. Los tests no deben requerir AVIF: comprobar `available_formats()` antes.
7. Nombres en inglés, mensajes de aserción claros.

## Lint y formato

```powershell
& .\.venv\Scripts\ruff.exe check app tests scripts main.py
& .\.venv\Scripts\ruff.exe format app tests scripts main.py
```

Configuración en `pyproject.toml`: línea 100, `select = [E, F, I, UP, B, SIM]`,
`quote-style = "double"`, `line-ending = "lf"`.

Los dos comandos deben salir limpios antes de compilar.

## Cobertura (opcional, futuro)

No se usa `coverage` porque no está en `wheels/`. Si se instala:

```powershell
& $py -m coverage run -m unittest discover -s tests -t .
& $py -m coverage report -m
```

Objetivo razonable: ≥ 85 % en `app/`, 100 % en `models.py` y `paths.py`.
