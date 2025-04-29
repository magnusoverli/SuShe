# main.py

from PyQt6.QtWidgets import (QDialog, QMenu, QGroupBox, QFileDialog, QComboBox, QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QListWidget, QMessageBox,
                             QProgressDialog, QAbstractItemView, QHeaderView, QTableView, QStyle, QProxyStyle)
from PyQt6.QtGui import QAction, QIcon, QPixmap, QDragEnterEvent, QDropEvent, QFont, QDesktopServices, QPen, QColor, QPainter, QDrag, QCursor
from PyQt6.QtCore import (Qt, QFile, QTextStream, QIODevice, pyqtSignal, QThread, QTimer, QObject, QUrl, QItemSelectionModel, QPoint, QParallelAnimationGroup, QAbstractAnimation, QPropertyAnimation, QEasingCurve)
from datetime import datetime
from pathlib import Path
from PIL import Image
from io import BytesIO
import requests
import logging
import hashlib
import shutil
import base64
from functools import partial
import os
import json
import sys
import urllib.parse
import subprocess
import time

from album_model import AlbumModel

from dialogs import HelpDialog, LogViewerDialog, ManualAddAlbumDialog, SubmitDialog, UpdateDialog, SendGenreDialog, GenreUpdateDialog
from workers import DownloadWorker, Worker
from menu_bar import MenuBar

from delegates import (
    ComboBoxDelegate, SearchHighlightDelegate, GenreSearchDelegate, strip_html_tags, CoverImageDelegate
)

def handle_exception(exc_type, exc_value, exc_traceback):
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    print("Uncaught exception:", exc_type, exc_value, exc_traceback)  # Print to console for debugging

