from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.cli import _handle_convert, build_parser  # noqa: SLF001 - prueba de la CLI
from app.config import Config
from app.models import ConflictPolicy, OutputFormat
from PIL import Image


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.inbox = self.root / "in"
        self.outbox = self.root / "out"
        self.inbox.mkdir()
        self.outbox.mkdir()
        self.settings = Config(path=self.root / "config.ini")
        self.settings.default_format = OutputFormat.WEBP
        self.settings.on_conflict = ConflictPolicy.RENAME

    def run_convert(self, *arguments: object) -> tuple[int, str]:
        """Ejecuta `_handle_convert` con la configuración temporal del test."""
        parsed = build_parser().parse_args(["convert", *(str(item) for item in arguments)])
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch("app.cli.Config", return_value=self.settings),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = _handle_convert(parsed)
        return code, stdout.getvalue() + stderr.getvalue()

    def make_image(self, path: Path) -> Path:
        Image.new("RGB", (16, 16), (20, 100, 200)).save(path)
        return path

    def test_conflict_flag_overrides_the_ini_policy(self) -> None:
        source = self.make_image(self.inbox / "a.png")
        existing = self.outbox / "a.webp"
        existing.write_bytes(b"destino anterior")

        code, output = self.run_convert(
            source, "--format", "webp", "--out", self.outbox, "--conflict", "skip"
        )

        self.assertEqual(code, 0)
        self.assertEqual(existing.read_bytes(), b"destino anterior")
        self.assertIn("Omitidas: 1", output)

    def test_recursive_folders_from_config_controls_folder_scan(self) -> None:
        nested = self.inbox / "sub"
        nested.mkdir()
        self.make_image(nested / "nested.png")
        self.settings.recursive_folders = False

        code, output = self.run_convert(self.inbox, "--format", "webp", "--out", self.outbox)
        self.assertEqual(code, 2)
        self.assertIn("no se encontraron imagenes", output)

        self.settings.recursive_folders = True
        code, _ = self.run_convert(self.inbox, "--format", "webp", "--out", self.outbox)
        self.assertEqual(code, 0)
        self.assertTrue((self.outbox / "nested.webp").is_file())

    def test_no_recursive_flag_wins_over_config(self) -> None:
        nested = self.inbox / "sub"
        nested.mkdir()
        self.make_image(nested / "nested.png")
        self.settings.recursive_folders = True

        code, output = self.run_convert(
            self.inbox, "--format", "webp", "--out", self.outbox, "--no-recursive"
        )

        self.assertEqual(code, 2)
        self.assertIn("no se encontraron imagenes", output)


if __name__ == "__main__":
    unittest.main()
