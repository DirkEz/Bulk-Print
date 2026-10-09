from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QItemSelectionModel, QSettings, QThread, QTimer, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence, QResizeEvent, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QMainWindow, QMessageBox, QPushButton, QProgressBar,
    QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from bulk_print.files.validation import SUPPORTED_EXTENSIONS, validate_file
from bulk_print.gui.theme import STYLESHEET, icon
from bulk_print.gui.widgets import FileNameDelegate
from bulk_print.printing.printers import default_printer, list_printers, open_printer_preferences
from bulk_print.printing.settings import PrintOrientation, PrintSettings
from bulk_print.printing.worker import PrintFailure, PrintWorker
from bulk_print.services.update_service import UpdateService
from bulk_print.settings import APP_COMPANY, APP_NAME, APP_VERSION


FILE_STATES = {
    "ready": ("Gereed", "#748292"),
    "printing": ("Verzenden…", "#157d73"),
    "sent": ("Verzonden", "#117466"),
    "failed": ("Mislukt", "#b54a40"),
    "cancelled": ("Niet verzonden", "#8b6b3f"),
}


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
        self.preferences = QSettings(APP_COMPANY, APP_NAME)
        self.files: list[Path] = []
        self.file_keys: set[str] = set()
        self.file_statuses: dict[Path, tuple[str, str]] = {}
        self.worker: PrintWorker | None = None
        self.update_worker: UpdateCheckWorker | None = None
        self.update_download_worker: UpdateDownloadWorker | None = None
        self.printing = False
        self._close_requested = False
        self._has_result = False
        self._batch_files: list[Path] = []
        self._batch_completed = 0
        self._batch_success = 0
        self.compact_mode: bool | None = None
        self.printer_combo = QComboBox()
        self.printer_settings_button = self._tool_button("settings", "Printerinstellingen")
        self.refresh_printers_button = self._tool_button("refresh", "Printers vernieuwen")
        self.update_button = QPushButton("Updates zoeken")
        self.help_button = QPushButton("Help")
        self.add_button = QPushButton("Bestanden toevoegen")
        self.clear_button = QPushButton("Lijst leegmaken")
        self.remove_button = QPushButton("Verwijderen")
        self.up_button = self._tool_button("up", "Omhoog (Alt+↑)")
        self.down_button = self._tool_button("down", "Omlaag (Alt+↓)")
        self.start_button = QPushButton("Print starten")
        self.retry_button = QPushButton("Mislukte opnieuw proberen")
        self.cancel_button = QPushButton("Stoppen")
        self.copies_spin = QSpinBox()
        self.orientation_combo = QComboBox()
        self.table = QTableWidget(0, 4)
        self.summary_label = QLabel("Klaar voor je documenten")
        self.current_label = QLabel("Voeg bestanden toe om te beginnen.")
        self.count_label = QLabel()
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.progress = QProgressBar()
        self.log = QTextEdit()
        self.details_button = QToolButton()
        self._build_ui()
        self._connect_signals()
        self._load_printers()
        self.refresh_table()
        QTimer.singleShot(1800, self.check_updates_on_startup)

    def _tool_button(self, name: str, label: str) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon(name))
        button.setIconSize(QSize(18, 18))
        button.setFixedSize(38, 38)
        button.setToolTip(label)
        button.setAccessibleName(label)
        return button

    @staticmethod
    def _label(text: str, name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(name)
        return label

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("AppRoot")
        self.root_layout = QVBoxLayout(central)
        self.root_layout.setContentsMargins(28, 24, 28, 14)
        self.root_layout.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(14)
        mark = self._label("", "AppMark")
        mark.setPixmap(icon("print", "#ffffff").pixmap(28, 28))
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(56, 56)
        header.addWidget(mark)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self._label("Bulk Print", "Title"))
        self.subtitle_label = self._label("Je documenten. Eén lijst. Zo geprint.", "Subtitle")
        titles.addWidget(self.subtitle_label)
        header.addLayout(titles, 1)
        header.addWidget(self._label("DEYVO", "Brand"))
        self.root_layout.addLayout(header)

        settings_panel = QFrame()
        settings_panel.setObjectName("Panel")
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setContentsMargins(18, 16, 18, 14)
        settings_layout.setSpacing(8)
        self.settings_grid = QGridLayout()
        self.settings_grid.setHorizontalSpacing(18)
        self.settings_grid.setVerticalSpacing(12)
        self.printer_field = QWidget()
        printer_layout = QVBoxLayout(self.printer_field)
        printer_layout.setContentsMargins(0, 0, 0, 0)
        printer_layout.setSpacing(6)
        printer_label = self._label("Printer", "FieldLabel")
        printer_label.setBuddy(self.printer_combo)
        printer_layout.addWidget(printer_label)
        printer_row = QHBoxLayout()
        printer_row.setSpacing(6)
        self.printer_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.printer_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.printer_combo.setMinimumContentsLength(12)
        self.printer_combo.setAccessibleName("Printer")
        printer_row.addWidget(self.printer_combo, 1)
        printer_row.addWidget(self.refresh_printers_button)
        printer_row.addWidget(self.printer_settings_button)
        printer_layout.addLayout(printer_row)
        self.copies_spin.setRange(1, 99)
        self.copies_spin.setValue(1)
        self.copies_spin.setAccessibleName("Kopieën per bestand")
        self.copies_spin.setFixedWidth(96)
        self.copies_spin.setToolTip("Aantal kopieën per bestand")
        self.orientation_combo.addItem("Automatisch", PrintOrientation.AUTO.value)
        self.orientation_combo.addItem("Staand", PrintOrientation.PORTRAIT.value)
        self.orientation_combo.addItem("Liggend", PrintOrientation.LANDSCAPE.value)
        self.orientation_combo.setAccessibleName("Oriëntatie")
        self.orientation_combo.setToolTip("Geldt voor PDF's en afbeeldingen. Office gebruikt de documentinstellingen.")
        self.options_field = QWidget()
        options_layout = QHBoxLayout(self.options_field)
        options_layout.setContentsMargins(0, 0, 0, 0)
        options_layout.setSpacing(16)
        for label, widget in (("Kopieën", self.copies_spin), ("Oriëntatie", self.orientation_combo)):
            field = QVBoxLayout()
            field.setSpacing(6)
            field_label = self._label(label, "FieldLabel")
            field_label.setBuddy(widget)
            field.addWidget(field_label)
            field.addWidget(widget)
            options_layout.addLayout(field)
        self.settings_grid.addWidget(self.printer_field, 0, 0)
        self.settings_grid.addWidget(self.options_field, 0, 1)
        self.settings_grid.setColumnStretch(0, 1)
        settings_layout.addLayout(self.settings_grid)
        self.printer_hint = self._label("", "Hint")
        self.printer_hint.setWordWrap(True)
        settings_layout.addWidget(self.printer_hint)
        self.root_layout.addWidget(settings_panel)

        file_panel = QFrame()
        file_panel.setObjectName("Panel")
        file_layout = QVBoxLayout(file_panel)
        self.file_layout = file_layout
        file_layout.setContentsMargins(18, 16, 18, 14)
        file_layout.setSpacing(10)
        file_header = QHBoxLayout()
        self.file_header = file_header
        file_header.setSpacing(9)
        file_header.addWidget(self._label("Bestanden", "SectionTitle"))
        self.file_count = self._label("0", "FileCount")
        self.file_count.setFixedHeight(24)
        file_header.addWidget(self.file_count)
        file_header.addStretch()
        self.add_button.setObjectName("SecondaryButton")
        self.add_button.setIcon(icon("add", "#116b60"))
        file_header.addWidget(self.add_button)
        file_layout.addLayout(file_header)
        self.queue_toolbar = QWidget()
        toolbar = QHBoxLayout(self.queue_toolbar)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)
        toolbar.addWidget(self.up_button)
        toolbar.addWidget(self.down_button)
        self.remove_button.setIcon(icon("remove"))
        self.remove_button.setObjectName("QuietButton")
        toolbar.addWidget(self.remove_button)
        toolbar.addStretch()
        self.clear_button.setObjectName("QuietButton")
        toolbar.addWidget(self.clear_button)
        file_layout.addWidget(self.queue_toolbar)

        self.file_stack = QStackedWidget()
        empty = QFrame()
        empty.setObjectName("EmptyState")
        empty.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(18, 22, 18, 22)
        empty_layout.setSpacing(10)
        empty_layout.addStretch()
        empty_icon = self._label("", "EmptyIcon")
        empty_icon.setPixmap(icon("files", "#157d73").pixmap(32, 32))
        empty_icon.setFixedSize(64, 64)
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        for text, name in (("Sleep je bestanden hierheen", "EmptyTitle"), ("of kies ze via Bestanden toevoegen", "Hint"), ("PDF  ·  Word  ·  Excel  ·  PowerPoint  ·  Afbeeldingen", "Hint")):
            label = self._label(text, name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            empty_layout.addWidget(label)
        empty_layout.addStretch()
        self.file_stack.addWidget(empty)
        self.table.setHorizontalHeaderLabels(["#", "Bestand", "Type", "Status"])
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for column in (0, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(2, 72)
        self.table.setColumnWidth(3, 124)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(False)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(58)
        self.table.setItemDelegateForColumn(1, FileNameDelegate(self.table))
        self.table.setAccessibleName("Bestanden in printvolgorde")
        self.table.setMinimumHeight(180)
        self.file_stack.addWidget(self.table)
        file_layout.addWidget(self.file_stack, 1)
        self.queue_hint = self._label("Bestanden worden in de volgorde van de lijst geprint.", "Hint")
        self.queue_hint.setWordWrap(True)
        file_layout.addWidget(self.queue_hint)
        self.root_layout.addWidget(file_panel, 1)

        status_panel = QFrame()
        status_panel.setObjectName("Panel")
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(10)
        status_row = QHBoxLayout()
        self.summary_label.setObjectName("StatusTitle")
        self.summary_label.setTextFormat(Qt.TextFormat.PlainText)
        self.summary_label.setWordWrap(True)
        self.current_label.setObjectName("Hint")
        self.current_label.setTextFormat(Qt.TextFormat.PlainText)
        self.current_label.setWordWrap(True)
        self.current_label.setMinimumWidth(0)
        self.current_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        summary = QVBoxLayout()
        summary.setSpacing(5)
        summary.addWidget(self.summary_label)
        summary.addWidget(self.current_label)
        status_row.addLayout(summary, 1)
        self.count_label.setObjectName("Hint")
        status_row.addWidget(self.count_label)
        status_layout.addLayout(status_row)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        status_layout.addWidget(self.progress)
        actions = QGridLayout()
        self.actions_layout = actions
        actions.setSpacing(8)
        actions.setColumnStretch(0, 1)
        self.details_button.setText("Details")
        self.details_button.setObjectName("QuietButton")
        self.details_button.setCheckable(True)
        self.details_button.setArrowType(Qt.ArrowType.RightArrow)
        self.details_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        actions.addWidget(self.details_button, 0, 0, Qt.AlignmentFlag.AlignLeft)
        self.retry_button.setObjectName("PrimaryButton")
        self.retry_button.hide()
        actions.addWidget(self.retry_button, 0, 1)
        self.cancel_button.setObjectName("DangerButton")
        self.cancel_button.hide()
        actions.addWidget(self.cancel_button, 0, 2)
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.setIcon(icon("print", "#ffffff"))
        actions.addWidget(self.start_button, 0, 2)
        status_layout.addLayout(actions)
        self.log.setReadOnly(True)
        self.log.setFixedHeight(100)
        self.log.setPlaceholderText("Hier verschijnen meldingen over je printopdracht.")
        self.log.document().setMaximumBlockCount(1000)
        self.log.hide()
        status_layout.addWidget(self.log)
        self.root_layout.addWidget(status_panel)
        footer = QHBoxLayout()
        self.version_label.setObjectName("VersionLabel")
        footer.addWidget(self.version_label)
        footer.addStretch()
        for button in (self.help_button, self.update_button):
            button.setObjectName("FooterButton")
            footer.addWidget(button)
        self.root_layout.addLayout(footer)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("MainScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(central)
        self.setCentralWidget(self.scroll_area)
        self.setStyleSheet(STYLESHEET)
        self.apply_responsive_layout(self.width(), self.height())

    def _connect_signals(self) -> None:
        self.add_button.clicked.connect(self.choose_files)
        self.clear_button.clicked.connect(self.clear_files)
        self.remove_button.clicked.connect(self.remove_selected_files)
        self.up_button.clicked.connect(lambda: self.move_selected_files(-1))
        self.down_button.clicked.connect(lambda: self.move_selected_files(1))
        self.table.itemSelectionChanged.connect(self.update_controls)
        self.start_button.clicked.connect(self.start_printing)
        self.retry_button.clicked.connect(self.retry_failed_files)
        self.cancel_button.clicked.connect(self.cancel_printing)
        self.printer_settings_button.clicked.connect(self.open_selected_printer_preferences)
        self.refresh_printers_button.clicked.connect(self._load_printers)
        self.printer_combo.currentTextChanged.connect(self.printer_changed)
        self.copies_spin.valueChanged.connect(self.update_summary)
        self.update_button.clicked.connect(self.check_updates_manually)
        self.help_button.clicked.connect(self.show_manual)
        self.details_button.toggled.connect(self.toggle_details)
        for key, action in ((QKeySequence.StandardKey.Open, self.choose_files), (QKeySequence.StandardKey.Print, self.start_printing)):
            QShortcut(QKeySequence(key), self, activated=action)
        for key, action in (("Delete", self.remove_selected_files), ("Alt+Up", lambda: self.move_selected_files(-1)), ("Alt+Down", lambda: self.move_selected_files(1))):
            shortcut = QShortcut(QKeySequence(key), self.table, activated=action)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def _load_printers(self) -> None:
        if self.printing:
            return
        preferred = self.printer_combo.currentText() or self.preferences.value("printer", "", type=str)
        self.printer_combo.blockSignals(True)
        self.printer_combo.clear()
        try:
            printers = list_printers()
            fallback = default_printer()
        except Exception as exc:
            printers, fallback = [], ""
            self.append_log(f"Printers laden mislukt: {exc}")
        self.printer_combo.addItems(printers)
        if printers:
            selected = preferred if preferred in printers else fallback if fallback in printers else printers[0]
            self.printer_combo.setCurrentText(selected)
        self.printer_combo.setPlaceholderText("Geen printer gevonden")
        self.printer_combo.blockSignals(False)
        self.printer_hint.setText("Geen printer gevonden. Voeg een printer toe in Windows en klik op vernieuwen.")
        self.printer_hint.setVisible(not printers)
        self.update_controls()
        self.update_summary()

    def printer_changed(self, printer: str) -> None:
        if printer:
            self.preferences.setValue("printer", printer)
        self.update_controls()
        self.update_summary()

    def choose_files(self) -> None:
        if self.printing:
            return
        extensions = " ".join(f"*{extension}" for extension in sorted(SUPPORTED_EXTENSIONS))
        selected, _ = QFileDialog.getOpenFileNames(self, "Bestanden selecteren", "", f"Ondersteunde bestanden ({extensions})")
        self.add_files([Path(path) for path in selected])

    def add_files(self, paths: list[Path]) -> None:
        if self.printing:
            return
        added, duplicates = 0, 0
        rejected: list[str] = []
        for path in paths:
            validation = validate_file(path)
            key = str(validation.path).casefold()
            if not validation.valid:
                rejected.append(f"{validation.path.name}: {validation.error}")
            elif key in self.file_keys:
                duplicates += 1
            else:
                self.files.append(validation.path)
                self.file_keys.add(key)
                added += 1
        if added:
            self._reset_result()
            self.refresh_table()
            self.append_log(f"{added} bestand(en) toegevoegd.")
        if duplicates:
            self.append_log(f"{duplicates} bestand(en) stonden al in de lijst en zijn overgeslagen.")
        if rejected:
            self.show_warning_popup("Niet toegevoegd", "\n".join(rejected))

    def refresh_table(self, selected: list[Path] | None = None) -> None:
        self.table.setRowCount(0)
        for row, path in enumerate(self.files):
            self.table.insertRow(row)
            number = QTableWidgetItem(str(row + 1))
            number.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            number.setForeground(QColor("#748292"))
            self.table.setItem(row, 0, number)
            name = QTableWidgetItem(path.name)
            name.setData(Qt.ItemDataRole.UserRole, str(path.parent))
            name.setToolTip(str(path))
            self.table.setItem(row, 1, name)
            file_type = QTableWidgetItem(path.suffix.removeprefix(".").upper())
            file_type.setForeground(QColor("#748292"))
            self.table.setItem(row, 2, file_type)
            self.table.setItem(row, 3, QTableWidgetItem())
            self._render_file_status(row, path)
        if selected:
            for row, path in enumerate(self.files):
                if path in selected:
                    self.table.selectionModel().select(self.table.model().index(row, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.file_count.setText(str(len(self.files)))
        self.file_stack.setCurrentIndex(1 if self.files else 0)
        self.queue_toolbar.setVisible(bool(self.files))
        self.queue_hint.setVisible(bool(self.files))
        self.update_controls()
        self.update_summary()

    def _render_file_status(self, row: int, path: Path) -> None:
        state, message = self.file_statuses.get(path, ("ready", ""))
        text, color = FILE_STATES[state]
        item = self.table.item(row, 3)
        item.setText(text)
        item.setForeground(QColor(color))
        item.setToolTip(message or text)

    def set_file_status(self, path: Path, state: str, message: str = "") -> None:
        self.file_statuses[path] = (state, message)
        if path in self.files:
            self._render_file_status(self.files.index(path), path)

    def selected_rows(self) -> list[int]:
        return sorted(index.row() for index in self.table.selectionModel().selectedRows())

    def move_selected_files(self, direction: int) -> None:
        if self.printing or direction not in (-1, 1):
            return
        rows = self.selected_rows()
        if not rows or (direction == -1 and rows[0] == 0) or (direction == 1 and rows[-1] == len(self.files) - 1):
            return
        selected = [self.files[row] for row in rows]
        for row in rows if direction == -1 else reversed(rows):
            target = row + direction
            self.files[row], self.files[target] = self.files[target], self.files[row]
        self.refresh_table(selected)
        self.table.scrollToItem(self.table.item(rows[0] + direction, 1))

    def remove_selected_files(self) -> None:
        if self.printing:
            return
        rows = self.selected_rows()
        if not rows:
            return
        for row in reversed(rows):
            path = self.files.pop(row)
            self.file_keys.discard(str(path).casefold())
            self.file_statuses.pop(path, None)
        self._reset_result()
        self.refresh_table()
        if self.files:
            self.table.selectRow(min(rows[0], len(self.files) - 1))

    def clear_files(self) -> None:
        if self.printing:
            return
        self.files.clear()
        self.file_keys.clear()
        self.file_statuses.clear()
        self._reset_result()
        self.refresh_table()
        self.append_log("Lijst leeggemaakt.")

    def _reset_result(self) -> None:
        self._has_result = False
        self.progress.hide()
        self.count_label.clear()
        self.set_summary_tone("")

    def update_controls(self) -> None:
        idle = not self.printing
        has_printer = bool(self.printer_combo.currentText())
        rows = self.selected_rows()
        self.add_button.setEnabled(idle)
        self.clear_button.setEnabled(idle and bool(self.files))
        self.remove_button.setEnabled(idle and bool(rows))
        self.up_button.setEnabled(idle and bool(rows) and rows[0] > 0)
        self.down_button.setEnabled(idle and bool(rows) and rows[-1] < len(self.files) - 1)
        self.start_button.setEnabled(idle and bool(self.files) and has_printer)
        self.start_button.setVisible(idle)
        already_sent = any(state == "sent" for state, _ in self.file_statuses.values())
        self.start_button.setText("Alles opnieuw printen" if already_sent and idle else "Print starten")
        has_failures = any(state == "failed" for state, _ in self.file_statuses.values())
        button_style = "SecondaryButton" if has_failures and idle else "PrimaryButton"
        if self.start_button.objectName() != button_style:
            self.start_button.setObjectName(button_style)
            self.start_button.setIcon(icon("print", "#116b60" if has_failures and idle else "#ffffff"))
            self.start_button.style().unpolish(self.start_button)
            self.start_button.style().polish(self.start_button)
        self.printer_combo.setEnabled(idle)
        self.printer_settings_button.setEnabled(idle and has_printer)
        self.refresh_printers_button.setEnabled(idle)
        self.copies_spin.setEnabled(idle)
        self.orientation_combo.setEnabled(idle)
        self.cancel_button.setVisible(self.printing)
        self.retry_button.setVisible(idle and has_failures)
        self.retry_button.setEnabled(idle and has_printer)
        self.update_button.setEnabled(idle and self.update_worker is None and self.update_download_worker is None)

    def update_summary(self) -> None:
        if self.printing or self._has_result:
            return
        if not self.files:
            self.summary_label.setText("Klaar voor je documenten")
            self.current_label.setText("Voeg bestanden toe om te beginnen.")
        elif not self.printer_combo.currentText():
            self.summary_label.setText("Kies een printer om te beginnen")
            self.current_label.setText(f"{len(self.files)} bestand(en) staan klaar.")
        else:
            count = len(self.files)
            copies = self.copies_spin.value()
            self.summary_label.setText(f"{count} {'bestand staat' if count == 1 else 'bestanden staan'} klaar")
            self.current_label.setText(f"{copies} {'kopie' if copies == 1 else 'kopieën'} per bestand · {self.printer_combo.currentText()}")

    def start_printing(self) -> None:
        self._start_batch(list(self.files))

    def retry_failed_files(self) -> None:
        self._start_batch([path for path in self.files if self.file_statuses.get(path, ("ready", ""))[0] == "failed"])

    def _start_batch(self, paths: list[Path]) -> None:
        if self.printing or self.worker is not None or not paths:
            return
        printer = self.printer_combo.currentText().strip()
        if not printer:
            self.show_warning_popup("Geen printer", "Selecteer eerst een printer.")
            return
        self.preferences.setValue("printer", printer)
        self._batch_files = paths
        self._batch_completed = 0
        self._batch_success = 0
        self._has_result = False
        self.log.clear()
        for path in paths:
            self.set_file_status(path, "ready")
        self.progress.setValue(0)
        self.progress.show()
        self.set_summary_tone("")
        self.summary_label.setText("Bestanden naar printer verzenden")
        self.count_label.setText(f"0 / {len(paths)}")
        self.worker = PrintWorker(paths, printer, self.current_print_settings())
        self.worker.progress_changed.connect(self.update_progress)
        self.worker.file_finished.connect(self.file_finished)
        self.worker.completed.connect(self.print_completed)
        self.worker.cancelled.connect(self.print_cancelled)
        self.worker.finished.connect(self.worker_finished)
        self.set_printing_state(True)
        self.worker.start()

    def current_print_settings(self) -> PrintSettings:
        return PrintSettings(copies=self.copies_spin.value(), orientation=PrintOrientation(self.orientation_combo.currentData()))

    def open_selected_printer_preferences(self) -> None:
        if self.printing:
            return
        printer = self.printer_combo.currentText().strip()
        if not printer:
            return
        try:
            open_printer_preferences(printer)
        except Exception as exc:
            self.show_warning_popup("Printerinstellingen", f"Printerinstellingen konden niet worden geopend:\n{exc}")

    def show_manual(self) -> None:
        self.show_info_popup(
            "Zo werkt Bulk Print",
            "1. Kies een printer, het aantal kopieën en eventueel de oriëntatie.\n"
            "   Via het instellingenknopje open je de Windows-printervoorkeuren.\n\n"
            "2. Voeg bestanden toe of sleep ze naar het venster.\n"
            "   PDF, Word, Excel, PowerPoint en afbeeldingen worden ondersteund.\n\n"
            "3. Selecteer bestanden en gebruik de pijlen om de printvolgorde aan te passen.\n"
            "   Met Ctrl of Shift selecteer je meerdere bestanden. Delete verwijdert de selectie.\n\n"
            "4. Klik op Print starten. De status verschijnt naast elk bestand.\n"
            "   Mislukte bestanden kun je apart opnieuw proberen.\n\n"
            "Stoppen rondt het huidige bestand af; al verzonden opdrachten blijven in de Windows-printerwachtrij.\n\n"
            "Oriëntatie geldt voor PDF's en afbeeldingen. Office gebruikt de documentinstellingen.\n"
            "Verzonden betekent dat de printerwachtrij de opdracht heeft ontvangen, niet dat de fysieke afdruk klaar is.\n\n"
            "Sneltoetsen: Ctrl+O toevoegen · Ctrl+P printen · Alt+↑ / Alt+↓ verplaatsen.",
        )

    def cancel_printing(self) -> None:
        if self.worker is not None:
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("Bezig met stoppen…")
            self.summary_label.setText("Stoppen na het huidige bestand")
            self.append_log("Stoppen aangevraagd. Het huidige bestand wordt nog afgerond.")

    def update_progress(self, current_file: str, completed: int, total: int) -> None:
        path = Path(current_file)
        self.current_label.setText(path.name)
        self.current_label.setToolTip(str(path))
        self.count_label.setText(f"{completed} / {total}")
        self.progress.setValue(int(completed / total * 100) if total else 0)
        if self.file_statuses.get(path, ("ready", ""))[0] == "ready":
            self.set_file_status(path, "printing")

    def file_finished(self, path: str, success: bool, message: str) -> None:
        self._batch_completed += 1
        self._batch_success += int(success)
        self.set_file_status(Path(path), "sent" if success else "failed", message)
        self.append_log(f"Verzonden: {Path(path).name}" if success else f"Mislukt: {Path(path).name} — {message}")

    def print_completed(self, failures: list[PrintFailure]) -> None:
        self.show_result(False, failures)

    def print_cancelled(self, failures: list[PrintFailure]) -> None:
        for path in self._batch_files:
            if self.file_statuses.get(path, ("ready", ""))[0] == "ready":
                self.set_file_status(path, "cancelled")
        self.show_result(True, failures)

    def worker_finished(self) -> None:
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        self.set_printing_state(False)

    def show_result(self, cancelled: bool, failures: list[PrintFailure]) -> None:
        self._has_result = True
        remaining = len(self._batch_files) - self._batch_completed
        parts = [f"{self._batch_success} verzonden"]
        if failures:
            parts.append(f"{len(failures)} mislukt")
        if remaining:
            parts.append(f"{remaining} niet verzonden")
        self.summary_label.setText(("Gestopt · " if cancelled else "") + " · ".join(parts))
        self.current_label.setText("Bekijk de foutmelding bij het bestand of in Details." if failures else "De Windows-printerwachtrij verwerkt de verzonden bestanden.")
        self.current_label.setToolTip("")
        self.count_label.setText(f"{self._batch_completed} / {len(self._batch_files)}")
        self.set_summary_tone("warning" if cancelled or failures else "success")
        if failures:
            self.details_button.setChecked(True)

    def set_summary_tone(self, tone: str) -> None:
        self.summary_label.setProperty("tone", tone)
        self.summary_label.style().unpolish(self.summary_label)
        self.summary_label.style().polish(self.summary_label)

    def set_printing_state(self, printing: bool) -> None:
        self.printing = printing
        self.cancel_button.setText("Stoppen")
        self.cancel_button.setEnabled(printing)
        self.update_controls()

    def toggle_details(self, expanded: bool) -> None:
        self.log.setVisible(expanded)
        self.details_button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

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
        self.update_controls()

    def handle_update_error(self, message: str, automatic: bool) -> None:
        if automatic:
            return
        self.show_warning_popup("Updates zoeken", f"Updatecontrole is mislukt:\n{message}")
        self.append_log(f"Updatecontrole mislukt: {message}")

    def handle_update_result(self, result: dict[str, Any], automatic: bool) -> None:
        current_version = result["current_version"]
        latest_version = result["latest_version"]
        if not result["available"]:
            if not automatic:
                self.show_info_popup(
                    "Geen update beschikbaar",
                    f"Je gebruikt al de nieuwste versie.\n\nHuidige versie: {current_version}\nNieuwste versie: {latest_version}",
                )
                self.append_log(f"Geen update beschikbaar. Huidige versie: {current_version}.")
            return

        release = result["release"]
        title = release.get("name") or f"Versie {latest_version}"
        answer = self.show_question_popup(
            "Update beschikbaar",
            f"Er is een nieuwe versie beschikbaar.\n\nHuidige versie: {current_version}\nNieuwe versie: {latest_version}\nRelease: {title}\n\nWil je deze update downloaden?",
        )
        if answer != QMessageBox.StandardButton.Yes:
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
        self.update_controls()

    def handle_update_download_error(self, message: str) -> None:
        self.show_warning_popup("Update downloaden", f"Update downloaden is mislukt:\n{message}")
        self.append_log(f"Update downloaden mislukt: {message}")

    def handle_update_downloaded(self, installer_path: object) -> None:
        path = Path(installer_path)
        self.append_log(f"Update gedownload: {path}")
        if not UpdateService.is_frozen():
            self.show_info_popup(
                "Update gedownload",
                f"De installer is gedownload naar:\n{path}\n\nAutomatisch installeren werkt alleen vanuit de geinstalleerde .exe.",
            )
            return
        self.show_info_popup(
            "Update klaar",
            "De app wordt nu gesloten. De installer werkt de app bij en start daarna opnieuw.",
        )
        UpdateService.install_update(path)

    def append_log(self, message: str) -> None:
        # Filenames and printer messages are plain text, never HTML.
        self.log.moveCursor(QTextCursor.MoveOperation.End)
        self.log.insertPlainText(message + "\n")
        self.log.ensureCursorVisible()

    def show_info_popup(self, title: str, message: str) -> QMessageBox.StandardButton:
        return self.show_popup(QMessageBox.Icon.Information, title, message)

    def show_warning_popup(self, title: str, message: str) -> QMessageBox.StandardButton:
        return self.show_popup(QMessageBox.Icon.Warning, title, message)

    def show_error_popup(self, title: str, message: str) -> QMessageBox.StandardButton:
        return self.show_popup(QMessageBox.Icon.Critical, title, message)

    def show_question_popup(self, title: str, message: str) -> QMessageBox.StandardButton:
        return self.show_popup(
            QMessageBox.Icon.Question,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

    def show_popup(
        self,
        icon: QMessageBox.Icon,
        title: str,
        message: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    ) -> QMessageBox.StandardButton:
        box = QMessageBox(self)
        box.setOption(QMessageBox.Option.DontUseNativeDialog, True)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(message)
        box.setStandardButtons(buttons)
        box.setDefaultButton(default_button)
        box.setStyleSheet(STYLESHEET)
        return QMessageBox.StandardButton(box.exec())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.apply_responsive_layout(event.size().width(), event.size().height())

    def apply_responsive_layout(self, width: int, height: int) -> None:
        compact = width < 840
        if self.compact_mode == compact:
            return
        self.compact_mode = compact
        margin = 14 if compact else 28
        self.root_layout.setContentsMargins(margin, 18 if compact else 24, margin, 12)
        self.root_layout.setSpacing(12 if compact else 18)
        self.settings_grid.removeWidget(self.options_field)
        self.settings_grid.addWidget(self.options_field, 1 if compact else 0, 0 if compact else 1)
        self.subtitle_label.setVisible(not compact)
        self.table.setColumnHidden(2, compact)
        self.add_button.setText("Toevoegen" if compact else "Bestanden toevoegen")
        self.clear_button.setText("Leegmaken" if compact else "Lijst leegmaken")
        self.retry_button.setText("Mislukte opnieuw" if compact else "Mislukte opnieuw proberen")
        for widget in (self.details_button, self.retry_button, self.start_button, self.cancel_button):
            self.actions_layout.removeWidget(widget)
        self.actions_layout.addWidget(self.details_button, 1 if compact else 0, 0, Qt.AlignmentFlag.AlignLeft)
        self.actions_layout.addWidget(self.retry_button, 0, 1)
        for widget in (self.start_button, self.cancel_button):
            self.actions_layout.addWidget(widget, 1 if compact else 0, 1 if compact else 2)
        self.file_header.removeWidget(self.queue_toolbar)
        self.file_layout.removeWidget(self.queue_toolbar)
        if compact:
            self.file_layout.insertWidget(1, self.queue_toolbar)
        else:
            self.file_header.insertWidget(self.file_header.count() - 1, self.queue_toolbar)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if not self.printing and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if self.printing:
            event.ignore()
            return
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self.add_files(paths)
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None and not self._close_requested:
            answer = self.show_question_popup("Verzenden actief", "Wil je stoppen en afsluiten nadat het huidige bestand is afgerond?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.cancel_printing()
        self._close_requested = True
        # Never destroy a QThread while a document or update is still processing.
        if any(worker is not None and worker.isRunning() for worker in (self.worker, self.update_worker, self.update_download_worker)):
            QTimer.singleShot(100, self.close)
            event.ignore()
            return
        event.accept()
