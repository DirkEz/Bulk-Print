"""Shared, deliberately small visual language for the desktop interface."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap


def icon(name: str, color: str = "#526477") -> QIcon:
    paths = {
        "add": '<path d="M12 5v14M5 12h14"/>',
        "up": '<path d="m6 14 6-6 6 6"/>',
        "down": '<path d="m6 10 6 6 6-6"/>',
        "refresh": '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 6M4 12l2 6a7 7 0 0 0 12-1"/>',
        "settings": '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="white"/><circle cx="15" cy="17" r="3" fill="white"/>',
        "remove": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5M14 11v5"/>',
        "print": '<path d="M7 8V3h10v5M7 17H4V9h16v8h-3M7 14h10v7H7zM16 11h1"/>',
        "files": '<path d="M8 3h8l4 4v14H8zM16 3v5h4M4 7v14M11 12h6M11 16h6"/>',
    }
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" '
        f'stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>'
    )
    pixmap = QPixmap()
    pixmap.loadFromData(svg.encode(), "SVG")
    return QIcon(pixmap)


STYLESHEET = """
QWidget { font-family: "Segoe UI", "Helvetica Neue", sans-serif; font-size: 10pt; color: #203247; }
QWidget#AppRoot, QScrollArea#MainScroll { background: #f3f5f7; border: 0; }
QLabel { background: transparent; }
QLabel#Title { font-size: 25pt; font-weight: 700; color: #172b40; }
QLabel#Subtitle, QLabel#Hint, QLabel#VersionLabel { color: #69798a; }
QLabel#Brand { color: #526477; font-size: 9pt; font-weight: 600; }
QLabel#AppMark { background: #157d73; border-radius: 14px; }
QLabel#FieldLabel { color: #526477; font-size: 9pt; font-weight: 600; }
QLabel#SectionTitle { font-size: 13pt; font-weight: 600; color: #172b40; }
QLabel#FileCount { background: #edf2f5; color: #526477; border-radius: 10px; padding: 3px 9px; font-size: 9pt; }
QLabel#StatusTitle { font-size: 11pt; font-weight: 600; }
QLabel#StatusTitle[tone="success"] { color: #117466; }
QLabel#StatusTitle[tone="warning"] { color: #a14d24; }
QLabel#EmptyTitle { font-size: 16pt; font-weight: 600; color: #334a60; }
QLabel#EmptyIcon { background: #e8f2f0; border-radius: 18px; }
QFrame#Panel { background: #ffffff; border: 1px solid #dfe5eb; border-radius: 14px; }
QFrame#EmptyState { background: #fafcfc; border: 1px dashed #c9d9d7; border-radius: 10px; }
QComboBox, QSpinBox {
    background: #ffffff; border: 1px solid #ccd6df; border-radius: 7px;
    padding: 6px 10px; min-height: 24px; selection-background-color: #dcefeb;
    selection-color: #203247;
}
QComboBox { padding-right: 24px; }
QComboBox::drop-down { border: 0; width: 24px; }
QComboBox::down-arrow, QSpinBox::down-arrow { image: url("@ASSETS@/chevron-down.svg"); width: 12px; height: 8px; }
QSpinBox::up-arrow { image: url("@ASSETS@/chevron-up.svg"); width: 12px; height: 8px; }
QSpinBox::up-button, QSpinBox::down-button { border: 0; width: 20px; background: transparent; }
QComboBox:hover, QSpinBox:hover { border-color: #8ca79f; }
QComboBox:focus, QSpinBox:focus { border: 1px solid #157d73; }
QComboBox:disabled, QSpinBox:disabled { color: #8996a2; background: #f5f7f8; }
QComboBox QAbstractItemView { background: white; color: #203247; selection-background-color: #dcefeb; selection-color: #203247; }
QPushButton, QToolButton {
    background: #ffffff; color: #344a5f; border: 1px solid #ccd6df;
    border-radius: 7px; padding: 8px 13px; font-weight: 600;
}
QToolButton { padding: 8px; }
QPushButton:hover, QToolButton:hover { background: #f0f5f5; border-color: #9ab4ad; }
QPushButton:pressed, QToolButton:pressed { background: #dcefeb; }
QPushButton:focus, QToolButton:focus { border-color: #157d73; }
QPushButton#PrimaryButton { background: #157d73; border-color: #157d73; color: white; padding: 10px 22px; }
QPushButton#PrimaryButton:hover { background: #10685f; border-color: #10685f; }
QPushButton#PrimaryButton:pressed { background: #0a564e; }
QPushButton#SecondaryButton { background: #edf6f3; color: #116b60; border-color: #c6ded7; }
QPushButton#SecondaryButton:hover { background: #deeee8; border-color: #9bc4b7; }
QPushButton#QuietButton, QToolButton#QuietButton { background: transparent; border-color: transparent; color: #627487; }
QPushButton#QuietButton:hover, QToolButton#QuietButton:hover { background: #edf2f5; color: #203247; }
QPushButton#FooterButton { background: transparent; border-color: transparent; color: #69798a; font-size: 9pt; padding: 4px 8px; }
QPushButton#FooterButton:hover { background: #e6ecef; color: #203247; }
QPushButton#DangerButton { color: #ad433d; background: #fff7f6; border-color: #edcfcb; }
QPushButton:disabled, QPushButton#PrimaryButton:disabled, QPushButton#SecondaryButton:disabled,
QPushButton#QuietButton:disabled, QToolButton:disabled {
    background: #f0f3f5; color: #96a2ae; border-color: #e4e9ed;
}
QTableWidget { background: #ffffff; border: 0; selection-background-color: #e5f2ef; selection-color: #203247; outline: 0; }
QTableWidget::item { padding: 8px; border-bottom: 1px solid #edf1f4; }
QTableWidget::item:selected { background: #e5f2ef; }
QHeaderView::section {
    background: #f7f9fa; color: #748292; border: 0; border-bottom: 1px solid #e6ebef;
    padding: 9px 8px; font-size: 9pt; font-weight: 600;
}
QTextEdit { background: #f7f9fa; border: 1px solid #e2e8ed; border-radius: 7px; padding: 8px; color: #526477; font-size: 9pt; }
QProgressBar { background: #e8eeef; border: 0; border-radius: 3px; min-height: 6px; max-height: 6px; }
QProgressBar::chunk { background: #157d73; border-radius: 3px; }
QScrollBar:vertical { background: #f5f7f8; width: 12px; margin: 0; border: 0; }
QScrollBar::handle:vertical { background: #c4ced7; min-height: 28px; border-radius: 6px; }
QScrollBar::handle:vertical:hover { background: #9babb9; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background: #203247; color: white; border: 0; padding: 6px; }
QMessageBox { background: #f3f5f7; }
""".replace("@ASSETS@", (Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / "assets").as_posix())
