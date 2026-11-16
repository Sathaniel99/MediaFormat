"""Qt table model for the file list.

Pure UI state: it never touches the filesystem beyond ``stat()`` and never
imports the conversion engine. The window feeds it results.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QImage

from app.i18n import tr
from app.models import ConversionResult, JobStatus
from app.paths import format_size

COLUMN_PREVIEW = 0
COLUMN_NAME = 1
COLUMN_DIMENSIONS = 2
COLUMN_SIZE = 3
COLUMN_STATUS = 4

ITEM_ROLE = int(Qt.ItemDataRole.UserRole) + 1

_STATUS_KEYS: dict[JobStatus, str] = {
    JobStatus.PENDING: "status.pending",
    JobStatus.RUNNING: "status.running",
    JobStatus.DONE: "status.done",
    JobStatus.SKIPPED: "status.skipped",
    JobStatus.ERROR: "status.error",
}

#: Compatibilidad con codigo que solo necesita la etiqueta en español.
STATUS_LABELS: dict[JobStatus, str] = {status: tr(key) for status, key in _STATUS_KEYS.items()}


def status_label(status: JobStatus) -> str:
    """Etiqueta traducida del estado de una fila."""
    key = _STATUS_KEYS.get(status)
    return tr(key) if key is not None else ""


def path_key(path: Path) -> str:
    """Case-insensitive key for Windows-style duplicate detection."""
    try:
        return str(path.resolve()).lower()
    except OSError:
        return str(path).lower()


@dataclass(slots=True)
class FileItem:
    """One row of the list."""

    path: Path
    size: int = 0
    status: JobStatus = JobStatus.PENDING
    message: str = ""
    image_size: tuple[int, int] | None = None
    thumbnail: QImage | None = None
    output: Path | None = None
    size_out: int = 0
    duration_ms: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)


class FileListModel(QAbstractTableModel):
    """List of images to convert, with status and thumbnail per row."""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._items: list[FileItem] = []
        self._rows: dict[str, int] = {}

    @property
    def HEADERS(self) -> tuple[str, str, str, str, str]:  # noqa: N802 - nombre historico
        return (
            tr("header.preview"),
            tr("header.name"),
            tr("header.dimensions"),
            tr("header.size"),
            tr("header.status"),
        )

    # ----------------------------------------------------------- Qt interface
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802, B008
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> object:
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        column = index.column()

        if role == ITEM_ROLE:
            return item
        if role == int(Qt.ItemDataRole.DisplayRole):
            if column == COLUMN_NAME:
                return item.path.name
            if column == COLUMN_DIMENSIONS:
                return self._dimensions(item)
            if column == COLUMN_SIZE:
                return format_size(item.size)
            if column == COLUMN_STATUS:
                return status_label(item.status)
            return ""
        if role == int(Qt.ItemDataRole.ToolTipRole):
            return self._tooltip(item)
        if role == int(Qt.ItemDataRole.TextAlignmentRole):
            if column in (COLUMN_PREVIEW, COLUMN_NAME):
                alignment = Qt.AlignmentFlag.AlignLeft
            else:
                alignment = Qt.AlignmentFlag.AlignHCenter
            return alignment | Qt.AlignmentFlag.AlignVCenter
        if role == int(Qt.ItemDataRole.AccessibleTextRole):
            return item.path.name
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> object:
        if orientation is Qt.Orientation.Horizontal and role == int(Qt.ItemDataRole.DisplayRole):
            headers = self.HEADERS
            return headers[section] if 0 <= section < len(headers) else ""
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsDragEnabled
            | Qt.ItemFlag.ItemIsDropEnabled
        )

    def supportedDropActions(self) -> Qt.DropAction:  # noqa: N802
        return Qt.DropAction.MoveAction

    def supportedDragActions(self) -> Qt.DropAction:  # noqa: N802
        return Qt.DropAction.MoveAction

    # ------------------------------------------------------------- public API
    def add_paths(self, paths: Iterable[Path]) -> list[Path]:
        """Append new files, ignoring duplicates; return the added paths."""
        fresh: list[FileItem] = []
        keys: set[str] = set()
        for raw in paths:
            path = Path(raw)
            key = path_key(path)
            if key in self._rows or key in keys or not path.is_file():
                continue
            keys.add(key)
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            fresh.append(FileItem(path=path, size=size))

        if not fresh:
            return []
        start = len(self._items)
        self.beginInsertRows(QModelIndex(), start, start + len(fresh) - 1)
        self._items.extend(fresh)
        self.endInsertRows()
        self._reindex()
        return [item.path for item in fresh]

    def remove_rows(self, rows: Iterable[int]) -> None:
        """Remove rows by index (descending to keep indexes valid)."""
        for row in sorted(set(rows), reverse=True):
            if 0 <= row < len(self._items):
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._items[row]
                self.endRemoveRows()
        self._reindex()

    def move_rows(self, rows: Iterable[int], target: int) -> list[int]:
        """Move the given rows so they sit before ``target``.

        ``target`` is an insertion index in the *current* list. Returns the new
        row numbers occupied by the moved block.
        """
        selected = sorted({row for row in rows if 0 <= row < len(self._items)})
        if not selected:
            return []
        target = max(0, min(int(target), len(self._items)))

        moving = [self._items[row] for row in selected]
        selected_set = set(selected)
        remaining = [item for index, item in enumerate(self._items) if index not in selected_set]
        insert_at = max(0, min(target - sum(1 for row in selected if row < target), len(remaining)))

        reordered = remaining[:insert_at] + moving + remaining[insert_at:]
        if reordered == self._items:
            return selected

        self.beginResetModel()
        self._items = reordered
        self._reindex()
        self.endResetModel()
        return list(range(insert_at, insert_at + len(moving)))

    def clear(self) -> None:
        if not self._items:
            return
        self.beginResetModel()
        self._items.clear()
        self._rows.clear()
        self.endResetModel()

    def item_at(self, row: int) -> FileItem | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def find_row(self, path: Path) -> int:
        return self._rows.get(path_key(path), -1)

    def rows_matching(self, paths: Iterable[Path]) -> list[int]:
        rows: list[int] = []
        for path in paths:
            row = self.find_row(path)
            if row >= 0:
                rows.append(row)
        return rows

    def paths(self) -> list[Path]:
        return [item.path for item in self._items]

    def total_size(self) -> int:
        return sum(item.size for item in self._items)

    def set_image_info(
        self,
        path: Path,
        width: int,
        height: int,
        thumbnail: QImage | None = None,
    ) -> None:
        row = self.find_row(path)
        if row < 0:
            return
        item = self._items[row]
        item.image_size = (width, height)
        if thumbnail is not None:
            item.thumbnail = thumbnail
        self._emit_row(row, (COLUMN_PREVIEW, COLUMN_DIMENSIONS))

    def apply_result(self, result: ConversionResult) -> None:
        row = self.find_row(result.source)
        if row < 0:
            return
        item = self._items[row]
        item.status = result.status
        item.output = result.output
        item.size_out = result.size_out
        item.duration_ms = result.duration_ms
        item.notes = result.notes
        item.message = result.error or "; ".join(result.notes)
        self._emit_row(row)

    def set_status(self, rows: Iterable[int], status: JobStatus, message: str = "") -> None:
        """Force a status in selected rows (used while cancelling)."""
        changed: list[int] = []
        for row in rows:
            if 0 <= row < len(self._items):
                item = self._items[row]
                item.status = status
                item.message = message
                changed.append(row)
        if changed:
            self._emit_row(changed)

    def reset_rows(self, rows: Iterable[int] | None = None) -> None:
        """Mark the given rows (or all) as pending before a new conversion."""
        targets = range(len(self._items)) if rows is None else rows
        changed: list[int] = []
        for row in targets:
            if 0 <= row < len(self._items):
                item = self._items[row]
                item.status = JobStatus.PENDING
                item.message = ""
                item.output = None
                item.size_out = 0
                item.duration_ms = 0
                item.notes = ()
                changed.append(row)
        if changed:
            self._emit_row(changed)

    def reset_batch(self) -> None:
        """Mark every row as pending again before a new conversion."""
        self.reset_rows()

    def failed_rows(self) -> list[int]:
        return [row for row, item in enumerate(self._items) if item.status is JobStatus.ERROR]

    def status_counts(self) -> dict[JobStatus, int]:
        counts = dict.fromkeys(JobStatus, 0)
        for item in self._items:
            counts[item.status] += 1
        return counts

    # ------------------------------------------------------------- internals
    def _reindex(self) -> None:
        self._rows = {path_key(item.path): row for row, item in enumerate(self._items)}

    def _emit_row(
        self,
        rows: int | Iterable[int],
        columns: Iterable[int] | None = None,
    ) -> None:
        if isinstance(rows, int):
            first = last = rows
        else:
            values = list(rows)
            if not values:
                return
            first, last = min(values), max(values)
        if last < first:
            return
        if columns is None:
            self.dataChanged.emit(
                self.index(first, 0),
                self.index(last, len(self.HEADERS) - 1),
            )
        else:
            for column in columns:
                self.dataChanged.emit(self.index(first, column), self.index(last, column))

    @staticmethod
    def _dimensions(item: FileItem) -> str:
        if item.image_size is None:
            return "—"
        width, height = item.image_size
        return f"{width} × {height}"

    @staticmethod
    def _tooltip(item: FileItem) -> str:
        lines = [str(item.path), tr("list.tooltip.size", size=format_size(item.size))]
        if item.output is not None:
            lines.append(tr("list.tooltip.output", path=item.output))
            lines.append(tr("list.tooltip.final_size", size=format_size(item.size_out)))
        if item.duration_ms:
            lines.append(tr("list.tooltip.duration", value=item.duration_ms))
        if item.message:
            lines.append(item.message)
        return "\n".join(lines)
