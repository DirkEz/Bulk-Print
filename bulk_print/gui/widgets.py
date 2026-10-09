from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem


class FileNameDelegate(QStyledItemDelegate):
    """Keep the filename readable, with its folder on a quieter second line."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        styled.text = ""
        option.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, option.widget)
        painter.save()
        rect = option.rect.adjusted(10, 8, -10, -8)
        font = option.font
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#203247"))
        metrics = QFontMetrics(font)
        painter.drawText(rect.left(), rect.top() + metrics.ascent(), metrics.elidedText(index.data(), Qt.TextElideMode.ElideMiddle, rect.width()))
        font.setBold(False)
        font.setPointSizeF(max(8, font.pointSizeF() - 1))
        painter.setFont(font)
        painter.setPen(QColor("#748292"))
        metrics = QFontMetrics(font)
        folder = index.data(Qt.ItemDataRole.UserRole) or ""
        painter.drawText(rect.left(), rect.bottom() - metrics.descent(), metrics.elidedText(folder, Qt.TextElideMode.ElideMiddle, rect.width()))
        painter.restore()
