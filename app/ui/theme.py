"""Paleta y hoja de estilos inspiradas en Windows 11 (Fase 2).

La UI usa el estilo ``Fusion`` de Qt para que el QSS se aplique igual en
cualquier equipo, con una paleta propia y tipografía Segoe UI.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, replace
from string import Template

from PySide6.QtGui import QColor, QPalette

from app.accents import DEFAULT_ACCENT, resolve_accent

FONT_FAMILY = '"Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", sans-serif'


@dataclass(frozen=True, slots=True)
class ThemeColors:
    """Colores de un tema concreto (claro u oscuro)."""

    dark: bool
    background: str
    surface: str
    surface_alt: str
    surface_pressed: str
    border: str
    border_strong: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    on_accent: str
    selection: str
    track: str
    scroll: str
    scroll_hover: str
    danger: str
    success: str
    warning: str


LIGHT = ThemeColors(
    dark=False,
    background="#F3F3F3",
    surface="#FFFFFF",
    surface_alt="#F7F7F7",
    surface_pressed="#EFEFEF",
    border="#E4E4E4",
    border_strong="#D2D2D2",
    text="#1A1A1A",
    muted="#6E6E6E",
    accent="#0067C0",
    accent_hover="#00579F",
    accent_pressed="#004C8C",
    accent_soft="#E9F2FB",
    on_accent="#FFFFFF",
    selection="#E5F0FA",
    track="#E3E3E3",
    scroll="#C9C9C9",
    scroll_hover="#A9A9A9",
    danger="#C42B1C",
    success="#0F7B0F",
    warning="#9D5D00",
)

DARK = ThemeColors(
    dark=True,
    background="#1F1F1F",
    surface="#2A2A2A",
    surface_alt="#323232",
    surface_pressed="#3A3A3A",
    border="#3A3A3A",
    border_strong="#4A4A4A",
    text="#F2F2F2",
    muted="#A6A6A6",
    accent="#4CC2FF",
    accent_hover="#6FD0FF",
    accent_pressed="#3AB4F2",
    accent_soft="#17394D",
    on_accent="#06202E",
    selection="#1E3D52",
    track="#3D3D3D",
    scroll="#555555",
    scroll_hover="#6E6E6E",
    danger="#FF99A4",
    success="#6CCB5F",
    warning="#FCE100",
)


@dataclass(frozen=True, slots=True)
class AccentColors:
    """Colores derivados de un acento, para un modo claro u oscuro."""

    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    on_accent: str
    selection: str


# Un par (claro, oscuro) por acento. Los valores están pensados para mantener
# contraste AA sobre las superficies del tema correspondiente.
_ACCENTS: dict[str, tuple[AccentColors, AccentColors]] = {
    "blue": (
        AccentColors("#0067C0", "#00579F", "#004C8C", "#E9F2FB", "#FFFFFF", "#E5F0FA"),
        AccentColors("#4CC2FF", "#6FD0FF", "#3AB4F2", "#17394D", "#06202E", "#1E3D52"),
    ),
    "red": (
        AccentColors("#C42B1C", "#A82618", "#8E2014", "#FBEAE8", "#FFFFFF", "#F7E3E0"),
        AccentColors("#FF7A7A", "#FF9494", "#F06060", "#4A1F1F", "#2B0A0A", "#3D1B1B"),
    ),
    "green": (
        AccentColors("#107C10", "#0C6B0C", "#095A09", "#E8F5E8", "#FFFFFF", "#E3F2E3"),
        AccentColors("#6CCB5F", "#85D97A", "#55B84A", "#1E3A1C", "#0B2609", "#22421F"),
    ),
    "yellow": (
        AccentColors("#9D5D00", "#865000", "#6F4200", "#FCF2E3", "#FFFFFF", "#F9EEDC"),
        AccentColors("#FCE100", "#FFEA4D", "#E8CF00", "#3D3700", "#2B2600", "#4A4200"),
    ),
    "purple": (
        AccentColors("#6B21A8", "#5B1C8F", "#4C1778", "#F3EAF9", "#FFFFFF", "#EEE3F7"),
        AccentColors("#B48CF2", "#C6A5F7", "#A277E8", "#33234D", "#1A0B2B", "#2C1E42"),
    ),
    "pink": (
        AccentColors("#C2185B", "#A81450", "#8E1044", "#FBE9F0", "#FFFFFF", "#F8E0EA"),
        AccentColors("#FF7BA9", "#FF95BA", "#F06595", "#4A1F2E", "#2B0A17", "#3D1B28"),
    ),
    "brown": (
        AccentColors("#8B5A2B", "#774C24", "#633E1D", "#F5EFE8", "#FFFFFF", "#EFE6DB"),
        AccentColors("#D7A86E", "#E2B988", "#C89858", "#3B2C1E", "#241708", "#33261A"),
    ),
}


def system_is_dark() -> bool:
    """Return True when Windows is configured with dark app mode."""
    if os.name != "nt":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return int(value) == 0
    except (OSError, ValueError):
        return False


def resolve_colors(mode: str, accent: str = DEFAULT_ACCENT) -> ThemeColors:
    """Map ``system|light|dark`` and an accent name to a concrete palette."""
    if mode == "light":
        base = LIGHT
    elif mode == "dark":
        base = DARK
    else:
        base = DARK if system_is_dark() else LIGHT
    light_accent, dark_accent = _ACCENTS[resolve_accent(accent)]
    chosen = dark_accent if base.dark else light_accent
    return replace(
        base,
        accent=chosen.accent,
        accent_hover=chosen.accent_hover,
        accent_pressed=chosen.accent_pressed,
        accent_soft=chosen.accent_soft,
        on_accent=chosen.on_accent,
        selection=chosen.selection,
    )


def build_palette(colors: ThemeColors) -> QPalette:
    """Build a QPalette so native widgets match the stylesheet."""
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: colors.background,
        QPalette.ColorRole.WindowText: colors.text,
        QPalette.ColorRole.Base: colors.surface,
        QPalette.ColorRole.AlternateBase: colors.surface_alt,
        QPalette.ColorRole.Text: colors.text,
        QPalette.ColorRole.Button: colors.surface,
        QPalette.ColorRole.ButtonText: colors.text,
        QPalette.ColorRole.Highlight: colors.accent,
        QPalette.ColorRole.HighlightedText: colors.on_accent,
        QPalette.ColorRole.PlaceholderText: colors.muted,
        QPalette.ColorRole.Mid: colors.border,
        QPalette.ColorRole.Light: colors.border,
        QPalette.ColorRole.Dark: colors.border_strong,
        QPalette.ColorRole.ToolTipBase: colors.surface,
        QPalette.ColorRole.ToolTipText: colors.text,
        QPalette.ColorRole.Link: colors.accent,
        QPalette.ColorRole.BrightText: colors.danger,
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors.muted))
    return palette


_QSS = Template(
    """
