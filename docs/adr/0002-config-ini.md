# ADR 0002 — Configuración en `.ini` bajo `%APPDATA%`

- **Estado**: aceptado
- **Fecha**: 2026-11-15

## Contexto

La app necesita recordar carpeta de salida, formato, calidad y preferencias de
procesamiento. El usuario pidió explícitamente un `.ini` y poder editarlo a mano.

## Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| **`.ini` con `configparser`** | Legible, editable, stdlib, pedido por el usuario | Sin tipos; hay que validar |
| JSON | Tipado, ubicuo | Menos legible a mano; comentarios imposibles |
| Registro de Windows | Nativo | Opaco, difícil de depurar, complicado de portar |
| YAML/TOML | Bonito | Dependencia extra (TOML es stdlib solo en 3.11+, pero peor para comentar) |

## Decisión

`configparser` con `interpolation=None`, archivo en
`%APPDATA%\MediaFormat\config.ini`.

Detalles que importan:

- **Sin interpolación**: las rutas usan `%USERPROFILE%` y se expanden luego con
  `os.path.expandvars`. Con interpolación activa, `%USERPROFILE%` rompería.
- **Sin comentarios inline**: `inline_comment_prefixes=None` para que
  `background = #FFFFFF` no se trunque.
- **Validación al cargar**: valores inválidos se corrigen y se registran en
  `Config.warnings`; nunca se lanza una excepción al usuario.
- **Corrupción**: el archivo se mueve a `config.ini.bak` y se usan defaults.
- **Guardado atómico**: `.tmp` + `os.replace`.
- **Carpeta por defecto**: `SHGetKnownFolderPath(FOLDERID_Documents)` para
  respetar OneDrive; no se concatena `%USERPROFILE%\Documents`.
- **Se reescribe completo**: los comentarios manuales se pierden al guardar; se
  documenta en `docs/03-config.md`.

## Consecuencias

- El `.ini` es la única fuente de configuración persistente; no hay base de
  datos ni registro.
- Toda clave nueva requiere: default, propiedad tipada, template, ejemplo y test.
- El esquema tiene `[app].version` para futuras migraciones.
