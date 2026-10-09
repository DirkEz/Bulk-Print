import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QItemSelectionModel, QMimeData, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from bulk_print.gui.main_window import MainWindow
from bulk_print.printing.backends import PrintError
from bulk_print.printing.settings import PrintSettings
from bulk_print.printing.worker import PrintWorker


class PrintWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.preferences = QSettings(str(self.directory / "settings.ini"), QSettings.Format.IniFormat)
        self.preferences.setValue("printer", "Kantoor")
        self.patch("bulk_print.gui.main_window.QSettings", return_value=self.preferences)
        self.printers = self.patch("bulk_print.gui.main_window.list_printers", return_value=["PDF", "Kantoor"])
        self.patch("bulk_print.gui.main_window.default_printer", return_value="PDF")
        self.patch("bulk_print.gui.main_window.MainWindow.check_updates_on_startup")
        self.print_file = self.patch("bulk_print.printing.worker.print_file")
        self.warning = self.patch("bulk_print.gui.main_window.MainWindow.show_warning_popup")
        self.window = MainWindow()
        self.addCleanup(self.close_window)

    def patch(self, name, **kwargs):
        patcher = patch(name, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def close_window(self):
        if self.window.worker is not None:
            self.window.worker_finished()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def files(self, count=4):
        paths = [self.directory / f"Document {index}.pdf" for index in range(count)]
        for path in paths:
            path.touch()
        self.window.add_files(paths)
        return paths

    def select(self, *rows):
        self.window.table.clearSelection()
        for row in rows:
            self.window.table.selectionModel().select(
                self.window.table.model().index(row, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )

    def run_batch(self, retry=False):
        # Run the real worker synchronously, with only the OS print call mocked.
        with patch.object(PrintWorker, "start"):
            self.window.retry_failed_files() if retry else self.window.start_printing()
        self.window.worker.run()
        self.window.worker_finished()

    def test_printer_selection_is_remembered_and_refresh_preserves_it(self):
        self.assertEqual(self.window.printer_combo.currentText(), "Kantoor")
        self.window.printer_combo.setCurrentText("PDF")
        self.assertEqual(self.preferences.value("printer"), "PDF")
        self.window._load_printers()
        self.assertEqual(self.window.printer_combo.currentText(), "PDF")

    def test_missing_printer_falls_back_and_empty_list_disables_print(self):
        self.files(1)
        self.printers.return_value = ["PDF"]
        self.window._load_printers()
        self.assertEqual(self.window.printer_combo.currentText(), "PDF")
        self.printers.return_value = []
        self.window._load_printers()
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertFalse(self.window.printer_settings_button.isEnabled())
        self.assertFalse(self.window.printer_hint.isHidden())
        self.printers.return_value = ["PDF", "Kantoor"]
        self.window._load_printers()
        self.assertEqual(self.window.printer_combo.currentText(), "Kantoor")

    def test_duplicates_and_invalid_files_do_not_enter_queue(self):
        paths = self.files(1)
        unsupported = self.directory / "script.exe"
        unsupported.touch()
        self.window.add_files([paths[0], unsupported, self.directory / "missing.pdf"])
        self.assertEqual(self.window.files, paths)
        self.assertEqual(len(self.window.file_keys), 1)
        self.warning.assert_called_once()
        self.assertIn("overgeslagen", self.window.log.toPlainText())

    def test_multiple_rows_move_in_order_and_keep_selection(self):
        paths = self.files(5)
        self.select(1, 2, 4)
        self.window.move_selected_files(-1)
        self.assertEqual(self.window.files, [paths[1], paths[2], paths[0], paths[4], paths[3]])
        self.assertEqual(self.window.selected_rows(), [0, 1, 3])
        self.window.move_selected_files(-1)
        self.assertFalse(self.window.up_button.isEnabled())
        self.assertEqual(self.window.files[0:2], paths[1:3])
        self.window.move_selected_files(1)
        self.assertEqual(self.window.files, paths)
        self.assertEqual(self.window.selected_rows(), [1, 2, 4])
        self.assertFalse(self.window.down_button.isEnabled())

    def test_removing_selection_clears_status_and_allows_readding(self):
        paths = self.files()
        self.window.set_file_status(paths[1], "failed", "Test")
        self.select(1, 3)
        self.window.remove_selected_files()
        self.assertEqual(self.window.files, [paths[0], paths[2]])
        self.assertNotIn(paths[1], self.window.file_statuses)
        self.assertTrue(self.window.retry_button.isHidden())
        self.window.add_files([paths[1]])
        self.assertEqual(self.window.files[-1], paths[1])

    def test_queue_is_locked_during_print_including_drop_and_shortcuts(self):
        paths = self.files()
        self.select(1)
        with patch.object(PrintWorker, "start") as start:
            self.window.start_printing()
            worker = self.window.worker
            self.window.start_printing()
            self.window.clear_files()
            self.window.remove_selected_files()
            self.window.move_selected_files(-1)
            self.window.add_files([self.directory / "new.pdf"])
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(paths[0]))])
            event = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            self.window.dropEvent(event)
            self.assertFalse(event.isAccepted())
            self.assertEqual(self.window.files, paths)
            self.assertIs(self.window.worker, worker)
            self.assertFalse(self.window.start_button.isEnabled())
            start.assert_called_once()

    def test_only_failed_files_are_retried(self):
        paths = self.files(3)
        self.window.copies_spin.setValue(2)
        self.print_file.side_effect = [None, PrintError("Printer tijdelijk niet bereikbaar"), None]
        self.run_batch()
        self.assertEqual([self.window.file_statuses[path][0] for path in paths], ["sent", "failed", "sent"])
        self.assertIn("2 verzonden · 1 mislukt", self.window.summary_label.text())
        self.assertFalse(self.window.retry_button.isHidden())
        self.assertTrue(self.window.details_button.isChecked())
        self.assertEqual(self.window.progress.value(), 100)
        self.assertEqual(self.window.start_button.text(), "Alles opnieuw printen")
        self.print_file.reset_mock(side_effect=True)
        self.run_batch(retry=True)
        self.print_file.assert_called_once_with(paths[1], "Kantoor", PrintSettings(copies=2))
        self.assertTrue(all(state == "sent" for state, _ in self.window.file_statuses.values()))
        self.assertTrue(self.window.retry_button.isHidden())
        self.assertIn("1 verzonden", self.window.summary_label.text())

    def test_cancel_reports_unsubmitted_files_without_claiming_success(self):
        paths = self.files(3)
        self.print_file.side_effect = lambda *args: self.window.cancel_printing()
        self.run_batch()
        self.assertEqual(self.print_file.call_count, 1)
        self.assertEqual([self.window.file_statuses[path][0] for path in paths], ["sent", "cancelled", "cancelled"])
        self.assertEqual(self.window.summary_label.text(), "Gestopt · 1 verzonden · 2 niet verzonden")
        self.assertEqual(self.window.count_label.text(), "1 / 3")
        self.assertFalse(self.window.printing)
        self.assertTrue(self.window.cancel_button.isHidden())

    def test_cancel_before_first_file_reports_zero_sent(self):
        paths = self.files(2)
        with patch.object(PrintWorker, "start"):
            self.window.start_printing()
        self.window.cancel_printing()
        self.window.worker.run()
        self.window.worker_finished()
        self.print_file.assert_not_called()
        self.assertEqual(self.window.summary_label.text(), "Gestopt · 0 verzonden · 2 niet verzonden")
        self.assertTrue(all(self.window.file_statuses[path][0] == "cancelled" for path in paths))

    def test_missing_file_advances_progress_and_other_files_continue(self):
        paths = self.files(2)
        paths[-1].unlink()
        self.run_batch()
        self.assertEqual(self.print_file.call_count, 1)
        self.assertEqual(self.window.progress.value(), 100)
        self.assertEqual(self.window.count_label.text(), "2 / 2")
        self.assertEqual(self.window.table.item(1, 3).text(), "Mislukt")
        self.assertIn("Bestand bestaat niet", self.window.table.item(1, 3).toolTip())

    def test_print_uses_reordered_queue(self):
        paths = self.files(3)
        self.select(2)
        self.window.move_selected_files(-1)
        self.run_batch()
        self.assertEqual([call.args[0] for call in self.print_file.call_args_list], [paths[0], paths[2], paths[1]])

    def test_real_thread_completion_restores_controls(self):
        paths = self.files(2)
        self.window.start_printing()
        for _ in range(100):
            if self.window.worker is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.window.worker)
        self.assertFalse(self.window.printing)
        self.assertTrue(self.window.start_button.isEnabled())
        self.assertEqual([self.window.file_statuses[path][0] for path in paths], ["sent", "sent"])
        self.assertEqual(self.window.progress.value(), 100)

    def test_keyboard_reorders_and_removes_selected_rows(self):
        paths = self.files(3)
        self.window.show()
        self.window.activateWindow()
        self.window.table.setFocus()
        self.window.table.selectRow(1)
        self.app.processEvents()
        QTest.keyClick(self.window.table, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(self.window.files, [paths[1], paths[0], paths[2]])
        QTest.keyClick(self.window.table, Qt.Key.Key_Delete)
        self.assertEqual(self.window.files, [paths[0], paths[2]])

    def test_logs_treat_filenames_as_plain_text(self):
        self.window.append_log("<b>document</b>.pdf")
        self.assertIn("<b>document</b>.pdf", self.window.log.toPlainText())

    def test_close_waits_until_worker_finishes(self):
        self.files(2)
        with patch.object(PrintWorker, "start"):
            self.window.start_printing()
        with patch.object(self.window, "show_question_popup", return_value=QMessageBox.StandardButton.Yes), patch.object(self.window.worker, "isRunning", return_value=True), patch("bulk_print.gui.main_window.QTimer.singleShot"):
            event = QCloseEvent()
            self.window.closeEvent(event)
            self.assertFalse(event.isAccepted())
            self.assertTrue(self.window.worker._cancel_requested)

    def test_compact_layout_fits_without_horizontal_clipping(self):
        paths = self.files(2)
        self.window.resize(500, 560)
        self.window.show()
        self.window.set_file_status(paths[0], "sent")
        self.window.set_file_status(paths[1], "failed", "Testfout")
        self.window.update_controls()
        for _ in range(5):
            self.app.processEvents()
        self.assertLessEqual(self.window.scroll_area.widget().width(), self.window.scroll_area.viewport().width())
        self.assertTrue(self.window.table.isColumnHidden(2))
        self.window.scroll_area.ensureWidgetVisible(self.window.start_button)
        self.app.processEvents()
        self.assertTrue(self.window.start_button.isVisible())
        for width in (760, 839, 840, 1040):
            self.window.resize(width, 800)
            for _ in range(5):
                self.app.processEvents()
            self.assertLessEqual(self.window.scroll_area.widget().width(), self.window.scroll_area.viewport().width(), f"Layout clipped at width {width}")


if __name__ == "__main__":
    unittest.main()