QWidget {
    color: $text;
    font-family: $font_family;
    font-size: 10pt;
}

QMainWindow, QWidget#Root, QDialog, QMessageBox {
    background: $background;
}

QFrame#Card {
    background: $surface;
    border: 1px solid $border;
    border-radius: 10px;
}

QFrame#Banner {
    background: $accent_soft;
    border: 1px solid $accent;
    border-radius: 8px;
}

QGroupBox {
    border: 1px solid $border;
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px 10px 8px 10px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QScrollArea {
    background: transparent;
    border: none;
}

QSpinBox {
    background: $surface_alt;
    border: 1px solid $border_strong;
    border-radius: 6px;
    padding: 5px 8px;
    min-height: 20px;
    min-width: 70px;
}

QDialogButtonBox QPushButton {
    min-width: 90px;
}

QLabel#Title {
    font-size: 20pt;
    font-weight: 600;
    letter-spacing: -0.4px;
}

QLabel#Subtitle {
    color: $muted;
    font-size: 9.5pt;
}

QLabel#SectionTitle {
    font-weight: 600;
    font-size: 10pt;
}

QLabel#Muted {
    color: $muted;
}

QLabel#Hint {
    color: $muted;
    font-size: 9pt;
}

QLabel#DropTitle {
    font-size: 12pt;
    font-weight: 600;
}

QPushButton {
    background: $surface;
    border: 1px solid $border_strong;
    border-radius: 6px;
    padding: 7px 14px;
    min-height: 20px;
}

QPushButton:hover {
    background: $surface_alt;
}

QPushButton:pressed {
    background: $surface_pressed;
}

QPushButton:disabled {
    color: $muted;
    background: transparent;
    border-color: $border;
}

