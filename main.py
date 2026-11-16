"""Punto de entrada de MediaFormat.

Sin argumentos (o con ``gui``) abre la ventana Qt; cualquier otro argumento se
delega en la CLI de ``app.cli``.  El import de PySide6 es diferido para que un
uso puramente CLI no cargue Qt.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] != "gui":
        from app.cli import main as cli_main

        return cli_main(args)

    from app.ui.main_window import run

    return run(args[1:] if args and args[0] == "gui" else [])


if __name__ == "__main__":
    raise SystemExit(main())
