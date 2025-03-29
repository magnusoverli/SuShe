from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFileDialog,
                             QLineEdit, QPushButton, QMessageBox, QTextEdit, QTextBrowser)
from PyQt6.QtCore import Qt, pyqtSignal
import logging
from datetime import datetime
import os
import requests

# Assuming ImageWidget is defined elsewhere or needs to be imported
# If ImageWidget is in main.py, consider moving it to a utilities module or keep it in main.py
# For this example, we'll assume it's kept in main.py

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


class ManualAddAlbumDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cover_image_path = None  # Store the selected image path internally
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Add Album Manually")

        layout = QVBoxLayout()

        self.artistEdit = QLineEdit(self)
        self.artistEdit.setPlaceholderText("Artist")
        layout.addWidget(self.artistEdit)

        self.albumEdit = QLineEdit(self)
        self.albumEdit.setPlaceholderText("Album")
        layout.addWidget(self.albumEdit)

        self.releaseDateEdit = QLineEdit(self)
        self.releaseDateEdit.setPlaceholderText("Release Date (DD-MM-YYYY)")
        layout.addWidget(self.releaseDateEdit)

        self.browseButton = QPushButton("Choose Cover Image", self)
        self.browseButton.clicked.connect(self.browse_cover_image)
        layout.addWidget(self.browseButton)

        # Country Drop-down
        countryLayout = QHBoxLayout()
        countryLabel = QLabel("Country:", self)
        countryLayout.addWidget(countryLabel)
        self.countryComboBox = QComboBox(self)
        self.countryComboBox.addItems(self.parent().countries)
        countryLayout.addWidget(self.countryComboBox)
        layout.addLayout(countryLayout)

        # Genre 1 Drop-down
        genre1Layout = QHBoxLayout()
        genre1Label = QLabel("Genre 1:", self)
        genre1Layout.addWidget(genre1Label)
        self.genre1ComboBox = QComboBox(self)
        self.genre1ComboBox.addItems(self.parent().genres)
        genre1Layout.addWidget(self.genre1ComboBox)
        layout.addLayout(genre1Layout)

        # Genre 2 Drop-down
        genre2Layout = QHBoxLayout()
        genre2Label = QLabel("Genre 2:", self)
        genre2Layout.addWidget(genre2Label)
        self.genre2ComboBox = QComboBox(self)
        self.genre2ComboBox.addItems(self.parent().genres)
        genre2Layout.addWidget(self.genre2ComboBox)
        layout.addLayout(genre2Layout)

        self.commentsEdit = QLineEdit(self)
        self.commentsEdit.setPlaceholderText("Comments")
        layout.addWidget(self.commentsEdit)

        self.submitButton = QPushButton("Add Album", self)
        self.submitButton.clicked.connect(self.add_album)
        layout.addWidget(self.submitButton)

        self.setLayout(layout)

    def browse_cover_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Cover Image", "", "Image Files (*.png *.jpg *.bmp)")
        if file_path:
            self.cover_image_path = file_path  # Store the selected image path internally
            self.browseButton.setText("Image Selected")  # Indicate that an image has been selected

    def add_album(self):
        artist = self.artistEdit.text().strip()
        album = self.albumEdit.text().strip()
        release_date = self.releaseDateEdit.text().strip()
        country = self.countryComboBox.currentText()
        genre1 = self.genre1ComboBox.currentText()
        genre2 = self.genre2ComboBox.currentText()
        comments = self.commentsEdit.text().strip()

        if not artist or not album or not release_date:
            QMessageBox.warning(self, "Input Error", "Please fill in all required fields (Artist, Album, Release Date).")
            return

        # Validate and convert the release date
        release_date_formatted = self.parse_date(release_date)
        if not release_date_formatted:
            QMessageBox.warning(self, "Input Error", "Invalid date format. Please use DDMMYY, DDMMYYYY, or DD-MM-YYYY.")
            return

        self.parent().add_manual_album_to_table(
            artist, album, release_date_formatted, self.cover_image_path,
            country, genre1, genre2, comments
        )
        self.accept()


    def parse_date(self, date_str):
        """Parse the date string into YYYY-MM-DD format."""
        formats = ["%d%m%y", "%d%m%Y", "%d-%m-%Y"]
        for fmt in formats:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None


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