QPushButton#Primary {
    background: $accent;
    border: 1px solid $accent;
    color: $on_accent;
    font-weight: 600;
}

QPushButton#Primary:hover {
    background: $accent_hover;
    border-color: $accent_hover;
}

QPushButton#Primary:pressed {
    background: $accent_pressed;
    border-color: $accent_pressed;
}

QPushButton#Primary:disabled {
    background: $border;
    border-color: $border;
    color: $muted;
}

QPushButton#Ghost {
    background: transparent;
    border: none;
    color: $muted;
    padding: 6px 10px;
}

QPushButton#Ghost:hover {
    background: $surface_alt;
    color: $text;
}

QPushButton#Ghost:pressed {
    background: $surface_pressed;
}

QPushButton#Ghost:disabled {
    background: transparent;
    color: $muted;
}

QPushButton#Danger {
    color: $danger;
}

QPushButton#IconButton {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px;
}

QPushButton#IconButton:hover {
    background: $surface_alt;
}

QPushButton#IconButton:pressed {
    background: $surface_pressed;
}

QPushButton#IconButton:disabled {
    background: transparent;
}

QLineEdit {
    background: $surface_alt;
    border: 1px solid $border_strong;
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: $accent;
    selection-color: $on_accent;
}

QLineEdit:focus {
    background: $surface;
    border-color: $accent;
}

QLineEdit:disabled {
    color: $muted;
    background: $surface_alt;
}

QComboBox {
    background: $surface;
    border: 1px solid $border_strong;
    border-radius: 8px;
    padding: 8px 34px 8px 12px;
    min-height: 20px;
}

QComboBox:hover {
    background: $surface_alt;
    border-color: $accent;
}

QComboBox:focus,
QComboBox:on {
    background: $surface;
    border-color: $accent;
}

QComboBox:disabled {
    color: $muted;
    background: $surface_alt;
    border-color: $border;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border: none;
    background: transparent;
}

QComboBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}

QComboBox QAbstractItemView {
    background: $surface;
    border: 1px solid $border_strong;
    border-radius: 8px;
    padding: 6px;
    outline: none;
    selection-background-color: $accent_soft;
    selection-color: $text;
}

QComboBox QAbstractItemView::item {
    min-height: 30px;
    padding: 4px 10px;
    border-radius: 6px;
}

QComboBox QAbstractItemView::item:hover {
    background: $accent_soft;
}

QLineEdit[readOnly="true"] {
    background: $surface_alt;
    border-color: $border;
    color: $text;
}

QSlider {
    min-height: 22px;
}

QSlider::groove:horizontal {
    height: 4px;
    background: $track;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: $accent;
    border-radius: 2px;
}

QSlider::add-page:horizontal {
    background: $track;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: $accent;
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
}

QSlider::handle:horizontal:hover {
    background: $accent_hover;
}

QSlider::handle:horizontal:disabled {
    background: $border_strong;
}

QProgressBar {
    background: $track;
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
}

QProgressBar::chunk {
    background: $accent;
    border-radius: 3px;
}

QTableView {
    background: transparent;
    border: none;
    selection-background-color: $selection;
    selection-color: $text;
    outline: none;
}

QTableView[dragActive="true"] {
    border: 1.5px solid $accent;
    border-radius: 10px;
}

QTableView::item {
    border: none;
    padding: 0 8px;
}

QTableView::item:hover {
    background: $surface_alt;
}

QTableView::item:selected {
    background: $selection;
    color: $text;
}

QHeaderView {
    background: transparent;
}

QHeaderView::section {
    background: $surface;
    color: $muted;
    border: none;
    padding: 6px 8px;
    font-size: 9pt;
    font-weight: 600;
}

QTableCornerButton::section {
    background: $surface;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: $scroll;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: $scroll_hover;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background: $scroll;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: none;
}

QToolTip {
    background: $surface;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 6px;
    padding: 6px 8px;
}

QMessageBox QLabel {
    color: $text;
}

QMenu {
    background: $surface;
    border: 1px solid $border_strong;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}

QMenu::item:selected {
    background: $accent_soft;
}
"""
)


def build_stylesheet(colors: ThemeColors) -> str:
    """Render the QSS template for ``colors``."""
    values = asdict(colors)
    values["font_family"] = FONT_FAMILY
    return _QSS.substitute(values)
