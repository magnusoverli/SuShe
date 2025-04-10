# delegates.py

from PyQt6.QtWidgets import (
    QStyledItemDelegate, QComboBox, QCompleter, QLabel, QStyle
)
from PyQt6.QtGui import QPalette, QColor, QPolygon, QImage, QPixmap
from PyQt6.QtCore import Qt, QRectF, QRect, QPointF, QPoint
import logging
import re
from html import unescape
import base64


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

class CoverImageDelegate(QStyledItemDelegate):
    """
    Delegate for rendering cover images in the album table view.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def paint(self, painter, option, index):
        base64_image = index.data(Qt.ItemDataRole.UserRole)
        if base64_image:
            try:
                painter.save()
                
                # Get the cell rect
                rect = option.rect
                
                # Draw the background
                parent = self.parent()
                if parent:
                    parent.style().drawPrimitive(
                        QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, parent
                    )
                
                # Decode the base64 image
                image_bytes = base64.b64decode(base64_image)
                image = QImage.fromData(image_bytes)
                pixmap = QPixmap.fromImage(image)
                
                # Scale the pixmap to fit the cell while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    rect.size(), 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Center the pixmap in the cell
                x = rect.x() + (rect.width() - scaled_pixmap.width()) // 2
                y = rect.y() + (rect.height() - scaled_pixmap.height()) // 2
                
                # Draw the pixmap
                painter.drawPixmap(x, y, scaled_pixmap)
                
            except Exception as e:
                logging.error(f"Error in CoverImageDelegate.paint: {e}")
                painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, "Image Error")
            finally:
                painter.restore()
        else:
            # Draw "No Image" placeholder
            painter.save()
            parent = self.parent()
            if parent:
                parent.style().drawPrimitive(
                    QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, parent
                )
            painter.setPen(option.palette.color(QPalette.ColorRole.WindowText))
            painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, "No Image")
            painter.restore()

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

        # Apply consistent styling to dropdown and completer
        completer.popup().setStyleSheet("background-color: #282828; color: white; padding: 4px;")
        comboBox.setStyleSheet("background-color: #333333; color: white; padding: 4px;")

        return comboBox

    def paint(self, painter, option, index):
        try:
            painter.save()
            
            # Draw consistent background
            option.rect = option.rect.adjusted(0, 0, 0, 0)  # Ensure no adjustment to rect size
            
            # Check if cell is selected and apply proper styling
            if option.state & QStyle.StateFlag.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight())
            else:
                # Use alternating colors if the table has them enabled
                if index.row() % 2 == 0:
                    painter.fillRect(option.rect, QColor("#121212"))
                else:
                    painter.fillRect(option.rect, QColor("#1A1A1A"))
            
            # Draw text with consistent spacing
            text = index.data(Qt.ItemDataRole.DisplayRole) or ""
            text_rect = option.rect.adjusted(6, 0, -24, 0)  # Left padding of 6px, right space for dropdown indicator
            
            # Set text color based on selection state
            if option.state & QStyle.StateFlag.State_Selected:
                painter.setPen(option.palette.highlightedText().color())
            else:
                painter.setPen(option.palette.text().color())
                
            # Ensure consistent vertical centering of text
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
            
            # Draw dropdown indicator
            indicator_rect = QRect(
                option.rect.right() - 20, 
                option.rect.top() + (option.rect.height() - 8) // 2,
                12, 8
            )
            
            # Set indicator color
            painter.setPen(Qt.GlobalColor.gray)
            painter.setBrush(QColor("#666666"))
            
            # Draw triangle indicator
            points = [
                QPoint(indicator_rect.left(), indicator_rect.top()),
                QPoint(indicator_rect.left() + indicator_rect.width(), indicator_rect.top()),
                QPoint(indicator_rect.left() + indicator_rect.width() // 2, indicator_rect.bottom())
            ]
            painter.drawPolygon(QPolygon(points))
            
        except Exception as e:
            logging.error(f"Error in ComboBoxDelegate.paint: {e}")
            super().paint(painter, option, index)
        finally:
            painter.restore()

    def setEditorData(self, editor, index):
        """Sets the editor's current value based on the model's data."""
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if value:
            idx = editor.findText(value, Qt.MatchFlag.MatchFixedString)
            editor.setCurrentIndex(idx if idx >= 0 else -1)
        else:
            editor.setCurrentIndex(-1)  # No selection if no value

    def setModelData(self, editor, model, index):
        """Updates the model with the editor's current value."""
        new_value = editor.currentText().strip()
        
        # Don't set empty values - keep the placeholder
        if not new_value:
            return
            
        # Only update if the value actually changed
        current_value = model.data(index, Qt.ItemDataRole.EditRole)
        if new_value != current_value:
            model.setData(index, new_value, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        """Sets the editor's geometry to match cell dimensions."""
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

            # First check if this cell has a widget
            widget = parent.indexWidget(index)
            if widget:
                # If there's a widget, don't draw any text - let the widget handle it
                return  # No explicit restore here - the finally block will handle it

            # Get the cell text
            data = index.data(Qt.ItemDataRole.DisplayRole)
            if not data:
                # For backward compatibility, try the old method
                widget = parent.cellWidget(index.row(), index.column())
                if isinstance(widget, QLabel):
                    data = strip_html_tags(widget.text())

            if data:
                data_lower = str(data).lower()
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
                            segments.append((str(data)[start:], False))
                            break
                        if idx > start:
                            segments.append((str(data)[start:idx], False))
                        segments.append((str(data)[idx:idx+len(self.search_text)], True))
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
                    # No matches, draw text directly without calling super()
                    text_rect = option.rect.adjusted(5, 0, -5, 0)
                    painter.setPen(option.palette.color(QPalette.ColorRole.WindowText))
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, str(data))
            else:
                # No data, but don't call super().paint() to avoid double drawing
                # Just leave the background as is
                pass
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

        return comboBox

    def setEditorData(self, editor, index):
        """
        Sets the editor's current value based on the model's data.
        """
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        if not value:
            return
            
        idx = editor.findText(value, Qt.MatchFlag.MatchFixedString)
        editor.setCurrentIndex(idx if idx >= 0 else -1)

    def setModelData(self, editor, model, index):
        """
        Updates the model with the editor's current value.
        """
        new_value = editor.currentText().strip()
        
        # Don't set empty values - keep the placeholder
        if not new_value:
            return
            
        # Only update if the value actually changed
        current_value = model.data(index, Qt.ItemDataRole.EditRole)
        if new_value != current_value:
            model.setData(index, new_value, Qt.ItemDataRole.EditRole)

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
                data = ""

            data_str = str(data)
            data_lower = data_str.lower()
            
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
                        segments.append((data_str[start:], False))
                        break
                    if idx > start:
                        segments.append((data_str[start:idx], False))
                    segments.append((data_str[idx:idx+len(self.search_text)], True))
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
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, data_str)
                
            # Draw dropdown indicator
            indicator_rect = QRect(
                option.rect.right() - 16, 
                option.rect.top() + (option.rect.height() - 8) // 2,
                8, 8
            )
            painter.setPen(Qt.GlobalColor.white)
            painter.setBrush(QColor("#666666"))
            
            # Draw a simple rectangle instead of a polygon
            painter.drawRect(indicator_rect)
            
        except Exception as e:
            logging.error(f"Error in GenreSearchDelegate.paint: {e}")
        finally:
            painter.restore()