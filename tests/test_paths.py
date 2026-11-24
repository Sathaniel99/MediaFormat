from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.paths import (
    default_output_dir,
    documents_dir,
    expand_path,
    format_size,
    is_writable_dir,
    path_key,
    unique_path,
)


class PathsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_unique_path_returns_same_when_free(self) -> None:
        target = self.root / "foto.png"
        self.assertEqual(unique_path(target), target)

    def test_unique_path_adds_counter(self) -> None:
        target = self.root / "foto.png"
        target.write_bytes(b"x")
        self.assertEqual(unique_path(target).name, "foto_1.png")
        (self.root / "foto_1.png").write_bytes(b"x")
        self.assertEqual(unique_path(target).name, "foto_2.png")

    def test_expand_path_expands_environment_variables(self) -> None:
        os.environ["MF_TEST_ROOT"] = str(self.root)
        try:
            self.assertEqual(expand_path("%MF_TEST_ROOT%/salida"), self.root / "salida")
        finally:
            os.environ.pop("MF_TEST_ROOT", None)

    def test_expand_path_strips_quotes(self) -> None:
        self.assertEqual(expand_path(f'"{self.root}"'), self.root)

    def test_expand_path_rejects_an_undefined_variable(self) -> None:
        name = "MF_TEST_UNDEFINED_VAR"
        os.environ.pop(name, None)
        with self.assertRaises(ValueError):
            expand_path(f"%{name}%/salida")

    def test_unique_path_respects_reserved_destinations(self) -> None:
        target = self.root / "foto.png"
        reserved = {path_key(target)}
        self.assertEqual(unique_path(target, reserved).name, "foto_1.png")
        reserved.add(path_key(self.root / "foto_1.png"))
        self.assertEqual(unique_path(target, reserved).name, "foto_2.png")
        self.assertFalse(any(self.root.glob("foto*.png")))

    def test_format_size(self) -> None:
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(999), "999 B")
        self.assertEqual(format_size(1_500), "1.5 KB")
        self.assertEqual(format_size(2_500_000), "2.5 MB")

    def test_is_writable_dir(self) -> None:
        self.assertTrue(is_writable_dir(self.root))
        missing = self.root / "nueva"
        self.assertFalse(is_writable_dir(missing))
        self.assertTrue(is_writable_dir(missing, create=True))

    def test_documents_and_default_output(self) -> None:
        docs = documents_dir()
        self.assertIsInstance(docs, Path)
        self.assertTrue(docs.is_absolute())
        self.assertEqual(default_output_dir().name, "MediaFormat")


if __name__ == "__main__":
    unittest.main()
