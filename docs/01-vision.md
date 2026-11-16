# 01 — Visión y alcance

## Problema

Convertir imágenes entre formatos en Windows suele implicar herramientas web
(privacidad), suites pesadas (lentas, llenas de opciones) o scripts manuales.
MediaFormat busca el punto medio: una ventana simple, conversión por lotes fiable
y configuración transparente en un `.ini`.

## Usuario objetivo

- Personas que preparan imágenes para web, documentación o archivos.
- Usuarios técnicos que quieren automatizar sin depender de la nube.
- El propio autor del proyecto, que decide cuándo una versión es nueva.

## Alcance del MVP

1. Añadir imágenes por selector de archivos y por drag & drop (archivos y carpetas).
2. Ver la lista con miniatura, dimensiones, peso y estado.
3. Elegir formato de salida entre los soportados por Pillow.
4. Ajustar calidad, compresión y tratamiento de transparencia.
5. Convertir en lote con progreso y resumen de errores.
6. Guardar todo en un `config.ini` editable.

## No-objetivos (por ahora)

- Edición de imagen (recortar, rotar, filtros, marcas de agua).
- Procesamiento de vídeo o audio (aunque el FFmpeg del repositorio de librerías
  está disponible para el futuro).
- Sincronización en la nube, cuentas o telemetría.
- HEIC/HEIF (requiere `pillow-heif`; evaluable en una fase posterior).
- Instalador MSI; el MVP se distribuye como `.exe` portable.

## Criterios de éxito

- Convertir 50 imágenes mezcladas sin bloquear la UI ni perder archivos.
- Ningún archivo de origen se modifica ni se sobrescribe sin permiso explícito.
- Un archivo corrupto no cancela el lote; se reporta y se continúa.
- El `.ini` sobrevive a ediciones manuales y a valores inválidos.
- Arranque en frío < 2 s y conversión limitada por disco/CPU, no por la app.

## Fases

| Fase | Entregable | Criterio de cierre | Estado |
|---|---|---|---|
| 1 | Motor + config + CLI + tests + docs | Tests verdes, conversión real por CLI | ✅ |
| 2 | UI Qt funcional | Drag & drop, lista, progreso, errores | ✅ |
| 3 | Pulido + build windowed + icono | `.exe` usable de doble clic | ✅ |
| 4 | Extras (perfiles, cola, ajustes, i18n, notificaciones) | Solo si el usuario lo pide | ✅ |

## Principios

1. **Predecible antes que potente**: opciones claras, valores por defecto seguros.
2. **Nada se pierde**: nunca sobrescribir el origen; colisiones renombran.
3. **Transparencia**: configuración legible y log local.
4. **Offline primero**: sin red en tiempo de ejecución ni en la instalación.
