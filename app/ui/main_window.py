"""Main window for MediaFormat (Phase 2), styled after Windows 11."""

from __future__ import annotations

import ctypes
import logging
import os
import re
import sys
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QThread, QTimer
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QFont,
    QFontDatabase,
    QKeySequence,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from app.accents import ACCENT_CHOICES
from app.config import Config
from app.converter import available_formats, collect_sources, supported_extensions
from app.i18n import set_language, tr
from app.logging_setup import setup_logging
from app.models import ConflictPolicy, ConversionOptions, JobStatus, OutputFormat
from app.paths import expand_path, format_size, is_writable_dir, open_folder
from app.profiles import (
    Profile,
    all_profiles,
    custom_profile_key,
    profile_label,
    profile_to_json,
)
from app.queue_state import QueueEntry, clear_queue, load_queue, save_queue
from app.ui.branding import app_icon, apply_dark_titlebar, set_taskbar_identity
from app.ui.convert_worker import ConvertWorker
from app.ui.delegates import StatusDelegate, ThumbnailDelegate
from app.ui.file_model import (
    COLUMN_DIMENSIONS,
    COLUMN_NAME,
    COLUMN_PREVIEW,
    COLUMN_SIZE,
    COLUMN_STATUS,
    FileListModel,
)
from app.ui.icons import app_logo, icon, pixmap, swatch
from app.ui.settings_dialog import SettingsDialog
from app.ui.theme import ThemeColors, build_palette, build_stylesheet, resolve_colors
from app.ui.thumbnails import ThumbnailService
from app.ui.widgets import FileTable, SelectComboBox, ToggleSwitch

LOGGER = logging.getLogger("mediaformat.ui")

_THEME_ORDER = ("system", "light", "dark")
_THEME_ICONS = {"system": "monitor", "light": "sun", "dark": "moon"}
_COMMON_FILTER = "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif *.ico *.tga *.avif"
_QUALITY_PRESETS = (
    ("quality.maximum", 95),
    ("quality.high", 85),
    ("quality.medium", 75),
    ("quality.low", 60),
)
_PRESET_QUALITIES = tuple(value for _, value in _QUALITY_PRESETS)
_LEGACY_GEOMETRIES = ("", "900x640", "1040x780")
_MIN_WINDOW = (940, 700)


