from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from bulk_print.gui.main_window import MainWindow
from bulk_print import settings


def resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    return base_path / relative_path


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(getattr(settings, "APP_NAME", "Bulk Print"))
    app.setOrganizationName(getattr(settings, "APP_COMPANY", "Deyvo"))
    icon_path = resource_path("assets/deyvo-logo.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.resize(980, 680)
    window.show()
    return app.exec()
