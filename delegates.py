# delegates.py

from PyQt6.QtWidgets import (
    QComboBox, QStyledItemDelegate, QCompleter, QDoubleSpinBox, QMessageBox, QStyle, QLabel
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QLocale
from PyQt6.QtGui import QKeyEvent, QPalette
from functools import partial
from utils import resource_path, strip_html_tags
import logging


class CustomDoubleSpinBox(QDoubleSpinBox):
    """
    Custom DoubleSpinBox that replaces comma with dot as decimal separator.
    This ensures consistent decimal input regardless of keyboard locale.
    """
    def keyPressEvent(self, event: QKeyEvent):
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
    Delegate for QTableWidget to provide a QComboBox editor with autocomplete.
    Useful for columns like 'Country' or any categorical data.
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
        comboBox.currentIndexChanged.connect(partial(self.commitAndClose, comboBox))

        # Initialize the current text
        current_value = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        if current_value in self.items:
            comboBox.setCurrentIndex(self.items.index(current_value))
        else:
            comboBox.setCurrentIndex(-1)

        return comboBox

    def commitAndClose(self, editor):
        """
        Commit the data from the editor to the model and close the editor.
        """
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)

    def setEditorData(self, editor, index):
        """
        Populate the editor with the current data from the model.
        """
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        idx = editor.findText(value, Qt.MatchFlag.MatchFixedString)
        editor.setCurrentIndex(idx if idx >= 0 else -1)

    def setModelData(self, editor, model, index):
        """
        Update the model with the data from the editor.
        """
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        """
        Set the geometry of the editor to match the cell.
        """
        editor.setGeometry(option.rect)


class SearchHighlightDelegate(QStyledItemDelegate):
    """
    Delegate to highlight search matches in the table view.
    Useful for enhancing user experience during search operations.
    """
    def __init__(self, parent=None, highlight_color=Qt.GlobalColor.darkYellow):
        super().__init__(parent)
        self.search_text = ""
        self.highlight_color = highlight_color

    def set_search_text(self, text):
        """
        Update the text to search for and trigger a repaint.
        """
        self.search_text = text.lower()
        self.parent().viewport().update()

    def paint(self, painter, option, index):
        try:
            painter.save()

            parent = self.parent()
            if parent is None:
                # If parent is None, fallback to default painting
                super().paint(painter, option, index)
                return

            # Draw the background
            option.widget.style().drawPrimitive(
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
    Delegate for genre columns with autocomplete and search highlighting.
    Extends QStyledItemDelegate to provide specialized behavior for genre fields.
    """
    def __init__(self, items, parent=None, highlight_color=Qt.GlobalColor.cyan):
        super().__init__(parent)
        self.items = items
        self.search_text = ""
        self.highlight_color = highlight_color

    def set_search_text(self, text):
        """
        Update the text to search for and trigger a repaint.
        """
        self.search_text = text.lower()
        self.parent().viewport().update()

    def createEditor(self, parent, option, index):
        """
        Create a QComboBox editor with autocomplete for genre selection.
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
        comboBox.currentIndexChanged.connect(partial(self.commitAndClose, comboBox))

        # Initialize the current text
        current_value = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        if current_value in self.items:
            comboBox.setCurrentIndex(self.items.index(current_value))
        else:
            comboBox.setCurrentIndex(-1)

        return comboBox

    def commitAndClose(self, editor):
        """
        Commit the data from the editor to the model and close the editor.
        """
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)

    def setEditorData(self, editor, index):
        """
        Populate the editor with the current data from the model.
        """
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        idx = editor.findText(value, Qt.MatchFlag.MatchFixedString)
        editor.setCurrentIndex(idx if idx >= 0 else -1)

    def setModelData(self, editor, model, index):
        """
        Update the model with the data from the editor.
        """
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        """
        Set the geometry of the editor to match the cell.
        """
        editor.setGeometry(option.rect)

    def paint(self, painter, option, index):
        """
        Paint the cell, highlighting search matches if present.
        """
        painter.save()

        try:
            # Draw the background
            option.widget.style().drawPrimitive(
                QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget
            )

            data = index.data(Qt.ItemDataRole.DisplayRole)
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


class RatingDelegate(QStyledItemDelegate):
    """
    Delegate for the 'Rating' column to provide a QDoubleSpinBox editor with validation.
    Ensures ratings are between 0.00 and 5.00 with two decimal places.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        """
        Create a CustomDoubleSpinBox editor for entering ratings.
        """
        editor = CustomDoubleSpinBox(parent)
        editor.setFrame(False)
        editor.setDecimals(2)
        # Set locale to English (United States) to use dot as decimal separator
        editor.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        
        # Correctly locate and set the stylesheet for the editor
        style_sheet_path = resource_path('style.qss')
        try:
            with open(style_sheet_path, "r") as file:
                stylesheet = file.read()
                editor.setStyleSheet(stylesheet)
        except Exception as e:
            logging.error(f"Failed to apply stylesheet to RatingDelegate editor: {e}")
        
        return editor

    def setEditorData(self, editor, index):
        """
        Populate the editor with the current rating from the model.
        """
        data = index.model().data(index, Qt.ItemDataRole.EditRole)
        try:
            value = float(data.replace(",", ".")) if data else 0.0
        except ValueError:
            value = 0.0
        editor.setValue(value)

    def setModelData(self, spinBox, model, index):
        """
        Update the model with the new rating from the editor.
        Validates the rating to be within 0.00 and 5.00.
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
        Set the geometry of the editor to match the cell.
        """
        editor.setGeometry(option.rect)
