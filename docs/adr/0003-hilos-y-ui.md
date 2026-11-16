# ADR 0003 — Hilos en el motor, señales en la UI

- **Estado**: aceptado
- **Fecha**: 2026-11-15

## Contexto

Convertir 50 imágenes puede tardar decenas de segundos. Si se hace en el hilo
principal, la ventana se congela; si se hace todo en la UI, el motor deja de ser
reutilizable por la CLI y los tests.

## Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| Síncrono en la UI | Simple | Congela la ventana |
| Hilos dentro del motor (`ThreadPoolExecutor`) | Reutilizable por CLI y UI | Hay que canalizar el progreso |
| `QThread` dentro del motor | Integración Qt | Acopla el motor a Qt |
| `asyncio` | Moderno | Pillow es bloqueante; no aporta aquí |
| Multiproceso | Evita GIL | Coste de arranque y de serializar resultados |

## Decisión

- El motor expone `BatchConverter.run(sources, on_progress=...)` y usa
  `ThreadPoolExecutor` (1–16 hilos). No conoce Qt.
- El callback `on_progress(BatchProgress)` puede ejecutarse en cualquier hilo:
  el consumidor decide cómo marshallizarlo.
- La UI (Fase 2) envolverá el lote en un `QObject` worker movido a un `QThread`
  y emitirá señales; Qt entrega las señales al hilo del receptor (la ventana).
- Cancelación con `threading.Event`: los trabajos en curso terminan, los
  pendientes se devuelven como `SKIPPED` con nota "cancelado por el usuario".

## Consecuencias

- La CLI usa el mismo motor sin Qt y sin hilos especiales.
- Los tests verifican orden de resultados y aislamiento de errores sin depender
  del orden de finalización.
- La UI nunca debe llamar a `convert_file` en el hilo principal.
- Si en el futuro el rendimiento lo pide, se puede añadir un backend
  multiproceso detrás de la misma interfaz, sin tocar la UI.
