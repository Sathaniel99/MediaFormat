from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from app.logging_setup import LOGGER_NAME, setup_logging


class LoggingTest(unittest.TestCase):
    """El nivel de log se puede cambiar en llamadas posteriores a ``setup_logging``."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.logger = logging.getLogger(LOGGER_NAME)
        self.original_handlers = list(self.logger.handlers)
        self.original_level = self.logger.level
        for handler in self.original_handlers:
            self.logger.removeHandler(handler)
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
            handler.close()
        for handler in self.original_handlers:
            self.logger.addHandler(handler)
        self.logger.setLevel(self.original_level)

    def test_repeated_setup_updates_level_without_duplicating_handlers(self) -> None:
        target = Path(self._tmp.name) / "mediaformat.log"
        setup_logging(level=logging.DEBUG, log_file=target)
        setup_logging(level=logging.WARNING, log_file=target)

        self.assertEqual(self.logger.level, logging.WARNING)
        self.assertEqual(len(self.logger.handlers), 2)
        self.assertTrue(target.is_file())


if __name__ == "__main__":
    unittest.main()