class MainWindow(QMainWindow):
    """Single-window UI: queue, options and conversion controls."""

    def __init__(
        self,
        config: Config | None = None,
        queue_file: Path | None = None,
    ) -> None:
        super().__init__()
        self.config = config or Config()
        set_language(self.config.language)
        self.colors: ThemeColors = resolve_colors(self.config.theme, self.config.accent)
        self._running = False
        self._closing = False
        self._worker: ConvertWorker | None = None
        self._thread: QThread | None = None
        self._shortcuts: list[QShortcut] = []
        self._summary = ""
        self._quality_cache: dict[OutputFormat, int] = {}
        self._updating_quality = False
        self._profiles: list[Profile] = []
        self._loading_profile = False
        self._tray: QSystemTrayIcon | None = None
        self._queue_file = queue_file
        self._batch_sources: set[str] = set()
        self._center_on_show = False

        self.setWindowTitle("MediaFormat")
        self.setMinimumSize(*_MIN_WINDOW)
        self.setWindowIcon(app_icon())

        self._build_ui()
        self._connect_signals()
        self._seed_quality_cache()
        self._load_config()
        self._apply_theme()
        self._setup_tray()
        self._restore_geometry()
        self._update_count()
        self._update_actions()
        self._restore_queue()
        self._refresh_banner()

    # ------------------------------------------------------------------ layout
    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(14)

        outer.addLayout(self._build_header())
        self.banner = self._build_banner(root)
        outer.addWidget(self.banner)
        outer.addWidget(self._build_list_card(), 1)
        outer.addWidget(self._build_options_card())

        self.progress_bar = QProgressBar(root)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setAccessibleName(tr("progress.accessible"))
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setVisible(False)
        outer.addWidget(self.progress_bar)

        outer.addLayout(self._build_footer())
        self.setCentralWidget(root)

    def _build_header(self) -> QHBoxLayout:
        logo = QLabel(self)
        logo.setPixmap(app_logo(44))
        logo.setFixedSize(44, 44)
        logo.setToolTip("MediaFormat")

        title = QLabel("MediaFormat", self)
        title.setObjectName("Title")
        subtitle = QLabel(tr("app.subtitle"), self)
        subtitle.setObjectName("Subtitle")

        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(title)
        text.addWidget(subtitle)

        self.theme_button = QPushButton(self)
        self.theme_button.setObjectName("IconButton")
        self.theme_button.setFixedSize(34, 34)
        self.theme_button.setIconSize(QSize(18, 18))
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.setAccessibleName(tr("settings.theme"))

        self.accent_button = QPushButton(self)
        self.accent_button.setObjectName("IconButton")
        self.accent_button.setFixedSize(34, 34)
        self.accent_button.setIconSize(QSize(18, 18))
        self.accent_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.accent_button.setAccessibleName(tr("settings.accent"))
        self._accent_menu = QMenu(self.accent_button)
        self._accent_group = QActionGroup(self._accent_menu)
        self._accent_group.setExclusive(True)
        self._accent_actions: dict[str, QAction] = {}
        for name in ACCENT_CHOICES:
            action = self._accent_menu.addAction(tr(f"accent.{name}"))
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, accent=name: self._set_accent(accent))
            self._accent_group.addAction(action)
            self._accent_actions[name] = action

        self.settings_button = QPushButton(self)
        self.settings_button.setObjectName("IconButton")
        self.settings_button.setFixedSize(34, 34)
        self.settings_button.setIconSize(QSize(18, 18))
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setToolTip(tr("tooltip.settings"))
        self.settings_button.setAccessibleName(tr("button.settings"))

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(logo)
        header.addLayout(text)
        header.addStretch(1)
        header.addWidget(self.accent_button)
        header.addWidget(self.theme_button)
        header.addWidget(self.settings_button)
        return header

    def _build_banner(self, parent: QWidget) -> QFrame:
        banner = QFrame(parent)
        banner.setObjectName("Banner")
        banner.setVisible(False)
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(8)

        self.banner_icon = QLabel(banner)
        self.banner_icon.setFixedSize(18, 18)
        self.banner_label = QLabel("", banner)
        self.banner_label.setWordWrap(True)
        self.banner_details = QPushButton(tr("banner.view"), banner)
        self.banner_details.setObjectName("Ghost")
        self.banner_details.setAccessibleName(tr("banner.view"))
        self.banner_details.setCursor(Qt.CursorShape.PointingHandCursor)
        self.banner_close = QPushButton(banner)
        self.banner_close.setObjectName("IconButton")
        self.banner_close.setFixedSize(28, 28)
        self.banner_close.setIconSize(QSize(14, 14))
        self.banner_close.setToolTip(tr("banner.close"))
        self.banner_close.setAccessibleName(tr("banner.close"))
        self.banner_close.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(self.banner_icon)
        layout.addWidget(self.banner_label, 1)
        layout.addWidget(self.banner_details)
        layout.addWidget(self.banner_close)
        return banner

    def _build_list_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 10, 8, 6)
        toolbar.setSpacing(4)

        self.count_label = QLabel(tr("section.images", count=0), card)
        self.count_label.setObjectName("SectionTitle")

        self.add_files_button = QPushButton(tr("button.add_files"), card)
        self.add_files_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_files_button.setIconSize(QSize(16, 16))
        self.add_files_button.setAccessibleName(tr("button.add_files"))

        self.add_folder_button = self._icon_button("folder", tr("button.add_folder"), card)
        self.remove_button = self._icon_button("trash", tr("button.remove"), card)
        self.clear_button = self._icon_button("clear", tr("button.clear"), card)

        toolbar.addWidget(self.count_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self.add_files_button)
        toolbar.addWidget(self.add_folder_button)
        toolbar.addWidget(self.remove_button)
        toolbar.addWidget(self.clear_button)
        layout.addLayout(toolbar)

        self.model = FileListModel(self)
        self.table = FileTable(card)
        self.table.setAccessibleName(tr("table.accessible"))
        self.table.setModel(self.model)
        self.table.setItemDelegateForColumn(COLUMN_PREVIEW, ThumbnailDelegate(self.table))
        self._status_delegate = StatusDelegate(self.table, dark=self.colors.dark)
        self.table.setItemDelegateForColumn(COLUMN_STATUS, self._status_delegate)

        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionResizeMode(COLUMN_PREVIEW, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COLUMN_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COLUMN_DIMENSIONS, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COLUMN_SIZE, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COLUMN_STATUS, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COLUMN_PREVIEW, 68)
        self.table.setColumnWidth(COLUMN_DIMENSIONS, 124)
        self.table.setColumnWidth(COLUMN_SIZE, 92)
        self.table.setColumnWidth(COLUMN_STATUS, 118)

        layout.addWidget(self.table, 1)
        self.thumbnails = ThumbnailService(self)
        return card

    def _build_options_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        row_profile = QHBoxLayout()
        row_profile.setSpacing(8)
        row_profile.addWidget(QLabel(tr("label.profile"), card))
        self.profile_combo = SelectComboBox(card)
        self.profile_combo.setMinimumWidth(150)
        self.profile_combo.setToolTip(tr("tooltip.profile"))
        self.profile_combo.setAccessibleName(tr("label.profile"))
        row_profile.addWidget(self.profile_combo)
        self.save_profile_button = QPushButton(tr("button.save_profile"), card)
        self.save_profile_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_profile_button = QPushButton(tr("button.delete_profile"), card)
        self.delete_profile_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_profile_button.setObjectName("Ghost")
        row_profile.addWidget(self.save_profile_button)
        row_profile.addWidget(self.delete_profile_button)
        row_profile.addStretch(1)
        layout.addLayout(row_profile)

        row_format = QHBoxLayout()
        row_format.setSpacing(10)
        row_format.addWidget(QLabel(tr("label.format"), card))
        self.format_combo = SelectComboBox(card)
        self.format_combo.setMinimumWidth(120)
        self.format_combo.setAccessibleName(tr("label.format"))
        row_format.addWidget(self.format_combo)

        row_format.addSpacing(14)
        self.quality_label = QLabel(tr("label.quality"), card)
        self.quality_combo = SelectComboBox(card)
        self.quality_combo.setMinimumWidth(160)
        self.quality_combo.setToolTip(tr("tooltip.quality"))
        self.quality_combo.setAccessibleName(tr("label.quality"))
        for key, value in _QUALITY_PRESETS:
            self.quality_combo.addItem(tr(key), value)
        row_format.addWidget(self.quality_label)
        row_format.addWidget(self.quality_combo)

        row_format.addSpacing(12)
        self.lossless_toggle = ToggleSwitch(card)
        self.lossless_toggle.setAccessibleName(tr("label.lossless"))
        self.lossless_label = QLabel(tr("label.lossless"), card)
        row_format.addWidget(self.lossless_toggle)
        row_format.addWidget(self.lossless_label)
        row_format.addStretch(1)
        layout.addLayout(row_format)

        row_output = QHBoxLayout()
        row_output.setSpacing(10)
        row_output.addWidget(QLabel(tr("label.save_in"), card))
        self.output_edit = QLineEdit(card)
        self.output_edit.setPlaceholderText(tr("placeholder.output"))
        self.output_edit.setReadOnly(True)
        self.output_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.output_edit.setToolTip(tr("tooltip.output"))
        self.output_edit.setAccessibleName(tr("label.save_in"))
        self.browse_output_button = QPushButton(tr("button.choose_output"), card)
        self.browse_output_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_output_button.setIconSize(QSize(16, 16))
        self.browse_output_button.setAccessibleName(tr("button.choose_output"))
        row_output.addWidget(self.output_edit, 1)
        row_output.addWidget(self.browse_output_button)
        layout.addLayout(row_output)

        row_extra = QHBoxLayout()
        row_extra.setSpacing(10)
        row_extra.addWidget(QLabel(tr("label.if_exists"), card))
        self.conflict_combo = SelectComboBox(card)
        self.conflict_combo.setMinimumWidth(118)
        self.conflict_combo.setAccessibleName(tr("label.if_exists"))
        row_extra.addWidget(self.conflict_combo)
        row_extra.addStretch(1)

        self.open_after_toggle = ToggleSwitch(card)
        self.open_after_toggle.setAccessibleName(tr("label.open_after"))
        row_extra.addWidget(self.open_after_toggle)
        row_extra.addWidget(QLabel(tr("label.open_after"), card))
        row_extra.addSpacing(12)

        self.animated_toggle = ToggleSwitch(card)
        self.animated_toggle.setAccessibleName(tr("label.keep_animation"))
        row_extra.addWidget(self.animated_toggle)
        row_extra.addWidget(QLabel(tr("label.keep_animation"), card))
        layout.addLayout(row_extra)
        return card

    def _build_footer(self) -> QHBoxLayout:
        self.status_label = QLabel(tr("status.no_images"), self)
        self.status_label.setObjectName("Muted")
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.open_folder_button = QPushButton(tr("button.open_folder"), self)
        self.open_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_button.setIconSize(QSize(16, 16))
        self.open_folder_button.setAccessibleName(tr("button.open_folder"))

        self.retry_button = QPushButton(tr("button.retry_failed"), self)
        self.retry_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_button.setIconSize(QSize(16, 16))
        self.retry_button.setVisible(False)
        self.retry_button.setAccessibleName(tr("button.retry_failed"))

        self.cancel_button = QPushButton(tr("button.cancel"), self)
        self.cancel_button.setObjectName("Ghost")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setIconSize(QSize(16, 16))
        self.cancel_button.setVisible(False)
        self.cancel_button.setAccessibleName(tr("button.cancel"))

        self.convert_button = QPushButton(tr("button.convert"), self)
        self.convert_button.setObjectName("Primary")
        self.convert_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.convert_button.setIconSize(QSize(16, 16))
        self.convert_button.setMinimumWidth(148)
        self.convert_button.setMinimumHeight(38)
        self.convert_button.setAccessibleName(tr("button.convert"))

        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.open_folder_button)
        footer.addWidget(self.retry_button)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.convert_button)
        return footer

    def _icon_button(self, name: str, tooltip: str, parent: QWidget) -> QPushButton:
        button = QPushButton(parent)
        button.setObjectName("IconButton")
        button.setFixedSize(32, 32)
        button.setIconSize(QSize(18, 18))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setProperty("iconName", name)
        return button

    # ---------------------------------------------------------------- signals
    def _connect_signals(self) -> None:
        self.add_files_button.clicked.connect(self._browse_files)
        self.add_folder_button.clicked.connect(self._browse_folder)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self._clear_all)
        self.convert_button.clicked.connect(self._start_conversion)
        self.cancel_button.clicked.connect(self._cancel_conversion)
        self.retry_button.clicked.connect(self._retry_failed)
        self.open_folder_button.clicked.connect(self._open_output_folder)
        self.browse_output_button.clicked.connect(self._browse_output)
        self.theme_button.clicked.connect(self._cycle_theme)
        self.accent_button.clicked.connect(self._show_accent_menu)
        self.settings_button.clicked.connect(self._open_settings)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.quality_combo.currentIndexChanged.connect(self._on_quality_changed)
        self.lossless_toggle.toggled.connect(self._on_lossless_changed)
        self.thumbnails.ready.connect(self._on_thumbnail_ready)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self.save_profile_button.clicked.connect(self._save_profile)
        self.delete_profile_button.clicked.connect(self._delete_profile)
        self.banner_details.clicked.connect(self._show_banner_details)
        self.banner_close.clicked.connect(lambda: self.banner.setVisible(False))
        self.table.pathsDropped.connect(self._add_paths)
        self.table.browseRequested.connect(self._browse_files)
        self.table.rowsReordered.connect(self._on_rows_reordered)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        selection = self.table.selectionModel()
        if selection is not None:
            selection.selectionChanged.connect(self._update_actions)

        hints = QApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

        self._add_shortcut(QKeySequence.StandardKey.Open, self._browse_files)
        self._add_shortcut(QKeySequence("Ctrl+Shift+O"), self._browse_folder)
        self._add_shortcut(QKeySequence("Ctrl+Return"), self._start_conversion)
        self._add_shortcut(QKeySequence("Esc"), self._cancel_conversion)
        self._add_shortcut(QKeySequence.StandardKey.Delete, self._remove_selected)
        self._add_shortcut(QKeySequence("Ctrl+,"), self._open_settings)

    def _add_shortcut(self, sequence: QKeySequence | QKeySequence.StandardKey, slot) -> None:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.activated.connect(slot)
        self._shortcuts.append(shortcut)

    # ------------------------------------------------------------- config/state
    def _seed_quality_cache(self) -> None:
        self._quality_cache = {
            OutputFormat.JPEG: self.config.jpeg_quality,
            OutputFormat.WEBP: self.config.webp_quality,
        }

    @staticmethod
    def _quality_key(fmt: OutputFormat) -> OutputFormat:
        """AVIF comparte la calidad de WebP en la configuración."""
        return OutputFormat.WEBP if fmt is OutputFormat.AVIF else fmt

    def _load_config(self) -> None:
        for fmt in available_formats():
            self.format_combo.addItem(fmt.value, fmt.value)
        target_index = self.format_combo.findData(self.config.default_format.value)
        self.format_combo.setCurrentIndex(max(0, target_index))

        for key, policy in (
            ("conflict.rename", ConflictPolicy.RENAME),
            ("conflict.overwrite", ConflictPolicy.OVERWRITE),
            ("conflict.skip", ConflictPolicy.SKIP),
        ):
            self.conflict_combo.addItem(tr(key), policy.value)
        conflict_index = self.conflict_combo.findData(self.config.on_conflict.value)
        self.conflict_combo.setCurrentIndex(max(0, conflict_index))

        self._load_profiles()
        self._apply_config_to_widgets()

    def _apply_config_to_widgets(self) -> None:
        self.output_edit.setText(os.fspath(self.config.output_folder))
        self.open_after_toggle.setChecked(self.config.open_after_convert)
        self.animated_toggle.setChecked(self.config.animated_frames)
        self.lossless_toggle.setChecked(self.config.webp_lossless)
        index = self.format_combo.findData(self.config.default_format.value)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
        conflict_index = self.conflict_combo.findData(self.config.on_conflict.value)
        if conflict_index >= 0:
            self.conflict_combo.setCurrentIndex(conflict_index)
        self._seed_quality_cache()
        self._on_format_changed()

    def _load_profiles(self, select_key: str | None = None) -> None:
        self._loading_profile = True
        try:
            self.profile_combo.clear()
            self.profile_combo.addItem(tr("profile.none"), "")
            self._profiles = all_profiles(self.config.profiles_raw)
            for profile in self._profiles:
                self.profile_combo.addItem(profile_label(profile, tr), profile.key)
            index = self.profile_combo.findData(select_key) if select_key else 0
            self.profile_combo.setCurrentIndex(max(0, index))
        finally:
            self._loading_profile = False
        self._update_actions()

    def _save_config(self) -> None:
        try:
            text = self.output_edit.text().strip()
            if text:
                self.config.output_folder = expand_path(text)
            fmt = self._current_format()
            self.config.default_format = fmt
            self.config.jpeg_quality = self._quality_cache.get(
                OutputFormat.JPEG, self.config.jpeg_quality
            )
            self.config.webp_quality = self._quality_cache.get(
                OutputFormat.WEBP, self.config.webp_quality
            )
            self.config.open_after_convert = self.open_after_toggle.isChecked()
            self.config.animated_frames = self.animated_toggle.isChecked()
            self.config.webp_lossless = self.lossless_toggle.isChecked()
            self.config.on_conflict = self._current_conflict()

            normal = self.normalGeometry()
            self.config.window_geometry = f"{normal.width()}x{normal.height()}"
            # La posición ya no se restaura: la ventana se abre siempre centrada.
            self.config.window_position = None
            self.config.window_maximized = self.isMaximized()
            self.config.save()
        except OSError as exc:
            LOGGER.warning("no se pudo guardar la configuracion: %s", exc)

    def _default_window_size(self) -> QSize:
        """70 % del área útil de la pantalla principal, con mínimos legibles."""
        screen = QApplication.primaryScreen()
        min_width, min_height = _MIN_WINDOW
        if screen is None:
            return QSize(1040, 780)
        available = screen.availableGeometry()
        return QSize(
            max(min_width, int(available.width() * 0.7)),
            max(min_height, int(available.height() * 0.7)),
        )

    def _restore_geometry(self) -> None:
        default = self._default_window_size()
        match = re.match(r"^(\d+)x(\d+)$", self.config.window_geometry)
        legacy = not match or self.config.window_geometry in _LEGACY_GEOMETRIES
        if legacy:
            width, height = default.width(), default.height()
        else:
            width, height = int(match.group(1)), int(match.group(2))
        width, height = max(_MIN_WINDOW[0], width), max(_MIN_WINDOW[1], height)

        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, available.width())
            height = min(height, available.height())
        self.resize(width, height)

        # La posición guardada por versiones anteriores se ignora siempre: la
        # ventana se abre centrada para no heredar desplazamientos antiguos.
        if self.config.window_maximized:
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        else:
            self._center_on_show = True
            self._center_window()

    def _center_window(self) -> None:
        """Centra el marco real de la ventana en el área útil de su pantalla."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        frame = self.frameGeometry()
        if frame.width() <= 0 or frame.height() <= 0:
            frame.setSize(self.size())
        frame.moveCenter(screen.availableGeometry().center())
        # Windows incluye un borde invisible en la parte inferior que Qt no
        # cuenta en frameGeometry; se compensa para centrar el marco nativo.
        self.move(frame.x(), frame.y() - self._native_extra_height() // 2)

    def _native_extra_height(self) -> int:
        """Altura del borde nativo que Qt no incluye en ``frameGeometry``."""
        if sys.platform != "win32":
            return 0
        handle = self.windowHandle()
        if handle is None:
            return 0
        rect = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(handle.winId(), ctypes.byref(rect)):
            return 0
        ratio = self.devicePixelRatioF() or 1.0
        return max(0, round((rect.bottom - rect.top) / ratio) - self.frameGeometry().height())

    # ------------------------------------------------------------------- theme
    def _apply_theme(self) -> None:
        self.colors = resolve_colors(self.config.theme, self.config.accent)
        app = QApplication.instance()
        if app is not None:
            app.setPalette(build_palette(self.colors))
            app.setStyleSheet(build_stylesheet(self.colors))

        icon_name = _THEME_ICONS.get(self.config.theme, "monitor")
        self.theme_button.setIcon(icon(icon_name, self.colors.muted, 18))
        self.theme_button.setToolTip(tr("tooltip.theme", value=tr(f"theme.{self.config.theme}")))
        self.accent_button.setIcon(swatch(self.colors.accent, 18))
        self.accent_button.setToolTip(
            tr("tooltip.accent", value=tr(f"accent.{self.config.accent}"))
        )
        self._refresh_accent_actions()
        apply_dark_titlebar(self, self.colors.dark)

        for toggle in (self.lossless_toggle, self.open_after_toggle, self.animated_toggle):
            toggle.set_colors(self.colors.accent, self.colors.track)
        self._status_delegate.set_dark(self.colors.dark)
        self.banner_icon.setPixmap(pixmap("warning", self.colors.warning, 18))
        self._refresh_icons()
        self.table.viewport().update()
        self.update()

    def _refresh_icons(self) -> None:
        self.add_files_button.setIcon(icon("plus", self.colors.text, 16))
        self.add_folder_button.setIcon(icon("folder", self.colors.muted, 18))
        self.remove_button.setIcon(icon("trash", self.colors.muted, 18))
        self.clear_button.setIcon(icon("clear", self.colors.muted, 18))
        self.browse_output_button.setIcon(icon("folder", self.colors.muted, 18))
        self.open_folder_button.setIcon(icon("folder", self.colors.muted, 16))
        self.retry_button.setIcon(icon("refresh", self.colors.muted, 16))
        self.cancel_button.setIcon(icon("cancel", self.colors.danger, 16))
        self.convert_button.setIcon(icon("play", self.colors.on_accent, 16))
        self.settings_button.setIcon(icon("settings", self.colors.muted, 18))
        self.banner_close.setIcon(icon("cancel", self.colors.muted, 14))

    def _cycle_theme(self) -> None:
        current = self.config.theme if self.config.theme in _THEME_ORDER else "system"
        index = (_THEME_ORDER.index(current) + 1) % len(_THEME_ORDER)
        self.config.theme = _THEME_ORDER[index]
        self._apply_theme()

    def _refresh_accent_actions(self) -> None:
        mode = "dark" if self.colors.dark else "light"
        for name, action in self._accent_actions.items():
            action.setIcon(swatch(resolve_colors(mode, name).accent, 16))
            action.setChecked(name == self.config.accent)

    def _show_accent_menu(self) -> None:
        self._refresh_accent_actions()
        self._accent_menu.popup(
            self.accent_button.mapToGlobal(QPoint(0, self.accent_button.height() + 6))
        )

    def _set_accent(self, accent: str) -> None:
        self.config.accent = accent
        self._apply_theme()

    def _on_system_scheme_changed(self, _scheme: object) -> None:
        if self.config.theme == "system" or self.config.accent == "system":
            self._apply_theme()

    # ------------------------------------------------------------------ banner
    def _refresh_banner(self) -> None:
        warnings = self.config.warnings
        if not warnings:
            self.banner.setVisible(False)
            return
        self.banner_label.setText(tr("banner.title", count=len(warnings)))
        self.banner.setVisible(True)

    def _show_banner_details(self) -> None:
        QMessageBox.information(
            self,
            tr("banner.details.title"),
            "\n".join(f"• {warning}" for warning in self.config.warnings),
        )

    # ----------------------------------------------------------------- profiles
    def _on_profile_changed(self, _index: int) -> None:
        if self._loading_profile:
            return
        key = self.profile_combo.currentData()
        if not key:
            self._revert_profile()
            return
        profile = next((item for item in self._profiles if item.key == key), None)
        if profile is None:
            return
        self._apply_profile(profile)
        self.status_label.setText(tr("profile.applied", name=profile_label(profile, tr)))

    def _revert_profile(self) -> None:
        """Restore the format/quality that was active before the first profile."""
        state = getattr(self, "_profile_snapshot", None)
        if state is None:
            return
        fmt = state["format"]
        self._quality_cache[fmt] = state["quality"]
        index = self.format_combo.findData(fmt.value)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
        self.lossless_toggle.setChecked(state["lossless"])
        self.animated_toggle.setChecked(state["animated"])
        self.config.jpeg_subsampling = state["subsampling"]
        self.config.png_compress_level = state["compress"]
        self._profile_snapshot = None
        self._on_format_changed()
        self.status_label.setText(tr("profile.none"))

    def _apply_profile(self, profile: Profile) -> None:
        if getattr(self, "_profile_snapshot", None) is None:
            previous = self._current_format()
            self._profile_snapshot = {
                "format": previous,
                "quality": self._quality_cache.get(self._quality_key(previous), 95),
                "lossless": self.lossless_toggle.isChecked(),
                "animated": self.animated_toggle.isChecked(),
                "subsampling": self.config.jpeg_subsampling,
                "compress": self.config.png_compress_level,
            }
        fmt = profile.output_format
        self._quality_cache[self._quality_key(fmt)] = profile.quality
        index = self.format_combo.findData(fmt.value)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
        self.lossless_toggle.setChecked(profile.lossless)
        self.animated_toggle.setChecked(profile.animated)
        self.config.jpeg_subsampling = profile.jpeg_subsampling
        self.config.png_compress_level = profile.png_compress_level
        self._on_format_changed()

    def _save_profile(self) -> None:
        name, accepted = QInputDialog.getText(
            self,
            tr("profile.save.title"),
            tr("profile.save.prompt"),
        )
        name = name.strip()
        if not accepted:
            return
        if not name:
            QMessageBox.warning(self, tr("profile.save.title"), tr("profile.name.required"))
            return
        existing = {profile.key for profile in self._profiles}
        key = custom_profile_key(name, existing)
        fmt = self._current_format()
        profile = Profile(
            key=key,
            label_key=f"profile.custom.{name}",
            output_format=fmt,
            quality=self._current_quality(),
            lossless=fmt is OutputFormat.WEBP and self.lossless_toggle.isChecked(),
            animated=self.animated_toggle.isChecked(),
            jpeg_subsampling=self.config.jpeg_subsampling,
            png_compress_level=self.config.png_compress_level,
            builtin=False,
        )
        self.config.set_profile(key, profile_to_json(profile))
        try:
            self.config.save()
        except OSError as exc:
            LOGGER.warning("no se pudo guardar el perfil: %s", exc)
        self._load_profiles(key)
        self.status_label.setText(tr("status.profile_saved", name=name))

    def _delete_profile(self) -> None:
        key = self.profile_combo.currentData()
        if not key:
            return
        profile = next((item for item in self._profiles if item.key == key), None)
        if profile is None:
            return
        if profile.builtin:
            QMessageBox.information(
                self,
                tr("profile.delete.title"),
                tr("profile.builtin.readonly"),
            )
            return
        answer = QMessageBox.question(
            self,
            tr("profile.delete.title"),
            tr("profile.delete.body", name=profile_label(profile, tr)),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.config.remove_profile(key)
        try:
            self.config.save()
        except OSError as exc:
            LOGGER.warning("no se pudo guardar la configuracion: %s", exc)
        self._load_profiles()
        self.status_label.setText(tr("status.profile_deleted", name=profile_label(profile, tr)))

    # ----------------------------------------------------------------- settings
    def _open_settings(self) -> None:
        quality_cache = dict(self._quality_cache)
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        self._apply_config_to_widgets()
        self._quality_cache.update(quality_cache)
        self._on_format_changed()
        self._apply_theme()
        self._refresh_banner()
        self._load_profiles()
        self._update_actions()
        if dialog.language_changed:
            QMessageBox.information(
                self,
                tr("settings.title"),
                tr("settings.language_changed"),
            )

    # ---------------------------------------------------------------- queue
    def _restore_queue(self) -> None:
        if not self.config.restore_queue:
            clear_queue(self._queue_file)
            return
        snapshot = load_queue(self._queue_file)
        if snapshot.empty:
            return
        existing = [Path(entry.path) for entry in snapshot.entries if Path(entry.path).is_file()]
        missing = len(snapshot.entries) - len(existing)
        added = self.model.add_paths(existing)
        for path in added:
            self.thumbnails.load(path)
        if snapshot.output_dir:
            self.output_edit.setText(snapshot.output_dir)
        if added:
            self._update_count()
            self.status_label.setText(tr("status.queue_restored", count=len(added)))
        if missing:
            self.status_label.setText(tr("status.queue_missing", count=missing))
        self._update_actions()

    def _save_queue(self) -> None:
        if not self.config.restore_queue:
            clear_queue(self._queue_file)
            return
        if self.model.rowCount() == 0:
            clear_queue(self._queue_file)
            return
        entries = [
            QueueEntry(path=os.fspath(item.path), status=JobStatus.PENDING.value)
            for item in (self.model.item_at(row) for row in range(self.model.rowCount()))
            if item is not None
        ]
        try:
            save_queue(entries, self._output_dir(), self._queue_file)
        except OSError as exc:
            LOGGER.warning("no se pudo guardar la cola: %s", exc)

    # ----------------------------------------------------------------- actions
    def _browse_files(self) -> None:
        if self._running:
            return
        patterns = f"{tr('dialog.filters.images', patterns=_COMMON_FILTER)};;"
        patterns += tr("dialog.filters.all")
        files, _ = QFileDialog.getOpenFileNames(
            self,
            tr("dialog.add_images"),
            str(Path.home()),
            patterns,
        )
        if files:
            self._add_paths([Path(name) for name in files])

    def _browse_folder(self) -> None:
        if self._running:
            return
        folder = QFileDialog.getExistingDirectory(self, tr("dialog.add_folder"), str(Path.home()))
        if folder:
            self._add_paths([Path(folder)])

    def _add_paths(self, paths: list[Path]) -> None:
        if self._running or not paths:
            return
        found = collect_sources(paths, recursive=self.config.recursive_folders)
        extensions = supported_extensions()
        images = [path for path in found if path.suffix.lower() in extensions]
        added = self.model.add_paths(images)
        for path in added:
            self.thumbnails.load(path)

        self._summary = ""
        self._update_count()
        if added:
            noun = tr("status.noun.one" if len(added) == 1 else "status.noun.many")
            self.status_label.setText(
                tr("status.added", count=len(added), noun=noun, status=self._idle_status())
            )
            self.table.scrollToBottom()
        elif images:
            self.status_label.setText(tr("status.already_listed"))
        else:
            self.status_label.setText(tr("status.no_compatible"))
        self._update_actions()
        self._save_queue()

    def _selected_rows(self) -> list[int]:
        selection = self.table.selectionModel()
        if selection is None:
            return []
        return sorted({index.row() for index in selection.selectedRows()})

    def _remove_selected(self) -> None:
        if self._running:
            return
        rows = self._selected_rows()
        if not rows:
            return
        paths = [item.path for item in (self.model.item_at(row) for row in rows) if item]
        self.model.remove_rows(rows)
        for path in paths:
            self.thumbnails.forget(path)
        self._summary = ""
        self._update_count()
        self._update_actions()
        self._save_queue()

    def _clear_all(self) -> None:
        if self._running:
            return
        self.model.clear()
        self.thumbnails.reset()
        self._summary = ""
        self.status_label.setText(tr("status.no_images"))
        self._update_count()
        self._update_actions()
        self._save_queue()

    def _browse_output(self) -> None:
        start = self._output_dir()
        folder = QFileDialog.getExistingDirectory(
            self,
            tr("dialog.choose_output"),
            str(start),
        )
        if folder:
            self.output_edit.setText(os.fspath(Path(folder)))
            self._update_actions()

    def _open_output_folder(self) -> None:
        folder = self._output_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, tr("dialog.folder_error.title"), str(exc))
            return
        open_folder(folder)

    def _set_quality_value(self, value: int) -> None:
        value = max(1, min(100, value))
        self._updating_quality = True
        try:
            for index in range(self.quality_combo.count() - 1, -1, -1):
                if self.quality_combo.itemData(index) not in _PRESET_QUALITIES:
                    self.quality_combo.removeItem(index)
            index = self.quality_combo.findData(value)
            if index < 0:
                self.quality_combo.addItem(tr("quality.custom", value=value), value)
                index = self.quality_combo.count() - 1
            self.quality_combo.setCurrentIndex(index)
        finally:
            self._updating_quality = False

    def _current_quality(self) -> int:
        try:
            return max(1, min(100, int(self.quality_combo.currentData())))
        except (TypeError, ValueError):
            return 95

    def _on_format_changed(self, _index: int | None = None) -> None:
        fmt = self._current_format()
        has_quality = fmt.supports_quality
        self.quality_label.setVisible(has_quality)
        self.quality_combo.setVisible(has_quality)
        if has_quality:
            self._set_quality_value(self._quality_cache.get(self._quality_key(fmt), 95))
        self.quality_combo.setEnabled(has_quality and not self.lossless_toggle.isChecked())

        has_lossless = fmt is OutputFormat.WEBP
        self.lossless_toggle.setVisible(has_lossless)
        self.lossless_label.setVisible(has_lossless)
        self.animated_toggle.setEnabled(fmt.supports_animation and not self._running)
        self._update_actions()

    def _on_quality_changed(self, _index: int) -> None:
        if self._updating_quality:
            return
        self._quality_cache[self._quality_key(self._current_format())] = self._current_quality()

    def _on_lossless_changed(self, checked: bool) -> None:
        fmt = self._current_format()
        self.quality_combo.setEnabled(fmt.supports_quality and not checked)

    def _on_rows_reordered(self, _rows: list[int]) -> None:
        self.status_label.setText(tr("status.reordered"))
        self._save_queue()

    # --------------------------------------------------------------- context menu
    def _show_context_menu(self, position: QPoint) -> None:
        rows = self._selected_rows()
        menu = QMenu(self)
        has_selection = bool(rows)

        convert = menu.addAction(tr("menu.convert_selected"))
        convert.setEnabled(has_selection and not self._running)
        convert.triggered.connect(self._convert_selected)

        retry = menu.addAction(tr("menu.retry_selected"))
        retry.setEnabled(has_selection and not self._running)
        retry.triggered.connect(self._retry_selected)

        cancel = menu.addAction(tr("menu.cancel_selected"))
        cancel.setEnabled(has_selection and self._running)
        cancel.triggered.connect(self._cancel_selected_files)

        open_output = menu.addAction(tr("menu.open_output"))
        item = self.model.item_at(rows[0]) if len(rows) == 1 else None
        open_output.setEnabled(item is not None and item.output is not None)
        open_output.triggered.connect(self._open_selected_output)

        menu.addSeparator()
        remove = menu.addAction(tr("menu.remove"))
        remove.setEnabled(has_selection and not self._running)
        remove.triggered.connect(self._remove_selected)

        menu.exec(self.table.viewport().mapToGlobal(position))

    def _open_selected_output(self) -> None:
        rows = self._selected_rows()
        if len(rows) != 1:
            return
        item = self.model.item_at(rows[0])
        if item is not None and item.output is not None:
            open_folder(item.output)

    # ------------------------------------------------------------------ convert
    def _start_conversion(self, sources: list[Path] | None = None) -> None:
        if self._running:
            return
        explicit = sources is not None
        selected = list(sources) if explicit else self.model.paths()
        if not selected:
            return

        output_dir = self._output_dir()
        if not is_writable_dir(output_dir, create=True):
            QMessageBox.warning(
                self,
                tr("dialog.invalid_output.title"),
                tr("dialog.invalid_output.body", path=output_dir),
            )
            return

        self.output_edit.setText(os.fspath(output_dir))
        self.config.output_folder = output_dir
        self._summary = ""

        if explicit:
            rows = self.model.rows_matching(selected)
            self.model.reset_rows(rows)
        else:
            self.model.reset_batch()
            rows = self.model.rows_matching(selected)
        self.model.set_status(rows, JobStatus.RUNNING)

        self._batch_sources = {str(Path(path).resolve()).lower() for path in selected}
        self._set_running(True)
        self.progress_bar.setRange(0, len(selected))
        self.progress_bar.setValue(0)
        self.status_label.setText(tr("status.preparing", total=len(selected)))

        self._thread = QThread(self)
        self._worker = ConvertWorker(
            selected,
            output_dir,
            self._current_options(),
            self.config.max_workers,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()
        LOGGER.info("conversion iniciada: %s archivos -> %s", len(selected), output_dir)

    def _convert_selected(self) -> None:
        rows = self._selected_rows()
        paths = [item.path for item in (self.model.item_at(row) for row in rows) if item]
        if paths:
            self._start_conversion(paths)

    def _retry_failed(self) -> None:
        rows = self.model.failed_rows()
        paths = [item.path for item in (self.model.item_at(row) for row in rows) if item]
        if not paths:
            self.status_label.setText(tr("status.no_failed"))
            return
        self._start_conversion(paths)

    def _retry_selected(self) -> None:
        rows = self._selected_rows()
        paths = [item.path for item in (self.model.item_at(row) for row in rows) if item]
        if paths:
            self._start_conversion(paths)

    def _cancel_conversion(self) -> None:
        if not self._running or self._worker is None:
            return
        self._worker.cancel()
        self.cancel_button.setEnabled(False)
        self.status_label.setText(tr("status.cancelling"))

    def _cancel_selected_files(self) -> None:
        if not self._running or self._worker is None:
            return
        rows = self._selected_rows()
        paths = []
        mark: list[int] = []
        for row in rows:
            item = self.model.item_at(row)
            if item is None:
                continue
            key = str(item.path.resolve()).lower()
            if key in self._batch_sources and item.status is JobStatus.PENDING:
                paths.append(item.path)
                mark.append(row)
        if not paths:
            return
        self._worker.cancel_files(paths)
        self.model.set_status(mark, JobStatus.SKIPPED)
        self.status_label.setText(tr("status.cancel_files", count=len(paths)))

    def _on_progress(self, progress: object) -> None:
        self.model.apply_result(progress.result)  # type: ignore[attr-defined]
        self.progress_bar.setValue(progress.done)  # type: ignore[attr-defined]
        self.status_label.setText(
            tr(
                "status.progress",
                done=progress.done,  # type: ignore[attr-defined]
                total=progress.total,  # type: ignore[attr-defined]
                name=progress.result.source.name,  # type: ignore[attr-defined]
            )
        )

    def _on_finished(self, results: list) -> None:
        done = sum(1 for result in results if result.status is JobStatus.DONE)
        skipped = sum(1 for result in results if result.status is JobStatus.SKIPPED)
        errors = sum(1 for result in results if result.status is JobStatus.ERROR)
        self.progress_bar.setValue(len(results))
        self._summary = tr("status.summary", done=done, skipped=skipped, errors=errors)
        self.status_label.setText(self._summary)
        self._batch_sources = set()
        self._set_running(False)
        self._update_actions()
        if self.config.open_after_convert and done:
            open_folder(self._output_dir())
        if errors:
            self._save_queue()
        else:
            clear_queue(self._queue_file)
        self._notify_finished(done, errors)

    def _on_failed(self, message: str) -> None:
        running_rows = [
            row
            for row in range(self.model.rowCount())
            if (item := self.model.item_at(row)) is not None and item.status is JobStatus.RUNNING
        ]
        self.model.set_status(running_rows, JobStatus.PENDING)
        self._batch_sources = set()
        self._set_running(False)
        self.status_label.setText(tr("status.conversion_failed"))
        QMessageBox.critical(self, tr("dialog.conversion_failed.title"), message)

    def _on_thread_finished(self) -> None:
        sender = self.sender()
        if sender is not None and sender is not self._thread:
            return
        self._worker = None
        self._thread = None
        if self._closing:
            self.close()

    def _set_running(self, running: bool) -> None:
        self._running = running
        for widget in (
            self.add_files_button,
            self.add_folder_button,
            self.remove_button,
            self.clear_button,
            self.format_combo,
            self.quality_combo,
            self.lossless_toggle,
            self.animated_toggle,
            self.output_edit,
            self.browse_output_button,
            self.conflict_combo,
            self.profile_combo,
            self.save_profile_button,
            self.delete_profile_button,
        ):
            widget.setEnabled(not running)
        self.settings_button.setEnabled(not running)
        self.cancel_button.setVisible(running)
        self.cancel_button.setEnabled(running)
        self.progress_bar.setVisible(running)
        self.convert_button.setText(tr("button.converting") if running else tr("button.convert"))
        if not running:
            self._on_format_changed()
        self._update_actions()

    # ---------------------------------------------------------------- utilities
    def _on_thumbnail_ready(
        self,
        path: str,
        image: object,
        width: int,
        height: int,
    ) -> None:
        self.model.set_image_info(Path(path), width, height, image)  # type: ignore[arg-type]

    def _update_count(self) -> None:
        count = self.model.rowCount()
        self.count_label.setText(tr("section.images", count=count))
        self.status_label.setText(self._idle_status())
        self.setWindowTitle(tr("window.title.count", count=count) if count else "MediaFormat")
        self._update_actions()

    def _idle_status(self) -> str:
        count = self.model.rowCount()
        if not count:
            return tr("status.no_images")
        return tr("status.images", count=count, size=format_size(self.model.total_size()))

    def _update_actions(self) -> None:
        count = self.model.rowCount()
        has_selection = bool(self._selected_rows())
        failed = self.model.failed_rows()
        self.convert_button.setEnabled(count > 0 and not self._running)
        self.remove_button.setEnabled(has_selection and not self._running)
        self.clear_button.setEnabled(count > 0 and not self._running)
        self.open_folder_button.setEnabled(self._output_dir().is_dir() and not self._running)
        self.retry_button.setVisible(bool(failed) and not self._running)
        self.retry_button.setEnabled(bool(failed) and not self._running)
        key = self.profile_combo.currentData() if hasattr(self, "profile_combo") else None
        profile = next((item for item in self._profiles if item.key == key), None)
        self.delete_profile_button.setEnabled(
            profile is not None and not profile.builtin and not self._running
        )

    # ------------------------------------------------------------- notifications
    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        tray = QSystemTrayIcon(app_icon(), self)
        tray.setToolTip("MediaFormat")
        tray.show()
        self._tray = tray

    def _notify_finished(self, done: int, errors: int) -> None:
        if not self.config.notify_on_finish or self._tray is None:
            return
        self._tray.showMessage(
            tr("notify.title"),
            tr("notify.done", done=done, errors=errors),
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    def _current_format(self) -> OutputFormat:
        value = self.format_combo.currentData()
        return OutputFormat.from_value(value or OutputFormat.WEBP.value, OutputFormat.WEBP)

    def _current_conflict(self) -> ConflictPolicy:
        value = self.conflict_combo.currentData()
        return ConflictPolicy.from_value(
            value or ConflictPolicy.RENAME.value, ConflictPolicy.RENAME
        )

    def _current_options(self) -> ConversionOptions:
        fmt = self._current_format()
        return ConversionOptions(
            output_format=fmt,
            quality=self._current_quality(),
            lossless=self.lossless_toggle.isChecked() and fmt is OutputFormat.WEBP,
            background=self.config.jpeg_background,
            keep_metadata=self.config.keep_metadata,
            apply_exif_orientation=self.config.apply_exif_orientation,
            animated=self.animated_toggle.isChecked() and fmt.supports_animation,
            png_compress_level=self.config.png_compress_level,
            jpeg_subsampling=self.config.jpeg_subsampling,
            on_conflict=self._current_conflict(),
        ).normalized()

    def _output_dir(self) -> Path:
        text = self.output_edit.text().strip()
        return expand_path(text) if text else self.config.output_folder

    # ------------------------------------------------------------------- events
    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if self._center_on_show:
            self._center_on_show = False
            if not self.isMaximized():
                self._center_window()
                # El gestor de ventanas puede ajustar el marco o el layout
                # cambiar la altura mínima tras mostrarse: recentrar después.
                QTimer.singleShot(0, self._center_after_show)

    def _center_after_show(self) -> None:
        if not self.isMaximized():
            self._center_window()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._running:
            answer = QMessageBox.question(
                self,
                tr("dialog.running.title"),
                tr("dialog.running.body"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._closing = True
            self._cancel_conversion()
            event.ignore()
            return
        self.thumbnails.wait_for_done(2000)
        self._save_config()
        self._save_queue()
        if self._tray is not None:
            self._tray.hide()
        event.accept()


def _pick_font() -> QFont:
    families = set(QFontDatabase.families())
    for name in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI"):
        if name in families:
            return QFont(name, 10)
    return QFont()


def _install_excepthook() -> None:
    def handle(exc_type, exc, traceback) -> None:
        LOGGER.exception("error no controlado", exc_info=(exc_type, exc, traceback))
        QMessageBox.critical(None, tr("dialog.unexpected.title"), f"{exc_type.__name__}: {exc}")

    sys.excepthook = handle


def run(argv: list[str] | None = None) -> int:
    """Start the Qt application and return its exit code."""
    setup_logging(level=logging.INFO)
    set_taskbar_identity()
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName("MediaFormat")
    app.setApplicationDisplayName("MediaFormat")
    app.setOrganizationName("MediaFormat")
    app.setStyle("Fusion")
    app.setFont(_pick_font())
    app.setWindowIcon(app_icon())
    _install_excepthook()

    window = MainWindow()
    window.show()
    return int(app.exec())
