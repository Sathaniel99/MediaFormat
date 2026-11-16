# Documentación de MediaFormat

Índice de la documentación previa del proyecto. Los agentes deben leer al menos
`agents/context.md` y el documento del área que vayan a modificar.

| Documento | Contenido |
|---|---|
| [01-vision.md](01-vision.md) | Problema, alcance, no-objetivos, fases |
| [02-architecture.md](02-architecture.md) | Capas, módulos, flujo, hilos, errores |
| [03-config.md](03-config.md) | Referencia completa del `config.ini` |
| [04-conversion.md](04-conversion.md) | Formatos, pipeline, alfa, EXIF, colisiones |
| [05-ui.md](05-ui.md) | Especificación e implementación de la ventana |
| [06-build.md](06-build.md) | Política de compilación y versionado |
| [07-testing.md](07-testing.md) | Estrategia y ejecución de tests |
| [agents/](agents/README.md) | Onboarding, contexto y roles de agentes |
| [adr/0001](adr/0001-stack-pyside6.md) | Stack: PySide6-Essentials + Pillow |
| [adr/0002](adr/0002-config-ini.md) | Configuración `.ini` en `%APPDATA%` |
| [adr/0003](adr/0003-hilos-y-ui.md) | Hilos en el motor, señales en la UI |

## Convenciones de esta carpeta

- Español, frases cortas, tablas cuando aclaran.
- Cada afirmación debe poder comprobarse contra el código.
- Si cambias comportamiento, actualiza el doc **en el mismo cambio**.
- Las decisiones nuevas van a `adr/` con numeración incremental.
