# CLAUDE.md

Este proyecto usa un único documento de reglas para agentes:

**Lee [`AGENTS.md`](AGENTS.md) antes de tocar nada.**

Contexto adicional imprescindible:

- [`docs/agents/context.md`](docs/agents/context.md) — estado, versiones y entorno.
- [`docs/02-architecture.md`](docs/02-architecture.md) — capas y responsabilidades.
- [`docs/agents/roles.md`](docs/agents/roles.md) — checklist según la tarea.

Resumen de la regla más importante: **todo fix o feature termina con una
compilación** (`powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build.ps1`). El agente nunca decide la
versión: pregunta al usuario si es *rebuild* o *nueva versión*.
