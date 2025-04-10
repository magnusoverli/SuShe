from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QLineEdit, QTextEdit, QComboBox, 
                            QGroupBox, QFormLayout, QFileDialog, QMessageBox, QCompleter)
import logging
import os
import requests
from datetime import datetime

class EditableComboBox(QComboBox):
    """
    Custom ComboBox that opens the dropdown when clicking anywhere in the control,
    even when the ComboBox is editable.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        
        # Make the line edit in the combobox forward mouse events to the combobox
        self.lineEdit().installEventFilter(self)
        
    def eventFilter(self, obj, event):
        """Filter events for the line edit to handle mouse clicks"""
        if obj == self.lineEdit() and event.type() == event.Type.MouseButtonPress:
            # When user clicks in the line edit area, show the dropdown
            self.showPopup()
            return True
        return super().eventFilter(obj, event)


class ManualAddAlbumDialog(QDialog):
    """
    Dialog for manually adding an album with a modern Spotify-like design.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
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
            cursor: pointer;
        """)
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
        
        # Country dropdown
        self.country_combo = QComboBox(self)
        self.country_combo.addItems(self.parent.countries)
        self.country_combo.setMinimumHeight(36)
        classification_form.addRow("Country:", self.country_combo)
        
        # Genre 1 dropdown - using our custom EditableComboBox
        self.genre1_combo = EditableComboBox(self)
        self.genre1_combo.addItems(self.parent.genres)
        self.genre1_combo.setMinimumHeight(36)
        # Add completer for better search
        completer1 = QCompleter(self.parent.genres, self.genre1_combo)
        completer1.setFilterMode(Qt.MatchFlag.MatchContains)
        completer1.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.genre1_combo.setCompleter(completer1)
        classification_form.addRow("Genre 1:", self.genre1_combo)
        
        # Genre 2 dropdown - using our custom EditableComboBox
        self.genre2_combo = EditableComboBox(self)
        self.genre2_combo.addItems(self.parent.genres)
        self.genre2_combo.setMinimumHeight(36)
        # Add completer for better search
        completer2 = QCompleter(self.parent.genres, self.genre2_combo)
        completer2.setFilterMode(Qt.MatchFlag.MatchContains)
        completer2.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.genre2_combo.setCompleter(completer2)
        classification_form.addRow("Genre 2:", self.genre2_combo)
        
        right_column.addWidget(classification_group)
        
        # Comments Group
        comments_group = QGroupBox("Comment")
        comments_layout = QVBoxLayout(comments_group)
        
        # Comments input
        self.comments_input = QTextEdit(self)
        self.comments_input.setPlaceholderText("")
        self.comments_input.setMinimumHeight(80)
        comments_layout.addWidget(self.comments_input)
        
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
    
    def image_preview_clicked(self, event):
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
            self.release_date_input.style().unpolish(self.release_date_input)
            self.release_date_input.style().polish(self.release_date_input)
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
        self.release_date_input.style().unpolish(self.release_date_input)
        self.release_date_input.style().polish(self.release_date_input)
        
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
        
        # Get selected values
        country = self.country_combo.currentText()
        genre1 = self.genre1_combo.currentText()
        genre2 = self.genre2_combo.currentText()
        comments = self.comments_input.toPlainText()
        
        # Add the album to the parent's table
        self.parent.add_manual_album_to_table(
            artist, album, release_date, self.cover_image_path,
            country, genre1, genre2, comments
        )
        
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