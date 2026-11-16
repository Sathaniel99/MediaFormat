# ADR 0001 — Stack: Python + PySide6-Essentials + Pillow

- **Estado**: aceptado
- **Fecha**: 2026-11-15

## Contexto

Necesitamos una app de escritorio Windows para convertir imágenes por lotes,
con drag & drop, interfaz moderna y empaquetado en un `.exe`. El equipo no tiene
conexión a internet y las dependencias deben salir de un wheelhouse local.

## Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| Tkinter + Pillow | Ya instalado, cero dependencias | Estética anticuada, drag & drop pobre |
| CustomTkinter | Look moderno | Dependencia extra no disponible offline; menos control |
| **PySide6-Essentials** | Qt completo, drag & drop nativo, widgets potentes | Pesado (~200 MB) |
| Electron/web | UI flexible | Stack distinto, consumo de RAM, más complejo de empaquetar |
| .NET WinUI | Nativo | Fuera del stack Python del autor |

## Decisión

PySide6-Essentials 6.12.0 + Pillow 12.3.0 sobre Python 3.14.2.

- **Essentials** basta: solo se usan `QtCore`, `QtGui` y `QtWidgets`. Se
  desinstalaron `PySide6-Addons`, `WebEngine` y `Pdf` (venv de 718 MB → 279 MB).
- Pillow es el motor de imagen: maduro, sin dependencias nativas externas y con
  soporte de WebP/AVIF en esta build.
- PyInstaller 6.22.3 para el `.exe` (`--onefile`).

## Consecuencias

- El motor (`converter`, `config`, `models`, `paths`) **no importa Qt**, así que
  se puede probar y usar por CLI sin entorno gráfico.
- El `.exe` será grande (Qt); se acepta a cambio de una UI nativa.
- Si en el futuro hace falta QML/WebEngine, habría que reincorporar addons,
  lo que hoy no está disponible offline.
