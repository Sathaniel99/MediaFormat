"""Diálogo de ajustes: edita ``config.ini`` sin salir de la aplicación."""

from __future__ import annotations

import contextlib
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.accents import ACCENT_CHOICES
from app.config import Config
from app.converter import available_formats
from app.i18n import LANGUAGE_LABELS, LANGUAGES, tr
from app.models import ConflictPolicy, OutputFormat
from app.paths import expand_path, is_writable_dir
from app.ui.widgets import SelectComboBox, ToggleSwitch

_THEMES = ("system", "light", "dark")
_CONFLICTS = (
    ("conflict.rename", ConflictPolicy.RENAME),
    ("conflict.overwrite", ConflictPolicy.OVERWRITE),
    ("conflict.skip", ConflictPolicy.SKIP),
)


class SettingsDialog(QDialog):
    """Formulario modal que escribe los valores en :class:`app.config.Config`."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.language_changed = False
        self.setWindowTitle(tr("settings.title"))
        self.setModal(True)
        self.setMinimumWidth(520)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(12)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(scroll)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 6, 0)
        body_layout.setSpacing(14)
        body_layout.addWidget(self._build_appearance(body))
        body_layout.addWidget(self._build_conversion(body))
        body_layout.addWidget(self._build_output(body))
        body_layout.addWidget(self._build_behaviour(body))
        body_layout.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        buttons = QDialogButtonBox(self)
        save = buttons.addButton(tr("settings.save"), QDialogButtonBox.ButtonRole.AcceptRole)
        cancel = buttons.addButton(tr("settings.cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        save.setObjectName("Primary")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    # ------------------------------------------------------------------ groups
    def _build_appearance(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox(tr("settings.group.appearance"), parent)
        form = QFormLayout(group)
        form.setSpacing(8)

        self.theme_combo = SelectComboBox(group)
        for name in _THEMES:
            self.theme_combo.addItem(tr(f"theme.{name}"), name)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self.config.theme)))
        form.addRow(tr("settings.theme"), self.theme_combo)

        self.accent_combo = SelectComboBox(group)
        for name in ACCENT_CHOICES:
            self.accent_combo.addItem(tr(f"accent.{name}"), name)
        self.accent_combo.setCurrentIndex(max(0, self.accent_combo.findData(self.config.accent)))
        form.addRow(tr("settings.accent"), self.accent_combo)

        self.language_combo = SelectComboBox(group)
        for code in LANGUAGES:
            self.language_combo.addItem(LANGUAGE_LABELS.get(code, code), code)
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(self.config.language))
        )
        form.addRow(tr("settings.language"), self.language_combo)
        hint = QLabel(tr("settings.language.hint"), group)
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow("", hint)
        return group

    def _build_conversion(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox(tr("settings.group.conversion"), parent)
        form = QFormLayout(group)
        form.setSpacing(8)

        self.format_combo = SelectComboBox(group)
        for fmt in available_formats():
            self.format_combo.addItem(fmt.value, fmt.value)
        self.format_combo.setCurrentIndex(
            max(0, self.format_combo.findData(self.config.default_format.value))
        )
        form.addRow(tr("settings.default_format"), self.format_combo)

        self.png_level = self._spin(group, 0, 9, self.config.png_compress_level)
        form.addRow(tr("settings.png_level"), self.png_level)
        self.workers = self._spin(group, 1, 16, self.config.max_workers)
        form.addRow(tr("settings.workers"), self.workers)

        self.keep_metadata = ToggleSwitch(group)
        self.keep_metadata.setChecked(self.config.keep_metadata)
        form.addRow(tr("settings.keep_metadata"), self._toggle_row(group, self.keep_metadata))
        self.exif = ToggleSwitch(group)
        self.exif.setChecked(self.config.apply_exif_orientation)
        form.addRow(tr("settings.exif"), self._toggle_row(group, self.exif))
        self.animated = ToggleSwitch(group)
        self.animated.setChecked(self.config.animated_frames)
        form.addRow(tr("settings.animated"), self._toggle_row(group, self.animated))
        self.recursive = ToggleSwitch(group)
        self.recursive.setChecked(self.config.recursive_folders)
        form.addRow(tr("settings.recursive"), self._toggle_row(group, self.recursive))
        return group

    def _build_output(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox(tr("settings.group.output"), parent)
        form = QFormLayout(group)
        form.setSpacing(8)

        self.output_edit = QLineEdit(group)
        self.output_edit.setText(str(self.config.output_folder))
        self.output_edit.setReadOnly(True)
        self.output_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.output_edit.setToolTip(tr("tooltip.output"))
        browse = QPushButton(tr("button.choose_output"), group)
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.clicked.connect(self._browse_output)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.output_edit, 1)
        row.addWidget(browse)
        wrapper = QWidget(group)
        wrapper.setLayout(row)
        form.addRow(tr("settings.output_folder"), wrapper)

        self.conflict_combo = SelectComboBox(group)
        for key, policy in _CONFLICTS:
            self.conflict_combo.addItem(tr(key), policy.value)
        self.conflict_combo.setCurrentIndex(
            max(0, self.conflict_combo.findData(self.config.on_conflict.value))
        )
        form.addRow(tr("settings.conflict"), self.conflict_combo)

        self.open_after = ToggleSwitch(group)
        self.open_after.setChecked(self.config.open_after_convert)
        form.addRow(tr("settings.open_after"), self._toggle_row(group, self.open_after))
        return group

    def _build_behaviour(self, parent: QWidget) -> QGroupBox:
        group = QGroupBox(tr("settings.group.behaviour"), parent)
        form = QFormLayout(group)
        form.setSpacing(8)

        self.notify = ToggleSwitch(group)
        self.notify.setChecked(self.config.notify_on_finish)
        form.addRow(tr("settings.notify"), self._toggle_row(group, self.notify))
        self.restore_queue = ToggleSwitch(group)
        self.restore_queue.setChecked(self.config.restore_queue)
        form.addRow(tr("settings.restore_queue"), self._toggle_row(group, self.restore_queue))
        return group

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _spin(parent: QWidget, minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox(parent)
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    @staticmethod
    def _toggle_row(parent: QWidget, toggle: ToggleSwitch) -> QWidget:
        wrapper = QWidget(parent)
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(toggle)
        row.addStretch(1)
        return wrapper

    def _browse_output(self) -> None:
        start = self.output_edit.text().strip() or str(self.config.output_folder)
        folder = QFileDialog.getExistingDirectory(self, tr("dialog.choose_output"), start)
        if folder:
            self.output_edit.setText(folder)

    # ------------------------------------------------------------------ accept
    def accept(self) -> None:
        output_dir = expand_path(self.output_edit.text().strip())
        if not is_writable_dir(output_dir, create=False):
            QMessageBox.warning(
                self,
                tr("dialog.invalid_output.title"),
                tr("dialog.invalid_output.body", path=output_dir),
            )
            return

        previous_language = self.config.language
        self.config.theme = str(self.theme_combo.currentData())
        self.config.accent = str(self.accent_combo.currentData())
        self.config.language = str(self.language_combo.currentData())
        self.config.default_format = OutputFormat.from_value(self.format_combo.currentData())
        self.config.png_compress_level = self.png_level.value()
        self.config.max_workers = self.workers.value()
        self.config.keep_metadata = self.keep_metadata.isChecked()
        self.config.apply_exif_orientation = self.exif.isChecked()
        self.config.animated_frames = self.animated.isChecked()
        self.config.recursive_folders = self.recursive.isChecked()
        self.config.output_folder = output_dir
        self.config.on_conflict = ConflictPolicy.from_value(self.conflict_combo.currentData())
        self.config.open_after_convert = self.open_after.isChecked()
        self.config.notify_on_finish = self.notify.isChecked()
        self.config.restore_queue = self.restore_queue.isChecked()

        with contextlib.suppress(OSError):
            self.config.save()
        self.language_changed = self.config.language != previous_language
        super().accept()


def settings_output_dir(edit: QLineEdit) -> Path:
    """Utilidad compartida por las pruebas: normaliza la carpeta escrita."""
    return expand_path(edit.text().strip())
