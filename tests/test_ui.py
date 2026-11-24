"""Pruebas de humo de la UI Qt (Fase 2) en modo ``offscreen``.

No sustituyen a una revision visual, pero cubren el cableado entre la ventana,
el modelo de la lista y el motor de conversion.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.accents import ACCENT_CHOICES  # noqa: E402
from app.config import Config  # noqa: E402
from app.converter import available_formats  # noqa: E402
from app.i18n import set_language, tr  # noqa: E402
from app.models import ConversionOptions, JobStatus, OutputFormat  # noqa: E402
from app.queue_state import load_queue  # noqa: E402
from app.ui.convert_worker import ConvertWorker  # noqa: E402
from app.ui.file_model import FileListModel  # noqa: E402
from app.ui.theme import resolve_colors  # noqa: E402
from PIL import Image  # noqa: E402 - despues de fijar el backend de Qt
from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_APP = QApplication.instance() or QApplication([])
_APP.setStyle("Fusion")


def make_image(path: Path, size: tuple[int, int] = (48, 32)) -> Path:
    """Crea un PNG de prueba."""
    Image.new("RGB", size, (190, 40, 40)).save(path)
    return path


class FileListModelTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.first = make_image(root / "uno.png")
        self.second = make_image(root / "dos.png", (20, 20))
        self.model = FileListModel()

    def test_add_paths_and_dedupe(self) -> None:
        added = self.model.add_paths([self.first, self.second, self.first])
        self.assertEqual(len(added), 2)
        self.assertEqual(self.model.rowCount(), 2)
        self.assertEqual(self.model.add_paths([self.first]), [])
        self.assertEqual(self.model.find_row(self.second), 1)

    def test_remove_and_clear(self) -> None:
        self.model.add_paths([self.first, self.second])
        self.model.remove_rows([0])
        self.assertEqual(self.model.paths(), [self.second])
        self.model.clear()
        self.assertEqual(self.model.rowCount(), 0)
        self.assertEqual(self.model.total_size(), 0)

    def test_status_counts_and_image_info(self) -> None:
        self.model.add_paths([self.first, self.second])
        self.model.set_image_info(self.first, 48, 32)
        item = self.model.item_at(0)
        self.assertIsNotNone(item)
        self.assertEqual(item.image_size, (48, 32))
        counts = self.model.status_counts()
        self.assertEqual(counts[JobStatus.PENDING], 2)

    def test_move_rows_reorders_and_returns_new_positions(self) -> None:
        third = make_image(Path(self._tmp.name) / "tres.png")
        self.model.add_paths([self.first, self.second, third])

        new_rows = self.model.move_rows([2], 0)

        self.assertEqual(new_rows, [0])
        self.assertEqual(self.model.paths(), [third, self.first, self.second])

    def test_move_rows_keeps_order_of_a_multiple_selection(self) -> None:
        third = make_image(Path(self._tmp.name) / "tres.png")
        fourth = make_image(Path(self._tmp.name) / "cuatro.png")
        self.model.add_paths([self.first, self.second, third, fourth])

        self.model.move_rows([0, 2], 4)

        self.assertEqual(self.model.paths(), [self.second, fourth, self.first, third])

    def test_failed_rows_and_reset_rows(self) -> None:
        self.model.add_paths([self.first, self.second])
        self.model.set_status([1], JobStatus.ERROR)
        self.assertEqual(self.model.failed_rows(), [1])

        self.model.reset_rows([1])
        self.assertEqual(self.model.failed_rows(), [])
        self.assertEqual(self.model.item_at(1).status, JobStatus.PENDING)  # type: ignore[union-attr]


class ConvertWorkerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.source_dir = root / "in"
        self.source_dir.mkdir()
        self.output_dir = root / "out"
        self.sources = [
            make_image(self.source_dir / "a.png", (32, 16)),
            make_image(self.source_dir / "b.png", (16, 32)),
        ]

    def test_worker_converts_and_reports(self) -> None:
        worker = ConvertWorker(self.sources, self.output_dir, ConversionOptions(), max_workers=2)
        events: list[object] = []
        batches: list[list] = []
        worker.progress.connect(events.append)
        worker.finished.connect(batches.append)

        worker.run()

        self.assertEqual(len(events), 2)
        self.assertEqual(len(batches), 1)
        results = batches[0]
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.status is JobStatus.DONE for result in results))
        for result in results:
            self.assertIsNotNone(result.output)
            self.assertTrue(result.output.is_file())

    def test_worker_honours_cancel(self) -> None:
        worker = ConvertWorker(self.sources, self.output_dir, ConversionOptions(), max_workers=1)
        worker.cancel()
        batches: list[list] = []
        worker.finished.connect(batches.append)

        worker.run()

        self.assertEqual(len(batches), 1)
        self.assertTrue(all(result.status is JobStatus.SKIPPED for result in batches[0]))


class MainWindowTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        set_language("es")
        self.config = Config(path=self.root / "config.ini")
        from app.ui.main_window import MainWindow

        self.window = MainWindow(self.config, queue_file=self.root / "queue.json")
        self.addCleanup(self._dispose)
        self.window.show()
        _APP.processEvents()

    def _dispose(self) -> None:
        self.window.thumbnails.wait_for_done(5000)
        self.window.close()
        self.window.deleteLater()
        _APP.processEvents()

    def test_shell_is_ready(self) -> None:
        self.assertEqual(self.window.format_combo.count(), len(available_formats()))
        self.assertFalse(self.window.convert_button.isEnabled())
        self.assertEqual(self.window.model.rowCount(), 0)
        self.assertTrue(_APP.styleSheet())

    def test_add_paths_and_command_state(self) -> None:
        images = [make_image(self.root / f"img{i}.png") for i in range(3)]
        self.window._add_paths(images)  # noqa: SLF001 - prueba de integracion
        _APP.processEvents()
        self.window.thumbnails.wait_for_done(5000)
        _APP.processEvents()

        self.assertEqual(self.window.model.rowCount(), 3)
        self.assertTrue(self.window.convert_button.isEnabled())
        self.assertIn("3 imágenes", self.window.status_label.text())
        self.assertTrue(self.window.clear_button.isEnabled())

    def test_format_switch_toggles_quality(self) -> None:
        self.window.format_combo.setCurrentIndex(
            self.window.format_combo.findData(OutputFormat.PNG.value)
        )
        _APP.processEvents()
        self.assertTrue(self.window.quality_combo.isHidden())

        self.window.format_combo.setCurrentIndex(
            self.window.format_combo.findData(OutputFormat.JPEG.value)
        )
        _APP.processEvents()
        self.assertFalse(self.window.quality_combo.isHidden())

    def test_quality_defaults_to_maximum(self) -> None:
        self.window.format_combo.setCurrentIndex(
            self.window.format_combo.findData(OutputFormat.JPEG.value)
        )
        _APP.processEvents()
        self.assertEqual(self.window.quality_combo.currentData(), 95)
        self.assertEqual(self.window.quality_combo.currentText(), tr("quality.maximum"))

    def test_quality_presets_and_custom_value(self) -> None:
        self.window._set_quality_value(82)  # noqa: SLF001
        self.assertEqual(self.window.quality_combo.currentData(), 82)
        self.assertIn("Personalizada", self.window.quality_combo.currentText())

        self.window._set_quality_value(85)  # noqa: SLF001
        self.assertEqual(self.window.quality_combo.currentData(), 85)
        self.assertEqual(self.window.quality_combo.currentText(), tr("quality.high"))
        # El valor personalizado anterior ya no debe quedar en la lista.
        self.assertEqual(self.window.quality_combo.findData(82), -1)

    def test_output_field_is_read_only_and_has_browse_button(self) -> None:
        self.assertTrue(self.window.output_edit.isReadOnly())
        self.assertEqual(self.window.browse_output_button.text(), tr("button.choose_output"))

    def test_queue_replaces_the_old_drop_zone(self) -> None:
        self.assertFalse(hasattr(self.window, "drop_zone"))
        self.assertTrue(self.window.table.acceptDrops())
        self.assertEqual(self.window.model.rowCount(), 0)

    def test_paths_dropped_on_the_queue_are_appended(self) -> None:
        first = make_image(self.root / "drop1.png")
        second = make_image(self.root / "drop2.png")
        existing = make_image(self.root / "drop0.png")
        self.window._add_paths([existing])  # noqa: SLF001
        self.window.table.pathsDropped.emit([first, second])
        _APP.processEvents()
        self.assertEqual(self.window.model.paths(), [existing, first, second])

    def test_empty_queue_click_requests_browse(self) -> None:
        with mock.patch.object(self.window, "_browse_files") as browse:  # noqa: SLF001
            self.window.table.browseRequested.emit()
        browse.assert_called_once_with()

    def test_default_window_size_is_seventy_percent(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:  # pragma: no cover - backend sin pantalla
            self.skipTest("sin pantalla disponible")
        available = screen.availableGeometry()
        expected = (
            max(940, int(available.width() * 0.7)),
            max(700, int(available.height() * 0.7)),
        )
        size = self.window._default_window_size()  # noqa: SLF001
        self.assertEqual((size.width(), size.height()), expected)

    def test_legacy_geometry_is_replaced_by_the_default(self) -> None:
        self.config.window_geometry = "900x640"
        self.window._restore_geometry()  # noqa: SLF001
        default = self.window._default_window_size()  # noqa: SLF001
        self.assertEqual(self.window.width(), default.width())
        self.assertEqual(self.window.height(), default.height())

    def test_legacy_geometry_ignores_the_old_position_and_centers(self) -> None:
        self.window.hide()
        self.config.window_geometry = "900x640"
        self.config.window_position = (0, 0)
        self.window._restore_geometry()  # noqa: SLF001
        self.window.show()
        _APP.processEvents()

        screen = QApplication.primaryScreen()
        if screen is None:  # pragma: no cover - backend sin pantalla
            self.skipTest("sin pantalla disponible")
        available = screen.availableGeometry()
        frame = self.window.frameGeometry()
        self.assertLessEqual(abs(frame.center().x() - available.center().x()), 2)
        self.assertLessEqual(abs(frame.center().y() - available.center().y()), 2)

    def test_custom_size_ignores_a_saved_off_center_position(self) -> None:
        self.window.hide()
        screen = QApplication.primaryScreen()
        if screen is None:  # pragma: no cover - backend sin pantalla
            self.skipTest("sin pantalla disponible")
        available = screen.availableGeometry()
        width = min(1200, available.width())
        height = min(800, available.height())
        self.config.window_geometry = f"{width}x{height}"
        self.config.window_position = (0, 0)
        self.window._restore_geometry()  # noqa: SLF001
        self.window.show()
        _APP.processEvents()

        frame = self.window.frameGeometry()
        self.assertLessEqual(abs(frame.center().x() - available.center().x()), 2)
        self.assertLessEqual(abs(frame.center().y() - available.center().y()), 2)

    def test_saving_the_window_forgets_the_position(self) -> None:
        self.config.window_position = (40, 50)
        self.window._save_config()  # noqa: SLF001
        self.assertIsNone(self.config.window_position)

    def test_theme_cycle_returns_to_start(self) -> None:
        start = self.config.theme
        for _ in range(3):
            self.window._cycle_theme()  # noqa: SLF001
            _APP.processEvents()
        self.assertEqual(self.config.theme, start)

    def test_accent_menu_offers_every_colour(self) -> None:
        actions = self.window._accent_menu.actions()  # noqa: SLF001
        self.assertEqual(len(actions), len(ACCENT_CHOICES))
        self.assertEqual(
            [action.text() for action in actions],
            [tr(f"accent.{name}") for name in ACCENT_CHOICES],
        )
        self.assertEqual(sum(action.isChecked() for action in actions), 1)

    def test_choosing_an_accent_updates_the_theme_and_config(self) -> None:
        self.window._accent_actions["red"].trigger()  # noqa: SLF001
        _APP.processEvents()
        self.assertEqual(self.config.accent, "red")
        expected = resolve_colors(self.config.theme, "red").accent
        self.assertEqual(self.window.colors.accent, expected)
        self.assertTrue(self.window._accent_actions["red"].isChecked())  # noqa: SLF001
        self.assertEqual(
            sum(action.isChecked() for action in self.window._accent_actions.values()),  # noqa: SLF001
            1,
        )

    def test_accent_survives_a_config_roundtrip(self) -> None:
        self.window._set_accent("purple")  # noqa: SLF001
        self.config.save()
        self.assertEqual(Config(self.config.path).accent, "purple")

    def test_branding_uses_the_icon_file(self) -> None:
        from app.ui import branding

        self.assertTrue(branding.icon_path().is_file())
        self.assertFalse(branding.app_icon().isNull())
        self.assertFalse(self.window.windowIcon().isNull())
        # No deben lanzar ni en Windows ni en el backend offscreen.
        branding.set_taskbar_identity()
        branding.apply_dark_titlebar(self.window, True)
        branding.apply_dark_titlebar(self.window, False)

    def test_resources_dir_honours_pyinstaller(self) -> None:
        from app.ui import branding

        with mock.patch.object(sys, "_MEIPASS", str(self.root), create=True):
            self.assertEqual(branding.resources_dir(), self.root / "resources")

    def test_profile_combo_lists_builtins_and_applies_one(self) -> None:
        self.assertEqual(self.window.profile_combo.count(), 5)  # sin perfil + 4 integrados
        index = self.window.profile_combo.findData("web")
        self.window.profile_combo.setCurrentIndex(index)
        _APP.processEvents()

        self.assertEqual(self.window._current_format(), OutputFormat.WEBP)
        self.assertEqual(self.window._current_quality(), 82)
        self.assertIn("Personalizada", self.window.quality_combo.currentText())
        self.assertIn("Web", self.window.status_label.text())

    def test_banner_appears_and_can_be_dismissed(self) -> None:
        self.window.config.warnings.append("[app] theme invalido")
        self.window._refresh_banner()  # noqa: SLF001
        _APP.processEvents()

        self.assertFalse(self.window.banner.isHidden())
        self.assertIn("1", self.window.banner_label.text())
        self.window.banner_close.click()
        _APP.processEvents()
        self.assertTrue(self.window.banner.isHidden())

    def test_settings_dialog_saves_configuration(self) -> None:
        from app.ui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(self.config, self.window)
        self.assertTrue(dialog.output_edit.isReadOnly())
        self.assertFalse(hasattr(dialog, "jpeg_quality"))
        self.assertFalse(hasattr(dialog, "webp_quality"))
        dialog.output_edit.setText(os.fspath(self.root))
        dialog.png_level.setValue(7)
        dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("dark"))
        dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("en"))
        dialog.accept()

        self.assertTrue(dialog.language_changed)
        self.assertEqual(self.config.png_compress_level, 7)
        self.assertEqual(self.config.theme, "dark")
        self.assertEqual(self.config.language, "en")
        self.assertEqual(self.config.output_folder, self.root)
        self.assertEqual(Config(self.config.path).theme, "dark")

    def test_retry_failed_only_starts_the_failed_sources(self) -> None:
        first = make_image(self.root / "falla.png")
        second = make_image(self.root / "bien.png")
        self.window._add_paths([first, second])  # noqa: SLF001
        self.window.model.set_status([0], JobStatus.ERROR)
        self.window.model.set_status([1], JobStatus.DONE)

        with mock.patch.object(self.window, "_start_conversion") as start:  # noqa: SLF001
            self.window._retry_failed()  # noqa: SLF001

        start.assert_called_once_with([first])

    def test_queue_is_persisted_for_the_current_batch(self) -> None:
        images = [make_image(self.root / "q1.png"), make_image(self.root / "q2.png")]
        self.window._add_paths(images)  # noqa: SLF001
        self.window._save_queue()  # noqa: SLF001

        snapshot = load_queue(self.root / "queue.json")
        self.assertEqual([entry.path for entry in snapshot.entries], [os.fspath(p) for p in images])

    def test_full_conversion_through_window(self) -> None:
        images = [make_image(self.root / "x.png"), make_image(self.root / "y.png")]
        self.window._add_paths(images)  # noqa: SLF001
        self.window.output_edit.setText(os.fspath(self.root / "salida"))
        _APP.processEvents()

        self.window._start_conversion()  # noqa: SLF001
        deadline = time.monotonic() + 20
        while self.window._running and time.monotonic() < deadline:  # noqa: SLF001
            _APP.processEvents()
            time.sleep(0.02)

        self.assertFalse(self.window._running)  # noqa: SLF001
        counts = self.window.model.status_counts()
        self.assertEqual(counts[JobStatus.DONE], 2)
        self.assertIn("2 convertidas", self.window.status_label.text())
        self.assertEqual(len(list((self.root / "salida").glob("*.webp"))), 2)

    def test_settings_dialog_can_create_the_output_folder(self) -> None:
        from app.ui.settings_dialog import SettingsDialog

        target = self.root / "nueva" / "salida"
        dialog = SettingsDialog(self.config, self.window)
        dialog.output_edit.setText(os.fspath(target))
        with mock.patch("app.ui.settings_dialog.QMessageBox.warning") as warning:
            dialog.accept()

        warning.assert_not_called()
        self.assertEqual(dialog.result(), SettingsDialog.DialogCode.Accepted)
        self.assertEqual(self.config.output_folder, target)
        self.assertTrue(target.is_dir())

    def test_summary_counts_only_the_results_of_the_batch(self) -> None:
        from app.models import ConversionResult

        image = make_image(self.root / "previo.png")
        self.window._add_paths([image])  # noqa: SLF001
        self.window.model.set_status([0], JobStatus.ERROR)

        with mock.patch.object(self.window, "_notify_finished"):  # noqa: SLF001
            self.window._on_finished([ConversionResult(image, JobStatus.DONE)])  # noqa: SLF001

        self.assertIn("1 convertidas · 0 omitidas · 0 errores", self.window.status_label.text())

    def test_conversion_marks_rows_running_and_releases_the_thread(self) -> None:
        image = make_image(self.root / "hilo.png")
        self.window._add_paths([image])  # noqa: SLF001
        self.window._start_conversion()  # noqa: SLF001

        item = self.window.model.item_at(0)
        assert item is not None
        self.assertIs(item.status, JobStatus.RUNNING)

        deadline = time.monotonic() + 20
        while self.window._running and time.monotonic() < deadline:  # noqa: SLF001
            _APP.processEvents()
            time.sleep(0.02)
        for _ in range(10):
            _APP.processEvents()

        self.assertFalse(self.window._running)  # noqa: SLF001
        self.assertIsNone(self.window._thread)  # noqa: SLF001
        self.assertEqual(self.window.findChildren(QThread), [])

    def test_removing_rows_forgets_their_thumbnails(self) -> None:
        image = make_image(self.root / "miniatura.png")
        self.window._add_paths([image])  # noqa: SLF001
        self.window.thumbnails.wait_for_done(5000)
        key = str(image).lower()
        self.assertIn(key, self.window.thumbnails._requested)  # noqa: SLF001

        self.window.table.selectRow(0)
        _APP.processEvents()
        self.window._remove_selected()  # noqa: SLF001

        self.assertNotIn(key, self.window.thumbnails._requested)  # noqa: SLF001
        self.window._add_paths([image])  # noqa: SLF001
        self.assertIn(key, self.window.thumbnails._requested)  # noqa: SLF001

    def test_quality_selected_in_the_session_survives_settings(self) -> None:
        self.window.quality_combo.addItem(tr("quality.custom", value=82), 82)
        self.window.quality_combo.setCurrentIndex(self.window.quality_combo.count() - 1)
        self.assertEqual(self.window._quality_cache[OutputFormat.WEBP], 82)  # noqa: SLF001

        with mock.patch("app.ui.main_window.SettingsDialog.exec", return_value=1):
            self.window._open_settings()  # noqa: SLF001
        self.assertEqual(self.window._current_quality(), 82)  # noqa: SLF001

    def test_no_profile_restores_the_previous_format_and_quality(self) -> None:
        initial_format = self.window._current_format()  # noqa: SLF001
        initial_quality = self.window._current_quality()  # noqa: SLF001

        index = self.window.profile_combo.findData("social")
        self.window.profile_combo.setCurrentIndex(index)
        _APP.processEvents()
        self.assertEqual(self.window._current_format(), OutputFormat.JPEG)  # noqa: SLF001

        self.window.profile_combo.setCurrentIndex(self.window.profile_combo.findData(""))
        _APP.processEvents()
        self.assertEqual(self.window._current_format(), initial_format)  # noqa: SLF001
        self.assertEqual(self.window._current_quality(), initial_quality)  # noqa: SLF001

    def test_failed_conversion_restores_running_rows(self) -> None:
        image = make_image(self.root / "fallida.png")
        self.window._add_paths([image])  # noqa: SLF001
        self.window.model.set_status([0], JobStatus.RUNNING)

        with mock.patch("app.ui.main_window.QMessageBox.critical"):
            self.window._on_failed("fallo de prueba")  # noqa: SLF001

        item = self.window.model.item_at(0)
        assert item is not None
        self.assertIs(item.status, JobStatus.PENDING)

    def test_accessible_names_are_translated(self) -> None:
        from app.ui.widgets import ToggleSwitch

        toggle = ToggleSwitch(self.window)
        self.assertEqual(toggle.accessibleName(), tr("toggle.accessible"))
        self.assertEqual(self.window.table.accessibleName(), tr("table.accessible"))
        self.assertEqual(self.window.progress_bar.accessibleName(), tr("progress.accessible"))
        self.assertEqual(self.window.banner_details.accessibleName(), tr("banner.view"))
        self.assertEqual(self.window.banner_close.accessibleName(), tr("banner.close"))

    def test_lossless_is_only_available_for_webp(self) -> None:
        index = self.window.format_combo.findData(OutputFormat.AVIF.value)
        self.window.format_combo.setCurrentIndex(index)
        self.window.lossless_toggle.setChecked(True)
        _APP.processEvents()

        self.assertTrue(self.window.lossless_toggle.isHidden())
        self.assertTrue(self.window.lossless_label.isHidden())
        self.assertFalse(self.window._current_options().lossless)  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
