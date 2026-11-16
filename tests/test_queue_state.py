"""Pruebas de la cola persistente de conversión."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.models import JobStatus
from app.queue_state import QueueEntry, clear_queue, load_queue, save_queue


class QueueStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.path = self.root / "queue.json"

    def test_missing_file_returns_empty_snapshot(self) -> None:
        snapshot = load_queue(self.path)
        self.assertTrue(snapshot.empty)
        self.assertIsNone(snapshot.output_dir)

    def test_roundtrip_keeps_order_and_output_dir(self) -> None:
        entries = [
            QueueEntry("C:/fotos/a.png"),
            QueueEntry("C:/fotos/b.png", status=JobStatus.ERROR.value, message="fallo"),
        ]
        save_queue(entries, self.root / "salida", self.path)

        snapshot = load_queue(self.path)
        self.assertEqual(
            [entry.path for entry in snapshot.entries], ["C:/fotos/a.png", "C:/fotos/b.png"]
        )
        self.assertEqual(snapshot.entries[1].status, JobStatus.ERROR.value)
        self.assertEqual(snapshot.entries[1].message, "fallo")
        self.assertEqual(snapshot.output_dir, str(self.root / "salida"))
        self.assertTrue(snapshot.saved_at)

    def test_running_status_degrades_to_pending(self) -> None:
        payload = {
            "version": 1,
            "items": [{"path": "C:/fotos/a.png", "status": "running"}],
        }
        self.path.write_text(json.dumps(payload), encoding="utf-8")

        snapshot = load_queue(self.path)

        self.assertEqual(snapshot.entries[0].status, JobStatus.PENDING.value)

    def test_unknown_status_degrades_to_pending(self) -> None:
        payload = {"items": [{"path": "C:/fotos/a.png", "status": "exploded"}]}
        self.path.write_text(json.dumps(payload), encoding="utf-8")

        self.assertEqual(load_queue(self.path).entries[0].status, JobStatus.PENDING.value)

    def test_corrupt_file_and_invalid_entries_are_ignored(self) -> None:
        self.path.write_text("{no json", encoding="utf-8")
        self.assertTrue(load_queue(self.path).empty)

        payload = {"items": [{"path": ""}, "texto", {"path": "C:/ok.png"}]}
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        snapshot = load_queue(self.path)
        self.assertEqual([entry.path for entry in snapshot.entries], ["C:/ok.png"])

    def test_clear_queue_is_idempotent(self) -> None:
        save_queue([QueueEntry("C:/fotos/a.png")], path=self.path)
        clear_queue(self.path)
        self.assertFalse(self.path.exists())
        clear_queue(self.path)

    def test_save_leaves_no_temporary_file(self) -> None:
        save_queue([QueueEntry("C:/fotos/a.png")], path=self.path)
        self.assertFalse(self.path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
