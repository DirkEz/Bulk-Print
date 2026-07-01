from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from bulk_print.files.validation import validate_file
from bulk_print.printing.backends import PrintError, print_file
from bulk_print.printing.settings import PrintSettings


@dataclass(frozen=True)
class PrintFailure:
    path: Path
    message: str


class PrintWorker(QThread):
    progress_changed = Signal(str, int, int)
    file_finished = Signal(str, bool, str)
    completed = Signal(list)
    cancelled = Signal(list)

    def __init__(self, files: list[Path], printer_name: str, settings: PrintSettings) -> None:
        super().__init__()
        self.files = files
        self.printer_name = printer_name
        self.settings = settings
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        failures: list[PrintFailure] = []
        total = len(self.files)
        completed_count = 0
        for path in self.files:
            if self._cancel_requested:
                self.cancelled.emit(failures)
                return
            self.progress_changed.emit(str(path), completed_count, total)
            validation = validate_file(path)
            if not validation.valid:
                message = validation.error or "Bestand is ongeldig"
                failures.append(PrintFailure(path, message))
                self.file_finished.emit(str(path), False, message)
                completed_count += 1
                continue
            try:
                print_file(validation.path, self.printer_name, self.settings)
                self.file_finished.emit(str(path), True, "")
            except PrintError as exc:
                failures.append(PrintFailure(path, str(exc)))
                self.file_finished.emit(str(path), False, str(exc))
            except Exception as exc:
                failures.append(PrintFailure(path, f"Onverwachte fout: {exc}"))
                self.file_finished.emit(str(path), False, f"Onverwachte fout: {exc}")
            completed_count += 1
            self.progress_changed.emit(str(path), completed_count, total)
        self.completed.emit(failures)
