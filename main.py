from PyQt6.QtWidgets import (QDialog, QMenu, QGroupBox, QFileDialog, QComboBox, QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QListWidget, QTableWidget, QTableWidgetItem, QStyledItemDelegate, QDoubleSpinBox, QMessageBox, QTextEdit,
                             QTextBrowser, QProgressDialog, QCompleter, QAbstractItemView, QStyle, QHeaderView)
from PyQt6.QtGui import QAction, QImage, QIcon, QPixmap, QDragEnterEvent, QDropEvent, QFont, QDesktopServices, QKeyEvent, QBrush, QPalette
from PyQt6.QtCore import Qt, QFile, QTextStream, QIODevice, pyqtSignal, QThread, QTimer, QLocale, QObject, QUrl, QRectF, QPointF
from datetime import datetime
from pathlib import Path
from PIL import Image
from io import BytesIO
import requests
import logging
import base64
from functools import partial
from io import BytesIO
import os
import json
import sys
import urllib.parse
import subprocess

# Import worker classes from workers.py

from dialogs import HelpDialog, LogViewerDialog, ManualAddAlbumDialog, SubmitDialog, UpdateDialog
from workers import DownloadWorker, SubmitWorker, Worker
from image_handler import ImageWidget

def setup_logging():
    # Define the logs directory within the user's application data folder
    app_name = 'SuSheApp'
    log_dir = os.path.join(os.getenv('APPDATA'), app_name, 'logs')

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

    def handle_exception(exc_type, exc_value, exc_traceback):
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        print("Uncaught exception:", exc_type, exc_value, exc_traceback)  # Add this line
    sys.excepthook = handle_exception
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Logging setup complete")
    return text_edit_logger

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def read_file_lines(filepath):
    correct_path = resource_path(filepath)
    logging.debug(f"Reading file: {correct_path}")
    with open(correct_path, 'r') as file:
        lines = set(line.strip() for line in file)
        if 'genres.txt' in filepath:
            lines = {line.title() for line in lines}
        logging.debug(f"Read {len(lines)} lines from {filepath}")
        return sorted(lines)

def strip_html_tags(text):
    import re
    from html import unescape
    clean = re.compile('<.*?>')
    return unescape(re.sub(clean, '', text))

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
        # Flush the buffered messages to the log viewer
        for msg in self.buffer:
            self.log_viewer.append_log(msg)
        self.buffer.clear()

class CustomDoubleSpinBox(QDoubleSpinBox):
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
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        idx = editor.findText(value, Qt.MatchFlag.MatchFixedString)
        editor.setCurrentIndex(idx if idx >= 0 else -1)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

class RatingDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = CustomDoubleSpinBox(parent)
        editor.setFrame(False)
        editor.setDecimals(2)
        # Set locale to English (United States) to use dot as decimal separator
        editor.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        
        # Correctly locate and set the stylesheet for the editor
        style_sheet_path = resource_path('style.qss')
        with open(style_sheet_path, "r") as file:
            stylesheet = file.read()
            editor.setStyleSheet(stylesheet)

        return editor

    def setEditorData(self, editor, index):
        data = index.model().data(index, Qt.ItemDataRole.EditRole)
        try:
            value = float(data.replace(",", ".")) if data else 0.0
        except ValueError:
            value = 0.0
        editor.setValue(value)

    def setModelData(self, spinBox, model, index):
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
        editor.setGeometry(option.rect)

class SearchHighlightDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, highlight_color=Qt.GlobalColor.darkYellow):
        super().__init__(parent)
        self.search_text = ""
        self.highlight_color = highlight_color

    def set_search_text(self, text):
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
    def __init__(self, items, parent=None, highlight_color=Qt.GlobalColor.cyan):
        super().__init__(parent)
        self.items = items
        self.search_text = ""
        self.highlight_color = highlight_color

    def set_search_text(self, text):
        self.search_text = text.lower()
        self.parent().viewport().update()

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
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        idx = editor.findText(value, Qt.MatchFlag.MatchFixedString)
        editor.setCurrentIndex(idx if idx >= 0 else -1)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def paint(self, painter, option, index):
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

