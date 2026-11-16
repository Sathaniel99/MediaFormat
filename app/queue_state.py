"""Persistencia de la cola de conversion (JSON, sin Qt).

Se guarda en ``%LOCALAPPDATA%\\MediaFormat\\queue.json`` para no mezclar estado
efimero con el ``config.ini`` editable. ``RUNNING`` se degrada a ``PENDING`` al
recuperar, de modo que un cierre inesperado no deja filas bloqueadas.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.models import JobStatus
from app.paths import data_dir

QUEUE_VERSION = 1
QUEUE_FILENAME = "queue.json"


def queue_path() -> Path:
    return data_dir() / QUEUE_FILENAME


@dataclass(slots=True)
class QueueEntry:
    path: str
    status: str = JobStatus.PENDING.value
    message: str = ""


@dataclass(slots=True)
class QueueSnapshot:
    entries: list[QueueEntry] = field(default_factory=list)
    output_dir: str | None = None
    saved_at: str = ""

    @property
    def empty(self) -> bool:
        return not self.entries


def save_queue(
    entries: list[QueueEntry],
    output_dir: Path | str | None = None,
    path: Path | None = None,
) -> Path:
    """Escribe la cola de forma atomica y devuelve la ruta."""
    target = path or queue_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": QUEUE_VERSION,
        "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "output_dir": os.fspath(output_dir) if output_dir is not None else "",
        "items": [
            {"path": entry.path, "status": entry.status, "message": entry.message}
            for entry in entries
        ],
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            with contextlib.suppress(OSError):
                temporary.unlink()
    return target


def load_queue(path: Path | None = None) -> QueueSnapshot:
    """Lee la cola; un archivo ausente o corrupto produce una cola vacia."""
    target = path or queue_path()
    if not target.is_file():
        return QueueSnapshot()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return QueueSnapshot()
    if not isinstance(payload, dict):
        return QueueSnapshot()

    valid_status = {status.value for status in JobStatus}
    entries: list[QueueEntry] = []
    for raw in payload.get("items", []):
        if not isinstance(raw, dict):
            continue
        path_value = str(raw.get("path", "")).strip()
        if not path_value:
            continue
        status = str(raw.get("status", JobStatus.PENDING.value))
        if status not in valid_status or status == JobStatus.RUNNING.value:
            status = JobStatus.PENDING.value
        entries.append(
            QueueEntry(
                path=path_value,
                status=status,
                message=str(raw.get("message", "")),
            )
        )
    output = str(payload.get("output_dir", "")).strip() or None
    return QueueSnapshot(
        entries=entries,
        output_dir=output,
        saved_at=str(payload.get("saved_at", "")),
    )


def clear_queue(path: Path | None = None) -> None:
    target = path or queue_path()
    with contextlib.suppress(OSError):
        target.unlink()
