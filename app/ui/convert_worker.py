"""Puente entre el motor de conversion y el hilo de la UI.

El motor (:class:`app.converter.BatchConverter`) no conoce Qt.  Este modulo lo
ejecuta dentro de un ``QThread`` y reemite su progreso como senales, de modo que
la ventana nunca se bloquea.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.converter import BatchConverter
from app.models import ConversionOptions, ConversionResult

LOGGER = logging.getLogger("mediaformat.ui.worker")


class ConvertWorker(QObject):
    """Objeto movido a un ``QThread`` que ejecuta un lote completo."""

    progress = Signal(object)  # app.models.BatchProgress
    finished = Signal(list)  # list[ConversionResult]
    failed = Signal(str)

    def __init__(
        self,
        sources: Sequence[Path | str],
        output_dir: Path | str,
        options: ConversionOptions,
        max_workers: int = 4,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sources = list(sources)
        self._options = options
        self._cancel_event = threading.Event()
        self._converter = BatchConverter(
            output_dir,
            options,
            max_workers,
            cancel_event=self._cancel_event,
        )

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        """Pide al lote que deje de encolar archivos nuevos.

        Los archivos que ya estan convirtiendo terminan; el resto se marca como
        omitido.  Es seguro llamarlo desde el hilo de la UI.
        """
        if not self._cancel_event.is_set():
            LOGGER.info("cancelacion solicitada")
        self._cancel_event.set()

    def cancel_file(self, source: Path | str) -> None:
        """Cancela un archivo concreto si aun no ha empezado (hilo seguro)."""
        self._converter.cancel_file(source)

    def cancel_files(self, sources: Sequence[Path | str]) -> None:
        self._converter.cancel_files(sources)

    @Slot()
    def run(self) -> None:
        """Ejecuta el lote y emite ``progress`` por cada archivo."""
        try:
            results: list[ConversionResult] = self._converter.run(
                self._sources,
                on_progress=self.progress.emit,
            )
        except Exception as exc:  # noqa: BLE001 - se informa en la UI
            LOGGER.exception("el lote fallo")
            self.failed.emit(str(exc))
            return
        self.finished.emit(results)
