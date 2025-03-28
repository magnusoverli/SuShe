# main.py

from PyQt6.QtWidgets import (QDialog, QMenu, QGroupBox, QFileDialog, QComboBox, QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QListWidget, QTableWidget, QTableWidgetItem, QMessageBox,
                             QProgressDialog, QAbstractItemView, QHeaderView)
from PyQt6.QtGui import QAction, QImage, QIcon, QPixmap, QDragEnterEvent, QDropEvent, QFont, QDesktopServices, QBrush
from PyQt6.QtCore import (Qt, QFile, QTextStream, QIODevice, pyqtSignal, QThread, QTimer, QObject, QUrl)
from datetime import datetime
from pathlib import Path
from PIL import Image
from io import BytesIO
import requests
import logging
import base64
from functools import partial
import os
import json
import sys
import urllib.parse
import subprocess

# Import worker classes from workers.py

from dialogs import HelpDialog, LogViewerDialog, ManualAddAlbumDialog, SubmitDialog, UpdateDialog, SendGenreDialog
from workers import DownloadWorker, SubmitWorker, Worker
from image_handler import ImageWidget
from menu_bar import MenuBar

from delegates import (
    ComboBoxDelegate, RatingDelegate, SearchHighlightDelegate, GenreSearchDelegate, strip_html_tags
)

