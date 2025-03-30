# album_model.py

from PyQt6.QtCore import (Qt, QAbstractTableModel, QModelIndex, QVariant, 
                          QMimeData, QByteArray, QDataStream, QIODevice, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, QAbstractAnimation
)
import logging

class AlbumModel(QAbstractTableModel):
    """
    Custom model for the album list that supports drag and drop reordering.
    """
    
    # Column definitions
    ARTIST = 0
    ALBUM = 1
    RELEASE_DATE = 2
    COVER_IMAGE = 3
    COUNTRY = 4
    GENRE_1 = 5
    GENRE_2 = 6
    COMMENTS = 7
    
    COLUMN_NAMES = [
        "Artist", "Album", "Release Date", "Cover Image",
        "Country", "Genre 1", "Genre 2", "Comments"
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Initialize with empty album data
        self.album_data = []
        # Flag to track if data has been changed (similar to main window's dataChanged)
        self.is_modified = False

    def rowCount(self, parent=QModelIndex()):
        return len(self.album_data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMN_NAMES)
    
    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self.COLUMN_NAMES[section]
        return QVariant()
    
    def data(self, index, role):
        if not index.isValid():
            return QVariant()
        
        if index.row() >= len(self.album_data) or index.row() < 0:
            return QVariant()
        
        row = index.row()
        column = index.column()
        
        # Return appropriate data based on role and column
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if column == self.COVER_IMAGE:
                # Cover image is handled separately by the view
                return QVariant()
            else:
                # Return text data for all other columns
                return self.album_data[row].get(self.get_column_key(column), "")
        
        elif role == Qt.ItemDataRole.UserRole:
            # Store additional data like album_id
            if column == self.ALBUM:
                return self.album_data[row].get("album_id", "")
            elif column == self.COVER_IMAGE:
                return self.album_data[row].get("cover_image", None)
        
        return QVariant()
    
    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        
        row = index.row()
        column = index.column()
        
        if role == Qt.ItemDataRole.EditRole:
            if column != self.COVER_IMAGE:  # Cover image is handled separately
                self.album_data[row][self.get_column_key(column)] = value
                self.is_modified = True
                self.dataChanged.emit(index, index, [role])
                return True
        
        return False
    
    def flags(self, index):
        default_flags = super().flags(index)
        
        if not index.isValid():
            return default_flags | Qt.ItemFlag.ItemIsDropEnabled
        
        # Make items draggable and droppable
        flags = default_flags | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
        
        # Only make certain columns editable
        column = index.column()
        non_editable_columns = [self.ARTIST, self.ALBUM, self.RELEASE_DATE, self.COVER_IMAGE]
        
        if column not in non_editable_columns:
            flags |= Qt.ItemFlag.ItemIsEditable
        
        return flags
    
    def supportedDropActions(self):
        return Qt.DropAction.MoveAction
    
    def mimeTypes(self):
        return ["application/x-sushe-albumrow"]
    
    def mimeData(self, indexes):
        mime_data = QMimeData()
        encoded_data = QByteArray()
        stream = QDataStream(encoded_data, QIODevice.OpenModeFlag.WriteOnly)
        
        # Get the rows to be moved (only store each row once)
        rows = set()
        for index in indexes:
            if index.isValid():
                rows.add(index.row())
        
        # Store the row numbers
        stream.writeInt(len(rows))
        for row in rows:
            stream.writeInt(row)
        
        mime_data.setData("application/x-sushe-albumrow", encoded_data)
        return mime_data
    
    def canDropMimeData(self, data, action, row, column, parent):
        if not data.hasFormat("application/x-sushe-albumrow"):
            return False
        
        if action == Qt.DropAction.IgnoreAction:
            return True
        
        return True
    
    def dropMimeData(self, data, action, row, column, parent):
        if not self.canDropMimeData(data, action, row, column, parent):
            return False
        
        if action == Qt.DropAction.IgnoreAction:
            return True
        
        # Get the drop row
        drop_row = row
        if drop_row == -1 and parent.isValid():
            drop_row = parent.row()
        elif drop_row == -1:
            drop_row = self.rowCount()
        
        encoded_data = data.data("application/x-sushe-albumrow")
        stream = QDataStream(encoded_data, QIODevice.OpenModeFlag.ReadOnly)
        
        # Get number of rows being moved
        rows_count = stream.readInt()
        source_rows = []
        for _ in range(rows_count):
            source_rows.append(stream.readInt())
        
        source_rows.sort()  # Sort the rows
        
        # For better UX, don't adjust drop position when dragging down
        # This makes the behavior match what users expect from the indicator
        moved_data = []
        
        # Remove source rows from model (in reverse order to maintain indices)
        for row in reversed(source_rows):
            if row < len(self.album_data):
                moved_data.insert(0, self.album_data.pop(row))
                
                # When removing rows above the drop position, we need to adjust
                # the drop position to account for the removed rows
                if row < drop_row:
                    drop_row -= 1
        
        # Insert moved data at the drop position
        for i, item in enumerate(moved_data):
            self.album_data.insert(drop_row + i, item)
        
        # Mark data as changed
        self.is_modified = True
        
        # Refresh the view
        self.layoutChanged.emit()
        
        return True
    
    def sort(self, column, order):
        """Sort album data by the specified column."""
        self.beginResetModel()
        
        key = self.get_column_key(column)
        reverse = (order == Qt.SortOrder.DescendingOrder)
        
        # Don't sort by cover image column
        if column != self.COVER_IMAGE:
            self.album_data.sort(key=lambda x: str(x.get(key, "")), reverse=reverse)
        
        self.endResetModel()
    
    def get_column_key(self, column):
        """Convert column index to album data dictionary key."""
        mapping = {
            self.ARTIST: "artist",
            self.ALBUM: "album",
            self.RELEASE_DATE: "release_date",
            self.COVER_IMAGE: "cover_image",
            self.COUNTRY: "country",
            self.GENRE_1: "genre_1",
            self.GENRE_2: "genre_2",
            self.COMMENTS: "comments"
        }
        return mapping.get(column, "")

    def clear(self):
        """Clear all album data."""
        self.beginResetModel()
        self.album_data = []
        self.endResetModel()
        self.is_modified = False
        return True

    def set_album_data(self, data):
        """Set the album data from a list of dictionaries."""
        was_modified = self.is_modified  # Save current modified state
        self.beginResetModel()
        self.album_data = data
        self.endResetModel()
        self.is_modified = was_modified
    
    def get_album_data(self):
        """Get the album data as a list of dictionaries."""
        # Update ranks and points based on current order
        for index, album in enumerate(self.album_data):
            album["rank"] = index + 1
        
        return self.album_data
    
    def add_album(self, album_data):
        """Add a new album to the model."""
        self.beginInsertRows(QModelIndex(), len(self.album_data), len(self.album_data))
        self.album_data.append(album_data)
        self.endInsertRows()
        self.is_modified = True
        return True
    
    def remove_album(self, row):
        """Remove an album from the model."""
        if 0 <= row < len(self.album_data):
            self.beginRemoveRows(QModelIndex(), row, row)
            del self.album_data[row]
            self.endRemoveRows()
            self.is_modified = True
            return True
        return False
    
    def clear(self):
        """Clear all album data."""
        self.beginResetModel()
        self.album_data = []
        self.endResetModel()
        self.is_modified = False
        return True