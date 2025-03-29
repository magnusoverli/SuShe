# delegates.py

from PyQt6.QtWidgets import (
    QStyledItemDelegate, QComboBox, QCompleter, QDoubleSpinBox, QMessageBox, QLabel, QStyle
)
from PyQt6.QtGui import QKeyEvent, QPalette, QColor, QPolygon
from PyQt6.QtCore import Qt, QRectF, QRect, QPointF, QPointF
import logging
import re
from html import unescape
import os


def strip_html_tags(text):
    """
    Removes HTML tags from the given text and unescapes HTML entities.
    
    Args:
        text (str): The text containing HTML tags.
    
    Returns:
        str: The cleaned text without HTML tags.
    """
    clean = re.compile('<.*?>')
    return unescape(re.sub(clean, '', text))


class ComboBoxDelegate(QStyledItemDelegate):
    """
    A delegate that provides a QComboBox editor for table cells.
    """
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items

    def createEditor(self, parent, option, index):
        comboBox = QComboBox(parent)
        comboBox.setEditable(True)
        comboBox.addItems(self.items)
        comboBox.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        # Create the completer and set it to be case insensitive
        completer = QCompleter(self.items, comboBox)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comboBox.setCompleter(completer)

        # Apply the dark background style to the completer popup
        completer.popup().setStyleSheet("background-color: #2D2D30; color: white;")
        comboBox.setStyleSheet("background-color: #2D2D30; color: white;")

        # Connect the 'currentIndexChanged' signal to commit data and close editor
        comboBox.currentIndexChanged.connect(self.commitAndClose)

        return comboBox

    def paint(self, painter, option, index):
        try:
            painter.save()
            
            parent = self.parent()
            if parent is None:
                super().paint(painter, option, index)
                return
                
            # Draw background
            parent.style().drawPrimitive(
                QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, parent
            )
            
            # Draw text with space for indicator
            text = index.data(Qt.ItemDataRole.DisplayRole) or ""
            text_rect = option.rect.adjusted(5, 0, -20, 0)
            painter.setPen(option.palette.color(QPalette.ColorRole.WindowText))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)
            
            # Draw dropdown indicator
            indicator_rect = QRect(
                option.rect.right() - 16, 
                option.rect.top() + (option.rect.height() - 8) // 2,
                8, 8
            )
            painter.setPen(Qt.GlobalColor.white)
            painter.setBrush(QColor("#666666"))
            points = [
                QPoint(indicator_rect.left(), indicator_rect.top()),
                QPoint(indicator_rect.right(), indicator_rect.top()),
                QPoint(indicator_rect.left() + indicator_rect.width() // 2, indicator_rect.bottom())
            ]
            painter.drawPolygon(QPolygon(points))
        except Exception as e:
            logging.error(f"Error in ComboBoxDelegate.paint: {e}")
        finally:
            painter.restore()

    def commitAndClose(self):
        """
        Commits the data from the editor to the model and closes the editor.
        """
        editor = self.sender()  # Get the editor that sent the signal
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)

    def setEditorData(self, editor, index):
        """
        Sets the editor's current value based on the model's data.
        """
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        idx = editor.findText(value, Qt.MatchFlag.MatchFixedString)
        editor.setCurrentIndex(idx if idx >= 0 else -1)

    def setModelData(self, editor, model, index):
        """
        Updates the model with the editor's current value.
        """
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        """
        Sets the editor's geometry.
        """
        editor.setGeometry(option.rect)


class SearchHighlightDelegate(QStyledItemDelegate):
    """
    A delegate that highlights search matches within table cells.
    """
    def __init__(self, parent=None, highlight_color=Qt.GlobalColor.darkYellow):
        super().__init__(parent)
        self.search_text = ""
        self.highlight_color = highlight_color

    def set_search_text(self, text):
        """
        Updates the search text and triggers a repaint.
        """
        self.search_text = text.lower()
        self.parent().viewport().update()

    def paint(self, painter, option, index):
        try:
            painter.save()

            parent = self.parent()
            if parent is None:
                logging.error("Delegate parent is None")
                super().paint(painter, option, index)
                return

            # Draw the background
            parent.style().drawPrimitive(
                QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, parent
            )

            # Get the cell text
            data = index.data(Qt.ItemDataRole.DisplayRole)
            if not data:
                # Handle QLabel cells (e.g., album names with hyperlinks)
                widget = parent.cellWidget(index.row(), index.column())
                if isinstance(widget, QLabel):
                    data = strip_html_tags(widget.text())

            if data:
                data_lower = data.lower()
                if self.search_text and self.search_text in data_lower:
                    # Prepare to draw the text with highlighted matches
                    painter.setClipRect(option.rect)
                    text_rect = option.rect.adjusted(5, 0, -5, 0)

                    # Set up font metrics
                    fm = painter.fontMetrics()
                    text_height = fm.height()
                    x = text_rect.left()
                    y = text_rect.top() + (text_rect.height() - text_height) / 2

                    # Split the text into segments
                    segments = []
                    start = 0
                    while True:
                        idx = data_lower.find(self.search_text, start)
                        if idx == -1:
                            segments.append((data[start:], False))
                            break
                        if idx > start:
                            segments.append((data[start:idx], False))
                        segments.append((data[idx:idx+len(self.search_text)], True))
                        start = idx + len(self.search_text)

                    # Draw each segment
                    for segment, is_match in segments:
                        segment_width = fm.horizontalAdvance(segment)
                        segment_rect = QRectF(x, y, segment_width, text_height)
                        if is_match:
                            painter.fillRect(segment_rect, self.highlight_color)
                        painter.setPen(option.palette.color(QPalette.ColorRole.WindowText))
                        painter.drawText(QPointF(x, y + fm.ascent()), segment)
                        x += segment_width
                else:
                    # No matches, draw text normally
                    super().paint(painter, option, index)
            else:
                # No data, draw normally
                super().paint(painter, option, index)
        except Exception as e:
            logging.error(f"Error in SearchHighlightDelegate.paint: {e}")
        finally:
            painter.restore()