def handle_exception(exc_type, exc_value, exc_traceback):
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    print("Uncaught exception:", exc_type, exc_value, exc_traceback)  # Print to console for debugging

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

    # Set global exception handler
    sys.excepthook = handle_exception

    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Logging setup complete")

    # Suppress Pillow's debug logs
    logging.getLogger('PIL').setLevel(logging.WARNING)

    return text_edit_logger

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
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

        # Initialize search-related variables
        self.matches = []
        self.current_match_index = -1

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

        # Perform the update check and decide whether to show the main window
        should_show = self.check_for_updates()

        if should_show:
            # Show the main window after update check is done
            self.show()
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
        self.resize(1500, 800)
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

    def create_action(self, name, shortcut=None, triggered=None, icon_path=None):
        action = QAction(name, self)
        if shortcut:
            action.setShortcut(shortcut)
        if triggered:
            action.triggered.connect(triggered)
        if icon_path:
            action.setIcon(QIcon(resource_path(icon_path)))
        return action

    def open_log_viewer(self):
        if not hasattr(self, 'log_viewer_dialog'):
            self.log_viewer_dialog = LogViewerDialog(self)
            # Set the log_viewer in text_edit_logger
            self.text_edit_logger.set_log_viewer(self.log_viewer_dialog)
        self.log_viewer_dialog.show()

    def load_config(self):
        config_path = self.get_user_data_path('config.json')
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
                    # **Update the UI field with the loaded webhook URL**
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
            logging.warning("config.json not found. Telegram submission will not work.")
            # **Create config.json from template**
            template_path = resource_path('config_template.json')
            try:
                with open(template_path, 'r') as template_file:
                    default_config = json.load(template_file)
                with open(config_path, 'w') as config_file:
                    json.dump(default_config, config_file, indent=4)
                logging.info("Default config.json created from template.")

                # **Show a single QMessageBox with options**
                msg_box = QMessageBox(self)
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setWindowTitle("Configuration Missing")
                msg_box.setText("No configuration file found. A default config.json has been created from the template.")
                msg_box.setInformativeText("You can input the required values in the Settings tab or import an existing config.")

                # **Add buttons to the dialog**
                go_to_settings_button = msg_box.addButton("Go to Settings", QMessageBox.ButtonRole.AcceptRole)
                import_config_button = msg_box.addButton("Import Config", QMessageBox.ButtonRole.ActionRole)
                cancel_button = msg_box.addButton(QMessageBox.StandardButton.Cancel)

                # **Execute the dialog and handle user response**
                msg_box.exec()

                if msg_box.clickedButton() == go_to_settings_button:
                    # **Navigate to the Settings tab**
                    self.tabs.setCurrentWidget(self.settings_tab)
                elif msg_box.clickedButton() == import_config_button:
                    # **Open the Import Config dialog**
                    self.import_config()
                else:
                    # **User chose to cancel or closed the dialog**
                    pass
            except Exception as e:
                logging.error(f"Failed to create default config.json: {e}")
                QMessageBox.critical(self, "Configuration Error", f"Failed to create default config.json: {e}")

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
        """Initiate Spotify login flow"""
        # Default client ID embedded in app
        default_client_id = "2241ba6e592a4d60aa18c81a8507f0b3"  # Replace with your client ID
        
        if not hasattr(self, 'spotify_auth'):
            from spotify_auth import SpotifyAuth
            self.spotify_auth = SpotifyAuth(default_client_id)
        
        # Show a progress dialog while waiting for auth
        progress = QProgressDialog("Waiting for Spotify login...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Spotify Authentication")
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        # Start auth flow
        self.spotify_auth.start_auth_flow()
        
        # Wait for auth code
        max_wait_time = 120  # seconds
        auth_complete = False
        
        for _ in range(max_wait_time * 10):  # Check every 100ms
            QApplication.processEvents()
            if self.spotify_auth.auth_code:
                auth_complete = True
                break
            QThread.msleep(100)
        
        progress.close()
        
        if not auth_complete:
            QMessageBox.warning(self, "Authentication Timeout", 
                            "Spotify authentication timed out. Please try again.")
            return
        
        # Exchange code for tokens
        if self.spotify_auth.exchange_code_for_tokens():
            # Save tokens to user data folder
            tokens_path = self.get_user_data_path('spotify_tokens.json')
            self.spotify_auth.save_tokens(tokens_path)
            self.update_spotify_auth_status()
            QMessageBox.information(self, "Success", "Successfully logged in to Spotify.")
        else:
            QMessageBox.warning(self, "Authentication Failed", 
                            "Failed to obtain access tokens. Please try again.")

    def logout_from_spotify(self):
        """Log out from Spotify"""
        if hasattr(self, 'spotify_auth'):
            self.spotify_auth.access_token = None
            self.spotify_auth.refresh_token = None
            
            # Remove saved tokens
            tokens_path = self.get_user_data_path('spotify_tokens.json')
            if os.path.exists(tokens_path):
                try:
                    os.remove(tokens_path)
                except Exception as e:
                    logging.error(f"Failed to remove token file: {e}")
            
            self.update_spotify_auth_status()
            QMessageBox.information(self, "Logged Out", "Successfully logged out from Spotify.")

    def load_spotify_tokens(self):
        """Load saved Spotify tokens on startup"""
        tokens_path = self.get_user_data_path('spotify_tokens.json')
        
        if os.path.exists(tokens_path):
            # Default client ID embedded in app
            default_client_id = "YOUR_DEFAULT_CLIENT_ID"  # Replace with your client ID
            
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
        """Get a valid Spotify access token"""
        # If we have a spotify_auth instance with a token, use it
        if hasattr(self, 'spotify_auth') and self.spotify_auth.access_token:
            return self.spotify_auth.access_token
        
        # Try loading saved tokens
        if not hasattr(self, 'spotify_auth'):
            self.load_spotify_tokens()
            
        if hasattr(self, 'spotify_auth') and self.spotify_auth.access_token:
            return self.spotify_auth.access_token
        
        # Try refreshing the token if we have a refresh token
        if hasattr(self, 'spotify_auth') and self.spotify_auth.refresh_token:
            if self.spotify_auth.refresh_access_token():
                tokens_path = self.get_user_data_path('spotify_tokens.json')
                self.spotify_auth.save_tokens(tokens_path)
                return self.spotify_auth.access_token
        
        # If we get here, we need user to log in
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
            existing_album_item = self.album_table.item(row, 1)
            if existing_album_item and existing_album_item.text() == album_name:
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

                # Use QTableWidgetItem for the album name
                album_item = QTableWidgetItem(album_name)
                album_item.setData(Qt.ItemDataRole.UserRole, album_id)  # Store album_id in UserRole
                self.album_table.setItem(row_position, 1, album_item)

                self.album_table.setItem(row_position, 2, QTableWidgetItem(release_date_formatted))

                image_widget = ImageWidget(parent=self.album_table)
                self.album_table.setCellWidget(row_position, 3, image_widget)
                image_widget.setImageAsync(image_data=image_data, size=(200, 200), format="PNG")
                image_widget.base64_image = base64_image  # Store base64 image for saving
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
        open_album_action = context_menu.addAction("Open Album")  # Add "Open Album" option
        action = context_menu.exec(self.album_table.viewport().mapToGlobal(position))

        if action == remove_action:
            index = self.album_table.indexAt(position)
            if index.isValid():
                self.remove_album(index.row())
        elif action == open_album_action:  # Handle "Open Album" action
            index = self.album_table.indexAt(position)
            if index.isValid():
                album_item = self.album_table.item(index.row(), 1)
                if album_item:
                    album_id = album_item.data(Qt.ItemDataRole.UserRole)
                    artist_name = self.album_table.item(index.row(), 0).text()
                    album_name = album_item.text()
                    album_url = self.get_album_url(album_id, artist_name, album_name)
                    self.open_album_url(album_url)

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
        album_data = []
        for row in range(self.album_table.rowCount()):
            rank = row + 1  # Rank is determined by the row position + 1
            points = points_mapping.get(str(rank), 1)  # Use mapping to get points, default to 1 if rank is not in mapping

            artist = self.album_table.item(row, 0).text() if self.album_table.item(row, 0) else ""

            album_item = self.album_table.item(row, 1)
            if album_item:
                album_name = album_item.text()
                album_id = album_item.data(Qt.ItemDataRole.UserRole)
            else:
                album_name = ""
                album_id = ""

            release_date = self.album_table.item(row, 2).text() if self.album_table.item(row, 2) else ""

            row_data = {
                "artist": artist,
                "album": album_name,
                "album_id": album_id,
                "release_date": release_date,
                "cover_image": None,  # Will be set below
                "cover_image_format": None,  # New key for image format
                "country": self.album_table.item(row, 4).text() if self.album_table.item(row, 4) else "",
                "genre_1": self.album_table.item(row, 5).text() if self.album_table.item(row, 5) else "",
                "genre_2": self.album_table.item(row, 6).text() if self.album_table.item(row, 6) else "",
                "rating": self.album_table.item(row, 7).text() if self.album_table.item(row, 7) else "",
                "comments": self.album_table.item(row, 8).text() if self.album_table.item(row, 8) else "",
                "rank": rank,  # Include "Rank"
                "points": points,  # Include "Points"
            }

            # Retrieve the base64 image and its format from the ImageWidget
            image_widget = self.album_table.cellWidget(row, 3)
            if image_widget and hasattr(image_widget, 'base64_image') and image_widget.base64_image:
                row_data["cover_image"] = image_widget.base64_image
                row_data["cover_image_format"] = image_widget.image_processor.format  # Store the format
            else:
                row_data["cover_image"] = None
                row_data["cover_image_format"] = None

            album_data.append(row_data)

        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(album_data, file, indent=4)
            logging.info(f"Album data saved to {file_path}.")
        except Exception as e:
            logging.error(f"Failed to save album data to {file_path}: {e}")
            QMessageBox.critical(self, "Save Error", f"Failed to save album data: {e}")
            return

        # Reset the dataChanged flag after saving
        self.dataChanged = False
        self.update_window_title()
        logging.debug(f"Album data saved to {file_path}. dataChanged set to False.")

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
            "Rating": "20px",
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
        headers = ["No.", "Artist", "Album", "Release Date", "Cover", "Country", "Genre 1", "Genre 2", "Rating", "Comments"]
        for header in headers:
            width = column_widths.get(header, "10%")
            html_lines.append(f"<th style='width:{width};'>{header}</th>")
        html_lines.append("</tr>")

        for row in range(self.album_table.rowCount()):
            no = row + 1  # Row number starting at 1
            artist = self.album_table.item(row, 0).text() if self.album_table.item(row, 0) else ""
            album = self.album_table.item(row, 1).text() if self.album_table.item(row, 1) else ""
            release = self.album_table.item(row, 2).text() if self.album_table.item(row, 2) else ""
            country = self.album_table.item(row, 4).text() if self.album_table.item(row, 4) else ""
            genre1 = self.album_table.item(row, 5).text() if self.album_table.item(row, 5) else ""
            genre2 = self.album_table.item(row, 6).text() if self.album_table.item(row, 6) else ""
            rating = self.album_table.item(row, 7).text() if self.album_table.item(row, 7) else ""
            comments = self.album_table.item(row, 8).text() if self.album_table.item(row, 8) else ""

            image_widget = self.album_table.cellWidget(row, 3)
            if image_widget and hasattr(image_widget, 'base64_image') and image_widget.base64_image:
                img_tag = f'<img src="data:image/png;base64,{image_widget.base64_image}" width="100" />'
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
            html_lines.append(f"<td>{rating}</td>")
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

        self.album_table.blockSignals(True)  # Block signals before changing the table
        self.album_table.setRowCount(0)
        for row_data in album_data:
            row_pos = self.album_table.rowCount()
            self.album_table.insertRow(row_pos)

            self.album_table.setItem(row_pos, 0, QTableWidgetItem(row_data.get("artist", "")))

            album_name = row_data.get("album", "Unknown Album")
            album_id = row_data.get("album_id", "")
            artist_name = row_data.get("artist", "Unknown Artist")
            album_url = self.get_album_url(album_id, artist_name, album_name)

            album_item = QTableWidgetItem(album_name)
            album_item.setData(Qt.ItemDataRole.UserRole, album_id)  # Store album_id in UserRole
            self.album_table.setItem(row_pos, 1, album_item)

            release_date = row_data.get("release_date", "Unknown Release Date")
            self.album_table.setItem(row_pos, 2, QTableWidgetItem(release_date))

            # Handle cover image decoding
            base64_image = row_data.get("cover_image")
            cover_image_format = row_data.get("cover_image_format", "PNG")  # Default to PNG if not specified
            if base64_image:
                try:
                    image_bytes = base64.b64decode(base64_image)
                    # Create ImageWidget and set it in the table asynchronously
                    image_widget = ImageWidget(parent=self.album_table)
                    self.album_table.setCellWidget(row_pos, 3, image_widget)
                    image_widget.setImageAsync(image_data=image_bytes, size=(200, 200), format=cover_image_format)
                    # No need to set base64_image manually
                    self.album_table.setRowHeight(row_pos, 100)
                except Exception as e:
                    logging.error(f"Failed to load cover image for album '{album_name}': {e}")
                    self.album_table.setItem(row_pos, 3, QTableWidgetItem("Image Load Failed"))
            else:
                self.album_table.setItem(row_pos, 3, QTableWidgetItem())

            self.album_table.setItem(row_pos, 4, QTableWidgetItem(row_data.get("country", "")))
            self.album_table.setItem(row_pos, 5, QTableWidgetItem(row_data.get("genre_1", "")))
            self.album_table.setItem(row_pos, 6, QTableWidgetItem(row_data.get("genre_2", "")))
            self.album_table.setItem(row_pos, 7, QTableWidgetItem(row_data.get("rating", "0.00")))
            self.album_table.setItem(row_pos, 8, QTableWidgetItem(row_data.get("comments", "")))

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

        album_item = QTableWidgetItem(album)
        album_item.setData(Qt.ItemDataRole.UserRole, '')  # No album_id for manually added albums
        self.album_table.setItem(row_position, 1, album_item)

        self.album_table.setItem(row_position, 2, QTableWidgetItem(release_date_display))

        if cover_image_path:
            try:
                with open(cover_image_path, 'rb') as img_file:
                    image_data = img_file.read()
                # Determine the format based on the file extension
                _, ext = os.path.splitext(cover_image_path)
                format = ext.replace('.', '').upper()  # e.g., "PNG", "WEBP"
                if format not in ["PNG", "WEBP", "JPEG"]:
                    format = "PNG"  # Default to PNG if unsupported
                # Create ImageWidget and set it in the table asynchronously
                image_widget = ImageWidget(parent=self.album_table)
                self.album_table.setCellWidget(row_position, 3, image_widget)
                image_widget.setImageAsync(image_data=image_data, size=(200, 200), format=format)
                # No need to set base64_image here; ImageWidget handles it
                self.album_table.setRowHeight(row_position, 100)
            except Exception as e:
                logging.error(f"Failed to add cover image: {e}")
                self.album_table.setItem(row_position, 3, QTableWidgetItem("Image Load Failed"))

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