def setup_logging():
    # Define the logs directory within the user's application data folder
    app_name = 'SuSheApp'

    # Determine the base directory for application data based on OS
    if sys.platform == 'win32':
        base_dir = os.getenv('APPDATA')
        if base_dir is None:
            # Fallback if APPDATA is not set (unlikely on Windows, but good practice)
            base_dir = os.path.expanduser('~')
            print("Warning: APPDATA environment variable not found. Using home directory for logs.") # Use print initially as logging might not be set up
        app_data_base_dir = os.path.join(base_dir, app_name)
    elif sys.platform == 'darwin':
        # Use standard macOS Application Support directory
        app_data_base_dir = os.path.join(os.path.expanduser('~/Library/Application Support/'), app_name)
    else:  # Linux and other Unix-like OSes
        # Use standard XDG Base Directory Specification if possible, fallback to ~/.config
        xdg_config_home = os.getenv('XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config'))
        app_data_base_dir = os.path.join(xdg_config_home, app_name)

    log_dir = os.path.join(app_data_base_dir, 'logs')

    os.makedirs(log_dir, exist_ok=True)  # Create the directory if it doesn't exist

    # Use a more detailed timestamp for the log filename
    log_filename = os.path.join(log_dir, datetime.now().strftime("SuShe_%Y-%m-%d_%H-%M-%S.log"))
    logging.basicConfig(
        filename=log_filename,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Add the QTextEditLogger handler
    text_edit_logger = QTextEditLogger()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    text_edit_logger.setFormatter(formatter)
    logging.getLogger().addHandler(text_edit_logger)

    # Set global exception handler
    sys.excepthook = handle_exception

    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Logging setup complete")

    # Suppress Pillow's debug logs
    logging.getLogger('PIL').setLevel(logging.WARNING)

    return text_edit_logger

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # Check if running in a PyInstaller bundle
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            # Access the attribute safely now that we know it exists
            base_path = getattr(sys, '_MEIPASS')
        else:
            # Not running in a bundle, use the current directory
            base_path = os.path.abspath(".")
    except Exception as e:
        # Handle other potential exceptions during path resolution
        logging.error(f"Unexpected error getting base path: {e}")
        base_path = os.path.abspath(".") # Fallback
    return os.path.join(base_path, relative_path)

def read_file_lines(filepath, transform=None):
    correct_path = resource_path(filepath)
    logging.debug(f"Reading file: {correct_path}")
    try:
        with open(correct_path, 'r') as file:
            lines = set(line.strip() for line in file)
            if transform:
                lines = transform(lines)
            logging.debug(f"Read {len(lines)} lines from {filepath}")
            return sorted(lines)
    except Exception as e:
        logging.error(f"Failed to read file {filepath}: {e}")
        return []

class DragDropTableView(QTableView):
    """
    Custom TableView with smooth, animated reordering during drag operations.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setShowGrid(True)
        h_header = self.horizontalHeader()
        if h_header:
            h_header.setHighlightSections(False)
        v_header = self.verticalHeader()
        if v_header:
            v_header.setHighlightSections(False)
        
        # States for drag operation
        self.drag_active = False
        self.dragged_rows = []
        self.original_data = None
        self.current_drop_row = -1
        self.hover_row = -1
        self.dropped_rows = []
        
        # Animation properties
        self.row_animations = {}  # Store animations by row index
        self.animation_group = QParallelAnimationGroup(self)
        self.animation_group.finished.connect(self.on_animation_finished)
        self.animation_duration = 150  # Slightly faster animation (was 200ms)
        
        # Visual properties
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QTableView.DragDropMode.InternalMove)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        
        # Set a consistent row height
        v_header = self.verticalHeader()
        if v_header:
            v_header.setDefaultSectionSize(100)
        
        # Enable smooth scrolling
        self.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        
        # Enable item tracking for smoother animations
        viewport = self.viewport()
        if viewport:
            viewport.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        
        # Add visual feedback when hovering over rows
        self.setMouseTracking(True)

    # Override paintEvent to add custom hover highlighting
    def paintEvent(self, e):
        super().paintEvent(e)
        
        # Add subtle hover effect for the entire row
        if hasattr(self, 'hover_row') and self.hover_row >= 0:
            # Only apply hover if not dragging and not on selected row
            sel_model = self.selectionModel()
            if not self.drag_active and sel_model and not sel_model.isRowSelected(self.hover_row, self.rootIndex()):
                model = self.model()
                if model is None:
                    return
                rect = self.visualRect(model.index(self.hover_row, 0))
                vp = self.viewport()
                if vp:
                    rect.setWidth(vp.width())
                rect.setHeight(self.rowHeight(self.hover_row))
                
                painter = QPainter(self.viewport())
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 10))  # Very subtle highlight
                painter.drawRect(rect)
                painter.end()

    # Add event to track mouse position for hover effects
    def mouseMoveEvent(self, e):
        super().mouseMoveEvent(e)
        if e is None:
            return
            
        try:
            # For PyQt6
            pos = e.position().toPoint()
        except (AttributeError, TypeError):
            try:
                # Fallback for older PyQt versions
                pos = e.pos()
            except AttributeError:
                return  # Cannot determine position
        
        viewport = self.viewport()
        if viewport:  # Check if viewport exists before using it
            index = self.indexAt(pos)
            if index.isValid():
                self.hover_row = index.row()
            else:
                self.hover_row = -1
            viewport.update()

    def startDrag(self, supportedActions):
        indexes = self.selectedIndexes()
        if not indexes:
            return
        
        # Get all unique rows
        rows = set()
        for index in indexes:
            if index.isValid():
                rows.add(index.row())
        
        # Store dragged rows
        self.dragged_rows = sorted(list(rows))
        self.drag_active = True
        
        # Check if model exists before accessing its methods
        model = self.model()
        if model is None:
            logging.error("Cannot start drag: No model is set for the table view.")
            return
            
        # Create mime data
        mime_data = model.mimeData(indexes)
        
        # Create a QDrag object
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        
        # Determine the mouse position when the drag started
        # This is usually stored in the event that triggered the drag, but we don't have access to it
        # So we'll use the current cursor position relative to the viewport
        viewport = self.viewport()
        if not viewport:
            logging.error("Cannot start drag: Viewport is not available.")
            return # Cannot proceed without a viewport
        mouse_pos = viewport.mapFromGlobal(QCursor.pos())
        
        # Calculate the visible portion of the table
        visible_rect = viewport.rect()
        
        # Create a pixmap the size of the visible rows being dragged
        first_row = self.dragged_rows[0]
        row_height = self.rowHeight(first_row)
        visible_width = visible_rect.width()
        pixmap_height = len(self.dragged_rows) * row_height
        
        # Create the pixmap
        pixmap = QPixmap(visible_width, pixmap_height)
        pixmap.fill(Qt.GlobalColor.transparent)

        # Calculate the hotspot relative to the first row
        first_row_index = model.index(first_row, 0) # Use the checked 'model' variable
        if not first_row_index.isValid():
            logging.error(f"Cannot calculate hotspot: Invalid index for first row {first_row}.")
            return # Cannot proceed with invalid index
        first_row_rect = self.visualRect(first_row_index)
        hotspot_x = mouse_pos.x()
        hotspot_y = mouse_pos.y() - first_row_rect.y()

        # Create a painter for the pixmap
        painter = QPainter(pixmap)
        painter.setOpacity(0.7)  # Semi-transparent

        # Render each selected row into the pixmap
        for i, row in enumerate(self.dragged_rows):
            # Get the visible part of the row
            row_index = model.index(row, 0) # Use the checked 'model' variable
            if not row_index.isValid():
                logging.warning(f"Skipping invalid index for row {row} during drag pixmap creation.")
                continue
            row_rect = self.visualRect(row_index)
            row_rect.setLeft(visible_rect.left())
            row_rect.setWidth(visible_width)

            # Grab just the visible part of the row
            viewport = self.viewport()
            if viewport:
                row_pixmap = viewport.grab(row_rect)
                # Draw onto our drag pixmap
                target_y = i * row_height
                painter.drawPixmap(0, target_y, row_pixmap)
            else:
                logging.warning(f"Skipping row {row} during drag pixmap creation: Viewport is not available.")
                continue # Skip this row if viewport is not available

            # Draw onto our drag pixmap
            # target_y = i * row_height # Moved inside the 'if viewport' block
            painter.drawPixmap(0, target_y, row_pixmap)

        painter.end()
        
        # Set the drag pixmap with the calculated hotspot
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(hotspot_x, hotspot_y))
        
        # Execute the drag
        result = drag.exec(supportedActions)
        
        # Reset drag state
        self.drag_active = False

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-sushe-albumrow"):
            # Store the current state of the model
            self.drag_active = True
            self.dragged_rows = sorted([index.row() for index in self.selectedIndexes() if index.column() == 0])

            model = self.model()
            # Check if the model is an instance of AlbumModel and not None
            if isinstance(model, AlbumModel):
                # Make a deep copy of the current model data
                self.original_data = model.get_album_data().copy()
                event.acceptProposedAction()
            else:
                logging.error("Drag enter event received, but the model is not a valid AlbumModel.")
                event.ignore() # Ignore the event if the model is not correct
        else:
            super().dragEnterEvent(event)

    def dragLeaveEvent(self, event):
        if self.drag_active:
            # Restore the original order with animation
            self.animate_reordering(self.original_data)
            self.drag_active = False
            self.dragged_rows = []
            self.original_data = None
            self.current_drop_row = -1
        
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        if not self.drag_active or not event.mimeData().hasFormat("application/x-sushe-albumrow"):
            super().dragMoveEvent(event)
            return
        
        # Calculate drop position
        y_position = int(event.position().y())
        row = self.rowAt(y_position)
        
        if row == -1:
            # If no row at position, determine if we're above first row or below last row
            model = self.model()
            if model is not None and model.rowCount() > 0:
                first_row_rect = self.visualRect(model.index(0, 0))
                last_row_rect = self.visualRect(model.index(model.rowCount()-1, 0))
                
                if y_position < first_row_rect.top():
                    drop_row = 0
                else:
                    drop_row = model.rowCount()
            else:
                drop_row = 0
        else:
            # Get the rectangle for the current row
            model = self.model()
            if not model:
                return
            row_rect = self.visualRect(model.index(row, 0))
            
            # If cursor is in the top half of the row, place above; otherwise, below
            if y_position < (row_rect.top() + row_rect.height() / 2):
                drop_row = row
            else:
                drop_row = row + 1
        
        # Only update the model if the drop position changed
        if drop_row != self.current_drop_row:
            self.current_drop_row = drop_row
            
            # Create a new arrangement of the data
            if self.original_data is not None:
                current_data = self.original_data.copy()
            else:
                current_data = []
            
            # Extract the dragged items
            dragged_items = [current_data[i] for i in self.dragged_rows]
            
            # Remove dragged items from the list
            for i in sorted(self.dragged_rows, reverse=True):
                current_data.pop(i)
            
            # Insert them at the drop position
            adjusted_drop_index = drop_row
            for i in self.dragged_rows:
                if i < drop_row:
                    adjusted_drop_index -= 1
            
            # Insert the dragged items at the target position
            for i, item in enumerate(dragged_items):
                current_data.insert(max(0, adjusted_drop_index + i), item)
            
            # Animate the transition to the new arrangement
            self.animate_reordering(current_data)
            
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if self.drag_active:
            # The model already has the correct final arrangement
            # Just need to mark it as modified now
            self.model().is_modified = True
            self.model().layoutChanged.emit()
            
            # Store dropped rows for highlighting
            self.dropped_rows = self.dragged_rows
            
            # Reset drag state
            self.drag_active = False
            self.dragged_rows = []
            self.original_data = None
            self.current_drop_row = -1
            
            # Reset hover row
            self.hover_row = -1
            self.viewport().update()
            
            # Update vertical header to reflect new order
            self.verticalHeader().update()
            
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def animate_reordering(self, target_data):
        """Create smooth animations for transitioning to the target arrangement."""
        # Stop any existing animations
        if self.animation_group.state() == QAbstractAnimation.State.Running:
            self.animation_group.stop()
        
        # Clear previous animations
        while self.animation_group.animationCount() > 0:
            self.animation_group.takeAnimation(0)
        self.row_animations.clear()
        
        # Get current visual positions of all rows
        current_positions = {}
        for row in range(self.model().rowCount()):
            rect = self.visualRect(self.model().index(row, 0))
            current_positions[row] = rect.y()
        
        # Update the model with the new data arrangement
        was_modified = self.model().is_modified
        self.model().set_album_data(target_data)
        self.model().is_modified = was_modified  # Don't mark as modified during animations
        
        # Create animations from current positions to new positions
        for row in range(self.model().rowCount()):
            # Skip rows that are being dragged
            if self.drag_active and row in self.dragged_rows:
                continue
                
            # Get the target position
            target_rect = self.visualRect(self.model().index(row, 0))
            
            # If we have the current position, animate from there
            if row in current_positions:
                # Create proxy object for animation
                proxy = QObject(self)
                proxy.setProperty("pos", current_positions[row])
                proxy.row = row
                
                # Create the animation with easing curve for more natural motion
                animation = QPropertyAnimation(proxy, b"pos")
                animation.setDuration(self.animation_duration)
                animation.setStartValue(current_positions[row])
                animation.setEndValue(target_rect.y())
                animation.setEasingCurve(QEasingCurve.Type.OutQuad)  # Smoother easing
                
                # Store the animation reference
                self.row_animations[row] = animation
                
                # Value change handler to update row position
                def create_update_callback(row_num):
                    def update_position(value):
                        # Calculate offset from current position
                        current_rect = self.visualRect(self.model().index(row_num, 0))
                        offset = value - current_rect.y()
                        
                        # Adjust the row height to create the animation effect
                        if offset != 0:
                            self.setRowHeight(row_num, self.rowHeight(row_num) + offset)
                            self.update()
                    return update_position
                
                # Connect the animation value changed signal
                update_callback = create_update_callback(row)
                animation.valueChanged.connect(update_callback)
                
                # Add to parallel animation group
                self.animation_group.addAnimation(animation)
        
        # Start the animations
        self.animation_group.start()

    def on_animation_finished(self):
        """Called when animations complete to reset row heights."""
        for row in range(self.model().rowCount()):
            self.setRowHeight(row, 100)  # Reset to standard row height
        
        # Clean up animation references
        self.row_animations.clear()
        
    def sizeHintForRow(self, row):
        """Provide a consistent row height."""
        return 100
        
    def sizeHintForColumn(self, column):
        """Return the width that was set for this column."""
        return self.columnWidth(column)

class DropIndicatorStyle(QProxyStyle):
    """
    Custom style to enhance drop indicator appearance.
    """
    def drawPrimitive(self, element, option, painter, widget=None):
        # Customize the drop indicator
        if element == QStyle.PrimitiveElement.PE_IndicatorItemViewItemDrop:
            pen = QPen(QColor("#1DB954"), 2)  # Spotify green, thicker line
            painter.setPen(pen)
            
            # Draw a more visible indicator line
            if option.rect.height() == 0:
                # This is a line drop indicator (between rows)
                painter.drawLine(option.rect.topLeft(), option.rect.topRight())
            else:
                # This is a full rect indicator (on a row)
                painter.drawRect(option.rect)
                
            return
            
        # Use the parent style for everything else
        super().drawPrimitive(element, option, painter, widget)

class QTextEditLogger(logging.Handler, QObject):
    log_signal = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self)
        logging.Handler.__init__(self)
        self.log_viewer = None
        self.buffer = []  # Buffer to store log messages before log_viewer is set
        self.log_signal.connect(self._append_log)

    def emit(self, record):
        msg = self.format(record)
        self.buffer.append(msg)
        self.log_signal.emit(msg)

    def _append_log(self, msg):
        if self.log_viewer:
            self.log_viewer.append_log(msg)

    def set_log_viewer(self, log_viewer):
        self.log_viewer = log_viewer
        for msg in self.buffer:
            self.log_viewer.append_log(msg)
        self.buffer.clear()

class SpotifyAlbumAnalyzer(QMainWindow):
    auth_required_signal = pyqtSignal()
    def __init__(self, text_edit_logger):
        super().__init__()
        self.statusBar().showMessage("Welcome to SuShe!", 5000)
        self.text_edit_logger = text_edit_logger
        self.version = self.get_app_version()
        self.current_file_path = None
        self.last_opened_file = None
        self.recent_files = []
        self.bot_token = None
        self.chat_id = None
        self.message_thread_id = None
        self.dataChanged = False
        self.github_token = None
        self.github_owner = None
        self.github_repo = ''
        self.webhook_url = ""
        self.show_positions = True

        # Initialize search-related variables
        self.matches = []
        self.current_match_index = -1

        self.auth_required_signal.connect(self.show_auth_required_dialog)

    def perform_initialization(self):
        # Initialize UI and other components
        self.initUI()  # Initialize UI elements before loading settings
        self.load_config()
        self.load_settings()
        self.update_recent_files_menu()

        # Load Spotify tokens
        self.load_spotify_tokens()
        
        if self.last_opened_file and os.path.exists(self.last_opened_file):
            self.load_album_data(self.last_opened_file)
            self.current_file_path = self.last_opened_file
            self.update_window_title()
            self.dataChanged = False

        # Check for application updates first
        should_show = self.check_for_updates()
        
        if should_show:
            # Show the main window after update check is done
            self.show()
            
            # Also check for genre definition updates, but with a slight delay
            # to avoid too many operations at startup
            QTimer.singleShot(2000, self.check_for_genre_updates)
        else:
            # The user chose to download an update; exit the application
            logging.info("Exiting application after initiating update download.")

    def initUI(self):
        self.menu_bar = MenuBar(self)
        self.preferred_music_player = 'Spotify'  # Initialize with default value
        self.update_window_title()
        self.artist_id_map = {}
        self.album_id_map = {}

        # Initialize worker attributes
        self.artist_search_worker = None
        self.albums_fetch_worker = None
        self.album_details_worker = None

        self.setAcceptDrops(True)
        self.resize(1550, 800)
        self.setWindowTitle("SuShe!")
        self.setWindowIcon(QIcon(resource_path(os.path.join("logos", "logo.ico"))))
        
        # Initialize genres and countries before setting up tabs
        self.genres = read_file_lines('genres.txt', transform=lambda lines: {line.title() for line in lines})
        self.countries = read_file_lines('countries.txt')
        
        self.setup_tabs()

        # Add a QLabel for notifications
        self.notification_label = QLabel(self)
        self.notification_label.setStyleSheet(
            "background-color: #2D2D30; "
            "font-weight: bold; "
            "border-radius: 3px; "
            "color: white; "
            "padding: 5px; "
            "border: 2px solid white;"
        )
        self.notification_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notification_label.setGeometry(0, 0, 450, 100)
        self.notification_label.hide()

        # Add a QLabel for the cover image inside the notification
        self.notification_image_label = QLabel(self)
        self.notification_image_label.setStyleSheet("border: none;")
        self.notification_image_label.setGeometry(0, 0, 100, 100)
        self.notification_image_label.hide()

    def show_auth_required_dialog(self):
        """Shows the auth required dialog on the main thread"""
        logging.info("Showing authentication required dialog on main thread")
        reply = QMessageBox.question(
            self, "Spotify Login Required", 
            "You need to log in to Spotify to continue. Would you like to log in now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.tabs.setCurrentWidget(self.settings_tab)
            self.login_to_spotify()

    def create_action(self, name, shortcut=None, triggered=None, icon_path=None, checkable=False):
        action = QAction(name, self)
        if shortcut:
            action.setShortcut(shortcut)
        if triggered:
            action.triggered.connect(triggered)
        if icon_path:
            action.setIcon(QIcon(resource_path(icon_path)))
        if checkable:
            action.setCheckable(True)
        return action

    def open_log_viewer(self):
        if not hasattr(self, 'log_viewer_dialog'):
            self.log_viewer_dialog = LogViewerDialog(self)
            # Set the log_viewer in text_edit_logger
            self.text_edit_logger.set_log_viewer(self.log_viewer_dialog)
        self.log_viewer_dialog.show()

    def load_config(self):
        config_path = self.get_user_data_path('config.json')
        
        # Define default configuration in code as fallback
        default_config = {
            "spotify": {
                "default_client_id": "2241ba6e592a4d60aa18c81a8507f0b3"
            },
            "telegram": {
                "bot_token": "",
                "chat_id": "",
                "message_thread_id": ""
            },
            "tidal": {
                "client_id": "",
                "client_secret": ""
            },
            "preferred_music_service": "Tidal",
            "application": {
                "preferred_music_player": "Spotify"
            },
            "github": {
                "personal_access_token": "",
                "owner": "magnusoverli",
                "repo": "SuShe"
            },
            "webhook": {
                "url": "https://hook.eu2.make.com/g7t3udg4ojpvlr48ipuwfq8q345m5bjn"
            }
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as file:
                    config = json.load(file)
                    # Load Telegram credentials
                    self.bot_token = config.get('telegram', {}).get('bot_token', '')
                    self.chat_id = config.get('telegram', {}).get('chat_id', '')
                    self.message_thread_id = config.get('telegram', {}).get('message_thread_id', '')
                    self.bot_token_input.setText(self.bot_token)
                    self.chat_id_input.setText(self.chat_id)
                    self.message_thread_id_input.setText(self.message_thread_id)

                    # Load GitHub credentials
                    self.github_token = config.get('github', {}).get('personal_access_token', '')
                    self.github_owner = config.get('github', {}).get('owner', '')
                    self.github_repo = config.get('github', {}).get('repo', '')

                    # Load Preferred Music Player
                    self.preferred_music_player = config.get('application', {}).get('preferred_music_player', 'Spotify')
                    index = self.preferred_music_player_combo.findText(self.preferred_music_player)
                    if index >= 0:
                        self.preferred_music_player_combo.setCurrentIndex(index)
                    else:
                        self.preferred_music_player_combo.setCurrentIndex(0)

                    # Load Webhook URL
                    self.webhook_url = config.get('webhook', {}).get('url', '')
                    if not self.webhook_url:
                        logging.warning("Webhook URL not found in config.json.")
                    # Update the UI field with the loaded webhook URL
                    if hasattr(self, 'webhook_url_input'):
                        self.webhook_url_input.setText(self.webhook_url)
                        logging.debug(f"Webhook URL input set to: {self.webhook_url}")
                    else:
                        logging.error("webhook_url_input UI element not found.")

                    logging.info("Configuration loaded successfully.")
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing config.json: {e}")
                QMessageBox.critical(self, "Configuration Error", "Failed to parse config.json. Please check the file format.")
        else:
            logging.warning("config.json not found. Attempting to create default configuration.")
            
            # Try to create user data directory if it doesn't exist
            try:
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
            except Exception as e:
                logging.error(f"Failed to create user data directory: {e}")
            
            # First try to create from template
            template_created = False
            template_path = resource_path('config_template.json')
            
            if os.path.exists(template_path):
                try:
                    with open(template_path, 'r') as template_file:
                        loaded_config = json.load(template_file)
                        # Merge with default_config to ensure all keys exist
                        for key, value in default_config.items():
                            if key not in loaded_config:
                                loaded_config[key] = value
                        default_config = loaded_config
                    template_created = True
                    logging.info(f"Loaded configuration template from {template_path}")
                except Exception as e:
                    logging.error(f"Failed to load template from {template_path}: {e}")
            else:
                logging.warning(f"Template file not found at {template_path}, using built-in defaults")
                
            # Now create the config file with either template or default values
            try:
                with open(config_path, 'w') as config_file:
                    json.dump(default_config, config_file, indent=4)
                logging.info(f"Default config.json created at {config_path}")
                
                # Set initial values from default config
                self.bot_token = default_config.get('telegram', {}).get('bot_token', '')
                self.chat_id = default_config.get('telegram', {}).get('chat_id', '')
                self.message_thread_id = default_config.get('telegram', {}).get('message_thread_id', '')
                self.webhook_url = default_config.get('webhook', {}).get('url', '')
                self.github_token = default_config.get('github', {}).get('personal_access_token', '')
                self.github_owner = default_config.get('github', {}).get('owner', '')
                self.github_repo = default_config.get('github', {}).get('repo', '')
                self.preferred_music_player = default_config.get('application', {}).get('preferred_music_player', 'Spotify')
                
                # Update UI elements
                self.bot_token_input.setText(self.bot_token)
                self.chat_id_input.setText(self.chat_id)
                self.message_thread_id_input.setText(self.message_thread_id)
                if hasattr(self, 'webhook_url_input'):
                    self.webhook_url_input.setText(self.webhook_url)
                
                # Set preferred music player combo
                index = self.preferred_music_player_combo.findText(self.preferred_music_player)
                if index >= 0:
                    self.preferred_music_player_combo.setCurrentIndex(index)
                else:
                    self.preferred_music_player_combo.setCurrentIndex(0)
                    
                # Show a dialog to the user
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setWindowTitle("Configuration Created")
                
                if template_created:
                    msg_box.setText("A new configuration file has been created from the template.")
                else:
                    msg_box.setText("A new configuration file has been created with default values.")
                    
                msg_box.setInformativeText("You can customize the settings in the Settings tab.")
                
                # Add buttons to the dialog
                go_to_settings_button = msg_box.addButton("Go to Settings", QMessageBox.ButtonRole.AcceptRole)
                ok_button = msg_box.addButton(QMessageBox.StandardButton.Ok)
                
                # Execute the dialog and handle user response
                msg_box.exec()
                
                if msg_box.clickedButton() == go_to_settings_button:
                    # Navigate to the Settings tab
                    self.tabs.setCurrentWidget(self.settings_tab)
                    
            except Exception as e:
                logging.error(f"Failed to create default config.json: {e}")
                QMessageBox.critical(self, "Configuration Error", 
                                f"Failed to create default config.json: {e}\n\nThe application will use temporary settings for this session.")
                
                # Set built-in defaults even if we couldn't save them
                self.preferred_music_player = 'Spotify'
                index = self.preferred_music_player_combo.findText(self.preferred_music_player)
                if index >= 0:
                    self.preferred_music_player_combo.setCurrentIndex(index)

    def toggle_show_positions(self):
        # Get the current state from the action (checked or unchecked)
        show_positions = self.show_positions_action.isChecked()
        
        # Update the vertical header visibility based on the toggle state
        v_header = self.album_table.verticalHeader()
        if v_header:
            v_header.setVisible(show_positions)
        else:
            logging.warning("Could not toggle vertical header visibility: vertical header is None.")
        
        # Log the change
        logging.info(f"Row position numbers {'shown' if show_positions else 'hidden'}")
        
        # Update the configuration to save this preference (optional)
        if hasattr(self, 'app_settings'):
            self.app_settings['show_positions'] = show_positions
            self.save_application_settings()

    def open_send_genre_dialog(self):
        if not self.webhook_url:
            QMessageBox.warning(self, "Webhook URL Missing", "Webhook URL is not configured. Please set it in the Settings tab.")
            return

        dialog = SendGenreDialog(self.webhook_url, self)
        dialog.exec()

    def check_for_updates(self):
        # Ensure that GitHub owner and repo are set
        if not all([self.github_owner, self.github_repo]):
            logging.warning("GitHub owner or repository name is missing. Aborting update check.")
            return True  # Proceed to show the main window

        logging.debug("Starting update check...")
        current_version = self.version
        logging.debug(f"Current application version: {current_version}")

        latest_version, download_url, release_notes_url = self.get_latest_github_release()

        if latest_version:
            try:
                from packaging import version
                if version.parse(latest_version) > version.parse(current_version):
                    logging.info(f"A new version {latest_version} is available.")
                    if download_url:
                        update_dialog = UpdateDialog(latest_version, current_version, release_notes_url)
                        reply = update_dialog.exec()

                        if reply == QDialog.DialogCode.Accepted:
                            logging.info("User accepted the update. Initiating download.")
                            self.download_and_install_update(download_url)
                            return False  # Do not show the main window as update is being downloaded
                        else:
                            logging.info("User declined the update.")
                    else:
                        logging.warning("New version available but no executable asset found for download.")
                        QMessageBox.warning(
                            self,
                            "Update Available",
                            f"A new version ({latest_version}) is available, but no downloadable asset was found."
                        )
                else:
                    logging.info("You are running the latest version.")
            except Exception as e:
                logging.error(f"Error comparing versions: {e}")
        else:
            logging.error("Failed to retrieve the latest version information from GitHub.")

        return True  # Proceed to show the main window

    def get_latest_github_release(self):
        url = f"https://api.github.com/repos/{self.github_owner}/{self.github_repo}/releases/latest"
        try:
            logging.debug(f"Fetching latest release from URL: {url}")
            response = requests.get(url)
            response.raise_for_status()
            release_info = response.json()
            
            latest_version = release_info.get('tag_name')
            assets = release_info.get('assets', [])
            release_notes_url = release_info.get('html_url')  # Retain release notes URL
            
            logging.debug(f"Latest Version: {latest_version}")
            logging.debug(f"Number of assets found: {len(assets)}")
            
            download_url = None
            for asset in assets:
                if asset['name'].endswith('.exe'):
                    download_url = asset.get('browser_download_url')
                    logging.debug(f"Found executable asset: {asset['name']}")
                    break
            
            if download_url:
                logging.info(f"Latest version {latest_version} found with executable asset.")
                return latest_version, download_url, release_notes_url
            else:
                logging.warning("No executable (.exe) asset found in the latest release.")
                return latest_version, None, release_notes_url
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching latest release: {e}")
            return None, None, None
        except ValueError as e:
            logging.error(f"Error parsing JSON response: {e}")
            return None, None, None

    def download_and_install_update(self, download_url):
        self.progress_dialog = QProgressDialog("Downloading Update...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_download)
        self.progress_dialog.show()

        self.download_thread = QThread()
        self.download_worker = DownloadWorker(download_url, self.github_token or "")
        self.download_worker.moveToThread(self.download_thread)

        self.download_thread.started.connect(self.download_worker.start_download)
        self.download_worker.progress_changed.connect(self.progress_dialog.setValue)
        self.download_worker.download_finished.connect(self.on_download_finished)
        self.download_worker.download_failed.connect(self.on_download_failed)

        self.download_worker.download_finished.connect(self.download_thread.quit)
        self.download_worker.download_failed.connect(self.download_thread.quit)
        self.download_worker.download_finished.connect(self.download_worker.deleteLater)
        self.download_worker.download_failed.connect(self.download_worker.deleteLater)
        self.download_thread.finished.connect(self.download_thread.deleteLater)

        self.download_thread.start()

    def cancel_download(self):
        if hasattr(self, 'download_worker') and self.download_worker:
            self.download_worker.is_cancelled = True

    def on_download_finished(self, file_path):
        self.progress_dialog.close()
        # Launch the installer
        try:
            if sys.platform.startswith('win'):
                os.startfile(file_path)
            elif sys.platform == 'darwin':
                subprocess.call(['open', file_path])
            else:
                subprocess.call(['xdg-open', file_path])
        except Exception as e:
            logging.error(f"Failed to launch installer: {e}")
            QMessageBox.critical(None, "Installation Failed", f"Failed to launch installer: {e}")
        else:
            QApplication.quit()  # Exit the application after launching the installer

    def on_download_failed(self, error_message):
        self.progress_dialog.close()
        QMessageBox.critical(self, "Download Failed", f"Failed to download update: {error_message}")

    def check_for_genre_updates(self):
        """
        Check if there is a newer version of genres.txt on GitHub.
        If so, prompt the user to update.
        """
        if not all([self.github_owner, self.github_repo]):
            logging.warning("GitHub owner or repository name is missing. Cannot check for genre updates.")
            return
        
        try:
            # Get the content of the remote genres.txt file
            url = f"https://api.github.com/repos/{self.github_owner}/{self.github_repo}/contents/genres.txt"
            headers = {}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            remote_file_info = response.json()
            remote_content = base64.b64decode(remote_file_info["content"]).decode("utf-8")
            remote_sha = remote_file_info["sha"]
            
            # Get the local file info
            local_path = resource_path("genres.txt")
            if not os.path.exists(local_path):
                logging.error(f"Local genres.txt not found at {local_path}")
                return
            
            with open(local_path, 'r', encoding='utf-8') as f:
                local_content = f.read()
            
            # Calculate SHA of local file for comparison
            local_sha = hashlib.sha1(local_content.encode()).hexdigest()
            
            # If files are identical, no update needed
            if local_sha == remote_sha:
                logging.info("Genres.txt is up to date.")
                return
            
            # Compare the genre lists
            local_genres = set(line.strip() for line in local_content.splitlines() if line.strip())
            remote_genres = set(line.strip() for line in remote_content.splitlines() if line.strip())
            
            # Identify additions and removals
            added_genres = remote_genres - local_genres
            removed_genres = local_genres - remote_genres
            
            if not added_genres and not removed_genres:
                # Files differ but no actual genre changes (maybe just whitespace or order)
                logging.info("No actual changes in genres.txt content, skipping update.")
                return
            
            # Show dialog with changes and ask for confirmation
            dialog = GenreUpdateDialog(added_genres, removed_genres, self)
            result = dialog.exec()
            
            if result == QDialog.DialogCode.Accepted:
                # User confirmed update, apply it
                self.apply_genre_update(remote_content)
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Error checking for genre updates: {e}")
        except Exception as e:
            logging.error(f"Unexpected error checking for genre updates: {e}")

    def apply_genre_update(self, new_content):
        """
        Apply an update to the genres.txt file and reload genres.
        
        Args:
            new_content (str): The new content for genres.txt
        """
        try:
            local_path = resource_path("genres.txt")
            
            # Create a backup first
            backup_path = f"{local_path}.bak"
            if os.path.exists(local_path):
                shutil.copy2(local_path, backup_path)
                logging.info(f"Created backup of genres.txt at {backup_path}")
            
            # Write the new content
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            logging.info("Updated genres.txt successfully")
            
            # Reload the genres
            self.genres = read_file_lines('genres.txt', transform=lambda lines: {line.title() for line in lines})
            
            # Update any genre delegates that exist
            if hasattr(self, 'genre_delegate_1') and self.genre_delegate_1:
                self.genre_delegate_1.items = self.genres
            if hasattr(self, 'genre_delegate_2') and self.genre_delegate_2:
                self.genre_delegate_2.items = self.genres
                
            # Show success message
            QMessageBox.information(self, "Genres Updated", 
                                "Genre definitions have been updated successfully.")
                                
        except Exception as e:
            logging.error(f"Failed to apply genre update: {e}")
            QMessageBox.critical(self, "Update Failed", 
                                f"Failed to update genres: {e}")

    def load_settings(self):
        is_packaged = getattr(sys, 'frozen', False)
        settings_path = self.get_user_data_path('settings.json', packaged=is_packaged)

        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as file:
                    settings = json.load(file)
                    self.last_opened_file = settings.get('last_opened_file', None)
                    self.recent_files = settings.get('recent_files', [])
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing settings.json: {e}")
                self.last_opened_file = None
                self.recent_files = []
        else:
            # This is a fresh install or settings have been deleted
            self.last_opened_file = None
            self.recent_files = []

    def save_settings(self):
        is_packaged = getattr(sys, 'frozen', False)
        logging.debug(f"Application is packaged: {is_packaged}")
        settings_path = self.get_user_data_path('settings.json', packaged=is_packaged)
        logging.debug(f"Saving settings to: {settings_path}")

        settings = {
            'last_opened_file': self.current_file_path,
            'recent_files': self.recent_files,
        }

        try:
            with open(settings_path, 'w') as file:
                json.dump(settings, file, indent=4)
            logging.info(f"Settings saved successfully to {settings_path}")
        except Exception as e:
            logging.error(f"Failed to save settings: {e}")

    def get_app_version(self):
        try:
            version_file = resource_path('version.txt')
            logging.info(f"Looking for version file at: {version_file}")
            with open(version_file, 'r') as f:
                version = f.read().strip()
            return version
        except Exception as e:
            logging.error(f"Error reading version.txt: {e}")
            return "Unknown"

    def show_notification(self, message, image_path=None):
        self.notification_label.setText(message)
        self.notification_label.adjustSize()
        self.notification_label.move(self.width() // 2 - self.notification_label.width() // 2, 80)  # Adjust this value to move the notification down
        self.notification_label.show()

        if image_path:
            pixmap = QPixmap(image_path)
            scaled_pixmap = pixmap.scaled(70, 70, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.notification_image_label.setPixmap(scaled_pixmap)
            self.notification_image_label.move(self.notification_label.x() - 75, 50)  # Position the image to the left of the text
            self.notification_image_label.show()

        QTimer.singleShot(2000, self.notification_label.hide)
        QTimer.singleShot(2000, self.notification_image_label.hide)

    def show_search_bar(self):
        if not hasattr(self, 'search_widget'):
            self.search_bar = QLineEdit(self)
            self.search_bar.setPlaceholderText("Search...")
            self.search_bar.returnPressed.connect(self.goto_next_match)
            self.search_bar.textChanged.connect(self.search_album_list)

            # 'Next' and 'Previous' buttons
            self.search_prev_button = QPushButton("Previous")
            self.search_next_button = QPushButton("Next")
            self.search_close_button = QPushButton("X")
            self.search_prev_button.clicked.connect(self.goto_previous_match)
            self.search_next_button.clicked.connect(self.goto_next_match)
            self.search_close_button.clicked.connect(self.hide_search_bar)

            # Layout for the search bar and buttons
            self.search_layout = QHBoxLayout()
            self.search_layout.addWidget(self.search_bar)
            self.search_layout.addWidget(self.search_prev_button)
            self.search_layout.addWidget(self.search_next_button)
            self.search_layout.addWidget(self.search_close_button)

            # Container widget for the search layout
            self.search_widget = QWidget()
            self.search_widget.setLayout(self.search_layout)

            # Add the search widget to the album_list_tab layout
            self.album_list_layout.insertWidget(0, self.search_widget)
            self.search_widget.hide()

        if self.search_widget.isVisible():
            self.hide_search_bar()  # Hide and clear highlights
        else:
            self.search_widget.show()
            self.search_bar.setFocus()

    def hide_search_bar(self):
        self.search_widget.hide()
        self.search_bar.clear()
        # Clear search text in all delegates
        self.search_delegate.set_search_text("")
        self.genre_delegate_1.set_search_text("")
        self.genre_delegate_2.set_search_text("")
        # Clear matches
        self.matches = []
        self.current_match_index = -1
        # Update the view to remove highlights
        viewport = self.album_table.viewport()
        if viewport:
            viewport.update()

    def search_album_list(self):
        search_text = self.search_bar.text().strip().lower()
        self.search_delegate.set_search_text(search_text)
        self.genre_delegate_1.set_search_text(search_text)
        self.genre_delegate_2.set_search_text(search_text)

        self.matches = []

        if not search_text:
            self.current_match_index = -1
            return

        # Columns to search - don't use range(self.album_table.columnCount())
        # Instead use specific column constants from the model
        columns_to_search = [AlbumModel.ARTIST, AlbumModel.ALBUM, 
                            AlbumModel.GENRE_1, AlbumModel.GENRE_2, 
                            AlbumModel.COMMENTS]

        # Find matches
        for row in range(self.album_model.rowCount()):
            for column in columns_to_search:
                item_text = ""
                # Use model data instead of table items
                data = self.album_model.data(self.album_model.index(row, column), Qt.ItemDataRole.DisplayRole)
                if data:
                    item_text = str(data).lower()

                if search_text in item_text:
                    self.matches.append((row, column))

        self.current_match_index = -1
        if self.matches:
            self.goto_next_match()

    def goto_next_match(self):
        if not self.matches:
            return
        self.current_match_index = (self.current_match_index + 1) % len(self.matches)
        row, column = self.matches[self.current_match_index]
        model_index = self.album_model.index(row, column) # Get the model index
        self.album_table.scrollTo(model_index, QTableView.ScrollHint.PositionAtCenter) # Use model index for scrolling

        # Check if selection model exists before using it
        selection_model = self.album_table.selectionModel()
        if selection_model:
            selection_model.select(
                model_index, # Use model index for selection
                QItemSelectionModel.SelectionFlag.ClearAndSelect
            )
        else:
            logging.warning("Selection model not available for album table.")

    def goto_previous_match(self):
        if not self.matches:
            return
        self.current_match_index = (self.current_match_index - 1) % len(self.matches)
        row, column = self.matches[self.current_match_index]
        self.album_table.scrollToItem(self.album_table.item(row, column) or self.album_table.item(row, 0), QAbstractItemView.ScrollHint.PositionAtCenter)
        self.album_table.setCurrentCell(row, column)

    def show_about_dialog(self):
        version = self.get_app_version()
        about_text = f"""
        <h2>SuShe</h2>
        <p><strong>Version:</strong> {version}</p>
        <p>SuShe is an album list manager, aimed at creating superior album of the year lists.</p>
        <p>Contact: <a href="mailto:magnus+sushe@overli.dev">magnus+sushe@overli.dev</a></p>
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("About SuShe")
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setText(about_text)
        msg_box.setTextFormat(Qt.TextFormat.RichText)  # Enable rich text
        msg_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)  # Enable clickable links
        msg_box.exec()

    def update_recent_files_menu(self):
        self.recent_files_menu.clear()
        for file_path in self.recent_files:
            if os.path.exists(file_path):
                action = QAction(file_path, self)
                action.triggered.connect(partial(self.trigger_load_album_data, file_path))
                self.recent_files_menu.addAction(action)

    def show_help(self):
        help_file_path = resource_path('help.md')
        if os.path.exists(help_file_path):
            try:
                with open(help_file_path, 'r', encoding='utf-8') as file:
                    markdown_text = file.read()
                    # Convert markdown to HTML
                    import markdown
                    html_content = markdown.markdown(markdown_text)
                    # Display the HTML content in a HelpDialog
                    help_dialog = HelpDialog(html_content, self)
                    help_dialog.exec()
            except Exception as e:
                logging.error(f"Error reading help file: {e}")
                QMessageBox.warning(self, "Error", "An error occurred while reading the help file.")
        else:
            QMessageBox.warning(self, "Error", "Help file not found. Please ensure 'help.md' is in the application directory.")
            logging.error("Help file 'help.md' not found.")

    def close_application(self):
        self.close()

    def setup_tabs(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        
        self.album_list_tab = QWidget()
        self.search_tab = QWidget()
        self.settings_tab = QWidget()

        
        self.tabs.addTab(self.album_list_tab, "Album List")
        self.tabs.addTab(self.search_tab, "Search Albums")
        self.tabs.addTab(self.settings_tab, "Settings")

        
        self.setup_album_list_tab()
        self.setup_search_tab()
        self.setup_settings_tab()

        # Set the current tab to the "Album List" tab
        self.tabs.setCurrentWidget(self.album_list_tab)

    def openSubmitDialog(self):
        if self.dataChanged:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                "You have unsaved changes. Do you want to save them before submitting?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.trigger_save_album_data()
            elif reply == QMessageBox.StandardButton.Cancel:
                return  # Abort submission
            # If No, proceed without saving

        if not self.current_file_path:
            QMessageBox.warning(self, "No File Open", "Please open or save a file before attempting to submit.")
            logging.warning("Submit attempted without an open file")
            return

        if not all([self.bot_token, self.chat_id, self.message_thread_id]):
            QMessageBox.warning(self, "Configuration Error", "Telegram credentials are missing. Please update the Telegram settings.")
            logging.error("Telegram credentials are missing.")
            return

        dialog = SubmitDialog(self.bot_token, self.chat_id, self.message_thread_id, self.current_file_path, self)
        dialog.exec()

    def get_user_data_path(self, filename, packaged=False):
        """Get a path to the user-specific application data directory for storing the given filename."""
        app_name = 'SuSheApp'

        if sys.platform == 'win32':
            app_data_dir = os.path.join(os.getenv('APPDATA'), app_name)
        elif sys.platform == 'darwin':
            app_data_dir = os.path.join(os.path.expanduser('~/Library/Application Support/'), app_name)
        else:  # Linux and other Unix-like OSes
            app_data_dir = os.path.join(os.path.expanduser('~'), '.SuSheApp')

        if packaged:
            # Use a subdirectory for packaged application settings
            app_data_dir = os.path.join(app_data_dir, 'packaged')

        if not os.path.exists(app_data_dir):
            os.makedirs(app_data_dir)  # Ensure directory is created

        return os.path.join(app_data_dir, filename)

    def on_layout_changed(self):
            """Called when the album model layout changes due to operations like drag-and-drop."""
            # Update main window's dataChanged flag from the model
            self.dataChanged = self.album_model.is_modified
            self.update_window_title()
            logging.info("Album layout changed (reordering). Change state: %s", self.dataChanged)

    def dragEnterEvent(self, event: QDragEnterEvent):
        # First check if mimeData exists
        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls():  # Check if the drag event contains URLs
            event.acceptProposedAction()  # Accept the drag event
        else:
            event.ignore()  # Ignore the drag event if it does not contain URLs

    def dropEvent(self, event: QDropEvent):
        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls():
            urls = mime_data.urls()  # Extract URLs from the event
            for url in urls:
                self.process_spotify_uri(url.toString())  # Process each URL
        else:
            logging.warning("Drop event occurred but no valid URLs found")

    def import_config(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Config", "", "JSON Files (*.json)"
        )
        if file_path:
            logging.debug(f"Selected config file for import: {file_path}")
            try:
                with open(file_path, 'r') as file:
                    new_config = json.load(file)
                logging.debug("Config file loaded successfully.")

                config_path = self.get_user_data_path('config.json')
                logging.debug(f"Importing config to: {config_path}")

                with open(config_path, 'w') as file:
                    json.dump(new_config, file, indent=4)
                logging.info("Configuration imported successfully.")

                self.load_config()
                logging.debug("Configuration reloaded after import.")

                QTimer.singleShot(0, lambda: self.statusBar().showMessage("Configuration imported successfully.", 5000))
                logging.debug("Status bar message scheduled.")

                self.tabs.setCurrentWidget(self.settings_tab)
                logging.debug("Navigated to Settings tab after import.")
                
            except Exception as e:
                logging.error(f"Failed to import config: {e}")
                QMessageBox.critical(self, "Import Failed", f"Failed to import config: {e}")

    def setup_search_tab(self):
        layout = QVBoxLayout()

        search_label = QLabel("Search:")
        layout.addWidget(search_label)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        search_layout.addWidget(self.search_input)
        self.search_button = QPushButton("Search")
        search_layout.addWidget(self.search_button)
        self.search_button.clicked.connect(self.search_artist)
        layout.addLayout(search_layout)

        artist_label = QLabel("Artists:")
        layout.addWidget(artist_label)

        self.artist_list = QListWidget()
        layout.addWidget(self.artist_list)

        album_label = QLabel("Albums:")
        layout.addWidget(album_label)

        self.album_list = QListWidget()
        layout.addWidget(self.album_list)
        self.search_input.returnPressed.connect(self.search_artist)
        self.artist_list.itemDoubleClicked.connect(self.display_artist_albums)
        self.album_list.itemDoubleClicked.connect(self.fetch_album_details)
        self.search_tab.setLayout(layout)

    def setup_album_list_tab(self):
        layout = QVBoxLayout()

        # Create our custom TableView
        self.album_table = DragDropTableView()
        
        # Create and set the model
        self.album_model = AlbumModel(self)
        self.album_table.setModel(self.album_model)
        
        # Enable alternating row colors for better readability
        self.album_table.setAlternatingRowColors(True)
        
        # Configure the view for drag and drop
        self.album_table.setDragEnabled(True)
        self.album_table.setAcceptDrops(True)
        self.album_table.setDropIndicatorShown(True)
        self.album_table.setDragDropMode(QTableView.DragDropMode.InternalMove)
        self.album_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        
        # Make sure horizontal scrolling is enabled if needed
        self.album_table.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        
        # Apply the custom style for better drop indicators
        self.album_table.setStyle(DropIndicatorStyle())
        
        # Enable editing with appropriate triggers
        self.album_table.setEditTriggers(QTableView.EditTrigger.DoubleClicked | 
                                        QTableView.EditTrigger.EditKeyPressed |
                                        QTableView.EditTrigger.AnyKeyPressed)
        
        # Disable sorting initially
        self.album_table.setSortingEnabled(False)
        
        # Configure header behavior
        header = self.album_table.horizontalHeader()
        header.setSectionsClickable(False)  # Make header non-clickable
        header.setHighlightSections(False)  # Don't highlight sections
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        # Configure vertical header (row numbers)
        v_header = self.album_table.verticalHeader()
        v_header.setDefaultSectionSize(100)  # Consistent row height
        v_header.setVisible(self.show_positions)  # Set based on preference
        v_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)  # Prevent resizing
        v_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)  # Center the numbers
        v_header.setMinimumWidth(30)  # Give enough space for double-digit numbers
        v_header.setStyleSheet("""
            QHeaderView::section:vertical {
                background-color: #1A1A1A;
                color: #1DB954;  /* Spotify green */
                font-weight: bold;
                border: none;
                border-right: 1px solid #333333;
                padding: 4px;
            }
        """)
        
        # Create separate delegate instances properly parented to the view
        country_delegate = ComboBoxDelegate(self.countries, self.album_table)
        self.genre_delegate_1 = GenreSearchDelegate(self.genres, self.album_table, highlight_color=Qt.GlobalColor.darkYellow)
        self.genre_delegate_2 = GenreSearchDelegate(self.genres, self.album_table, highlight_color=Qt.GlobalColor.darkYellow)
        self.search_delegate = SearchHighlightDelegate(self.album_table, highlight_color=Qt.GlobalColor.darkYellow)
        cover_delegate = CoverImageDelegate(self.album_table)

        # Assign delegates to respective columns
        self.album_table.setItemDelegateForColumn(AlbumModel.COUNTRY, country_delegate)
        self.album_table.setItemDelegateForColumn(AlbumModel.GENRE_1, self.genre_delegate_1)
        self.album_table.setItemDelegateForColumn(AlbumModel.GENRE_2, self.genre_delegate_2)
        self.album_table.setItemDelegateForColumn(AlbumModel.COVER_IMAGE, cover_delegate)

        # Set the search highlight delegate for specified columns
        for column in [AlbumModel.ARTIST, AlbumModel.ALBUM, AlbumModel.COMMENTS]:
            self.album_table.setItemDelegateForColumn(column, self.search_delegate)

        # Connect signals
        self.album_table.clicked.connect(self.handleCellClick)
        self.album_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.album_table.customContextMenuRequested.connect(self.show_context_menu)

        # Connect model change signals to update UI state
        self.album_model.dataChanged.connect(self.on_album_data_changed)
        self.album_model.layoutChanged.connect(self.on_layout_changed)
        
        # Add to layout
        layout.addWidget(self.album_table)

        # Set the column widths
        self.set_album_table_column_widths()

        # Set the layout for the album list tab
        self.album_list_layout = layout  # Store the layout
        self.album_list_tab.setLayout(self.album_list_layout)

    def on_sort_order_changed(self, column, order):
        # Don't use self.album_table.horizontalHeaderItem(column).text()
        # Use the model's column names instead
        column_name = self.album_model.COLUMN_NAMES[column]
        order_str = 'ascending' if order == Qt.SortOrder.AscendingOrder else 'descending'
        logging.info(f"Album table sorted by column '{column_name}' in {order_str} order")

    def set_album_table_column_widths(self):
        """Set and lock column widths with proper header alignment."""
        # First, disable last section stretch to prevent automatic width adjustments
        header = self.album_table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(False)
        else:
            logging.error("Failed to get horizontal header - it returned None")
        
        # Set viewport margin to 0 to prevent offsets
        self.album_table.setViewportMargins(0, 0, 0, 0)
        
        # Define column widths
        column_widths = [
            (AlbumModel.ARTIST, 130),       # "Artist" column
            (AlbumModel.ALBUM, 200),        # "Album" column
            (AlbumModel.RELEASE_DATE, 120), # "Release Date" column
            (AlbumModel.COVER_IMAGE, 120),  # "Cover Image" column
            (AlbumModel.COUNTRY, 170),      # "Country" column
            (AlbumModel.GENRE_1, 190),      # "Genre 1" column
            (AlbumModel.GENRE_2, 190),      # "Genre 2" column
            (AlbumModel.COMMENTS, 340),     # "Comments" column
        ]
        
        # Apply column widths to both the header sections and table columns
        if header:  # Check if header is not None
            for column, width in column_widths:
                self.album_table.setColumnWidth(column, width)
                header.resizeSection(column, width)  # This ensures header width = column width
            
            # Lock column sizes after setting them
            for i in range(self.album_model.columnCount()):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            
            # We can add a bit of extra styling to the header for better appearance
            header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            # Update the visual properties of the headers to ensure they're refreshed
            header.update()
        else:
            logging.error("Could not apply column widths because horizontal header is None.")

    def setup_settings_tab(self):
        layout = QVBoxLayout()
        
        # Spotify Authentication GroupBox
        spotify_auth_group_box = QGroupBox("Spotify Authentication")
        spotify_auth_layout = QVBoxLayout()
        
        # Status label
        self.spotify_auth_status = QLabel("Not logged in to Spotify")
        spotify_auth_layout.addWidget(self.spotify_auth_status)
        
        # Login/logout buttons
        button_layout = QHBoxLayout()
        self.spotify_login_button = QPushButton("Login with Spotify")
        self.spotify_login_button.clicked.connect(self.login_to_spotify)
        
        self.spotify_logout_button = QPushButton("Logout from Spotify")
        self.spotify_logout_button.clicked.connect(self.logout_from_spotify)
        self.spotify_logout_button.setEnabled(False)  # Disabled by default
        
        button_layout.addWidget(self.spotify_login_button)
        button_layout.addWidget(self.spotify_logout_button)
        spotify_auth_layout.addLayout(button_layout)
        
        spotify_auth_group_box.setLayout(spotify_auth_layout)
        layout.addWidget(spotify_auth_group_box)
        
        layout.addSpacing(30)

        # Webhook Settings GroupBox
        webhook_group_box = QGroupBox("Webhook Settings")
        webhook_layout = QVBoxLayout()

        # Webhook URL Input
        webhook_url_label = QLabel("Webhook URL:")
        webhook_layout.addWidget(webhook_url_label)
        self.webhook_url_input = QLineEdit()
        self.webhook_url_input.setText(getattr(self, 'webhook_url', ''))
        webhook_layout.addWidget(self.webhook_url_input)

        # Save Webhook Settings Button
        save_webhook_button = QPushButton("Save Webhook Settings")
        webhook_layout.addWidget(save_webhook_button)
        save_webhook_button.clicked.connect(self.save_webhook_settings)

        webhook_group_box.setLayout(webhook_layout)
        layout.addWidget(webhook_group_box)

        layout.addSpacing(30)

        # Telegram settings group box
        telegram_group_box = QGroupBox("Telegram Submission Settings")
        telegram_layout = QVBoxLayout()

        # Bot Token Input
        bot_token_label = QLabel("Bot Token:")
        telegram_layout.addWidget(bot_token_label)
        self.bot_token_input = QLineEdit()
        telegram_layout.addWidget(self.bot_token_input)

        # Chat ID Input
        chat_id_label = QLabel("Chat ID:")
        telegram_layout.addWidget(chat_id_label)
        self.chat_id_input = QLineEdit()
        telegram_layout.addWidget(self.chat_id_input)

        # Message Thread ID Input
        message_thread_id_label = QLabel("Message Thread ID:")
        telegram_layout.addWidget(message_thread_id_label)
        self.message_thread_id_input = QLineEdit()
        telegram_layout.addWidget(self.message_thread_id_input)

        # Save Telegram Settings Button
        save_telegram_button = QPushButton("Save Telegram Settings")
        telegram_layout.addWidget(save_telegram_button)
        save_telegram_button.clicked.connect(self.save_telegram_settings)

        telegram_group_box.setLayout(telegram_layout)
        layout.addWidget(telegram_group_box)

        layout.addSpacing(30)

        # Application Settings GroupBox
        app_settings_group_box = QGroupBox("Application Settings")
        app_settings_layout = QVBoxLayout()

        # Preferred Music Player Setting
        preferred_music_player_label = QLabel("Preferred Music Player:")
        app_settings_layout.addWidget(preferred_music_player_label)
        self.preferred_music_player_combo = QComboBox()
        self.preferred_music_player_combo.addItems(["Spotify", "Tidal"])
        app_settings_layout.addWidget(self.preferred_music_player_combo)

        # Save Application Settings Button
        save_app_settings_button = QPushButton("Save Application Settings")
        app_settings_layout.addWidget(save_app_settings_button)
        save_app_settings_button.clicked.connect(self.save_application_settings)

        app_settings_group_box.setLayout(app_settings_layout)
        layout.addWidget(app_settings_group_box)

        layout.addStretch()
        self.settings_tab.setLayout(layout)

    def update_spotify_auth_status(self):
        """Update the Spotify authentication status display"""
        if hasattr(self, 'spotify_auth') and self.spotify_auth.access_token:
            self.spotify_auth_status.setText("✓ Logged in to Spotify")
            self.spotify_auth_status.setStyleSheet("color: green; font-weight: bold;")
            self.spotify_login_button.setEnabled(False)
            self.spotify_logout_button.setEnabled(True)
        else:
            self.spotify_auth_status.setText("Not logged in to Spotify")
            self.spotify_auth_status.setStyleSheet("")
            self.spotify_login_button.setEnabled(True)
            self.spotify_logout_button.setEnabled(False)

    def login_to_spotify(self):
        """
        Initiate Spotify login flow with improved error handling and state management.
        """
        logging.info("Starting Spotify login process")
        
        # Default client ID embedded in app
        default_client_id = "2241ba6e592a4d60aa18c81a8507f0b3"
        
        # Ensure we have a SpotifyAuth instance
        if not hasattr(self, 'spotify_auth'):
            try:
                from spotify_auth import SpotifyAuth
                self.spotify_auth = SpotifyAuth(default_client_id)
                
                # Connect signals only once
                self.spotify_auth.auth_complete.connect(self.on_spotify_auth_complete)
                self.spotify_auth.auth_timeout.connect(self.on_spotify_auth_timeout)
                
                logging.info("Created new SpotifyAuth instance")
            except Exception as e:
                logging.error(f"Failed to create SpotifyAuth instance: {e}")
                QMessageBox.critical(self, "Authentication Error", 
                                f"Failed to initialize Spotify authentication: {e}")
                return

        # Check if authentication is already in progress
        if hasattr(self, 'auth_progress') and self.auth_progress and self.auth_progress.isVisible():
            logging.warning("Authentication already in progress")
            QMessageBox.information(self, "Authentication In Progress", 
                            "A Spotify authentication process is already in progress. Please complete that process or wait for it to timeout.")
            return
        
        # Always clean up any existing auth resources first
        try:
            self.spotify_auth.cleanup_auth_resources()
            logging.info("Cleaned up existing auth resources")
        except Exception as e:
            logging.warning(f"Error during cleanup of auth resources: {e}")
        
        # Show a progress dialog while waiting for auth
        self.auth_progress = QProgressDialog("Waiting for Spotify login...", "Cancel", 0, 0, self)
        self.auth_progress.setWindowTitle("Spotify Authentication")
        self.auth_progress.setCancelButtonText("Cancel")
        self.auth_progress.canceled.connect(self.cancel_spotify_auth)
        self.auth_progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        # Start auth flow with adequate timeout
        try:
            # Show progress dialog BEFORE starting auth flow
            self.auth_progress.show()
            
            # Now start the auth flow
            self.spotify_auth.start_auth_flow(timeout_seconds=120)
            logging.info("Authentication flow started")
        except Exception as e:
            logging.error(f"Failed to start authentication flow: {e}")
            if hasattr(self, 'auth_progress') and self.auth_progress:
                self.auth_progress.close()
                self.auth_progress = None
            
            QMessageBox.critical(self, "Authentication Error", 
                            f"Failed to start Spotify authentication: {e}")

    def on_spotify_auth_complete(self, success):
        """
        Handle Spotify authentication completion with improved error handling.
        
        Args:
            success (bool): Whether authentication was successful
        """
        logging.info(f"Spotify auth complete signal received, success={success}")
        
        # First, handle the progress dialog
        if hasattr(self, 'auth_progress') and self.auth_progress:
            try:
                self.auth_progress.close()
            except Exception as e:
                logging.warning(f"Error closing auth progress dialog: {e}")
            finally:
                self.auth_progress = None
        
        # Then process the authentication result
        if success:
            if not hasattr(self, 'spotify_auth') or not self.spotify_auth.auth_code:
                logging.error("Auth success reported but no auth code available")
                QMessageBox.warning(self, "Authentication Error", 
                                "Authentication succeeded but no authorization code was received.")
                return
            
            logging.info("Exchanging authorization code for tokens")
            
            # Exchange code for tokens
            token_exchange_success = False
            try:
                token_exchange_success = self.spotify_auth.exchange_code_for_tokens()
            except Exception as e:
                logging.error(f"Exception during token exchange: {e}")
                QMessageBox.warning(self, "Authentication Error", 
                                f"Failed to exchange authorization code for tokens: {e}")
                return
            
            if token_exchange_success:
                # Save tokens to user data folder
                tokens_path = self.get_user_data_path('spotify_tokens.json')
                token_save_success = False
                
                try:
                    token_save_success = self.spotify_auth.save_tokens(tokens_path)
                except Exception as e:
                    logging.error(f"Exception saving tokens: {e}")
                    QMessageBox.warning(self, "Authentication Warning", 
                                    f"Successfully authenticated but failed to save tokens: {e}")
                
                # Update UI and show success message
                self.update_spotify_auth_status()
                QMessageBox.information(self, "Success", "Successfully logged in to Spotify.")
                
            else:
                logging.error("Token exchange failed")
                QMessageBox.warning(self, "Authentication Failed", 
                                "Failed to obtain access tokens. Please try again.")
        else:
            # Authentication failed
            logging.warning("Authentication failed")
            QMessageBox.warning(self, "Authentication Failed", 
                            "Failed to authenticate with Spotify. Please try again.")

    def on_spotify_auth_timeout(self):
        """
        Handle Spotify authentication timeout with improved cleanup.
        """
        logging.info("Spotify authentication timeout signal received")
        
        # Close the progress dialog
        if hasattr(self, 'auth_progress') and self.auth_progress:
            try:
                self.auth_progress.close()
            except Exception as e:
                logging.warning(f"Error closing auth progress dialog: {e}")
            finally:
                self.auth_progress = None
        
        # Clean up auth resources
        if hasattr(self, 'spotify_auth'):
            try:
                self.spotify_auth.cleanup_auth_resources()
            except Exception as e:
                logging.error(f"Error cleaning up auth resources after timeout: {e}")
        
        # Show timeout message
        QMessageBox.warning(self, "Authentication Timeout", 
                        "Spotify authentication timed out. Please try again.")

    def cancel_spotify_auth(self):
        """
        Handle cancellation of Spotify authentication with improved cleanup.
        """
        logging.info("Spotify authentication cancelled by user")
        
        if hasattr(self, 'spotify_auth'):
            try:
                self.spotify_auth.cleanup_auth_resources()
                logging.info("Auth resources cleaned up after cancellation")
            except Exception as e:
                logging.error(f"Error cleaning up after cancellation: {e}")
        
        if hasattr(self, 'auth_progress') and self.auth_progress:
            self.auth_progress.close()
            self.auth_progress = None

    def logout_from_spotify(self):
        """
        Log out from Spotify with improved cleanup and error handling.
        """
        logging.info("Starting Spotify logout process")
        
        if not hasattr(self, 'spotify_auth'):
            logging.warning("Logout attempted but no SpotifyAuth instance exists")
            QMessageBox.information(self, "Logged Out", "Not currently logged in to Spotify.")
            return
        
        try:
            # Clean up any existing server resources first
            self.spotify_auth.cleanup_auth_resources()
            
            # Clear tokens and state
            self.spotify_auth.access_token = None
            self.spotify_auth.refresh_token = None
            self.spotify_auth.auth_code = None
            self.spotify_auth.code_verifier = None
            
            # Remove saved tokens file
            tokens_path = self.get_user_data_path('spotify_tokens.json')
            if os.path.exists(tokens_path):
                try:
                    # Create a backup before removing
                    backup_path = f"{tokens_path}.bak"
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                    os.rename(tokens_path, backup_path)
                    logging.info(f"Created token backup at {backup_path}")
                except Exception as e:
                    logging.warning(f"Failed to create token backup: {e}")
                    
                    # Try direct removal if backup fails
                    try:
                        os.remove(tokens_path)
                    except Exception as e2:
                        logging.error(f"Failed to remove token file: {e2}")
            
            # Update UI
            self.update_spotify_auth_status()
            QMessageBox.information(self, "Logged Out", "Successfully logged out from Spotify.")
            
        except Exception as e:
            logging.error(f"Error during Spotify logout: {e}")
            QMessageBox.warning(self, "Logout Issue", 
                            f"There was an issue during logout: {e}\n\nYou may need to restart the application.")

    def load_spotify_tokens(self):
        """Load saved Spotify tokens on startup"""
        tokens_path = self.get_user_data_path('spotify_tokens.json')
        
        if os.path.exists(tokens_path):
            # Use the same client ID as in login_to_spotify
            default_client_id = "2241ba6e592a4d60aa18c81a8507f0b3"
            
            if not hasattr(self, 'spotify_auth'):
                from spotify_auth import SpotifyAuth
                self.spotify_auth = SpotifyAuth(default_client_id)
            
            if self.spotify_auth.load_tokens(tokens_path):
                self.update_spotify_auth_status()
                return True
        return False

    def load_config_section(self, section_name):
        config_path = resource_path('config.json')
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as file:
                    config = json.load(file)
                return config.get(section_name, {})
            else:
                return {}
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing config.json: {e}")
            return {}

    def save_config_section(self, section_name, data):
        config_path = resource_path('config.json')
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as file:
                    config = json.load(file)
            else:
                config = {}

            config[section_name] = data

            with open(config_path, 'w') as file:
                json.dump(config, file, indent=4)
            logging.info(f"{section_name.capitalize()} settings saved successfully.")
        except Exception as e:
            logging.error(f"Failed to save {section_name} settings: {e}")
            raise e  # Re-raise exception for the calling method to handle

    def save_webhook_settings(self):
        webhook_settings = {
            "url": self.webhook_url_input.text().strip()
        }
        try:
            self.save_config_section('webhook', webhook_settings)
            self.webhook_url = webhook_settings["url"]
            QMessageBox.information(self, "Success", "Webhook settings saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save Webhook settings. Details: {e}")

    def save_telegram_settings(self):
        telegram_settings = {
            "bot_token": self.bot_token_input.text().strip(),
            "chat_id": self.chat_id_input.text().strip(),
            "message_thread_id": self.message_thread_id_input.text().strip()
        }
        try:
            self.save_config_section('telegram', telegram_settings)
            self.bot_token = telegram_settings["bot_token"]
            self.chat_id = telegram_settings["chat_id"]
            self.message_thread_id = telegram_settings["message_thread_id"]
            QMessageBox.information(self, "Success", "Telegram settings saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save Telegram settings. Details: {e}")

    def save_application_settings(self):
        """
        Save application settings with improved player change handling.
        """
        new_player = self.preferred_music_player_combo.currentText()
        current_player = self.preferred_music_player
        
        # Only show confirm dialog if player is changing and we have albums
        is_changing_player = (new_player != current_player)
        has_albums = (self.album_model.rowCount() > 0)  # Use model.rowCount()
        
        if is_changing_player and has_albums:
            reply = QMessageBox.question(
                self, 'Changing Music Player',
                f"You are changing your preferred music player from {current_player} to {new_player}. "
                f"This will update all album links. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                # Revert combo box selection
                index = self.preferred_music_player_combo.findText(current_player)
                if index >= 0:
                    self.preferred_music_player_combo.setCurrentIndex(index)
                return
        
        # Save the settings
        app_settings = {
            "preferred_music_player": new_player
        }
        
        try:
            self.save_config_section('application', app_settings)
            
            # Update the player preference
            old_player = self.preferred_music_player
            self.preferred_music_player = new_player
            
            # Update links if player has changed
            if old_player != new_player and has_albums:
                try:
                    self.statusBar().showMessage(f"Updating album links for {new_player}...", 2000)
                    self.update_album_links()
                except Exception as e:
                    logging.error(f"Error updating album links: {e}")
                    QMessageBox.warning(self, "Warning", 
                                    f"Settings saved, but there was an error updating album links: {e}")
                    return
                
            QMessageBox.information(self, "Success", "Application settings saved successfully.")
            
        except Exception as e:
            logging.error(f"Failed to save application settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save application settings. Details: {e}")

    def update_album_links(self):
        """
        Update album data without displaying hyperlinks.
        Album opening is handled by the context menu instead.
        """
        # Use model for row count
        total_rows = self.album_model.rowCount()
        if total_rows == 0:
            return
            
        # Create progress dialog for large updates
        if total_rows > 50:
            progress = QProgressDialog("Updating album data...", "Cancel", 0, total_rows, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
        else:
            progress = None
        
        update_count = 0
        
        # Loop through all rows and update album data
        for row in range(total_rows):
            # Update progress
            if progress and row % 5 == 0:  # Update every 5 rows
                progress.setValue(row)
                if progress.wasCanceled():
                    break
            
            try:
                # Get the data from the model
                artist_name = self.album_model.data(self.album_model.index(row, AlbumModel.ARTIST), 
                                                Qt.ItemDataRole.DisplayRole)
                album_name = self.album_model.data(self.album_model.index(row, AlbumModel.ALBUM), 
                                                Qt.ItemDataRole.DisplayRole)
                album_id = self.album_model.data(self.album_model.index(row, AlbumModel.ALBUM), 
                                            Qt.ItemDataRole.UserRole)
                
                # Get the appropriate URL based on preferred player (but don't display it)
                if artist_name and album_name:
                    album_url = self.get_album_url(album_id, artist_name, album_name)
                    if album_url:
                        # Find the index for the album column
                        index = self.album_model.index(row, AlbumModel.ALBUM)
                        
                        # Get or create a widget for this cell - as plain text, not a hyperlink
                        widget = self.album_table.indexWidget(index)
                        
                        if isinstance(widget, QLabel):
                            # Update existing label to plain text
                            widget.setText(album_name)  # No hyperlink formatting
                            
                            # Keep the metadata for use by context menu
                            widget.album_name = album_name
                            widget.album_id = album_id
                            widget.album_url = album_url  # Store the URL for context menu use
                            widget.artist_name = artist_name
                            update_count += 1
                        else:
                            # Create a new label with plain text
                            label = QLabel(album_name)  # No hyperlink formatting
                            
                            # Style to match other text in the table
                            label.setStyleSheet("color: white; background: transparent;")
                            label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                            
                            # Store metadata for use by context menu
                            label.album_name = album_name
                            label.album_id = album_id
                            label.album_url = album_url  # Store the URL for context menu use
                            label.artist_name = artist_name
                            
                            # Use setIndexWidget to place the label in the cell
                            self.album_table.setIndexWidget(index, label)
                            update_count += 1
            except Exception as e:
                logging.error(f"Error updating album data at row {row}: {e}")
        
        # Close progress if shown
        if progress:
            progress.setValue(total_rows)
        
        logging.info(f"Updated {update_count} album entries")

    def get_access_token(self):
        """Get a valid Spotify access token with proper expiration checking"""
        # If we have a spotify_auth instance with a token, check if it's valid
        if hasattr(self, 'spotify_auth') and self.spotify_auth.access_token:
            # Check if token is expired or about to expire (within 5 minutes)
            current_time = int(time.time())
            token_expiry = getattr(self.spotify_auth, 'token_expiry', 0)
            time_to_expiry = token_expiry - current_time
            
            # Preemptively refresh token if it's about to expire
            if time_to_expiry < 300:  # Less than 5 minutes to expiry
                logging.info(f"Token expires in {time_to_expiry} seconds, refreshing")
                if self.spotify_auth.refresh_token:
                    if self.spotify_auth.refresh_access_token():
                        tokens_path = self.get_user_data_path('spotify_tokens.json')
                        self.spotify_auth.save_tokens(tokens_path)
                        return self.spotify_auth.access_token
            else:
                # Token is still valid
                return self.spotify_auth.access_token
        
        # Try loading saved tokens
        if not hasattr(self, 'spotify_auth') or not self.spotify_auth.access_token:
            self.load_spotify_tokens()
            
        if hasattr(self, 'spotify_auth') and self.spotify_auth.access_token:
            return self.spotify_auth.access_token
        
        # Try refreshing if we have a refresh token
        if hasattr(self, 'spotify_auth') and self.spotify_auth.refresh_token:
            logging.info("Attempting to refresh access token")
            if self.spotify_auth.refresh_access_token():
                tokens_path = self.get_user_data_path('spotify_tokens.json')
                self.spotify_auth.save_tokens(tokens_path)
                return self.spotify_auth.access_token
            else:
                logging.warning("Failed to refresh token, clearing invalid refresh token")
                self.spotify_auth.refresh_token = None
        
        # If in main thread, prompt for auth
        if QThread.currentThread() == QApplication.instance().thread():
            return self.show_auth_required_and_get_token()
        else:
            # In worker thread, emit signal and return None
            logging.info("Auth required from worker thread - emitting signal")
            self.auth_required_signal.emit()
            return None

    def show_auth_required_and_get_token(self):
        """Shows auth dialog and returns token if successful"""
        logging.info("Showing auth required dialog and getting token")
        reply = QMessageBox.question(
            self, "Spotify Login Required", 
            "You need to log in to Spotify to continue. Would you like to log in now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.tabs.setCurrentWidget(self.settings_tab)
            self.login_to_spotify()
            # Return the token if we got one
            if hasattr(self, 'spotify_auth') and self.spotify_auth.access_token:
                return self.spotify_auth.access_token
        
        return None

    def _refresh_token(self):
        """Worker function to refresh token"""
        if self.spotify_auth.refresh_access_token():
            tokens_path = self.get_user_data_path('spotify_tokens.json')
            self.spotify_auth.save_tokens(tokens_path)
            return True
        return False

    def on_token_refreshed(self, success):
        """Handle token refresh completion"""
        if success:
            logging.info("Spotify token refreshed successfully")
            # You might want to retry the operation that needed the token
        else:
            logging.warning("Failed to refresh Spotify token")
            # Handle failed refresh - may need to prompt for login again
            self.spotify_auth.access_token = None
            self.update_spotify_auth_status()

    def search_artist(self):
        artist_name = self.search_input.text().strip()
        if not artist_name:
            QMessageBox.warning(self, "Input Error", "Please enter an artist name.")
            logging.warning("Search attempted without an artist name")
            return

        self.artist_list.clear()
        logging.info(f"Searching for artist: {artist_name}")
        self.artist_search_worker = Worker(self._search_artist, artist_name)
        self.artist_search_worker.finished.connect(self.on_artists_fetched)
        self.artist_search_worker.start()

    def _search_artist(self, artist_name):
        access_token = self.get_access_token()
        if not access_token:
            return {"error": "Authentication required"}

        url = f"https://api.spotify.com/v1/search"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "q": artist_name,
            "type": "artist",
            "limit": 50
        }
        try:
            logging.info(f"Searching for artist: {artist_name}")
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            logging.info(f"Artist data fetched successfully for: {artist_name}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to search for artist {artist_name}: {e}")
            return {"error": str(e)}

    def on_artists_fetched(self, result):
        QApplication.restoreOverrideCursor()
        if "error" in result:
            if result["error"] == "Authentication required":
                # Don't show an error message here since we've already
                # prompted the user via the signal/slot mechanism
                logging.info("Authentication required for artist search")
                return
            else:
                logging.error(f"Error fetching artists: {result['error']}")
                QMessageBox.warning(self, "Error", f"Failed to fetch artists: {result['error']}")
                return

        artists = result.get("artists", {}).get("items", [])
        logging.info(f"Fetched {len(artists)} artists")
        self.artist_id_map.clear()
        artist_names = set()  # Keep track of artist names we've seen

        for artist in artists:
            display_name = artist['name']
            # If we've seen this artist name before, append a unique identifier (e.g., follower count)
            if display_name in artist_names:
                display_name = f"{artist['name']} ({artist['followers']['total']} followers)"
            self.artist_list.addItem(display_name)
            self.artist_id_map[display_name] = artist['id']
            artist_names.add(artist['name'])


    def display_artist_albums(self, item):
        artist_name = item.text()
        artist_id = self.artist_id_map.get(artist_name)
        if not artist_id:
            logging.error(f"Artist ID for {artist_name} not found")
            return

        self.album_list.clear()
        logging.info(f"Fetching albums for artist: {artist_name}")
        self.albums_fetch_worker = Worker(self._fetch_artist_albums, artist_id)
        self.albums_fetch_worker.finished.connect(self.on_albums_fetched)
        self.albums_fetch_worker.start()

    def _fetch_artist_albums(self, artist_id):
        access_token = self.get_access_token()
        if not access_token:
            return {"error": "Authentication required"}

        url = f"https://api.spotify.com/v1/artists/{artist_id}/albums"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "include_groups": "album,single",
            "limit": 50
        }
        try:
            logging.info(f"Fetching albums for artist ID: {artist_id}")
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            logging.info(f"Albums fetched successfully for artist ID: {artist_id}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch albums for artist_id {artist_id}: {e}")
            return {"error": str(e)}

    def on_albums_fetched(self, result):
        QApplication.restoreOverrideCursor()
        if "error" in result:
            if result["error"] == "Authentication required":
                # Don't show an error message here since we've already
                # prompted the user via the signal/slot mechanism
                logging.info("Authentication required for album fetch")
                return
            else:
                logging.error(f"Error fetching albums: {result['error']}")
                QMessageBox.warning(self, "Error", f"Failed to fetch albums: {result['error']}")
                return

        albums = result.get('items', [])
        logging.info(f"Fetched {len(albums)} albums")
        self.album_list.clear()
        self.album_id_map.clear()

        # Step 1: Group albums by name+year to detect duplicates
        albums_by_name_year = {}
        for album in albums:
            # Get release year (first 4 chars of release_date)
            year = album.get('release_date', '')[:4]
            # Create a key combining name and year
            name_year_key = f"{album['name']} - {year}"
            if name_year_key not in albums_by_name_year:
                albums_by_name_year[name_year_key] = []
            albums_by_name_year[name_year_key].append(album)
        
        # Step 2: Add items to the list, with disambiguation text for duplicates
        self.album_list.blockSignals(True)  # Block signals to minimize UI updates
        
        # Process albums in the original order to maintain the API's sort order
        for album in albums:
            year = album.get('release_date', '')[:4]
            name_year_key = f"{album['name']} - {year}"
            
            # Check if we need disambiguation (if there are multiple albums with same name+year)
            has_duplicates = len(albums_by_name_year[name_year_key]) > 1
            
            # Create appropriate display text
            if has_duplicates:
                album_type = album.get('album_type', '').title()
                display_text = f"{album['name']} - {year} ({album_type})"
            else:
                display_text = f"{album['name']} - {year}"
            
            # Add to list and map
            self.album_list.addItem(display_text)
            self.album_id_map[display_text] = album['id']
        
        self.album_list.blockSignals(False)

    def fetch_album_details(self, item):
        album_text = item.text()
        album_id = self.album_id_map.get(album_text)
        if not album_id:
            logging.error(f"Album ID for {album_text} not found")
            return
        self.fetch_album_details_by_id(album_id)

    def fetch_album_details_by_id(self, album_id: str):
        def fetch_data():
            access_token = self.get_access_token()
            if not access_token:
                logging.error("Failed to obtain access token")
                return {"error": "Failed to obtain access token"}
            
            url = f"https://api.spotify.com/v1/albums/{album_id}"
            headers = {"Authorization": f"Bearer {access_token}"}
            try:
                logging.info(f"Fetching details for album ID: {album_id}")
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                logging.info(f"Details fetched successfully for album ID: {album_id}")
                return response.json()
            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to fetch album details for album_id {album_id}: {e}")
                return {"error": str(e)}

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        if self.album_details_worker is None or not self.album_details_worker.isRunning():
            self.album_details_worker = Worker(fetch_data)
            self.album_details_worker.finished.connect(self.on_album_details_fetched)
            self.album_details_worker.start()
        else:
            logging.warning("A request is already in progress.")

    def format_date_dd_mm_yyyy(self, date_str):
        """Convert a date string from YYYY-MM-DD to DD-MM-YYYY format."""
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            return date_obj.strftime("%d-%m-%Y")
        except ValueError:
            return date_str  # Return the original string if it cannot be parsed

    def on_album_data_changed(self, topLeft, bottomRight, roles):
        """Called when the album model data changes"""
        # Update main window's dataChanged flag
        self.dataChanged = self.album_model.is_modified
        self.update_window_title()
        
        # Log the change if we have a valid index
        if topLeft.isValid():
            row = topLeft.row()
            column = topLeft.column()
            column_name = self.album_model.COLUMN_NAMES[column]
            artist = self.album_model.data(self.album_model.index(row, AlbumModel.ARTIST), Qt.ItemDataRole.DisplayRole)
            album = self.album_model.data(self.album_model.index(row, AlbumModel.ALBUM), Qt.ItemDataRole.DisplayRole)
            new_value = self.album_model.data(topLeft, Qt.ItemDataRole.DisplayRole)
            
            logging.info(f"Data changed in row {row}, column '{column_name}': '{artist}' - '{album}' set '{column_name}' to '{new_value}'")

    def on_album_details_fetched(self, result):
        QApplication.restoreOverrideCursor()
        if "error" in result:
            logging.error(result["error"])
            QMessageBox.warning(self, "Error", result["error"])
            return

        # Extract album details
        artist_name = result['artists'][0]['name'] if result['artists'] else 'Unknown Artist'
        album_name = result.get('name', 'Unknown Album')
        release_date = result.get('release_date', 'Unknown Release Date')
        album_id = result.get('id', '')

        logging.info(f"Album details fetched: '{album_name}' by '{artist_name}' released on '{release_date}'")

        # Convert release date to DD-MM-YYYY format
        release_date_formatted = self.format_date_dd_mm_yyyy(release_date)

        # Check if the album is already in the list
        is_album_in_list = False
        for row in range(self.album_model.rowCount()):
            existing_album = self.album_model.data(
                self.album_model.index(row, AlbumModel.ALBUM), 
                Qt.ItemDataRole.DisplayRole
            )
            if existing_album == album_name:
                is_album_in_list = True
                break

        if is_album_in_list:
            QMessageBox.information(self, "Album Already Added", f"The album '{album_name}' is already in the list.")
            return

        # Download and resize album cover image
        if result['images']:
            image_url = result['images'][0]['url']
            response = requests.get(image_url)
            if response.status_code == 200:
                image_data = response.content

                # Resize the image before encoding
                image = Image.open(BytesIO(image_data))
                image.thumbnail((200, 200), Image.Resampling.LANCZOS)
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                image_bytes = buffered.getvalue()
                base64_image = base64.b64encode(image_bytes).decode('utf-8')

                # Create album data dictionary with empty genre values
                album_data = {
                    "artist": artist_name,
                    "album": album_name,
                    "album_id": album_id,
                    "release_date": release_date_formatted,
                    "cover_image": base64_image,
                    "cover_image_format": "PNG",
                    "country": "Country",
                    "genre_1": "",  # Changed from "Genre 1" to empty string
                    "genre_2": "",  # Changed from "Genre 2" to empty string
                    "comments": "Comment",
                    "rank": self.album_model.rowCount() + 1,
                    "points": 1
                }

                # Add the album to the model
                self.album_model.add_album(album_data)
                
                # Set the row height for the new row
                row_index = self.album_model.rowCount() - 1
                self.album_table.setRowHeight(row_index, 100)
                
                # Get the album cell index
                album_index = self.album_model.index(row_index, AlbumModel.ALBUM)
                
                # Create a label for the album title (as plain text, not a link)
                album_label = QLabel(album_name)
                album_label.setStyleSheet("color: white; background: transparent;")
                album_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                
                # Store metadata for context menu use
                album_label.album_name = album_name
                album_label.album_id = album_id
                album_label.artist_name = artist_name
                album_label.album_url = self.get_album_url(album_id, artist_name, album_name)
                
                # Set the label as the widget for the album cell
                self.album_table.setIndexWidget(album_index, album_label)
                
                # Update the changed flags
                self.dataChanged = self.album_model.is_modified
                self.update_window_title()

                # Show the notification
                self.show_notification(f"Added album '{album_name}'")
            else:
                logging.error("Failed to download the album cover image.")

    def process_spotify_uri(self, uri: str):
        logging.info(f"Processing Spotify URI: {uri}")
        # Check if it's a valid Spotify URI for a track or an album
        if "open.spotify.com/track/" in uri:
            track_id = uri.split("track/")[1].split("?")[0]  # Extract the track ID
            logging.info(f"Detected track URI. Track ID: {track_id}")
            self.add_album_from_track(track_id)
        elif "open.spotify.com/album/" in uri:
            album_id = uri.split("album/")[1].split("?")[0]  # Extract the album ID
            logging.info(f"Detected album URI. Album ID: {album_id}")
            self.fetch_album_details_by_id(album_id)
        else:
            logging.warning(f"Unsupported Spotify URI: {uri}")
            QMessageBox.warning(self, "Unsupported URI", "The Spotify URI is not supported.")

    def get_album_url(self, album_id, artist_name, album_name):
        """
        Generate the appropriate URL for opening an album based on preferred music player.
        Includes improved validation, fallback handling, and fixed Tidal URL format.
        """
        if not artist_name or not album_name:
            logging.warning("Missing artist or album name for URL generation")
            return None

        if self.preferred_music_player == 'Spotify':
            if album_id:
                return f'spotify:album:{album_id}'
            else:
                logging.info(f"No Spotify album ID available for '{album_name}', falling back to search")
                search_term = urllib.parse.quote(f'{artist_name} {album_name}')
                return f'spotify:search:{search_term}'
        elif self.preferred_music_player == 'Tidal':
            # Updated Tidal URL format that works more reliably
            # Tidal search has changed - use a direct web search instead
            combined_term = f"{artist_name} {album_name}"
            encoded_term = urllib.parse.quote(combined_term)
            # Use the main web search which is more stable than the specialized album search
            return f'https://listen.tidal.com/search?q={encoded_term}'
        else:
            logging.warning(f"Unknown music player preference: {self.preferred_music_player}")
            # Default to a generic web search as fallback
            search_term = urllib.parse.quote(f'{artist_name} {album_name}')
            return f'https://www.google.com/search?q={search_term}+album'

    def open_album_url(self, url):
        """
        Open an album URL with improved error handling and fallbacks.
        Enhanced to better handle web URLs for both Spotify and Tidal.
        """
        if not url:
            logging.error("Attempted to open empty URL")
            QMessageBox.warning(self, "Error", "No valid URL available for this album")
            return

        logging.info(f"Opening album URL: {url}")
        
        # Handle Spotify URLs
        if url.startswith('spotify:'):
            spotify_installed = self.is_spotify_installed()
            logging.info(f"Is Spotify installed? {spotify_installed}")
            
            if spotify_installed:
                try:
                    # Try to open with the Spotify app
                    if sys.platform.startswith('win'):
                        subprocess.Popen(['start', '', url], shell=True)
                        return
                    elif sys.platform == 'darwin':
                        subprocess.call(['open', url])
                        return
                    else:
                        subprocess.call(['xdg-open', url])
                        return
                except Exception as e:
                    logging.error(f"Failed to open Spotify URI using client: {e}")
                    # Fall through to web fallback
            
            # Fallback to web if app opening fails or Spotify isn't installed
            try:
                # Convert spotify: URI to HTTP URL
                if url.startswith('spotify:album:'):
                    album_id = url.replace('spotify:album:', '')
                    web_url = f'https://open.spotify.com/album/{album_id}'
                    logging.info(f"Falling back to web URL: {web_url}")
                    QDesktopServices.openUrl(QUrl(web_url))
                    return
                elif url.startswith('spotify:search:'):
                    search_term = url.replace('spotify:search:', '')
                    web_url = f'https://open.spotify.com/search/{search_term}'
                    logging.info(f"Falling back to web URL: {web_url}")
                    QDesktopServices.openUrl(QUrl(web_url))
                    return
            except Exception as e:
                logging.error(f"Failed to open Spotify web URL: {e}")
                QMessageBox.warning(self, "Error", f"Failed to open album in Spotify: {e}")
        else:
            # Handle web URLs (Tidal, etc.)
            try:
                # For URLs that start with https://, use QDesktopServices
                if url.startswith('http://') or url.startswith('https://'):
                    logging.info(f"Opening web URL: {url}")
                    success = QDesktopServices.openUrl(QUrl(url))
                    
                    if not success:
                        # If openUrl returns False, use a fallback method
                        logging.warning("QDesktopServices.openUrl failed, trying fallback")
                        if sys.platform.startswith('win'):
                            os.startfile(url)
                        elif sys.platform == 'darwin':
                            subprocess.call(['open', url])
                        else:
                            subprocess.call(['xdg-open', url])
                else:
                    # For other URL schemes, try platform-specific methods
                    if sys.platform.startswith('win'):
                        os.startfile(url)
                    elif sys.platform == 'darwin':
                        subprocess.call(['open', url])
                    else:
                        subprocess.call(['xdg-open', url])
            except Exception as e:
                logging.error(f"Failed to open URL: {e}")
                QMessageBox.warning(self, "Error", f"Failed to open album URL: {e}")

    def is_spotify_installed(self):
        """
        Check if Spotify is installed on the system.
        """
        try:
            if sys.platform.startswith('win'):
                # Check Windows Registry
                import winreg
                try:
                    # Check both HKEY_CURRENT_USER and HKEY_LOCAL_MACHINE
                    try:
                        winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Spotify")
                        return True
                    except WindowsError:
                        try:
                            winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\Spotify")
                            return True
                        except WindowsError:
                            # Also check for Spotify.exe in common locations
                            program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
                            program_files_x86 = os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')
                            
                            paths_to_check = [
                                os.path.join(program_files, 'Spotify', 'Spotify.exe'),
                                os.path.join(program_files_x86, 'Spotify', 'Spotify.exe'),
                                os.path.join(os.environ.get('APPDATA', ''), 'Spotify', 'Spotify.exe')
                            ]
                            
                            for path in paths_to_check:
                                if os.path.exists(path):
                                    logging.info(f"Found Spotify at {path}")
                                    return True
                            
                            return False
                except Exception as e:
                    logging.warning(f"Error checking Windows registry: {e}")
                    return False
            elif sys.platform == 'darwin':
                # Check macOS Applications folder
                paths = [
                    "/Applications/Spotify.app",
                    os.path.expanduser("~/Applications/Spotify.app")
                ]
                for path in paths:
                    if os.path.exists(path):
                        return True
                return False
            else:
                # Basic check for Linux
                try:
                    result = subprocess.run(['which', 'spotify'], 
                                        stdout=subprocess.PIPE, 
                                        stderr=subprocess.PIPE)
                    return result.returncode == 0
                except Exception:
                    return False
        except Exception as e:
            logging.warning(f"Error checking if Spotify is installed: {e}")
            return False  # Assume not installed if check fails

    def add_album_from_track(self, track_id: str):
        # Fetch the track's details to get the associated album ID
        access_token = self.get_access_token()  # Assuming you have this method
        if not access_token:
            print("Failed to obtain access token")
            return

        track_url = f"https://api.spotify.com/v1/tracks/{track_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(track_url, headers=headers)
        if response.status_code == 200:
            album_id = response.json()['album']['id']
            self.fetch_album_details_by_id(album_id)  # Fetch and add the album details
        else:
            print("Failed to fetch track details")
        self.dataChanged = True
        self.update_window_title()

    def show_context_menu(self, position):
        """Show context menu for album table with improved URL handling."""
        context_menu = QMenu(self)
        remove_action = context_menu.addAction("Remove Album")
        open_album_action = context_menu.addAction("Open Album")
        
        # Make sure viewport exists before calling mapToGlobal
        viewport = self.album_table.viewport()
        if viewport:
            action = context_menu.exec(viewport.mapToGlobal(position))
        else:
            # Fallback to using the table widget's mapToGlobal directly
            action = context_menu.exec(self.album_table.mapToGlobal(position))

        if action == remove_action:
            index = self.album_table.indexAt(position)
            if index.isValid():
                # Get info for logging before removing
                row = index.row()
                artist = self.album_model.data(self.album_model.index(row, AlbumModel.ARTIST), Qt.ItemDataRole.DisplayRole)
                album = self.album_model.data(self.album_model.index(row, AlbumModel.ALBUM), Qt.ItemDataRole.DisplayRole)
                logging.info(f"Removing album '{album}' by '{artist}' from row {row}")
                
                self.remove_album(row)
        elif action == open_album_action:
            index = self.album_table.indexAt(position)
            if index.isValid():
                row = index.row()
                
                        # Try to get the URL from the widget first
                album_widget = self.album_table.indexWidget(self.album_model.index(row, AlbumModel.ALBUM))
                album_url = getattr(album_widget, 'album_url', None) # Safely get attribute

                if not album_url:
                    # Fall back to constructing the URL if widget or attribute is missing
                    album_id = self.album_model.data(self.album_model.index(row, AlbumModel.ALBUM), 
                                        Qt.ItemDataRole.UserRole)
                    artist_name = self.album_model.data(self.album_model.index(row, AlbumModel.ARTIST), 
                                                    Qt.ItemDataRole.DisplayRole)
                    album_name = self.album_model.data(self.album_model.index(row, AlbumModel.ALBUM), 
                                                    Qt.ItemDataRole.DisplayRole)
                    album_url = self.get_album_url(album_id, artist_name, album_name)
                
                if album_url:
                    self.open_album_url(album_url)
                else:
                    logging.warning(f"No URL available for album at row {row}")
                    QMessageBox.warning(self, "Cannot Open Album", 
                                    "No URL is available for this album.")

    def remove_album(self, row):
        """Remove an album from the model."""
        if self.album_model.remove_album(row):
            # Update the main window's dataChanged flag
            self.dataChanged = self.album_model.is_modified
            self.update_window_title()
            return True
        return False

    def handleCellClick(self, index):
        """Handle clicks on table cells (updated for QTableView)"""
        # With proper edit triggers set above, we don't need to manually call edit()
        # Just log the click if needed for debugging
        column = index.column()
        row = index.row()
        
        # Only log editable column clicks
        if column in [AlbumModel.COUNTRY, AlbumModel.GENRE_1, AlbumModel.GENRE_2]:
            logging.debug(f"Clicked on editable cell: row={row}, column={column}")
        
        # For album column, we might want to handle URL opening
        if column == AlbumModel.ALBUM:
            # The URL handling could go here if needed
            pass

    def trigger_save_album_data(self):
        if self.current_file_path:
            points_mapping = self.read_points_mapping(resource_path("points.json"))
            if not points_mapping:
                QMessageBox.warning(self, "Points Mapping Issue", "points.json is missing or invalid. Default points will be used.")
            self.save_album_data(self.current_file_path, points_mapping)
            self.dataChanged = False
            logging.info(f"Data saved successfully to {self.current_file_path}. dataChanged set to False.")
            
            self.statusBar().showMessage(f"Data saved to {self.current_file_path}.", 5000)
            
            # Update last opened file and recent files
            self.update_recent_files(self.current_file_path)
            self.save_settings()
        else:
            self.trigger_save_as_album_data()

    def trigger_save_as_album_data(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Album Data As", "", "JSON Files (*.json)")
        if file_path:
            if not file_path.lower().endswith('.json'):
                file_path += '.json'
            points_mapping = self.read_points_mapping(resource_path("points.json"))
            self.save_album_data(file_path, points_mapping)
            self.current_file_path = file_path
            self.dataChanged = False
            logging.debug(f"Data saved successfully to {file_path}. dataChanged set to False.")
            self.update_window_title()
            QMessageBox.information(self, "Saved", f"Data saved to {file_path}.")
            # Update last opened file and recent files
            self.update_recent_files(file_path)
            self.save_settings()
        else:
            QMessageBox.warning(self, "Save Error", "No file selected for saving.")

    def update_window_title(self):
        unsaved_indicator = "*" if self.dataChanged else ""
        if self.current_file_path:
            file_name = Path(self.current_file_path).name
            self.setWindowTitle(f"SuShe v{self.version} - {file_name}{unsaved_indicator}")
        else:
            self.setWindowTitle(f"SuShe v{self.version}{unsaved_indicator}")

    def trigger_load_album_data(self, file_path=None):
        # Check if there are unsaved changes before loading a new file
        if self.dataChanged:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                "You have unsaved changes. Do you want to save them before opening a new file?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.trigger_save_album_data()  # Save changes before proceeding
            elif reply == QMessageBox.StandardButton.Cancel:
                return  # Cancel the loading process

        # Proceed with loading the file
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(self, "Open Album Data", "", "JSON Files (*.json)")
        
        if file_path:
            self.load_album_data(file_path)
            self.current_file_path = file_path
            self.dataChanged = False  # Reset unsaved changes flag after loading
            logging.info(f"Album data loaded from {file_path}. dataChanged set to False.")
            self.update_window_title()
            QMessageBox.information(self, "Loaded", f"Data loaded from {file_path}.")
            
            # Update last opened file and recent files
            self.update_recent_files(file_path)
            self.save_settings()
        else:
            QMessageBox.warning(self, "Load Error", "No file selected for loading.")
            logging.warning("No file selected for loading.")

    def update_recent_files(self, file_path):
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:5]  # Keep only the last 5 files
        self.update_recent_files_menu()

    @staticmethod
    def read_points_mapping(file_path):
        """
        Reads the points mapping from a JSON file.

        Args:
            file_path (str): The path to the points.json file.

        Returns:
            dict: A dictionary mapping ranks to points. Returns an empty dict if the file is missing or invalid.
        """
        if not os.path.exists(file_path):
            logging.warning(f"points.json not found at {file_path}. Using default points.")
            return {}

        try:
            with open(file_path, 'r') as file:
                points_mapping = json.load(file)
            logging.info("Points mapping loaded successfully.")
            return points_mapping
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from points.json at {file_path}. Using default points.")
            return {}
        except Exception as e:
            logging.error(f"Unexpected error reading points.json at {file_path}: {e}. Using default points.")
            return {}

    def save_album_data(self, file_path, points_mapping):
        # Get album data from the model
        album_data = self.album_model.get_album_data()
        
        # Update ranks and points based on the current order
        for i, album in enumerate(album_data):
            rank = i + 1
            album["rank"] = rank
            album["points"] = points_mapping.get(str(rank), 1)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(album_data, file, indent=4)
            logging.info(f"Album data saved to {file_path}.")
            
            # Reset the changed flags
            self.album_model.is_modified = False
            self.dataChanged = False
            self.update_window_title()
        except Exception as e:
            logging.error(f"Failed to save album data to {file_path}: {e}")
            QMessageBox.critical(self, "Save Error", f"Failed to save album data: {e}")
            return

    def export_album_data_html(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to HTML", "", "HTML Files (*.html)"
        )
        if not file_path:
            return

        column_widths = {
            "No.": "5px",
            "Artist": "60px",
            "Album": "60px",
            "Release Date": "40px",
            "Cover": "40px",
            "Country": "60px",
            "Genre 1": "80px",
            "Genre 2": "80px",
            "Comments": "150px"
        }

        # Build HTML
        html_lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'>",
            "<title>Exported Albums</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; }",
            "table { border-collapse: collapse; width: 100%; table-layout: fixed; }",
            "th, td { border: 1px solid #ccc; padding: 8px; text-align: left; word-wrap: break-word; }",
            "th { background-color: #f2f2f2; }",
            "td img { display: block; margin: 0 auto; }",  # Center images in cells
            "</style>",
            "</head>",
            "<body>",
            "<h1>Album Export</h1>",
            "<table>",
            "<tr>"
        ]

        # Add table headers with defined widths, including "No."
        headers = ["No.", "Artist", "Album", "Release Date", "Cover", "Country", "Genre 1", "Genre 2", "Comments"]
        for header in headers:
            width = column_widths.get(header, "10%")
            html_lines.append(f"<th style='width:{width};'>{header}</th>")
        html_lines.append("</tr>")

        # Use the model's rowCount instead of the view's rowCount
        row_count = self.album_model.rowCount()
        
        for row in range(row_count):
            no = row + 1  # Row number starting at 1
            
            # Get data from the model instead of table items
            artist = self.album_model.data(self.album_model.index(row, AlbumModel.ARTIST), Qt.ItemDataRole.DisplayRole) or ""
            album = self.album_model.data(self.album_model.index(row, AlbumModel.ALBUM), Qt.ItemDataRole.DisplayRole) or ""
            release = self.album_model.data(self.album_model.index(row, AlbumModel.RELEASE_DATE), Qt.ItemDataRole.DisplayRole) or ""
            country = self.album_model.data(self.album_model.index(row, AlbumModel.COUNTRY), Qt.ItemDataRole.DisplayRole) or ""
            genre1 = self.album_model.data(self.album_model.index(row, AlbumModel.GENRE_1), Qt.ItemDataRole.DisplayRole) or ""
            genre2 = self.album_model.data(self.album_model.index(row, AlbumModel.GENRE_2), Qt.ItemDataRole.DisplayRole) or ""
            comments = self.album_model.data(self.album_model.index(row, AlbumModel.COMMENTS), Qt.ItemDataRole.DisplayRole) or ""

            # Get image from the model
            base64_image = self.album_model.data(self.album_model.index(row, AlbumModel.COVER_IMAGE), Qt.ItemDataRole.UserRole)
            if base64_image:
                img_tag = f'<img src="data:image/png;base64,{base64_image}" width="100" />'
            else:
                img_tag = ""

            html_lines.append("<tr>")
            html_lines.append(f"<td>{no}</td>")
            html_lines.append(f"<td>{artist}</td>")
            html_lines.append(f"<td>{album}</td>")
            html_lines.append(f"<td>{release}</td>")
            html_lines.append(f"<td>{img_tag}</td>")
            html_lines.append(f"<td>{country}</td>")
            html_lines.append(f"<td>{genre1}</td>")
            html_lines.append(f"<td>{genre2}</td>")
            html_lines.append(f"<td>{comments}</td>")
            html_lines.append("</tr>")

        html_lines.append("</table>")
        html_lines.append("</body></html>")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(html_lines))
            QMessageBox.information(self, "Export Complete", f"Exported to {file_path}")
        except Exception as e:
            logging.error(f"Failed to export to HTML: {e}")
            QMessageBox.critical(self, "Export Failed", f"Failed to export to HTML: {e}")

    def load_album_data(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                album_data = json.load(file)
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {file_path}: {e}")
            QMessageBox.critical(self, "Load Error", f"Failed to decode JSON from {file_path}.")
            return
        except Exception as e:
            logging.error(f"Unexpected error loading {file_path}: {e}")
            QMessageBox.critical(self, "Load Error", f"An unexpected error occurred: {e}")
            return

        # Load data into the model instead of using setRowCount
        self.album_model.set_album_data(album_data)
        
        # Set row heights for cover images
        for row in range(self.album_model.rowCount()):
            self.album_table.setRowHeight(row, 100)
        
        # Set the current file path and reset changed flag
        self.current_file_path = file_path
        self.dataChanged = False
        self.update_window_title()

    def close_album_data(self):
        if self.dataChanged:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                "You have unsaved changes. Do you want to save them before clearing the data?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.trigger_save_album_data()  # Save changes
            elif reply == QMessageBox.StandardButton.Cancel:
                return  # Cancel the clear action

        # Clear the model instead of using setRowCount(0)
        self.album_model.clear()
        self.dataChanged = False
        self.current_file_path = None
        self.update_window_title()

    def closeEvent(self, event):
        if self.dataChanged:
            reply = QMessageBox.question(
                self, 'Unsaved Changes',
                "You have unsaved changes. Do you want to save them before exiting?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                logging.debug("User chose to save changes before closing.")
                self.trigger_save_album_data()
            elif reply == QMessageBox.StandardButton.Cancel:
                logging.debug("User canceled the close event.")
                event.ignore()
                return
        self.save_settings()  # Save settings on close
        logging.debug("Closing the application. No unsaved changes or user chose not to save.")
        event.accept()

    def open_manual_add_album_dialog(self):
        logging.info("Opening Manual Add Album Dialog")
        dialog = ManualAddAlbumDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.dataChanged = True
            self.update_window_title()

    def add_manual_album_to_table(self, artist, album, release_date, cover_image_path, country, genre1, genre2, comments):
        """Add a manually created album to the table."""
        
        # Convert the release date to the standard format for storage
        release_date_display = release_date  # The date is already properly formatted
        
        # Process the cover image if provided
        base64_image = None
        image_format = "PNG"
        if cover_image_path:
            try:
                with open(cover_image_path, 'rb') as img_file:
                    image_data = img_file.read()
                    
                # Determine the format based on the file extension
                _, ext = os.path.splitext(cover_image_path)
                format = ext.replace('.', '').upper()  # e.g., "PNG", "WEBP"
                if format not in ["PNG", "WEBP", "JPEG", "JPG"]:
                    format = "PNG"  # Default to PNG if unsupported
                    
                # Resize the image before encoding
                image = Image.open(BytesIO(image_data))
                image.thumbnail((200, 200), Image.Resampling.LANCZOS)
                buffered = BytesIO()
                image.save(buffered, format=format)
                image_bytes = buffered.getvalue()
                base64_image = base64.b64encode(image_bytes).decode('utf-8')
                image_format = format
            except Exception as e:
                logging.error(f"Failed to process cover image: {e}")
                base64_image = None
        
        # Create album data dictionary
        album_data = {
            "artist": artist,
            "album": album,
            "album_id": "",  # No album_id for manually added albums
            "release_date": release_date_display,
            "cover_image": base64_image,
            "cover_image_format": image_format,
            "country": country,
            "genre_1": genre1,
            "genre_2": genre2,
            "comments": comments,
            "rank": self.album_model.rowCount() + 1,
            "points": 1
        }
        
        # Add the album to the model
        self.album_model.add_album(album_data)
        
        # Set the row height for the new row
        row_index = self.album_model.rowCount() - 1
        self.album_table.setRowHeight(row_index, 100)
        
        # Get the album cell index
        album_index = self.album_model.index(row_index, AlbumModel.ALBUM)
        
        # Create a label for the album title
        album_label = QLabel(album)
        album_label.setStyleSheet("color: white; background: transparent;")
        album_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        
        # Store metadata for context menu use
        album_label.album_name = album
        album_label.album_id = ""
        album_label.artist_name = artist
        album_label.album_url = self.get_album_url("", artist, album)
        
        # Set the label as the widget for the album cell
        self.album_table.setIndexWidget(album_index, album_label)
        
        # Update the changed flags
        self.dataChanged = True
        self.update_window_title()
        
        logging.info(f"Manually added album '{album}' by '{artist}' with release date '{release_date_display}'")

if __name__ == "__main__":
    text_edit_logger = setup_logging()
    
    app = QApplication([])
    
    # Set the application font to ensure support for certain characters
    app.setFont(QFont("Arial", 10))
    
    # Load and apply the stylesheet
    style_path = resource_path('style.qss')  # Use the standalone resource_path function
    if os.path.exists(style_path):
        file = QFile(style_path)
        if file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            stream = QTextStream(file)
            app.setStyleSheet(stream.readAll())
            file.close()
            logging.info("Stylesheet applied.")
        else:
            logging.error(f"Failed to open style sheet at {style_path}.")
    else:
        logging.warning(f"Style sheet not found at {style_path}.")
    
    window = SpotifyAlbumAnalyzer(text_edit_logger)
    
    # Schedule the initial update check
    QTimer.singleShot(0, window.perform_initialization)
    
    sys.exit(app.exec())