class GenreSearchDelegate(QStyledItemDelegate):
    """
    A delegate specifically for genre columns that highlights search matches.
    """
    def __init__(self, items, parent=None, highlight_color=Qt.GlobalColor.darkYellow):
        super().__init__(parent)
        self.items = items
        self.search_text = ""
        self.highlight_color = highlight_color

    def set_search_text(self, text):
        """
        Updates the search text and triggers a repaint.
        """
        self.search_text = text.lower()
        self.parent().viewport().update()

    def createEditor(self, parent, option, index):
        """
        Creates a QComboBox editor with autocomplete for genre selection.
        """
        comboBox = QComboBox(parent)
        comboBox.setEditable(True)
        comboBox.addItems(self.items)
        comboBox.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        # Create the completer and set it to be case insensitive
        completer = QCompleter(self.items, comboBox)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comboBox.setCompleter(completer)

        # Apply the dark background style to the completer popup
        completer.popup().setStyleSheet("background-color: #2D2D30; color: white;")
        comboBox.setStyleSheet("background-color: #2D2D30; color: white;")

        # Connect the 'currentIndexChanged' signal to commit data and close editor
        comboBox.currentIndexChanged.connect(self.commitAndClose)

        return comboBox

    def commitAndClose(self):
        """
        Commits the data from the editor to the model and closes the editor.
        """
        editor = self.sender()  # Get the editor that sent the signal
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)

    def setEditorData(self, editor, index):
        """
        Sets the editor's current value based on the model's data.
        """
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        idx = editor.findText(value, Qt.MatchFlag.MatchFixedString)
        editor.setCurrentIndex(idx if idx >= 0 else -1)

    def setModelData(self, editor, model, index):
        """
        Updates the model with the editor's current value.
        """
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        """
        Sets the editor's geometry.
        """
        editor.setGeometry(option.rect)

    def paint(self, painter, option, index):
        try:
            painter.save()

            parent = self.parent()
            if parent is None:
                logging.error("Delegate parent is None")
                super().paint(painter, option, index)
                return

            # Draw the background
            parent.style().drawPrimitive(
                QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, parent
            )

            # Get the cell text
            data = index.data(Qt.ItemDataRole.DisplayRole)
            if not data:
                # Handle QLabel cells (e.g., album names with hyperlinks)
                widget = parent.cellWidget(index.row(), index.column())
                if isinstance(widget, QLabel):
                    data = strip_html_tags(widget.text())

            if data:
                data_lower = data.lower()
                if self.search_text and self.search_text in data_lower:
                    # Prepare to draw the text with highlighted matches
                    painter.setClipRect(option.rect)
                    text_rect = option.rect.adjusted(5, 0, -20, 0)  # Leave space for dropdown indicator

                    # Set up font metrics
                    fm = painter.fontMetrics()
                    text_height = fm.height()
                    x = text_rect.left()
                    y = text_rect.top() + (text_rect.height() - text_height) / 2

                    # Split the text into segments
                    segments = []
                    start = 0
                    while True:
                        idx = data_lower.find(self.search_text, start)
                        if idx == -1:
                            segments.append((data[start:], False))
                            break
                        if idx > start:
                            segments.append((data[start:idx], False))
                        segments.append((data[idx:idx+len(self.search_text)], True))
                        start = idx + len(self.search_text)

                    # Draw each segment
                    for segment, is_match in segments:
                        segment_width = fm.horizontalAdvance(segment)
                        segment_rect = QRectF(x, y, segment_width, text_height)
                        if is_match:
                            painter.fillRect(segment_rect, self.highlight_color)
                        painter.setPen(option.palette.color(QPalette.ColorRole.WindowText))
                        painter.drawText(QPointF(x, y + fm.ascent()), segment)
                        x += segment_width
                else:
                    # No matches, draw text normally
                    text_rect = option.rect.adjusted(5, 0, -20, 0)
                    painter.setPen(option.palette.color(QPalette.ColorRole.WindowText))
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, data)
            else:
                # No data, draw nothing
                pass
                
            # Draw dropdown indicator
            indicator_rect = QRect(
                option.rect.right() - 16, 
                option.rect.top() + (option.rect.height() - 8) // 2,
                8, 8
            )
            painter.setPen(Qt.GlobalColor.white)
            painter.setBrush(QColor("#666666"))
            points = [
                QPoint(indicator_rect.left(), indicator_rect.top()),
                QPoint(indicator_rect.right(), indicator_rect.top()),
                QPoint(indicator_rect.left() + indicator_rect.width() // 2, indicator_rect.bottom())
            ]
            painter.drawPolygon(QPolygon(points))
            
        except Exception as e:
            logging.error(f"Error in GenreSearchDelegate.paint: {e}")
        finally:
            painter.restore()