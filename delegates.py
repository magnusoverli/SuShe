# delegates.py

from PyQt6.QtWidgets import (
    QStyledItemDelegate, QComboBox, QCompleter, QDoubleSpinBox, QMessageBox, QLabel, QStyle
)
from PyQt6.QtGui import QKeyEvent, QPalette
from PyQt6.QtCore import Qt, QRectF, QPointF, QLocale
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


class CustomDoubleSpinBox(QDoubleSpinBox):
    """
    A customized QDoubleSpinBox that replaces comma with dot for decimal input.
    """
    def keyPressEvent(self, event):
        if event.text() == ',':
            # Replace comma with dot
            new_event = QKeyEvent(
                event.type(),
                Qt.Key.Key_Period,
                event.modifiers(),
                '.',
                event.isAutoRepeat(),
                event.count()
            )
            super().keyPressEvent(new_event)
        else:
            super().keyPressEvent(event)


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


class RatingDelegate(QStyledItemDelegate):
    """
    A delegate that provides a customized QDoubleSpinBox editor for rating cells.
    """
    def createEditor(self, parent, option, index):
        editor = CustomDoubleSpinBox(parent)
        editor.setFrame(False)
        editor.setDecimals(2)
        # Set locale to English (United States) to use dot as decimal separator
        editor.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        
        # Correctly locate and set the stylesheet for the editor
        style_sheet_path = os.path.join(os.path.dirname(__file__), 'style.qss')
        if os.path.exists(style_sheet_path):
            try:
                with open(style_sheet_path, "r") as file:
                    stylesheet = file.read()
                    editor.setStyleSheet(stylesheet)
            except Exception as e:
                logging.error(f"Failed to apply stylesheet to RatingDelegate editor: {e}")
        else:
            logging.warning(f"Stylesheet not found at {style_sheet_path}. Skipping stylesheet application.")

        return editor

    def setEditorData(self, editor, index):
        """
        Sets the editor's value based on the model's data.
        """
        data = index.model().data(index, Qt.ItemDataRole.EditRole)
        try:
            value = float(data.replace(",", ".")) if data else 0.0
        except ValueError:
            value = 0.0
        editor.setValue(value)

    def setModelData(self, spinBox, model, index):
        """
        Updates the model with the editor's current value after validation.
        """
        spinBox.interpretText()
        text = spinBox.text().replace(",", ".")
        try:
            value = float(text)
        except ValueError:
            QMessageBox.warning(None, "Invalid Input", "Invalid number format.")
            return

        if not 0.00 <= value <= 5.00:
            QMessageBox.warning(None, "Invalid Input", "Rating must be between 0.00 and 5.00.")
            return
        else:
            formatted_value = "{:.2f}".format(value)
            model.setData(index, formatted_value, Qt.ItemDataRole.EditRole)

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
        """
        Overrides the paint method to highlight search matches.
        """
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
            logging.error(f"Error in GenreSearchDelegate.paint: {e}")
        finally:
            painter.restore()
