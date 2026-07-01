from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, QTimer, QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bulk_print.files.validation import SUPPORTED_EXTENSIONS, validate_file
from bulk_print.printing.printers import list_printers, open_printer_preferences
from bulk_print.printing.settings import PrintOrientation, PrintSettings
from bulk_print.printing.worker import PrintFailure, PrintWorker
from bulk_print.services.update_service import UpdateService
from bulk_print.settings import APP_VERSION


class UpdateCheckWorker(QThread):
    update_found = Signal(dict, bool)
    update_failed = Signal(str, bool)

    def __init__(self, automatic: bool) -> None:
        super().__init__()
        self.automatic = automatic

    def run(self) -> None:
        try:
            self.update_found.emit(UpdateService.check_for_update(), self.automatic)
        except Exception as exc:
            self.update_failed.emit(str(exc), self.automatic)


class UpdateDownloadWorker(QThread):
    download_finished = Signal(object)
    download_failed = Signal(str)

    def __init__(self, asset: dict[str, Any]) -> None:
        super().__init__()
        self.asset = asset

    def run(self) -> None:
        try:
            self.download_finished.emit(UpdateService.download_update(self.asset))
        except Exception as exc:
            self.download_failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bulk Print")
        self.setAcceptDrops(True)
        self.files: list[Path] = []
        self.file_keys: set[str] = set()
        self.worker: PrintWorker | None = None
        self.update_worker: UpdateCheckWorker | None = None
        self.update_download_worker: UpdateDownloadWorker | None = None
        self.printer_combo = QComboBox()
        self.printer_settings_button = QPushButton("Printerinstellingen")
        self.update_button = QPushButton("Updates zoeken")
        self.add_button = QPushButton("Bestanden toevoegen")
        self.clear_button = QPushButton("Lijst leegmaken")
        self.start_button = QPushButton("Print starten")
        self.cancel_button = QPushButton("Annuleren")
        self.copies_spin = QSpinBox()
        self.orientation_combo = QComboBox()
        self.table = QTableWidget(0, 3)
        self.current_label = QLabel("Huidig bestand: -")
        self.count_label = QLabel("Voltooid: 0 / 0")
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.progress = QProgressBar()
        self.log = QTextEdit()
        self._build_ui()
        self._connect_signals()
        self._load_printers()
        QTimer.singleShot(1800, self.check_updates_on_startup)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("AppRoot")
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(18)

        title = QLabel("Bulk Print")
        title.setObjectName("Title")
        subtitle = QLabel("Voeg documenten toe, kies een printer en print alles in dezelfde volgorde.")
        subtitle.setObjectName("Subtitle")

        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)

        top_panel = QFrame()
        top_panel.setObjectName("Panel")
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(18, 18, 18, 18)
        top_layout.setSpacing(14)

        printer_row = QHBoxLayout()
        printer_row.setSpacing(12)
        printer_label = QLabel("Printer")
        printer_label.setObjectName("FieldLabel")
        printer_row.addWidget(printer_label)
        printer_row.addWidget(self.printer_combo, 1)
        printer_row.addWidget(self.printer_settings_button)

        settings_row = QHBoxLayout()
        settings_row.setSpacing(12)
        copies_label = QLabel("Kopieën")
        copies_label.setObjectName("FieldLabel")
        orientation_label = QLabel("Oriëntatie")
        orientation_label.setObjectName("FieldLabel")
        self.copies_spin.setRange(1, 99)
        self.copies_spin.setValue(1)
        self.copies_spin.setMinimumHeight(40)
        self.orientation_combo.addItem("Automatisch", PrintOrientation.AUTO.value)
        self.orientation_combo.addItem("Staand", PrintOrientation.PORTRAIT.value)
        self.orientation_combo.addItem("Liggend", PrintOrientation.LANDSCAPE.value)
        self.orientation_combo.setMinimumHeight(40)
        settings_row.addWidget(copies_label)
        settings_row.addWidget(self.copies_spin)
        settings_row.addWidget(orientation_label)
        settings_row.addWidget(self.orientation_combo)
        settings_row.addStretch(1)
        settings_row.addWidget(self.update_button)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.clear_button)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.start_button)

        top_layout.addLayout(printer_row)
        top_layout.addLayout(settings_row)
        top_layout.addLayout(button_row)

        file_panel = QFrame()
        file_panel.setObjectName("Panel")
        file_layout = QVBoxLayout(file_panel)
        file_layout.setContentsMargins(16, 16, 16, 16)
        file_layout.setSpacing(12)

        self.drop_hint = QLabel("Sleep bestanden hierheen")
        self.drop_hint.setObjectName("DropHint")
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setMinimumHeight(54)

        self.table.setHorizontalHeaderLabels(["Bestand", "Map", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 58)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setShowGrid(False)

        file_layout.addWidget(self.drop_hint)
        file_layout.addWidget(self.table, 1)

        status_panel = QFrame()
        status_panel.setObjectName("Panel")
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(16, 16, 16, 16)
        status_layout.setSpacing(12)

        status_row = QHBoxLayout()
        status_row.addWidget(self.current_label, 2)
        status_row.addWidget(self.count_label, 1)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(116)
        self.cancel_button.setEnabled(False)

        self.add_button.setObjectName("SecondaryButton")
        self.clear_button.setObjectName("QuietButton")
        self.cancel_button.setObjectName("DangerButton")
        self.start_button.setObjectName("PrimaryButton")
        self.printer_settings_button.setObjectName("QuietButton")
        self.update_button.setObjectName("QuietButton")
        self.current_label.setObjectName("StatusLabel")
        self.count_label.setObjectName("StatusLabel")
        self.version_label.setObjectName("VersionLabel")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.printer_combo.setMinimumHeight(40)
        for button in (
            self.add_button,
            self.clear_button,
            self.cancel_button,
            self.start_button,
            self.printer_settings_button,
            self.update_button,
        ):
            button.setMinimumHeight(38)

        status_layout.addLayout(status_row)
        status_layout.addWidget(self.progress)
        status_layout.addWidget(self.log)

        root.addLayout(header_text)
        root.addWidget(top_panel)
        root.addWidget(file_panel, 1)
        root.addWidget(status_panel)
        root.addWidget(self.version_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.setCentralWidget(central)
        self.setStyleSheet(
            """
            QWidget#AppRoot {
                background: #f4f7fb;
            }
            QWidget {
                font-family: Segoe UI;
                font-size: 10.5pt;
                color: #172033;
            }
            QLabel#Title {
                font-size: 25pt;
                font-weight: 700;
                color: #121826;
            }
            QLabel#Subtitle {
                color: #607087;
                font-size: 10pt;
            }
            QLabel#FieldLabel {
                color: #3d4a5c;
                font-weight: 600;
                min-width: 58px;
            }
            QLabel#StatusLabel {
                color: #4b5c73;
                font-size: 10pt;
            }
            QLabel#VersionLabel {
                color: #8390a4;
                font-size: 9pt;
                padding-left: 2px;
            }
            QLabel#DropHint {
                color: #51617a;
                background: #f8fafc;
                border: 1px dashed #b8c4d6;
                border-radius: 12px;
                font-weight: 600;
            }
            QFrame#Panel {
                background: #ffffff;
                border: 1px solid #e1e7ef;
                border-radius: 14px;
            }
            QComboBox, QSpinBox {
                background: #ffffff;
                border: 1px solid #cfd8e6;
                border-radius: 10px;
                padding: 7px 36px 7px 12px;
                selection-background-color: #dbeafe;
            }
            QComboBox:hover, QSpinBox:hover {
                border-color: #8da2c0;
            }
            QComboBox:focus, QSpinBox:focus {
                border-color: #2563eb;
            }
            QSpinBox {
                min-width: 72px;
                padding-right: 8px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 22px;
                border: 0;
                background: transparent;
            }
            QSpinBox::up-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid #64748b;
            }
            QSpinBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #64748b;
            }
            QComboBox::drop-down {
                border: 0;
                width: 32px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #64748b;
                margin-right: 12px;
            }
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #e3e9f2;
                border-radius: 12px;
                padding: 0;
                selection-background-color: #dbeafe;
                selection-color: #172033;
            }
            QTableWidget::item {
                border-bottom: 1px solid #eef2f7;
                padding: 8px;
            }
            QTextEdit {
                background: #f8fafc;
                border: 1px solid #e3e9f2;
                border-radius: 12px;
                padding: 10px;
                color: #3d4a5c;
            }
            QHeaderView::section {
                background: #f1f5f9;
                border: 0;
                border-bottom: 1px solid #e3e9f2;
                padding: 10px;
                font-weight: 600;
                color: #344256;
            }
            QPushButton {
                border-radius: 10px;
                padding: 8px 15px;
                font-weight: 600;
                background: #ffffff;
                border: 1px solid #cfd8e6;
                color: #243246;
            }
            QPushButton:hover {
                background: #f1f5fb;
                border-color: #9fb0c8;
            }
            QPushButton:pressed {
                background: #e8eef7;
            }
            QPushButton:disabled {
                color: #9aa8ba;
                background: #eef2f7;
                border-color: #dde5ef;
            }
            QPushButton#PrimaryButton {
                background: #1f6feb;
                color: #ffffff;
                border-color: #1f6feb;
            }
            QPushButton#PrimaryButton:hover {
                background: #155bd1;
                border-color: #155bd1;
            }
            QPushButton#SecondaryButton {
                background: #eef6ff;
                border-color: #bed6f5;
                color: #174ea6;
            }
            QPushButton#SecondaryButton:hover {
                background: #e1efff;
                border-color: #8bbbf0;
            }
            QPushButton#QuietButton {
                background: #ffffff;
                color: #4b5c73;
            }
            QPushButton#DangerButton {
                background: #fff5f5;
                border-color: #ffc9c9;
                color: #b42318;
            }
            QPushButton#DangerButton:hover {
                background: #ffecec;
                border-color: #ffabab;
            }
            QToolButton#RemoveButton {
                min-width: 30px;
                max-width: 30px;
                min-height: 30px;
                max-height: 30px;
                padding: 0;
                border-radius: 15px;
                color: #b42318;
                background: transparent;
                border: 1px solid transparent;
            }
            QToolButton#RemoveButton:hover {
                background: #fff1f2;
                border-color: #fecdd3;
            }
            QToolButton#RemoveButton:pressed {
                background: #ffe4e6;
                border-color: #fda4af;
            }
            QProgressBar {
                background: #e6edf6;
                border: 0;
                border-radius: 7px;
                min-height: 14px;
                max-height: 14px;
            }
            QProgressBar::chunk {
                background: #1f6feb;
                border-radius: 7px;
            }
            """
        )

    def _connect_signals(self) -> None:
        self.add_button.clicked.connect(self.choose_files)
        self.clear_button.clicked.connect(self.clear_files)
        self.start_button.clicked.connect(self.start_printing)
        self.cancel_button.clicked.connect(self.cancel_printing)
        self.printer_settings_button.clicked.connect(self.open_selected_printer_preferences)
        self.update_button.clicked.connect(self.check_updates_manually)

    def _load_printers(self) -> None:
        self.printer_combo.clear()
        try:
            printers = list_printers()
        except Exception as exc:
            QMessageBox.critical(self, "Printerfout", f"Printers konden niet worden geladen:\n{exc}")
            printers = []
        self.printer_combo.addItems(printers)

    def choose_files(self) -> None:
        extensions = " ".join(f"*{extension}" for extension in sorted(SUPPORTED_EXTENSIONS))
        selected, _ = QFileDialog.getOpenFileNames(self, "Bestanden selecteren", "", f"Ondersteunde bestanden ({extensions})")
        self.add_files([Path(path) for path in selected])

    def add_files(self, paths: list[Path]) -> None:
        added = 0
        rejected: list[str] = []
        for path in paths:
            validation = validate_file(path)
            key = str(validation.path).casefold()
            if not validation.valid:
                rejected.append(f"{validation.path.name}: {validation.error}")
                continue
            if key in self.file_keys:
                continue
            self.files.append(validation.path)
            self.file_keys.add(key)
            added += 1
        if added:
            self.refresh_table()
            self.append_log(f"{added} bestand(en) toegevoegd.")
        if rejected:
            QMessageBox.warning(self, "Niet toegevoegd", "\n".join(rejected))

    def refresh_table(self) -> None:
        self.table.setRowCount(0)
        for path in self.files:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(path.name))
            self.table.setItem(row, 1, QTableWidgetItem(str(path.parent)))
            remove_button = QToolButton()
            remove_button.setObjectName("RemoveButton")
            remove_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
            remove_button.setIconSize(QSize(16, 16))
            remove_button.setToolTip(f"Verwijder {path.name}")
            remove_button.clicked.connect(lambda checked=False, item=path: self.remove_file(item))
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.addWidget(remove_button)
            self.table.setCellWidget(row, 2, cell)
        self.count_label.setText(f"Voltooid: 0 / {len(self.files)}")

    def remove_file(self, path: Path) -> None:
        if self.worker is not None:
            return
        key = str(path).casefold()
        self.files = [item for item in self.files if str(item).casefold() != key]
        self.file_keys.discard(key)
        self.refresh_table()

    def clear_files(self) -> None:
        if self.worker is not None:
            return
        self.files.clear()
        self.file_keys.clear()
        self.refresh_table()
        self.progress.setValue(0)
        self.current_label.setText("Huidig bestand: -")
        self.append_log("Lijst leeggemaakt.")

    def start_printing(self) -> None:
        printer = self.printer_combo.currentText().strip()
        if not printer:
            QMessageBox.warning(self, "Geen printer", "Selecteer eerst een printer.")
            return
        if not self.files:
            QMessageBox.warning(self, "Geen bestanden", "Voeg eerst een of meer bestanden toe.")
            return
        self.set_printing_state(True)
        self.progress.setValue(0)
        self.log.clear()
        self.worker = PrintWorker(list(self.files), printer, self.current_print_settings())
        self.worker.progress_changed.connect(self.update_progress)
        self.worker.file_finished.connect(self.file_finished)
        self.worker.completed.connect(self.print_completed)
        self.worker.cancelled.connect(self.print_cancelled)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def current_print_settings(self) -> PrintSettings:
        orientation = PrintOrientation(self.orientation_combo.currentData())
        return PrintSettings(copies=self.copies_spin.value(), orientation=orientation)

    def open_selected_printer_preferences(self) -> None:
        printer = self.printer_combo.currentText().strip()
        if not printer:
            QMessageBox.warning(self, "Geen printer", "Selecteer eerst een printer.")
            return
        try:
            open_printer_preferences(printer)
        except Exception as exc:
            QMessageBox.warning(self, "Printerinstellingen", f"Printerinstellingen konden niet worden geopend:\n{exc}")

    def cancel_printing(self) -> None:
        if self.worker is not None:
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.append_log("Annuleren aangevraagd. Het huidige bestand wordt nog afgerond.")

    def update_progress(self, current_file: str, completed: int, total: int) -> None:
        name = Path(current_file).name
        self.current_label.setText(f"Huidig bestand: {name}")
        self.count_label.setText(f"Voltooid: {completed} / {total}")
        self.progress.setValue(int((completed / total) * 100) if total else 0)

    def file_finished(self, path: str, success: bool, message: str) -> None:
        name = Path(path).name
        if success:
            self.append_log(f"Geprint: {name}")
        else:
            self.append_log(f"Fout: {name} - {message}")

    def print_completed(self, failures: list[PrintFailure]) -> None:
        self.show_result("Printen voltooid", failures)

    def print_cancelled(self, failures: list[PrintFailure]) -> None:
        self.show_result("Printen geannuleerd", failures)

    def worker_finished(self) -> None:
        self.worker = None
        self.set_printing_state(False)

    def show_result(self, title: str, failures: list[PrintFailure]) -> None:
        if failures:
            lines = [f"{failure.path.name}: {failure.message}" for failure in failures]
            QMessageBox.warning(self, title, "Deze bestanden konden niet worden geprint:\n\n" + "\n".join(lines))
        else:
            QMessageBox.information(self, title, "Alle bestanden zijn verwerkt zonder fouten.")

    def set_printing_state(self, printing: bool) -> None:
        self.add_button.setEnabled(not printing)
        self.clear_button.setEnabled(not printing)
        self.start_button.setEnabled(not printing)
        self.printer_combo.setEnabled(not printing)
        self.printer_settings_button.setEnabled(not printing)
        self.copies_spin.setEnabled(not printing)
        self.orientation_combo.setEnabled(not printing)
        self.cancel_button.setEnabled(printing)
        self.table.setEnabled(not printing)

    def check_updates_on_startup(self) -> None:
        self.start_update_check(automatic=True)

    def check_updates_manually(self) -> None:
        self.start_update_check(automatic=False)

    def start_update_check(self, automatic: bool) -> None:
        if self.update_worker is not None:
            return
        self.update_button.setEnabled(False)
        if not automatic:
            self.append_log("Zoeken naar updates...")
        self.update_worker = UpdateCheckWorker(automatic)
        self.update_worker.update_found.connect(self.handle_update_result)
        self.update_worker.update_failed.connect(self.handle_update_error)
        self.update_worker.finished.connect(self.update_check_finished)
        self.update_worker.start()

    def update_check_finished(self) -> None:
        self.update_worker = None
        self.update_button.setEnabled(True)

    def handle_update_error(self, message: str, automatic: bool) -> None:
        if automatic:
            return
        QMessageBox.warning(self, "Updates zoeken", f"Updatecontrole is mislukt:\n{message}")
        self.append_log(f"Updatecontrole mislukt: {message}")

    def handle_update_result(self, result: dict[str, Any], automatic: bool) -> None:
        current_version = result["current_version"]
        latest_version = result["latest_version"]
        if not result["available"]:
            if not automatic:
                QMessageBox.information(
                    self,
                    "Geen update beschikbaar",
                    f"Je gebruikt al de nieuwste versie.\n\nHuidige versie: {current_version}\nNieuwste versie: {latest_version}",
                )
                self.append_log(f"Geen update beschikbaar. Huidige versie: {current_version}.")
            return

        release = result["release"]
        title = release.get("name") or f"Versie {latest_version}"
        answer = QMessageBox.question(
            self,
            "Update beschikbaar",
            f"Er is een nieuwe versie beschikbaar.\n\nHuidige versie: {current_version}\nNieuwe versie: {latest_version}\nRelease: {title}\n\nWil je deze update downloaden?",
        )
        if answer != QMessageBox.Yes:
            self.append_log("Update overgeslagen.")
            return
        self.download_update(result["asset"])

    def download_update(self, asset: dict[str, Any]) -> None:
        if self.update_download_worker is not None:
            return
        self.update_button.setEnabled(False)
        self.append_log("Update wordt gedownload...")
        self.update_download_worker = UpdateDownloadWorker(asset)
        self.update_download_worker.download_finished.connect(self.handle_update_downloaded)
        self.update_download_worker.download_failed.connect(self.handle_update_download_error)
        self.update_download_worker.finished.connect(self.update_download_finished)
        self.update_download_worker.start()

    def update_download_finished(self) -> None:
        self.update_download_worker = None
        self.update_button.setEnabled(True)

    def handle_update_download_error(self, message: str) -> None:
        QMessageBox.warning(self, "Update downloaden", f"Update downloaden is mislukt:\n{message}")
        self.append_log(f"Update downloaden mislukt: {message}")

    def handle_update_downloaded(self, installer_path: object) -> None:
        path = Path(installer_path)
        self.append_log(f"Update gedownload: {path}")
        if not UpdateService.is_frozen():
            QMessageBox.information(
                self,
                "Update gedownload",
                f"De installer is gedownload naar:\n{path}\n\nAutomatisch installeren werkt alleen vanuit de geinstalleerde .exe.",
            )
            return
        QMessageBox.information(
            self,
            "Update klaar",
            "De app wordt nu gesloten. De installer werkt de app bij en start daarna opnieuw.",
        )
        UpdateService.install_update(path)

    def append_log(self, message: str) -> None:
        self.log.append(message)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self.add_files(paths)
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None:
            result = QMessageBox.question(self, "Printen actief", "Er wordt nog geprint. Wil je annuleren en afsluiten?")
            if result != QMessageBox.Yes:
                event.ignore()
                return
            self.worker.cancel()
            self.worker.wait(3000)
        QApplication.restoreOverrideCursor()
        event.accept()