class SpotifyAlbumAnalyzer(QMainWindow):
    def __init__(self, text_edit_logger):
        super().__init__()
        self.text_edit_logger = text_edit_logger
        self.version = self.get_app_version()  # Initialize version early
        self.current_file_path = None
        self.last_opened_file = None
        self.recent_files = []
        self.client_id = None
        self.client_secret = None
        self.bot_token = None
        self.chat_id = None
        self.message_thread_id = None
        self.dataChanged = False

        # Initialize search-related variables
        self.matches = []
        self.current_match_index = -1

    def perform_initialization(self):
        # Initialize UI and other components
        self.initUI()  # Initialize UI elements before loading settings
        self.load_config()
        self.load_settings()
        self.update_recent_files_menu()
        
        if self.last_opened_file and os.path.exists(self.last_opened_file):
            self.load_album_data(self.last_opened_file)
            self.current_file_path = self.last_opened_file
            self.update_window_title()
            self.dataChanged = False

        # Perform the update check and decide whether to show the main window
        should_show = self.check_for_updates()

        if should_show:
            # Show the main window after update check is done
            self.show()
        else:
            # The user chose to download an update; exit the application
            logging.info("Exiting application after initiating update download.")

    def initUI(self):
        self.client_id = None
        self.client_secret = None
        self.dataChanged = False
        self.preferred_music_player = 'Spotify'  # Initialize with default value
        self.update_window_title()
        self.artist_id_map = {}
        self.album_id_map = {}

        # Initialize worker attributes
        self.artist_search_worker = None
        self.albums_fetch_worker = None
        self.album_details_worker = None

        self.setAcceptDrops(True)
        self.resize(1500, 800)
        self.setWindowTitle("SuShe!")
        self.setWindowIcon(QIcon(resource_path(os.path.join("logos", "logo.ico"))))

        self.setup_menu_bar()
        
        # Initialize genres and countries before setting up tabs
        self.genres = read_file_lines('genres.txt')
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

    def open_log_viewer(self):
        if not hasattr(self, 'log_viewer_dialog'):
            self.log_viewer_dialog = LogViewerDialog(self)
            # Set the log_viewer in text_edit_logger
            self.text_edit_logger.set_log_viewer(self.log_viewer_dialog)
        self.log_viewer_dialog.show()

    def load_config(self):
        config_path = resource_path('config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as file:
                    config = json.load(file)
                    # Load Spotify credentials
                    self.client_id = config.get('spotify', {}).get('client_id', '')
                    self.client_secret = config.get('spotify', {}).get('client_secret', '')
                    self.client_id_input.setText(self.client_id)
                    self.client_secret_input.setText(self.client_secret)

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

                    logging.info("Configuration loaded successfully.")
            except json.JSONDecodeError as e:
                logging.error(f"Error parsing config.json: {e}")
                QMessageBox.critical(self, "Configuration Error", "Failed to parse config.json. Please check the file format.")
        else:
            logging.warning("config.json not found. Telegram submission will not work.")
            QMessageBox.warning(self, "Configuration Missing", "config.json not found. Telegram submission will not work.")

    def check_for_updates(self):
        if not all([self.github_token, self.github_owner, self.github_repo]):
            logging.warning("GitHub credentials are missing. Update check will not proceed.")
            return True  # Proceed to show the main window

        current_version = self.version
        latest_version, download_url, release_notes_url = self.get_latest_github_release()

        if latest_version and download_url:
            from packaging import version
            if version.parse(latest_version) > version.parse(current_version):
                logging.info(f"A new version {latest_version} is available.")
                update_dialog = UpdateDialog(latest_version, current_version, release_notes_url)
                reply = update_dialog.exec()

                if reply == QDialog.DialogCode.Accepted:
                    self.download_and_install_update(download_url)
                    # User chose to download the update; do not show the main window
                    return False
                else:
                    logging.info("User chose not to update.")
        else:
            logging.error("Failed to fetch the latest release information.")

        return True  # Proceed to show the main window

    def get_latest_github_release(self):
        url = f"https://api.github.com/repos/{self.github_owner}/{self.github_repo}/releases/latest"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            release_info = response.json()
            latest_version = release_info.get('tag_name')
            release_notes_url = release_info.get('html_url')  # URL to the release page with notes
            assets = release_info.get('assets', [])
            if assets:
                # Log the names of available assets
                logging.info(f"Available assets in the release: {[asset['name'] for asset in assets]}")
                # Find the asset that matches the expected installer name
                for asset in assets:
                    if asset['name'].endswith('.exe'):
                        download_url = asset.get('url')  # Use 'url' for API endpoint
                        return latest_version, download_url, release_notes_url
                logging.error("No executable (.exe) assets found in the latest release.")
                return None, None, release_notes_url
            else:
                logging.error("No assets found in the latest release.")
                return None, None, release_notes_url
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching latest release: {e}")
            return None, None, None

    def download_and_install_update(self, download_url):
        self.progress_dialog = QProgressDialog("Downloading Update...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_download)
        self.progress_dialog.show()

        self.download_thread = QThread()
        self.download_worker = DownloadWorker(download_url, self.github_token)
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

    def setup_menu_bar(self):
        self.menu_bar = self.menuBar()
        self.file_menu = self.menu_bar.addMenu("File")
        self.add_menu_actions()
        self.help_menu = self.menu_bar.addMenu("Help")
        self.help_menu.addAction("Help").triggered.connect(self.show_help)

        # Add the About menu
        self.about_menu = self.menu_bar.addMenu("About")
        self.about_menu.addAction("About SuShe").triggered.connect(self.show_about_dialog)

        # Add 'Edit' menu with 'Find' action
        self.edit_menu = self.menu_bar.addMenu("Edit")
        find_action = QAction("Find", self)
        find_action.setShortcut("Ctrl+F")
        find_action.triggered.connect(self.show_search_bar)
        self.edit_menu.addAction(find_action)

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
            self.album_list_tab.layout().insertWidget(0, self.search_widget)
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
        self.album_table.viewport().update()

    def search_album_list(self):
        search_text = self.search_bar.text().strip().lower()
        self.search_delegate.set_search_text(search_text)
        self.genre_delegate_1.set_search_text(search_text)
        self.genre_delegate_2.set_search_text(search_text)

        self.matches = []

        if not search_text:
            self.current_match_index = -1
            return

        # Columns to search
        columns_to_search = [0, 1, 5, 6, 8]  # Artist, Album, Genre 1, Genre 2, Comments

        # Find matches
        for row in range(self.album_table.rowCount()):
            for column in columns_to_search:
                item_text = ""
                item = self.album_table.item(row, column)
                widget = self.album_table.cellWidget(row, column)

                if item:
                    item_text = item.text().lower()
                elif widget and isinstance(widget, QLabel):
                    item_text = strip_html_tags(widget.text()).lower()

                if search_text in item_text:
                    self.matches.append((row, column))

        self.current_match_index = -1
        if self.matches:
            self.goto_next_match()

    def clear_search_highlights(self):
        for row in range(self.album_table.rowCount()):
            for column in range(self.album_table.columnCount()):
                item = self.album_table.item(row, column)
                if item:
                    item.setBackground(QBrush(Qt.GlobalColor.white))

    def goto_next_match(self):
        if not self.matches:
            return
        self.current_match_index = (self.current_match_index + 1) % len(self.matches)
        row, column = self.matches[self.current_match_index]
        self.album_table.scrollToItem(self.album_table.item(row, column) or self.album_table.item(row, 0), QAbstractItemView.ScrollHint.PositionAtCenter)
        self.album_table.setCurrentCell(row, column)

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

    def add_menu_actions(self):
        save_action = self.file_menu.addAction("Save")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.trigger_save_album_data)

        save_as_action = self.file_menu.addAction("Save As...")
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.trigger_save_as_album_data)

        open_action = self.file_menu.addAction("Open")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.trigger_load_album_data)

        close_action = self.file_menu.addAction("Close File")
        close_action.setShortcut("Ctrl+W")
        close_action.triggered.connect(self.close_album_data)

        # Move the 'Recent Files' submenu to just after 'Close'
        self.recent_files_menu = self.file_menu.addMenu("Recent Files")
        self.update_recent_files_menu()

        # Add a separator between 'Close' and 'Submit via Telegram'
        self.file_menu.addSeparator()

        self.submitAction = QAction("Submit via Telegram", self)
        self.file_menu.addAction(self.submitAction)
        self.submitAction.triggered.connect(self.openSubmitDialog)

        # Add a separator between 'Submit via Telegram' and 'Add Album Manually' if desired
        # self.file_menu.addSeparator()

        self.manualAddAlbumAction = QAction("Add Album Manually", self)
        self.file_menu.addAction(self.manualAddAlbumAction)
        self.manualAddAlbumAction.triggered.connect(self.open_manual_add_album_dialog)

        log_viewer_action = QAction("View Logs", self)
        self.file_menu.addAction(log_viewer_action)
        log_viewer_action.triggered.connect(self.open_log_viewer)

        # Add a separator before 'Quit' to group it separately
        self.file_menu.addSeparator()

        # Quit action
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close_application)
        self.file_menu.addAction(quit_action)

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

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():  # Check if the drag event contains URLs
            event.acceptProposedAction()  # Accept the drag event
        else:
            event.ignore()  # Ignore the drag event if it does not contain URLs

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()  # Extract URLs from the event
        for url in urls:
            self.process_spotify_uri(url.toString())  # Process each URL

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

        self.album_table = QTableWidget()
        self.album_table.setColumnCount(9)
        self.album_table.setHorizontalHeaderLabels([
            "Artist", "Album", "Release Date", "Cover Image",
            "Country", "Genre 1", "Genre 2", "Rating", "Comments"
        ])
        layout.addWidget(self.album_table)

        # Create separate delegate instances for countries and genres
        country_delegate = ComboBoxDelegate(self.countries, self.album_table)
        self.genre_delegate_1 = GenreSearchDelegate(self.genres, self.album_table, highlight_color=Qt.GlobalColor.darkYellow)
        self.genre_delegate_2 = GenreSearchDelegate(self.genres, self.album_table, highlight_color=Qt.GlobalColor.darkYellow)
        rating_delegate = RatingDelegate(self.album_table)

        # Assign delegates to respective columns
        self.album_table.setItemDelegateForColumn(4, country_delegate)      # 'Country' column
        self.album_table.setItemDelegateForColumn(5, self.genre_delegate_1)  # 'Genre 1' column
        self.album_table.setItemDelegateForColumn(6, self.genre_delegate_2)  # 'Genre 2' column
        self.album_table.setItemDelegateForColumn(7, rating_delegate)       # 'Rating' column

        # Set the search highlight delegate for specified columns
        self.search_delegate = SearchHighlightDelegate(self.album_table, highlight_color=Qt.GlobalColor.darkYellow)
        for column in [0, 1, 8]:  # Columns to search: Artist, Album, Comments
            self.album_table.setItemDelegateForColumn(column, self.search_delegate)

        # Connect signals
        self.album_table.cellClicked.connect(self.handleCellClick)
        self.album_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.album_table.customContextMenuRequested.connect(self.show_context_menu)

        # Enable sorting
        self.album_table.setSortingEnabled(True)

        # Set the column widths here
        self.set_album_table_column_widths()

        # Set the layout for the album list tab
        self.album_list_tab.setLayout(layout)

        # Connect additional signals
        self.album_table.horizontalHeader().sortIndicatorChanged.connect(self.on_sort_order_changed)
        self.album_table.itemChanged.connect(self.on_album_item_changed)

    def on_album_item_changed(self, item):
        # Get the row and column of the changed item
        row = item.row()
        column = item.column()
        column_name = self.album_table.horizontalHeaderItem(column).text()
        new_value = item.text()

        # Get the artist and album name for context
        artist = self.album_table.item(row, 0).text() if self.album_table.item(row, 0) else ""
        album = self.album_table.item(row, 1).text() if self.album_table.item(row, 1) else ""

        logging.info(f"Data changed in row {row}, column '{column_name}': '{artist}' - '{album}' set '{column_name}' to '{new_value}'")

        self.dataChanged = True
        self.update_window_title()

    def on_sort_order_changed(self, column, order):
        column_name = self.album_table.horizontalHeaderItem(column).text()
        order_str = 'ascending' if order == Qt.SortOrder.AscendingOrder else 'descending'
        logging.info(f"Album table sorted by column '{column_name}' in {order_str} order")

    def set_album_table_column_widths(self):
        # Set the desired column widths
        self.album_table.setColumnWidth(0, 130)  # "Artist" column
        self.album_table.setColumnWidth(1, 200)  # "Album" column
        self.album_table.setColumnWidth(2, 100)  # "Release Date" column
        self.album_table.setColumnWidth(3, 100)  # "Cover Image" column (adjusted width)
        self.album_table.setColumnWidth(4, 150)  # "Country" column
        self.album_table.setColumnWidth(5, 170)  # "Genre 1" column
        self.album_table.setColumnWidth(6, 170)  # "Genre 2" column
        self.album_table.setColumnWidth(7, 65)   # "Rating" column
        self.album_table.setColumnWidth(8, 340)  # "Comments" column

        # Set fixed column sizes
        header = self.album_table.horizontalHeader()
        for i in range(self.album_table.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)

    def set_static_row_heights(self):
        for row in range(self.album_table.rowCount()):
            self.album_table.setRowHeight(row, 100)  # Adjust the row height as needed

    def setup_settings_tab(self):
        layout = QVBoxLayout()

        # Existing Spotify API Credentials Help GroupBox
        info_group_box = QGroupBox("Spotify API Credentials Help")
        info_group_box_layout = QVBoxLayout()

        # Information text
        info_text = QLabel("Enter your Spotify API credentials below. You can obtain these credentials by registering your application in the Spotify Developer Dashboard.")
        info_text.setWordWrap(True)
        info_group_box_layout.addWidget(info_text)
        
        # Spotify documentation link
        link_text = '<a href="https://developer.spotify.com/documentation/web-api/tutorials/getting-started">Creating your own credentials</a>'
        link_label = QLabel(link_text)
        link_label.setOpenExternalLinks(True)
        info_group_box_layout.addWidget(link_label)

        info_group_box.setLayout(info_group_box_layout)
        layout.addWidget(info_group_box)
        
        layout.addSpacing(30)

        # Spotify Credentials GroupBox
        spotify_credentials_group_box = QGroupBox("Spotify API Credentials")
        spotify_credentials_layout = QVBoxLayout()
        spotify_credentials_layout.setContentsMargins(10, 10, 10, 10)

        # Client ID input
        client_id_label = QLabel("Client ID:")
        spotify_credentials_layout.addWidget(client_id_label)
        self.client_id_input = QLineEdit()
        spotify_credentials_layout.addWidget(self.client_id_input)

        # Client Secret input
        client_secret_label = QLabel("Client Secret:")
        spotify_credentials_layout.addWidget(client_secret_label)
        self.client_secret_input = QLineEdit()
        spotify_credentials_layout.addWidget(self.client_secret_input)

        # Save Spotify Settings Button
        save_spotify_button = QPushButton("Save Spotify Settings")
        spotify_credentials_layout.addWidget(save_spotify_button)
        save_spotify_button.clicked.connect(self.save_credentials)

        spotify_credentials_group_box.setLayout(spotify_credentials_layout)
        layout.addWidget(spotify_credentials_group_box)

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

    def save_credentials(self):
        spotify_settings = {
            "client_id": self.client_id_input.text().strip(),
            "client_secret": self.client_secret_input.text().strip()
        }
        try:
            self.save_config_section('spotify', spotify_settings)
            self.client_id = spotify_settings["client_id"]
            self.client_secret = spotify_settings["client_secret"]
            QMessageBox.information(self, "Success", "Spotify settings saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save Spotify settings. Details: {e}")

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
        preferred_music_player = self.preferred_music_player_combo.currentText()
        app_settings = {
            "preferred_music_player": preferred_music_player
        }
        try:
            self.save_config_section('application', app_settings)
            self.preferred_music_player = preferred_music_player
            self.update_album_links()
            QMessageBox.information(self, "Success", "Application settings saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save application settings. Details: {e}")

    def update_album_links(self):
        for row in range(self.album_table.rowCount()):
            # Get the album label widget
            album_label = self.album_table.cellWidget(row, 1)
            if album_label and isinstance(album_label, QLabel):
                album_name = album_label.album_name
                album_id = album_label.album_id
                artist_name = album_label.artist_name
                # Get the new album URL based on the preferred music player
                album_url = self.get_album_url(album_id, artist_name, album_name)
                # Update the label's text
                album_label.setText(f'<a href="{album_url}">{album_name}</a>')

    def get_access_token(self):
        if not self.client_id or not self.client_secret:
            logging.error("Client ID or Client Secret is missing")
            return None

        url = "https://accounts.spotify.com/api/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }

        try:
            logging.info("Requesting access token from Spotify")
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            logging.info("Access token obtained successfully")
            return token_data.get('access_token')
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to obtain access token: {e}")
            return None

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
            return {"error": "Failed to obtain access token"}

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
            logging.error(f"Error fetching artists: {result['error']}")
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
            return {"error": "Failed to obtain access token"}

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
            logging.error(f"Error fetching albums: {result['error']}")
            return

        albums = result.get('items', [])
        logging.info(f"Fetched {len(albums)} albums")
        self.album_list.clear()
        self.album_id_map.clear()

        self.album_list.blockSignals(True)  # Block signals to minimize UI updates
        for album in albums:
            display_text = f"{album['name']} - {album['release_date'][:4]}"
            self.album_list.addItem(display_text)
            self.album_id_map[display_text] = album['id']
        self.album_list.blockSignals(False)  # Unblock signals after updates

    def _fetch_album_details(self, album_id):
        access_token = self.get_access_token()
        if not access_token:
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

    def on_album_details_fetched(self, result):
        QApplication.restoreOverrideCursor()
        if "error" in result:
            logging.error(result["error"])
            QMessageBox.warning(self, "Error", result["error"])
            return

        # Extract album details
        main_artist_name = result['artists'][0]['name'] if result['artists'] else 'Unknown Artist'
        album_name = result.get('name', 'Unknown Album')
        release_date = result.get('release_date', 'Unknown Release Date')
        album_id = result.get('id', '')

        logging.info(f"Album details fetched: '{album_name}' by '{main_artist_name}' released on '{release_date}'")

        # Convert release date to DD-MM-YYYY format
        release_date_formatted = self.format_date_dd_mm_yyyy(release_date)

        # Check if the album is already in the list
        is_album_in_list = False
        for row in range(self.album_table.rowCount()):
            existing_album_label = self.album_table.cellWidget(row, 1)
            if existing_album_label and existing_album_label.album_name == album_name:
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
                image.thumbnail((200, 200), Image.LANCZOS)  # Resize while keeping aspect ratio
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                image_bytes = buffered.getvalue()
                base64_image = base64.b64encode(image_bytes).decode('utf-8')

                # Create QPixmap from image bytes
                qt_image = QImage.fromData(image_bytes)
                pixmap = QPixmap.fromImage(qt_image)

                # Add album details to the table
                row_position = self.album_table.rowCount()
                self.album_table.insertRow(row_position)
                self.album_table.setItem(row_position, 0, QTableWidgetItem(main_artist_name))

                # Create QLabel with hyperlink for the album name
                album_label = QLabel()
                album_url = self.get_album_url(album_id, main_artist_name, album_name)
                album_label.setText(f'<a href="{album_url}">{album_name}</a>')
                album_label.setOpenExternalLinks(False)
                album_label.linkActivated.connect(self.open_album_url)
                album_label.album_name = album_name
                album_label.album_id = album_id
                album_label.artist_name = main_artist_name

                self.album_table.setCellWidget(row_position, 1, album_label)

                self.album_table.setItem(row_position, 2, QTableWidgetItem(release_date_formatted))

                # Display cover image in table using ImageWidget
                image_widget = ImageWidget(pixmap)
                image_widget.base64_image = base64_image  # Store base64 image for saving
                self.album_table.setCellWidget(row_position, 3, image_widget)
                self.album_table.setRowHeight(row_position, 100)

                # Add placeholder/default values for the rest of the columns
                default_country = "Country"
                default_genre_1 = "Genre 1"
                default_genre_2 = "Genre 2"
                default_comments = "Comment"
                default_rating = "0.00"

                self.album_table.setItem(row_position, 4, QTableWidgetItem(default_country))
                self.album_table.setItem(row_position, 5, QTableWidgetItem(default_genre_1))
                self.album_table.setItem(row_position, 6, QTableWidgetItem(default_genre_2))
                self.album_table.setItem(row_position, 7, QTableWidgetItem(default_rating))
                self.album_table.setItem(row_position, 8, QTableWidgetItem(default_comments))

                self.dataChanged = True  # Set flag to True when album details are fetched and added
                self.update_window_title()
                # Set column widths after adding data
                self.set_album_table_column_widths()

                # Show the notification without the image path
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
        if self.preferred_music_player == 'Spotify':
            if album_id:
                return f'spotify:album:{album_id}'
            else:
                search_term = urllib.parse.quote(f'{artist_name} {album_name}')
                return f'spotify:search:{search_term}'
        elif self.preferred_music_player == 'Tidal':
            # Combine album name and artist name
            search_term = f'{album_name} {artist_name}'
            # URL-encode the search term
            encoded_search_term = urllib.parse.quote(search_term)
            # Construct the Tidal search URL
            return f'https://listen.tidal.com/search/albums?q={encoded_search_term}'
        else:
            return None

    def open_album_url(self, url):
        logging.info(f"Opening album URL: {url}")
        if url.startswith('spotify:'):
            try:
                if sys.platform.startswith('win'):
                    os.startfile(url)
                elif sys.platform == 'darwin':
                    subprocess.call(['open', url])
                else:
                    subprocess.call(['xdg-open', url])
            except Exception as e:
                logging.error(f"Failed to open Spotify URI: {e}")
                QMessageBox.warning(self, "Error", f"Failed to open Spotify URI: {e}")
        else:
            QDesktopServices.openUrl(QUrl(url))

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
        context_menu = QMenu(self)
        remove_action = context_menu.addAction("Remove Album")
        action = context_menu.exec(self.album_table.viewport().mapToGlobal(position))

        if action == remove_action:
            index = self.album_table.indexAt(position)
            if index.isValid():
                self.remove_album(index.row())

    def remove_album(self, row):
        # Verify if the row is within valid range before attempting to remove
        if 0 <= row < self.album_table.rowCount():
            artist = self.album_table.item(row, 0).text() if self.album_table.item(row, 0) else ""
            album = self.album_table.item(row, 1).text() if self.album_table.item(row, 1) else ""
            logging.info(f"Removing album '{album}' by '{artist}' from row {row}")
            self.album_table.removeRow(row)
            self.dataChanged = True
            self.update_window_title()

    def handleCellClick(self, row, column):
        if column in [5, 6, 4]:  # Adjust column indexes
            index = self.album_table.model().index(row, column)
            self.album_table.edit(index)

    def trigger_save_album_data(self):
        if self.current_file_path:
            points_mapping = self.read_points_mapping(resource_path("points.json"))
            if not points_mapping:
                QMessageBox.warning(self, "Points Mapping Issue", "points.json is missing or invalid. Default points will be used.")
            self.save_album_data(self.current_file_path, points_mapping)
            self.dataChanged = False
            logging.info(f"Data saved successfully to {self.current_file_path}. dataChanged set to False.")
            
            # Correct the reference to statusBar()
            self.statusBar().showMessage(f"Data saved to {self.current_file_path}.", 5000)
            
            QMessageBox.information(self, "Saved", f"Data saved to {self.current_file_path}.")
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
        album_data = []
        for row in range(self.album_table.rowCount()):
            rank = row + 1  # Rank is determined by the row position + 1
            points = points_mapping.get(str(rank), 1)  # Use mapping to get points, default to 1 if rank is not in mapping

            artist = self.album_table.item(row, 0).text() if self.album_table.item(row, 0) else ""

            album_label = self.album_table.cellWidget(row, 1)
            if album_label and isinstance(album_label, QLabel):
                album_name = album_label.album_name
                album_id = album_label.album_id
            else:
                album_name = self.album_table.item(row, 1).text() if self.album_table.item(row, 1) else ""
                album_id = ''

            release_date = self.album_table.item(row, 2).text() if self.album_table.item(row, 2) else ""

            row_data = {
                "artist": artist,
                "album": album_name,
                "album_id": album_id,
                "release_date": release_date,
                "cover_image": None,  # Will be set below
                "country": self.album_table.item(row, 4).text() if self.album_table.item(row, 4) else "",
                "genre_1": self.album_table.item(row, 5).text() if self.album_table.item(row, 5) else "",
                "genre_2": self.album_table.item(row, 6).text() if self.album_table.item(row, 6) else "",
                "rating": self.album_table.item(row, 7).text() if self.album_table.item(row, 7) else "",
                "comments": self.album_table.item(row, 8).text() if self.album_table.item(row, 8) else "",
                "rank": rank,  # Include "Rank"
                "points": points,  # Include "Points"
            }

            # Retrieve the base64 image from the ImageWidget
            image_widget = self.album_table.cellWidget(row, 3)
            if image_widget and hasattr(image_widget, 'base64_image'):
                row_data["cover_image"] = image_widget.base64_image
            else:
                row_data["cover_image"] = None

            album_data.append(row_data)

        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(album_data, file, indent=4)

        # Reset the dataChanged flag after saving
        self.dataChanged = False
        self.update_window_title()
        logging.debug(f"Album data saved to {file_path}. dataChanged set to False.")


    def load_album_data(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            album_data = json.load(file)

        self.album_table.blockSignals(True)  # Block signals before changing the table
        self.album_table.setRowCount(0)
        for row_data in album_data:
            row_pos = self.album_table.rowCount()
            self.album_table.insertRow(row_pos)

            self.album_table.setItem(row_pos, 0, QTableWidgetItem(row_data["artist"]))

            album_name = row_data["album"]
            album_id = row_data.get("album_id", "")
            artist_name = row_data["artist"]
            album_url = self.get_album_url(album_id, artist_name, album_name)

            album_label = QLabel()
            album_label.setText(f'<a href="{album_url}">{album_name}</a>')
            album_label.setOpenExternalLinks(False)
            album_label.linkActivated.connect(self.open_album_url)
            album_label.album_name = album_name
            album_label.album_id = album_id
            album_label.artist_name = artist_name

            self.album_table.setCellWidget(row_pos, 1, album_label)

            self.album_table.setItem(row_pos, 2, QTableWidgetItem(row_data["release_date"]))

            # Handle cover image decoding
            base64_image = row_data.get("cover_image")
            if base64_image:
                image_bytes = base64.b64decode(base64_image)
                qt_image = QImage.fromData(image_bytes)
                pixmap = QPixmap.fromImage(qt_image)

                # Create ImageWidget and set it in the table
                image_widget = ImageWidget(pixmap)
                image_widget.base64_image = base64_image  # Store base64 image for saving
                self.album_table.setCellWidget(row_pos, 3, image_widget)
                self.album_table.setRowHeight(row_pos, 100)
            else:
                self.album_table.setItem(row_pos, 3, QTableWidgetItem())

            self.album_table.setItem(row_pos, 4, QTableWidgetItem(row_data["country"]))
            self.album_table.setItem(row_pos, 5, QTableWidgetItem(row_data["genre_1"]))
            self.album_table.setItem(row_pos, 6, QTableWidgetItem(row_data["genre_2"]))
            self.album_table.setItem(row_pos, 7, QTableWidgetItem(row_data["rating"]))
            self.album_table.setItem(row_pos, 8, QTableWidgetItem(row_data["comments"]))

        # Set column widths after loading data
        self.set_album_table_column_widths()
        self.set_static_row_heights()
        self.album_table.blockSignals(False)

        self.album_table.sortItems(7, Qt.SortOrder.DescendingOrder)

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

        self.album_table.setRowCount(0)
        self.dataChanged = False  # Reset flag after clearing data
        self.current_file_path = None  # Reset current file path
        self.update_window_title()  # Update window title

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

    def add_manual_album_to_table(self, artist, album, release_date, cover_image_path, country, genre1, genre2, rating, comments):
        self.album_table.blockSignals(True)
        # Convert the release date to DD-MM-YYYY format for display
        release_date_display = self.format_date_dd_mm_yyyy(release_date)

        row_position = self.album_table.rowCount()
        self.album_table.insertRow(row_position)

        self.album_table.setItem(row_position, 0, QTableWidgetItem(artist))

        album_label = QLabel()
        album_label.album_name = album
        album_label.artist_name = artist
        album_label.album_id = ''  # No album_id for manually added albums
        album_url = self.get_album_url('', artist, album)
        album_label.setText(f'<a href="{album_url}">{album}</a>')
        album_label.setOpenExternalLinks(False)
        album_label.linkActivated.connect(self.open_album_url)
        self.album_table.setCellWidget(row_position, 1, album_label)

        self.album_table.setItem(row_position, 2, QTableWidgetItem(release_date_display))

        if cover_image_path:
            pixmap = QPixmap(cover_image_path)
            # Resize pixmap if necessary
            pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

            # Convert pixmap to base64
            buffered = BytesIO()
            image = pixmap.toImage()
            image.save(buffered, "PNG")
            image_bytes = buffered.getvalue()
            base64_image = base64.b64encode(image_bytes).decode('utf-8')

            # Create ImageWidget and set it in the table
            image_widget = ImageWidget(pixmap)
            image_widget.base64_image = base64_image
            self.album_table.setCellWidget(row_position, 3, image_widget)
            self.album_table.setRowHeight(row_position, 100)
        else:
            self.album_table.setItem(row_position, 3, QTableWidgetItem())

        self.album_table.setItem(row_position, 4, QTableWidgetItem(country))
        self.album_table.setItem(row_position, 5, QTableWidgetItem(genre1))
        self.album_table.setItem(row_position, 6, QTableWidgetItem(genre2))
        self.album_table.setItem(row_position, 7, QTableWidgetItem(rating))
        self.album_table.setItem(row_position, 8, QTableWidgetItem(comments))
        self.album_table.blockSignals(False)  # Unblock signals
        self.dataChanged = True
        self.update_window_title()

        logging.info(f"Manually added album '{album}' by '{artist}' with release date '{release_date_display}'")

if __name__ == "__main__":
    print("Starting application...")
    text_edit_logger = setup_logging()
    print("Logging initialized.")

    app = QApplication([])
    print("QApplication created.")

    # Set the application font to ensure support for certain characters
    app.setFont(QFont("Arial", 10))
    print("Font set.")

    # Load and apply the stylesheet
    style_path = resource_path('style.qss')  # Use the standalone resource_path function
    if os.path.exists(style_path):
        print(f"Stylesheet found at {style_path}.")
        file = QFile(style_path)
        if file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            stream = QTextStream(file)
            app.setStyleSheet(stream.readAll())
            file.close()
            print("Stylesheet applied.")
        else:
            logging.error(f"Failed to open style sheet at {style_path}.")
            print(f"Failed to open style sheet at {style_path}.")
    else:
        logging.warning(f"Style sheet not found at {style_path}.")
        print(f"Style sheet not found at {style_path}.")

    print("Creating main window...")
    window = SpotifyAlbumAnalyzer(text_edit_logger)
    print("Main window created but not shown yet.")

    # Schedule the initial update check
    QTimer.singleShot(0, window.perform_initialization)

    sys.exit(app.exec())