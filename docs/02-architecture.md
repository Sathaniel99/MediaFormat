# 02 — Arquitectura

## Capas

```
┌──────────────────────────────────────────────┐
│  UI (PySide6, app/ui/)                       │
│  ventana, drop zone, lista, progreso          │
└───────────────▲──────────────────────────────┘
                │ ConversionResult / BatchProgress
┌───────────────┴──────────────────────────────┐
│  Motor (Pillow)                              │
│  converter.convert_file / BatchConverter      │
└───────────────▲──────────────────────────────┘
                │ ConversionOptions
┌───────────────┴───────────────┬──────────────┐
│  Config (.ini tipado)         │  Paths       │
│  config.Config                │  paths.*     │
└───────────────────────────────┴──────────────┘
```

Regla dura: **el motor no conoce Qt**. `app/converter.py`, `app/config.py`,
`app/models.py` y `app/paths.py` se pueden importar en un script o en tests sin
entorno gráfico.

## Módulos

| Módulo | Responsabilidad | No hace |
|---|---|---|
| `app/models.py` | `OutputFormat`, `ConflictPolicy`, `ConversionOptions`, `ConversionResult` | I/O, Qt |
| `app/paths.py` | Documents real, `%VARS%`, colisiones, tamaños, abrir carpeta | Conversión |
| `app/config.py` | Leer/escribir/validar `config.ini`, mapear a opciones | Tocar imágenes |
| `app/accents.py` | Acentos válidos, normalización y acento real de Windows | Qt |
| `app/i18n.py` | Diccionarios es/en y `tr()` | Lógica de negocio |
| `app/profiles.py` | Perfiles integrados, slugs y JSON de perfiles | Qt |
| `app/queue_state.py` | Guardar/cargar la cola persistente | Conversión |
| `app/converter.py` | Abrir, normalizar, guardar, lotes, errores | Leer el `.ini` |
| `app/logging_setup.py` | Log rotativo en `%LOCALAPPDATA%` | UI |
| `app/cli.py` | Orquestación de la CLI | Lógica de conversión |
| `app/ui/main_window.py` | Ventana única, acciones, tema, i18n, cola | Conversión, I/O de imágenes |
| `app/ui/settings_dialog.py` | Diálogo de ajustes y guardado del `.ini` | Conversión |
| `app/ui/file_model.py` | Modelo de la lista (estado, reordenación y metadatos) | Tocar disco más allá de `stat()` |
| `app/ui/convert_worker.py` | `QThread` + `BatchConverter`, señales de progreso | Reglas de conversión |
| `app/ui/thumbnails.py` | Miniaturas Pillow en `QThreadPool` | UI principal |
| `app/ui/theme.py`, `icons.py`, `widgets.py`, `delegates.py` | Tema, iconos, toggles, selects, pintado y drag & drop de la cola | Motor |

## Flujo de una conversión

```
ruta origen + ConversionOptions
        │
        ├─ validar origen y calcular destino (colisiones)
        ├─ Image.open → n_frames, exif, icc
        ├─ exif_transpose (si procede y es estático)
        ├─ normalizar modo según formato (alfa, CMYK, P)
        ├─ guardar con parámetros del formato
        └─ ConversionResult(status, output, sizes, error, notes)
```

`convert_file` **no lanza** por errores de usuario: devuelve `JobStatus.ERROR`
con un mensaje en español. Los fallos de programación sí deben verse en tests.

## Hilos

- `BatchConverter` usa `ThreadPoolExecutor` con `max_workers` 1–16.
- Pillow libera el GIL en las operaciones pesadas de C; para lotes pequeños el
  beneficio es real, para muchos archivos pequeños manda el disco.
- La UI lanza el lote en un `QThread` con `app/ui/convert_worker.py` y emite
  `BatchProgress` por señal; **el hilo principal solo pinta**.
- Cancelación: `BatchConverter.cancel()` marca un `threading.Event`. Los trabajos
  en curso terminan; los pendientes se cancelan y se devuelven como `SKIPPED`.
- Cancelación por archivo: `cancel_file()`/`cancel_files()` añaden rutas a un
  conjunto protegido por lock. `convert_file(..., skip_check=...)` lo consulta al
  empezar, así nunca se interrumpe una escritura a medias.

## Modelo de errores

| Situación | Resultado |
|---|---|
| Archivo ilegible / corrupto | `ERROR` + "formato no reconocido" |
| Sin permisos | `ERROR` + mensaje de permisos |
| Sale igual que el origen | destino con sufijo `_converted` |
| Ya existe y política `skip` | `SKIPPED` |
| Ya existe y política `rename` | `nombre_1.ext` |
| Imagen gigante | `ERROR` por `DecompressionBombError` |

## Decisiones registradas

- [ADR 0001](adr/0001-stack-pyside6.md): PySide6-Essentials + Pillow.
- [ADR 0002](adr/0002-config-ini.md): `.ini` en `%APPDATA%`, sin interpolación.
- [ADR 0003](adr/0003-hilos-y-ui.md): hilos en el motor, señales en la UI.

## Invariantes para revisar un PR

1. Ningún `import PySide6` fuera de `app/ui/` y `main.py`.
2. Todo acceso a disco pasa por `pathlib`.
3. `ConversionOptions.normalized()` se aplica antes de guardar.
4. Un archivo de origen nunca se abre en modo escritura.
5. El `.ini` generado incluye todas las secciones de `default_values()`.
