from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from bulk_print.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Bulk Print")
    app.setOrganizationName("Bulk Print")
    window = MainWindow()
    window.resize(980, 680)
    window.show()
    return app.exec()
