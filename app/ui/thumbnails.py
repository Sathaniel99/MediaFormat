"""Background thumbnail loading with Pillow, without blocking the UI thread."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, Signal
from PySide6.QtGui import QImage

LOGGER = logging.getLogger("mediaformat.ui.thumbnails")


class _Signals(QObject):
    ready = Signal(str, object, int, int)
    failed = Signal(str)


class _ThumbnailTask(QRunnable):
    def __init__(self, path: Path, signals: _Signals, size: int) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._path = path
        self._signals = signals
        self._size = size

    def run(self) -> None:
        try:
            with Image.open(self._path) as image:
                width, height = image.size
                image.draft("RGB", (self._size * 2, self._size * 2))
                image.thumbnail((self._size, self._size), Image.Resampling.LANCZOS)
                has_alpha = "A" in image.getbands() or (
                    image.mode == "P" and "transparency" in image.info
                )
                mode = "RGBA" if has_alpha else "RGB"
                converted = image.convert(mode)
                data = converted.tobytes()
                image_format = (
                    QImage.Format.Format_RGBA8888 if mode == "RGBA" else QImage.Format.Format_RGB888
                )
                channels = 4 if mode == "RGBA" else 3
                qimage = QImage(
                    data,
                    converted.width,
                    converted.height,
                    converted.width * channels,
                    image_format,
                ).copy()
        except Exception as exc:  # noqa: BLE001 - a bad image must not crash the UI
            LOGGER.debug("miniatura fallida para %s: %s", self._path, exc)
            self._signals.failed.emit(str(self._path))
            return
        self._signals.ready.emit(str(self._path), qimage, width, height)


class ThumbnailService(QObject):
    """Queues thumbnail jobs and forwards their results to the main thread."""

    ready = Signal(str, object, int, int)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None, size: int = 96) -> None:
        super().__init__(parent)
        self._size = size
        self._signals = _Signals(self)
        self._signals.ready.connect(self.ready)
        self._signals.failed.connect(self._on_failed)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max(2, min(4, QThread.idealThreadCount())))
        self._requested: set[str] = set()

    def load(self, path: Path) -> None:
        key = str(path).lower()
        if key in self._requested:
            return
        self._requested.add(key)
        self._pool.start(_ThumbnailTask(path, self._signals, self._size))

    def forget(self, path: Path) -> None:
        self._requested.discard(str(path).lower())

    def reset(self) -> None:
        self._requested.clear()

    def wait_for_done(self, msecs: int = 5000) -> bool:
        """Block until the queued thumbnails finish (shutdown and tests)."""
        return self._pool.waitForDone(msecs)

    def _on_failed(self, path: str) -> None:
        self._requested.discard(path.lower())
