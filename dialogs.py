from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QSize, QRect, QFile, QIODevice, QTextStream
from PyQt6.QtGui import QIcon, QColor, QPixmap, QCursor
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QListWidgetItem, QScrollArea,
                            QPushButton, QLineEdit, QTextEdit, QComboBox, QStyledItemDelegate, QStyle,
                            QGroupBox, QFormLayout, QFileDialog, QMessageBox, QCompleter, QListWidget, QTextBrowser, QWidget)
import logging
import os
import requests
from datetime import datetime
from workers import Worker

class EditableComboBox(QComboBox):
    """
    Custom ComboBox that opens the dropdown when clicking anywhere in the control,
    even when the ComboBox is editable.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        
        # Make the line edit in the combobox forward mouse events to the combobox
        line_edit = self.lineEdit()
        if line_edit:  # Check if line edit exists before installing filter
            line_edit.installEventFilter(self)
        else:
            # If line edit isn't available immediately, connect to a signal that fires when it would be
            def lineEdit_changed(self=self):
                line_edit = self.lineEdit()
                if line_edit:
                    line_edit.installEventFilter(self)
            self.lineEdit_changed = lineEdit_changed
            self.currentIndexChanged.connect(self.lineEdit_changed)
        
    def eventFilter(self, a0, a1):
        """Filter events for the line edit to handle mouse clicks"""
        if a0 == self.lineEdit() and a1 is not None and a1.type() == QEvent.Type.MouseButtonPress:
            # When user clicks in the line edit area, show the dropdown
            self.showPopup()
            return True
        return super().eventFilter(a0, a1)


class ManualAddAlbumDialog(QDialog):
    """
    Dialog for manually adding an album with a modern Spotify-like design.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent
        self.setWindowTitle("Add Album Manually")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #121212;
            }
            QLabel {
                font-size: 12px;
                color: #B3B3B3;
                font-weight: bold;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #333333;
                color: white;
                padding: 10px;
                border-radius: 4px;
                border: none;
                selection-background-color: #1DB954;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 1px solid #1DB954;
            }
            QLineEdit[valid="true"] {
                border-left: 4px solid #1DB954;
            }
            QLineEdit[valid="false"] {
                border-left: 4px solid #e74c3c;
            }
            QPushButton {
                background-color: #1DB954;
                color: black;
                border-radius: 20px;
                padding: 8px 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #1ED760;
            }
            QPushButton#cancel_button {
                background-color: transparent;
                color: white;
                border: 1px solid #B3B3B3;
            }
            QPushButton#cancel_button:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton#select_image_button, QPushButton#clear_image_button {
                padding: 8px 16px;
                background-color: #333333;
                color: white;
                border-radius: 4px;
            }
            QPushButton#select_image_button:hover, QPushButton#clear_image_button:hover {
                background-color: #444444;
            }
            QGroupBox {
                color: white;
                font-weight: bold;
                border: 1px solid #333333;
                border-radius: 4px;
                margin-top: 16px;
                padding-top: 16px;
                background-color: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
                font-size: 13px;
            }
        """)
        self.initUI()
        
    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)
        
        # Content layout with two columns
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # Left column - Cover image
        left_column = QVBoxLayout()
        
        image_group = QGroupBox("Album Cover")
        image_layout = QVBoxLayout(image_group)
        
        # Image preview - make it larger and clickable
        self.image_preview = QLabel(self)
        self.image_preview.setFixedSize(200, 200)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setText("No Image\n\nClick to select")
        self.image_preview.setStyleSheet("""
            border: 2px dashed #555555;
            background-color: #1A1A1A;
            border-radius: 4px;
            font-size: 14px;
            color: #888888;
        """)
        # Set the cursor programmatically instead of with CSS
        self.image_preview.setCursor(Qt.CursorShape.PointingHandCursor)
        # Make the label clickable
        self.image_preview.mousePressEvent = self.image_preview_clicked
        image_layout.addWidget(self.image_preview, 1, Qt.AlignmentFlag.AlignCenter)
        
        # Image buttons
        image_buttons_layout = QHBoxLayout()
        self.select_image_button = QPushButton("Select Cover Image", self)
        self.select_image_button.setObjectName("select_image_button")
        self.select_image_button.clicked.connect(self.select_cover_image)
        image_buttons_layout.addWidget(self.select_image_button)
        
        self.clear_image_button = QPushButton("Clear", self)
        self.clear_image_button.setObjectName("clear_image_button")
        self.clear_image_button.clicked.connect(self.clear_cover_image)
        self.clear_image_button.setEnabled(False)
        image_buttons_layout.addWidget(self.clear_image_button)
        
        image_layout.addLayout(image_buttons_layout)
        left_column.addWidget(image_group)
        
        # Add stretch at the bottom
        left_column.addStretch()
        
        # Right column - Form fields
        right_column = QVBoxLayout()
        
        # Basic Info Group
        basic_info_group = QGroupBox("Basic Information")
        basic_form = QFormLayout(basic_info_group)
        basic_form.setSpacing(12)
        basic_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Artist input
        self.artist_input = QLineEdit(self)
        self.artist_input.setPlaceholderText("Enter artist name")
        self.artist_input.setMinimumHeight(36)
        basic_form.addRow("Artist:", self.artist_input)
        
        # Album input
        self.album_input = QLineEdit(self)
        self.album_input.setPlaceholderText("Enter album name")
        self.album_input.setMinimumHeight(36)
        basic_form.addRow("Album:", self.album_input)
        
        # Release date input with flexible formatting
        self.release_date_input = QLineEdit(self)
        self.release_date_input.setPlaceholderText("DD-MM-YYYY (flexible format)")
        self.release_date_input.setMinimumHeight(36)
        self.release_date_input.editingFinished.connect(self.validate_date_on_exit)
        basic_form.addRow("Release Date:", self.release_date_input)
        
        right_column.addWidget(basic_info_group)
        
        # Classification Group
        classification_group = QGroupBox("Classification")
        classification_form = QFormLayout(classification_group)
        classification_form.setSpacing(12)
        classification_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Country dropdown - using styled QComboBox
        self.country_combo = QComboBox(self)
        countries = getattr(self._parent, 'countries', []) if self._parent else []
        self.country_combo.addItems(countries)
        self.country_combo.setMinimumHeight(36)
        self.country_combo.setEditable(True)
        self.country_combo.setMaxVisibleItems(15)  # Show a reasonable number of items
        # Add completer for better search
        country_completer = QCompleter(countries, self.country_combo)
        country_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        country_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        # Make the popup match the combobox popup
        country_popup = country_completer.popup()
        if country_popup:
            country_popup.setStyleSheet("""
                background-color: #2D2D30; 
                color: white;
                selection-background-color: #3D3D42;
                border: 1px solid #555555;
            """)
        self.country_combo.setCompleter(country_completer)
        # Style the combobox popup to match the completer
        self.country_combo.setStyleSheet("""
            QComboBox QAbstractItemView {
                background-color: #2D2D30;
                color: white;
                selection-background-color: #3D3D42;
                border: 1px solid #555555;
            }
        """)
        classification_form.addRow("Country:", self.country_combo)
        
        # Genre 1 dropdown - using styled QComboBox
        self.genre1_combo = QComboBox(self)
        genres = getattr(self._parent, 'genres', []) if self._parent else []
        self.genre1_combo.addItems(genres)
        self.genre1_combo.setMinimumHeight(36)
        self.genre1_combo.setEditable(True)
        self.genre1_combo.setMaxVisibleItems(15)
        # Add completer for better search
        genre1_completer = QCompleter(genres, self.genre1_combo)
        genre1_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        genre1_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        # Make the popup match the combobox popup
        genre1_popup = genre1_completer.popup()
        if genre1_popup:
            genre1_popup.setStyleSheet("""
                background-color: #2D2D30; 
                color: white;
                selection-background-color: #3D3D42;
                border: 1px solid #555555;
            """)
        self.genre1_combo.setCompleter(genre1_completer)
        # Style the combobox popup to match the completer
        self.genre1_combo.setStyleSheet("""
            QComboBox QAbstractItemView {
                background-color: #2D2D30;
                color: white;
                selection-background-color: #3D3D42;
                border: 1px solid #555555;
            }
        """)
        classification_form.addRow("Genre 1:", self.genre1_combo)
        
        # Genre 2 dropdown - using styled QComboBox
        self.genre2_combo = QComboBox(self)
        self.genre2_combo.addItems(genres)
        self.genre2_combo.setMinimumHeight(36)
        self.genre2_combo.setEditable(True)
        self.genre2_combo.setMaxVisibleItems(15)
        # Add completer for better search
        genre2_completer = QCompleter(genres, self.genre2_combo)
        genre2_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        genre2_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        # Make the popup match the combobox popup
        genre2_popup = genre2_completer.popup()
        if genre2_popup:
            genre2_popup.setStyleSheet("""
                background-color: #2D2D30; 
                color: white;
                selection-background-color: #3D3D42;
                border: 1px solid #555555;
            """)
        self.genre2_combo.setCompleter(genre2_completer)
        # Style the combobox popup to match the completer
        self.genre2_combo.setStyleSheet("""
            QComboBox QAbstractItemView {
                background-color: #2D2D30;
                color: white;
                selection-background-color: #3D3D42;
                border: 1px solid #555555;
            }
        """)
        classification_form.addRow("Genre 2:", self.genre2_combo)
        
        classification_group.setLayout(classification_form)
        right_column.addWidget(classification_group)
        
        # Comments Group
        comments_group = QGroupBox("Comment")
        comments_layout = QVBoxLayout(comments_group)
        
        # Comments input
        self.comments_input = QTextEdit(self)
        self.comments_input.setPlaceholderText("")
        self.comments_input.setMinimumHeight(80)
        comments_layout.addWidget(self.comments_input)
        
        comments_group.setLayout(comments_layout)
        right_column.addWidget(comments_group)
        
        # Add columns to content layout
        content_layout.addLayout(left_column, 1)
        content_layout.addLayout(right_column, 2)
        
        main_layout.addLayout(content_layout)
        
        # Action Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Add spacer to push buttons to right
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setObjectName("cancel_button")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.setMinimumHeight(40)
        button_layout.addWidget(self.cancel_button)
        
        self.add_button = QPushButton("Add Album", self)
        self.add_button.clicked.connect(self.accept)
        self.add_button.setMinimumWidth(150)
        self.add_button.setMinimumHeight(40)
        button_layout.addWidget(self.add_button)
        
        main_layout.addLayout(button_layout)
        
        # Store the image path
        self.cover_image_path = ""
        
        # Set focus on artist input
        self.artist_input.setFocus()
    
    def image_preview_clicked(self, ev):
        """Handle clicks on the image preview area to open file dialog."""
        self.select_cover_image()
        
    def select_cover_image(self):
        """Open file dialog to select an image file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Cover Image", "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        
        if file_path:
            # Load and display the image
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # Scale the pixmap to fit the label
                scaled_pixmap = pixmap.scaled(
                    self.image_preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_preview.setPixmap(scaled_pixmap)
                self.cover_image_path = file_path
                self.clear_image_button.setEnabled(True)
                
                # Remove text when image is displayed
                self.image_preview.setText("")
            else:
                QMessageBox.warning(self, "Image Error", "Failed to load the selected image.")
                
    def clear_cover_image(self):
        """Clear the selected cover image."""
        self.image_preview.setText("No Image\n\nClick to select")
        self.image_preview.setPixmap(QPixmap())  # Clear pixmap
        self.cover_image_path = ""
        self.clear_image_button.setEnabled(False)
    
    def validate_date_on_exit(self):
        """Validate and format the date when the user leaves the date field."""
        date_str = self.release_date_input.text().strip()
        if not date_str:  # Skip validation if empty
            self.release_date_input.setProperty("valid", None)
            # Get style and check if it's not None before using it
            style = self.release_date_input.style()
            if style:
                style.unpolish(self.release_date_input)
                style.polish(self.release_date_input)
            return
            
        is_valid, formatted_date = self._parse_and_format_date(date_str)
        
        if is_valid:
            # Set the formatted date back to the field
            self.release_date_input.setText(formatted_date)
            # Set the valid property for CSS
            self.release_date_input.setProperty("valid", True)
        else:
            # Set invalid property for CSS
            self.release_date_input.setProperty("valid", False)
        
        # Force style refresh
        style = self.release_date_input.style()
        if style:
            style.unpolish(self.release_date_input)
            style.polish(self.release_date_input)
        
    def _parse_and_format_date(self, date_str):
        """
        Parse date string in various formats and return whether it's valid and
        the formatted date string in DD-MM-YYYY format.
        
        Returns:
            tuple: (is_valid, formatted_date)
        """
        # Remove any whitespace
        date_str = date_str.strip()
        
        try:
            # Check for common separators and replace with standard format
            for sep in ['/', '.', ' ']:
                if sep in date_str:
                    date_str = date_str.replace(sep, '-')
            
            parts = date_str.split('-')
            
            # Handle different formats based on number of parts and their lengths
            if len(parts) == 3:  # DD-MM-YYYY or DD-MM-YY
                day = int(parts[0])
                month = int(parts[1])
                year = int(parts[2])
                
                # Handle 2-digit year
                if len(parts[2]) == 2:
                    current_century = (datetime.now().year // 100) * 100
                    year = current_century + year
                    if year > datetime.now().year + 10:  # If year is more than 10 years in future
                        year -= 100  # Assume previous century
                        
            elif len(parts) == 2:  # MM-YYYY
                # Assume it's month and year
                day = 1  # Default to first day of month
                month = int(parts[0])
                year = int(parts[1])
                
                # Handle 2-digit year
                if len(parts[1]) == 2:
                    current_century = (datetime.now().year // 100) * 100
                    year = current_century + year
                    if year > datetime.now().year + 10:
                        year -= 100
                        
            elif len(date_str) == 8 and date_str.isdigit():  # DDMMYYYY
                day = int(date_str[:2])
                month = int(date_str[2:4])
                year = int(date_str[4:])
                
            elif len(date_str) == 6 and date_str.isdigit():  # DDMMYY
                day = int(date_str[:2])
                month = int(date_str[2:4])
                year_short = int(date_str[4:])
                current_century = (datetime.now().year // 100) * 100
                year = current_century + year_short
                if year > datetime.now().year + 10:
                    year -= 100
                    
            elif len(date_str) == 4 and date_str.isdigit():  # MMYY
                day = 1  # Default to first day of month
                month = int(date_str[:2])
                year_short = int(date_str[2:])
                current_century = (datetime.now().year // 100) * 100
                year = current_century + year_short
                if year > datetime.now().year + 10:
                    year -= 100
                    
            else:
                return False, ""
            
            # Basic validation
            if not (1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100):
                return False, ""
                
            # Validate using datetime
            date_obj = datetime(year, month, day)
            
            # Format the date as DD-MM-YYYY
            formatted_date = f"{day:02d}-{month:02d}-{year:04d}"
            
            return True, formatted_date
            
        except (ValueError, IndexError):
            return False, ""
                
    def accept(self):
        """Validate input and add the album."""
        # Validate required fields
        artist = self.artist_input.text().strip()
        album = self.album_input.text().strip()
        release_date = self.release_date_input.text().strip()
        
        if not artist:
            QMessageBox.warning(self, "Missing Information", "Please enter an artist name.")
            self.artist_input.setFocus()
            return
        
        if not album:
            QMessageBox.warning(self, "Missing Information", "Please enter an album name.")
            self.album_input.setFocus()
            return
            
        if not release_date:
            QMessageBox.warning(self, "Missing Information", "Please enter a release date.")
            self.release_date_input.setFocus()
            return
            
        # Validate the date one more time
        is_valid, formatted_date = self._parse_and_format_date(release_date)
        if not is_valid:
            QMessageBox.warning(self, "Invalid Date", "Please enter a valid release date in DD-MM-YYYY format.")
            self.release_date_input.setFocus()
            return
            
        # Use the formatted date
        release_date = formatted_date
        
        # Get selected values from the QComboBox fields
        country = self.country_combo.currentText().strip()
        genre1 = self.genre1_combo.currentText().strip()
        genre2 = self.genre2_combo.currentText().strip()
        comments = self.comments_input.toPlainText()
        
        # Add the album to the parent's table if parent exists and has the method
        if self._parent and hasattr(self._parent, 'add_manual_album_to_table'):
            self._parent.add_manual_album_to_table(
                artist, album, release_date, self.cover_image_path,
                country, genre1, genre2, comments
            )
        else:
            logging.warning("Cannot add album: Parent object missing or doesn't have 'add_manual_album_to_table' method")
            QMessageBox.warning(self, "Error", "Cannot add the album due to an internal error.")
        
        # Close the dialog
        super().accept()

class LogViewerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Live Log Viewer")
        self.resize(800, 600)
        layout = QVBoxLayout()
        self.log_text_edit = QTextEdit(self)
        self.log_text_edit.setReadOnly(True)
        # Set dark background and light text
        self.log_text_edit.setStyleSheet("background-color: #2D2D30; color: white;")
        layout.addWidget(self.log_text_edit)
        self.setLayout(layout)

    def append_log(self, message):
        self.log_text_edit.append(message)


class SubmitDialog(QDialog):
    """
    Dialog window to handle the submission of album data to Telegram.
    """
    submission_finished = pyqtSignal(bool, str)  # Signal to indicate submission status

    def __init__(self, bot_token, chat_id, message_thread_id, file_path, parent=None):
        super().__init__(parent)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id
        self.file_path = file_path  # Store the current file path
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Submit to Telegram")
        layout = QVBoxLayout()

        self.nameEdit = QLineEdit(self)
        self.nameEdit.setPlaceholderText("Enter your name here")
        layout.addWidget(self.nameEdit)

        self.submitBtn = QPushButton("Submit", self)
        self.submitBtn.clicked.connect(self.onSubmit)
        layout.addWidget(self.submitBtn)

        self.progress_label = QLabel("", self)
        layout.addWidget(self.progress_label)

        self.setLayout(layout)

    def onSubmit(self):
        name = self.nameEdit.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Please enter your name before submitting.")
            logging.warning("Submission attempted without a name")
            return

        if not self.file_path or not os.path.exists(self.file_path):
            QMessageBox.warning(self, "Error", "No valid file is currently open for submission.")
            logging.warning("Submission attempted without a valid open file")
            return

        self.submitBtn.setEnabled(False)  # Disable the button to prevent multiple submissions
        self.progress_label.setText("Submitting... Please wait.")
        logging.info(f"User '{name}' is submitting file '{self.file_path}' to Telegram")

        # Compose the caption message
        caption_message = f"Here is the list from {name}."

        # Start a worker thread for submission
        from workers import SubmitWorker  # Import here to avoid circular imports if necessary
        self.worker = SubmitWorker(
            self.bot_token,
            self.chat_id,
            self.message_thread_id,
            self.file_path,
            caption_message  # Pass the caption to the worker
        )
        self.worker.submission_finished.connect(self.onSubmissionFinished)
        self.worker.start()

    def onSubmissionFinished(self, success, message):
        self.submitBtn.setEnabled(True)  # Re-enable the button
        self.progress_label.setText("")  # Clear the progress label

        if success:
            QMessageBox.information(self, "Success", "File submitted successfully.")
            logging.info(f"File {self.file_path} submitted successfully")
            self.accept()  # Close the dialog
        else:
            QMessageBox.critical(self, "Failed", f"File submission failed. Details: {message}")
            logging.error(f"Failed to submit file {self.file_path}: {message}")


class HelpDialog(QDialog):
    def __init__(self, html_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help")
        self.resize(800, 600)
        layout = QVBoxLayout()
        self.text_browser = QTextBrowser(self)
        self.text_browser.setReadOnly(True)
        self.text_browser.setHtml(html_content)
        self.text_browser.setOpenExternalLinks(True)  # Enable opening links in external browser
        layout.addWidget(self.text_browser)
        self.setLayout(layout)

class UpdateDialog(QDialog):
    def __init__(self, latest_version, current_version, release_notes_url, parent=None):
        super().__init__(parent)
        self.latest_version = latest_version
        self.current_version = current_version
        self.release_notes_url = release_notes_url
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Update Available")
        self.setModal(True)
        self.resize(450, 250)  # Adjusted size to accommodate additional text

        layout = QVBoxLayout()

        # Update Message
        message_label = QLabel(f"""
            <p>A new version <b>{self.latest_version}</b> is available.</p>
            <p>You are running version <b>{self.current_version}</b>.</p>
            <p>Do you want to download and install the updated version of SuShe?</p>
            """)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        # Release Notes Link
        if self.release_notes_url:
            release_notes_label = QLabel(f'<a href="{self.release_notes_url}">View Release Notes</a>')
            release_notes_label.setTextFormat(Qt.TextFormat.RichText)
            release_notes_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            release_notes_label.setOpenExternalLinks(True)
            layout.addWidget(release_notes_label)

        # Buttons Layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.yes_button = QPushButton("Yes")
        self.no_button = QPushButton("No")

        button_layout.addWidget(self.yes_button)
        button_layout.addWidget(self.no_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Connect Buttons
        self.yes_button.clicked.connect(self.accept)
        self.no_button.clicked.connect(self.reject)

class SendGenreDialog(QDialog):
    """
    Dialog window to allow users to send in genre suggestions.
    Users can input up to five genres and optional notes.
    """
    def __init__(self, webhook_url, parent=None):
        super().__init__(parent)
        self.webhook_url = webhook_url
        self.setWindowTitle("Send in Genre")
        self.setFixedSize(400, 350)  # Adjust size as needed
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        # Instruction Label
        instruction_label = QLabel("Enter up to 5 genres:")
        layout.addWidget(instruction_label)

        # Genre Input Fields
        self.genre_inputs = []
        for i in range(5):
            h_layout = QHBoxLayout()
            label = QLabel(f"Genre {i + 1}:")
            line_edit = QLineEdit()
            self.genre_inputs.append(line_edit)
            h_layout.addWidget(label)
            h_layout.addWidget(line_edit)
            layout.addLayout(h_layout)

        # User Notes
        notes_label = QLabel("User Notes (optional):")
        layout.addWidget(notes_label)
        self.notes_input = QLineEdit()
        layout.addWidget(self.notes_input)

        # Submit and Cancel Buttons
        button_layout = QHBoxLayout()
        self.submit_button = QPushButton("Submit")
        self.cancel_button = QPushButton("Cancel")
        self.submit_button.clicked.connect(self.submit)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.submit_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def submit(self):
        # Collect genres
        genres = [le.text().strip() for le in self.genre_inputs if le.text().strip()]
        if not genres:
            QMessageBox.warning(self, "Input Error", "Please enter at least one genre.")
            return

        user_notes = self.notes_input.text().strip()

        # Prepare JSON payload
        payload = {
            "genre_list": genres,
            "user_notes": user_notes
        }

        # **DEBUG: Print the payload to console/log**
        print("Submitting payload:", payload)
        logging.debug(f"Submitting payload: {payload}")

        # Send POST request
        try:
            response = requests.post(self.webhook_url, json=payload)
            if response.status_code == 200 or response.status_code == 201:
                QMessageBox.information(self, "Success", "Genres submitted successfully! The application developer will review them, and it is likely they will appear in the next update.")
                logging.info(f"Genres submitted successfully: {payload}")
                self.accept()
            else:
                logging.error(f"Webhook POST failed with status code {response.status_code}: {response.text}")
                QMessageBox.critical(self, "Submission Failed", f"Failed to submit genres. Status Code: {response.status_code}")
        except Exception as e:
            logging.error(f"Exception occurred while submitting genres: {e}")
            QMessageBox.critical(self, "Submission Error", f"An error occurred: {e}")

class GenreUpdateDialog(QDialog):
    """
    Dialog to display genre changes and ask for confirmation.
    """
    def __init__(self, added_genres, removed_genres, parent=None):
        super().__init__(parent)
        self.added_genres = sorted(added_genres)
        self.removed_genres = sorted(removed_genres)
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Genre Definitions Update")
        self.setMinimumWidth(450)
        
        # Set up the layout
        layout = QVBoxLayout(self)
        
        # Info label at the top
        info_label = QLabel("A new version of genre definitions is available. "
                           "Would you like to update?")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Added genres group
        if self.added_genres:
            added_group = QGroupBox(f"New Genres ({len(self.added_genres)})")
            added_layout = QVBoxLayout(added_group)
            
            added_list = QListWidget()
            for genre in self.added_genres:
                added_list.addItem(genre)
            added_list.setMaximumHeight(150)
            
            added_layout.addWidget(added_list)
            layout.addWidget(added_group)
        
        # Removed genres group
        if self.removed_genres:
            removed_group = QGroupBox(f"Removed Genres ({len(self.removed_genres)})")
            removed_layout = QVBoxLayout(removed_group)
            
            removed_list = QListWidget()
            for genre in self.removed_genres:
                removed_list.addItem(genre)
            removed_list.setMaximumHeight(150)
            
            removed_layout.addWidget(removed_list)
            layout.addWidget(removed_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Skip Update")
        self.update_button = QPushButton("Update Genres")
        self.update_button.setDefault(True)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.update_button)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        self.cancel_button.clicked.connect(self.reject)
        self.update_button.clicked.connect(self.accept)
        
        # Apply the Spotify-style styling that matches the rest of the app
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #333333;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
            
            QListWidget {
                background-color: #1A1A1A;
                border: 1px solid #333333;
                border-radius: 3px;
            }
            
            QPushButton {
                min-width: 120px;
                min-height: 30px;
            }
        """)

class SearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Add Album")
        self.setMinimumSize(750, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: #121212;
            }
        """)
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)
        
        # Header with title
        header_label = QLabel("Search for Albums")
        header_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: white;
            margin-bottom: 16px;
        """)
        main_layout.addWidget(header_label)
        
        # Search input group
        search_group = QGroupBox()
        search_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 16px;
                background-color: #181818;
            }
        """)
        search_layout = QVBoxLayout(search_group)
        search_layout.setSpacing(12)
        
        # Artist search section
        search_label = QLabel("Enter artist name:")
        search_label.setStyleSheet("color: #B3B3B3; font-weight: bold;")
        search_layout.addWidget(search_label)
        
        # Search input with icon
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for artist...")
        self.search_input.setMinimumHeight(40)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                border-radius: 20px;
                padding: 8px 16px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #1DB954;
            }
        """)
        
        self.search_button = QPushButton("Search")
        self.search_button.setMinimumHeight(40)
        self.search_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.search_button.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: black;
                border-radius: 20px;
                padding: 8px 20px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #1ED760;
            }
            QPushButton:pressed {
                background-color: #169C46;
            }
        """)
        
        input_layout.addWidget(self.search_input, 1)
        input_layout.addWidget(self.search_button)
        search_layout.addWidget(input_container)
        
        # Loading indicator
        self.loading_indicator = QLabel("Searching...")
        self.loading_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_indicator.setStyleSheet("color: #B3B3B3; font-style: italic;")
        self.loading_indicator.hide()
        search_layout.addWidget(self.loading_indicator)
        
        main_layout.addWidget(search_group)
        
        # Results section
        results_layout = QHBoxLayout()
        results_layout.setSpacing(20)
        
        # Artists column
        artist_column = QVBoxLayout()
        artist_label = QLabel("Artists")
        artist_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        artist_column.addWidget(artist_label)
        
        self.artist_list = QListWidget()
        self.artist_list.setStyleSheet("""
            QListWidget {
                background-color: #181818;
                border-radius: 8px;
                padding: 8px;
                border: 1px solid #333333;
            }
        """)
        
        # Set up the custom delegate for artist items
        self.artist_delegate = ArtistItemDelegate(self.artist_list)
        self.artist_list.setItemDelegate(self.artist_delegate)
        self.artist_list.setIconSize(QSize(50, 50))
        self.artist_list.setUniformItemSizes(True)
        artist_column.addWidget(self.artist_list)
        
        # Albums column
        album_column = QVBoxLayout()
        album_label = QLabel("Albums")
        album_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        album_column.addWidget(album_label)
        
        self.album_list = QListWidget()
        self.album_list.setStyleSheet("""
            QListWidget {
                background-color: #181818;
                border-radius: 8px;
                padding: 8px;
                border: 1px solid #333333;
            }
        """)
        
        # Set up custom delegate for album items
        self.album_delegate = AlbumItemDelegate(self.album_list)
        self.album_list.setItemDelegate(self.album_delegate)
        self.album_list.setIconSize(QSize(50, 50))
        self.album_list.setUniformItemSizes(True)
        album_column.addWidget(self.album_list)
        
        results_layout.addLayout(artist_column)
        results_layout.addLayout(album_column)
        main_layout.addLayout(results_layout, 1)
        
        # Instructions
        instructions = QLabel("Double-click on an artist to see their albums. Double-click on an album to add it to your list.")
        instructions.setStyleSheet("color: #B3B3B3; font-style: italic;")
        instructions.setWordWrap(True)
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(instructions)
        
        # Connect signals
        self.search_button.clicked.connect(self.search_artist)
        self.search_input.returnPressed.connect(self.search_artist)
        self.artist_list.itemDoubleClicked.connect(self.display_artist_albums)
        self.album_list.itemDoubleClicked.connect(self.fetch_album_details)
        
        # Image cache and active threads
        self.image_cache = {}
        self.active_threads = []
    
    def closeEvent(self, event):
        for thread in self.active_threads:
            if thread.isRunning():
                thread.wait(500)
        event.accept()
    
    def search_artist(self):
        artist_name = self.search_input.text().strip()
        if not artist_name:
            QMessageBox.warning(self, "Input Error", "Please enter an artist name.")
            return
            
        self.artist_list.clear()
        self.album_list.clear()
        
        self.loading_indicator.show()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        # Check if main_window is None or doesn't have get_access_token method
        if not self.main_window or not hasattr(self.main_window, 'get_access_token'):
            QMessageBox.warning(self, "Error", "Cannot search: Main window reference is missing.")
            self.loading_indicator.hide()
            QApplication.restoreOverrideCursor()
            return
        
        self.artist_search_worker = Worker(self._search_artist, artist_name)
        self.artist_search_worker.finished.connect(self.on_artists_fetched)
        self.active_threads.append(self.artist_search_worker)
        self.artist_search_worker.start()
    
    def _search_artist(self, artist_name):
        """Modified version that also fetches artist images"""
        if not self.main_window or not hasattr(self.main_window, 'get_access_token'):
            return {"error": "Main window reference is missing"}
            
        access_token = self.main_window.get_access_token()
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
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def on_artists_fetched(self, result):
        QApplication.restoreOverrideCursor()
        self.loading_indicator.hide()
        
        if "error" in result:
            if result["error"] == "Authentication required":
                return
            else:
                QMessageBox.warning(self, "Error", f"Failed to fetch artists: {result['error']}")
                return

        artists = result.get("artists", {}).get("items", [])
        self.main_window.artist_id_map.clear()
        artist_names = set()

        for artist in artists:
            display_name = artist['name']
            if display_name in artist_names:
                display_name = f"{artist['name']} ({artist['followers']['total']} followers)"
            
            # Create item with artist name
            item = QListWidgetItem(display_name)
            
            # Set the text alignment to leave room for the icon
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            # Store ID in main window's map
            self.main_window.artist_id_map[display_name] = artist['id']
            artist_names.add(artist['name'])
            
            # Get artist image if available
            image_url = None
            if artist['images'] and len(artist['images']) > 0:
                # Find a suitable small image (around 64x64)
                for img in artist['images']:
                    if img['width'] <= 100:
                        image_url = img['url']
                        break
                
                # If no small image found, use the last one (typically smallest)
                if not image_url and len(artist['images']) > 0:
                    image_url = artist['images'][-1]['url']
                
                # Download and set the image
                if image_url:
                    self.load_artist_image(item, image_url)
            
            self.artist_list.addItem(item)
            
        if not artists:
            QMessageBox.information(self, "No Results", "No artists found matching your search.")
    
    def load_artist_image(self, item, image_url):
        """Load artist image and set it as item icon"""
        # Check cache first
        if image_url in self.image_cache:
            item.setIcon(self.image_cache[image_url])
            return
            
        # Download image in a worker thread
        worker = Worker(self._download_image, image_url)
        worker.finished.connect(lambda result, item=item, url=image_url: 
                               self._set_artist_image(result, item, url))
        self.active_threads.append(worker)
        worker.start()
    
    def _download_image(self, image_url):
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logging.error(f"Error downloading image: {e}")
            return None
    
    def _set_artist_image(self, image_data, item, url):
        if not image_data:
            return
            
        try:
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            
            # Scale the image to correct size
            scaled_pixmap = pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            # Create icon and set it
            icon = QIcon(scaled_pixmap)
            self.image_cache[url] = icon
            item.setIcon(icon)
            
            # Force item height to accommodate the icon
            item.setSizeHint(QSize(item.sizeHint().width(), 48))
        except Exception as e:
            logging.error(f"Error setting artist image: {e}")
    
    def display_artist_albums(self, item):
        artist_name = item.text()
        artist_id = self.main_window.artist_id_map.get(artist_name)
        if not artist_id:
            logging.error(f"Artist ID for {artist_name} not found")
            return

        self.album_list.clear()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        # Create album fetch worker
        if self.main_window and hasattr(self.main_window, '_fetch_artist_albums'):
            self.albums_fetch_worker = Worker(self.main_window._fetch_artist_albums, artist_id)
        else:
            QMessageBox.warning(self, "Error", "Cannot fetch albums: Main window reference is missing.")
            QApplication.restoreOverrideCursor()
            return
            
        self.albums_fetch_worker.finished.connect(self.on_albums_fetched)
        
        # Track the thread
        self.active_threads.append(self.albums_fetch_worker)
        
        # Start the worker
        self.albums_fetch_worker.start()
    
    def on_albums_fetched(self, result):
        QApplication.restoreOverrideCursor()
        if "error" in result:
            if result["error"] == "Authentication required":
                return
            else:
                QMessageBox.warning(self, "Error", f"Failed to fetch albums: {result['error']}")
                return

        albums = result.get('items', [])
        self.album_list.clear()
        self.main_window.album_id_map.clear()

        # Group albums by name+year
        albums_by_name_year = {}
        for album in albums:
            year = album.get('release_date', '')[:4]
            name_year_key = f"{album['name']} - {year}"
            if name_year_key not in albums_by_name_year:
                albums_by_name_year[name_year_key] = []
            albums_by_name_year[name_year_key].append(album)
        
        # Add items to list
        self.album_list.blockSignals(True)
        for album in albums:
            year = album.get('release_date', '')[:4]
            name_year_key = f"{album['name']} - {year}"
            
            has_duplicates = len(albums_by_name_year[name_year_key]) > 1
            
            if has_duplicates:
                album_type = album.get('album_type', '').title()
                display_text = f"{album['name']} - {year} ({album_type})"
            else:
                display_text = f"{album['name']} - {year}"
            
            # Create item with album name
            item = QListWidgetItem(display_text)
            
            # Store album ID in map
            self.main_window.album_id_map[display_text] = album['id']
            
            # Get album cover if available
            image_url = None
            if album['images'] and len(album['images']) > 0:
                for img in album['images']:
                    if img['width'] <= 300:  # Get a reasonably sized image
                        image_url = img['url']
                        break
                
                # If no small image found, use the last one
                if not image_url and len(album['images']) > 0:
                    image_url = album['images'][-1]['url']
                
                # Download and set the image
                if image_url:
                    self.load_album_image(item, image_url)
            
            self.album_list.addItem(item)
        
        self.album_list.blockSignals(False)

    def load_album_image(self, item, image_url):
        """Load album cover image and set it as item icon"""
        # Check cache first
        if image_url in self.image_cache:
            item.setIcon(self.image_cache[image_url])
            return
            
        # Download image in a worker thread
        worker = Worker(self._download_image, image_url)
        worker.finished.connect(lambda result, item=item, url=image_url: 
                            self._set_album_image(result, item, url))
        self.active_threads.append(worker)
        worker.start()

    def _set_album_image(self, image_data, item, url):
        if not image_data:
            return
            
        try:
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            
            # Scale the image to correct size
            scaled_pixmap = pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            # Create icon and set it
            icon = QIcon(scaled_pixmap)
            self.image_cache[url] = icon
            item.setIcon(icon)
            
            # Force item height to accommodate the icon
            item.setSizeHint(QSize(item.sizeHint().width(), 60))
        except Exception as e:
            logging.error(f"Error setting album image: {e}")

    
    def fetch_album_details(self, item):
        if not self.main_window:
            logging.error("Main window reference is missing")
            QMessageBox.warning(self, "Error", "Cannot add album: Main window reference is missing.")
            return
            
        album_text = item.text()
        album_id = self.main_window.album_id_map.get(album_text)
        if not album_id:
            logging.error(f"Album ID for {album_text} not found")
            return
        
        # Call main window's method to add album to list - no confirmation dialog
        if hasattr(self.main_window, 'fetch_album_details_by_id'):
            self.main_window.fetch_album_details_by_id(album_id)
        else:
            logging.error("Main window doesn't have fetch_album_details_by_id method")
            QMessageBox.warning(self, "Error", "Cannot add album: Required method not found.")

class ArtistItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_cache = {}
        
    def paint(self, painter, option, index):
        # Check if painter is None before using it
        if painter is None:
            return
            
        # Draw the background
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(29, 185, 84, 76))  # Spotify green with transparency
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor(51, 51, 51))
        else:
            painter.fillRect(option.rect, QColor(24, 24, 24))
            
        # Get icon and text
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        
        # Draw icon if available
        if icon and isinstance(icon, QIcon):
            # Increase icon size to 50x50
            icon_size = 50
            # Calculate vertical center position for the icon
            icon_y = option.rect.top() + (option.rect.height() - icon_size) // 2
            icon_rect = QRect(option.rect.left() + 10, icon_y, icon_size, icon_size)
            icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)
            
        # Draw text
        painter.setPen(QColor(255, 255, 255))
        # Adjust text position to account for larger icon
        text_rect = option.rect.adjusted(70, 0, -10, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)
        
    def sizeHint(self, option, index):
        # Ensure each item has enough height for the larger icon
        size = super().sizeHint(option, index)
        return QSize(size.width(), 60)  # Increase height to 60px

class AlbumItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # Check if painter is None before using it
        if painter is None:
            return
            
        # Draw the background
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(29, 185, 84, 76))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor(51, 51, 51))
        else:
            painter.fillRect(option.rect, QColor(24, 24, 24))
            
        # Get icon and text
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        
        # Draw icon if available
        if icon and isinstance(icon, QIcon):
            icon_size = 50
            icon_y = option.rect.top() + (option.rect.height() - icon_size) // 2
            icon_rect = QRect(option.rect.left() + 10, icon_y, icon_size, icon_size)
            icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)
            
        # Draw text
        painter.setPen(QColor(255, 255, 255))
        text_rect = option.rect.adjusted(70, 0, -10, 0)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)
        
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width(), 60)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent
        self.setWindowTitle("Settings")
        self.setMinimumWidth(600)
        self.setMinimumHeight(700)
        self.setObjectName("settings_dialog")
        
        # Load settings stylesheet
        self.load_settings_stylesheet()
        
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)
        
        # Add a header label
        header_label = QLabel("Settings")
        header_label.setObjectName("settings_header")
        layout.addWidget(header_label)
        
        # Create a scrollable area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setObjectName("settings_scroll_area")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(20)
        
        # Spotify Authentication Section
        spotify_group = QGroupBox("Spotify Authentication")
        spotify_group.setObjectName("settings_group")
        spotify_layout = QVBoxLayout(spotify_group)
        spotify_layout.setSpacing(12)
        spotify_layout.setContentsMargins(20, 24, 20, 20)
        
        # Status label
        self.spotify_auth_status = QLabel("Not logged in to Spotify")
        self.spotify_auth_status.setObjectName("auth_status")
        spotify_layout.addWidget(self.spotify_auth_status)
        
        # Login/logout buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        self.spotify_login_button = QPushButton("Login with Spotify")
        self.spotify_login_button.setObjectName("primary_button")
        self.spotify_login_button.clicked.connect(self.login_to_spotify)
        
        self.spotify_logout_button = QPushButton("Logout from Spotify")
        self.spotify_logout_button.setObjectName("secondary_button")
        self.spotify_logout_button.clicked.connect(self.logout_from_spotify)
        self.spotify_logout_button.setEnabled(False)
        
        button_layout.addWidget(self.spotify_login_button)
        button_layout.addWidget(self.spotify_logout_button)
        button_layout.addStretch()
        spotify_layout.addLayout(button_layout)
        
        scroll_layout.addWidget(spotify_group)
        
        # Webhook Settings Group
        webhook_group = QGroupBox("Webhook Settings")
        webhook_group.setObjectName("settings_group")
        webhook_layout = QFormLayout(webhook_group)
        webhook_layout.setSpacing(12)
        webhook_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        webhook_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        webhook_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        webhook_layout.setContentsMargins(20, 24, 20, 20)
        
        webhook_url_label = QLabel("Webhook URL:")
        
        self.webhook_url_input = QLineEdit()
        self.webhook_url_input.setObjectName("settings_input")
        if hasattr(self._parent, 'webhook_url') and self._parent.webhook_url:
            self.webhook_url_input.setText(self._parent.webhook_url)
        
        webhook_layout.addRow(webhook_url_label, self.webhook_url_input)
        
        save_webhook_button = QPushButton("Save Webhook")
        save_webhook_button.setObjectName("save_button")
        save_webhook_button.clicked.connect(self.save_webhook_settings)
        webhook_layout.addRow("", save_webhook_button)
        
        scroll_layout.addWidget(webhook_group)
        
        # Telegram Settings Group
        telegram_group = QGroupBox("Telegram Submission")
        telegram_group.setObjectName("settings_group")
        telegram_layout = QFormLayout(telegram_group)
        telegram_layout.setSpacing(12)
        telegram_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        telegram_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        telegram_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        telegram_layout.setContentsMargins(20, 24, 20, 20)
        
        # Bot Token Input
        bot_token_label = QLabel("Bot Token:")
        self.bot_token_input = QLineEdit()
        self.bot_token_input.setObjectName("settings_input")
        if hasattr(self._parent, 'bot_token'):
            self.bot_token_input.setText(self._parent.bot_token)
        telegram_layout.addRow(bot_token_label, self.bot_token_input)
        
        # Chat ID Input
        chat_id_label = QLabel("Chat ID:")
        self.chat_id_input = QLineEdit()
        self.chat_id_input.setObjectName("settings_input")
        if hasattr(self._parent, 'chat_id'):
            self.chat_id_input.setText(self._parent.chat_id)
        telegram_layout.addRow(chat_id_label, self.chat_id_input)
        
        # Message Thread ID Input
        message_thread_id_label = QLabel("Message Thread ID:")
        self.message_thread_id_input = QLineEdit()
        self.message_thread_id_input.setObjectName("settings_input")
        if hasattr(self._parent, 'message_thread_id'):
            self.message_thread_id_input.setText(self._parent.message_thread_id)
        telegram_layout.addRow(message_thread_id_label, self.message_thread_id_input)
        
        # Save Telegram Settings Button
        save_telegram_button = QPushButton("Save Telegram")
        save_telegram_button.setObjectName("save_button")
        save_telegram_button.clicked.connect(self.save_telegram_settings)
        telegram_layout.addRow("", save_telegram_button)
        
        scroll_layout.addWidget(telegram_group)
        
        # Application Settings Group
        app_settings_group = QGroupBox("Application")
        app_settings_group.setObjectName("settings_group")
        app_settings_layout = QFormLayout(app_settings_group)
        app_settings_layout.setSpacing(12)
        app_settings_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        app_settings_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        app_settings_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        app_settings_layout.setContentsMargins(20, 24, 20, 20)
        
        # Preferred Music Player Setting
        preferred_music_player_label = QLabel("Preferred Music Player:")
        self.preferred_music_player_combo = QComboBox()
        self.preferred_music_player_combo.setObjectName("settings_combo")
        self.preferred_music_player_combo.addItems(["Spotify", "Tidal"])
        if hasattr(self._parent, 'preferred_music_player'):
            index = self.preferred_music_player_combo.findText(self._parent.preferred_music_player)
            if index >= 0:
                self.preferred_music_player_combo.setCurrentIndex(index)
        
        app_settings_layout.addRow(preferred_music_player_label, self.preferred_music_player_combo)
        
        # Save Application Settings Button
        save_app_settings_button = QPushButton("Save Application")
        save_app_settings_button.setObjectName("save_button")
        save_app_settings_button.clicked.connect(self.save_application_settings)
        app_settings_layout.addRow("", save_app_settings_button)
        
        scroll_layout.addWidget(app_settings_group)
        
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, 1)
        
        # Footer with close button
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 16, 0, 0)
        footer_layout.setSpacing(0)
        
        close_button = QPushButton("Close")
        close_button.setObjectName("close_button")
        close_button.clicked.connect(self.accept)
        close_button.setMinimumWidth(120)
        
        footer_layout.addStretch()
        footer_layout.addWidget(close_button)
        
        layout.addLayout(footer_layout)
        
        # Update Spotify auth status when dialog opens
        self.update_spotify_auth_status()

    def load_settings_stylesheet(self):
        """Load the dedicated settings stylesheet"""
        from main import resource_path  # Import the resource_path function
        
        settings_style_path = resource_path('settings_style.qss')
        if os.path.exists(settings_style_path):
            file = QFile(settings_style_path)
            if file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
                stream = QTextStream(file)
                self.setStyleSheet(stream.readAll())
                file.close()
                logging.info("Settings stylesheet loaded successfully.")
            else:
                logging.error(f"Failed to open settings stylesheet at {settings_style_path}.")
        else:
            logging.warning(f"Settings stylesheet not found at {settings_style_path}.")

    def update_spotify_auth_status(self):
        """Update the Spotify authentication status display"""
        if self._parent and hasattr(self._parent, 'spotify_auth') and self._parent.spotify_auth.access_token:
            self.spotify_auth_status.setText("✓ Connected to Spotify")
            self.spotify_auth_status.setProperty("logged_in", True)
            self.spotify_login_button.setEnabled(False)
            self.spotify_logout_button.setEnabled(True)
        else:
            self.spotify_auth_status.setText("⚠ Not connected to Spotify")
            self.spotify_auth_status.setProperty("logged_in", False)
            self.spotify_login_button.setEnabled(True)
            self.spotify_logout_button.setEnabled(False)
        
        # Force style refresh
        self.spotify_auth_status.style().unpolish(self.spotify_auth_status)
        self.spotify_auth_status.style().polish(self.spotify_auth_status)
    
    def login_to_spotify(self):
        """Delegate to parent's login method"""
        if self._parent and hasattr(self._parent, 'login_to_spotify'):
            self._parent.login_to_spotify()
    
    def logout_from_spotify(self):
        """Delegate to parent's logout method"""
        if self._parent and hasattr(self._parent, 'logout_from_spotify'):
            self._parent.logout_from_spotify()
    
    def save_webhook_settings(self):
        """Save webhook settings"""
        if self._parent and hasattr(self._parent, 'save_webhook_settings'):
            # Update parent's webhook_url_input if needed
            if hasattr(self._parent, 'webhook_url_input'):
                self._parent.webhook_url_input.setText(self.webhook_url_input.text())
            self._parent.save_webhook_settings()
    
    def save_telegram_settings(self):
        """Save telegram settings"""
        if self._parent and hasattr(self._parent, 'save_telegram_settings'):
            # Update parent's input fields if needed
            if hasattr(self._parent, 'bot_token_input'):
                self._parent.bot_token_input.setText(self.bot_token_input.text())
            if hasattr(self._parent, 'chat_id_input'):
                self._parent.chat_id_input.setText(self.chat_id_input.text())
            if hasattr(self._parent, 'message_thread_id_input'):
                self._parent.message_thread_id_input.setText(self.message_thread_id_input.text())
            self._parent.save_telegram_settings()
    
    def save_application_settings(self):
        """Save application settings"""
        if self._parent and hasattr(self._parent, 'save_application_settings'):
            # Update parent's combo box if needed
            if hasattr(self._parent, 'preferred_music_player_combo'):
                index = self.preferred_music_player_combo.findText(self.preferred_music_player_combo.currentText())
                if index >= 0:
                    self._parent.preferred_music_player_combo.setCurrentIndex(index)
            self._parent.save_application_settings()