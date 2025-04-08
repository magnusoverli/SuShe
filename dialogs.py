from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QLineEdit, QTextEdit, QComboBox, 
                            QGroupBox, QFormLayout, QFileDialog)
import logging

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
    def __init__(self, parent=None, countries=None, genres=None):
        super().__init__(parent)
        self.setWindowTitle("Add Album Manually")
        self.setMinimumWidth(500)
        
        # Initialize selected cover path
        self.selected_cover_path = None
        
        # Load countries and genres from files if not provided
        self.countries = countries if countries is not None else self.load_countries()
        self.genres = genres if genres is not None else self.load_genres()
        
        # Set up the dialog layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Add title
        title_label = QLabel("Add New Album")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        main_layout.addWidget(title_label)
        
        # Album Cover section
        cover_group = QGroupBox("Album Cover")
        cover_group.setStyleSheet("QGroupBox { border: 1px solid #333; border-radius: 5px; padding: 15px; }")
        cover_layout = QVBoxLayout(cover_group)
        
        # Placeholder for album cover
        self.cover_placeholder = QLabel("No image selected")
        self.cover_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_placeholder.setFixedSize(180, 180)
        self.cover_placeholder.setStyleSheet("background-color: #333; color: #888; border-radius: 3px;")
        
        # Center the cover placeholder
        cover_placeholder_layout = QHBoxLayout()
        cover_placeholder_layout.addStretch()
        cover_placeholder_layout.addWidget(self.cover_placeholder)
        cover_placeholder_layout.addStretch()
        cover_layout.addLayout(cover_placeholder_layout)
        
        # Add button to choose cover image
        self.choose_cover_btn = QPushButton("Choose Cover Image")
        self.choose_cover_btn.setFixedHeight(50)
        self.choose_cover_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                border-radius: 25px;
                padding: 10px;
                color: white;
            }
            QPushButton:hover {
                background-color: #444;
            }
        """)
        cover_layout.addWidget(self.choose_cover_btn)
        main_layout.addWidget(cover_group)
        
        # Album Details section
        details_group = QGroupBox("Album Details")
        details_group.setStyleSheet("QGroupBox { border: 1px solid #333; border-radius: 5px; padding: 15px; }")
        details_layout = QFormLayout(details_group)
        details_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        details_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        details_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        details_layout.setSpacing(10)
        
        # Artist input
        self.artist_input = QLineEdit()
        self.artist_input.setPlaceholderText("Enter artist name")
        self.artist_input.setFixedHeight(40)
        self.artist_input.setStyleSheet("background-color: #333; border-radius: 3px; padding: 5px; color: white;")
        details_layout.addRow("Artist:", self.artist_input)
        
        # Album input
        self.album_input = QLineEdit()
        self.album_input.setPlaceholderText("Enter album title")
        self.album_input.setFixedHeight(40)
        self.album_input.setStyleSheet("background-color: #333; border-radius: 3px; padding: 5px; color: white;")
        details_layout.addRow("Album:", self.album_input)
        
        # Release date input
        self.release_date_input = QLineEdit()
        self.release_date_input.setPlaceholderText("DD-MM-YYYY")
        self.release_date_input.setFixedHeight(40)
        self.release_date_input.setStyleSheet("background-color: #333; border-radius: 3px; padding: 5px; color: white;")
        details_layout.addRow("Release Date:", self.release_date_input)
        
        main_layout.addWidget(details_group)
        
        # Additional Information section
        additional_group = QGroupBox("Additional Information")
        additional_group.setStyleSheet("QGroupBox { border: 1px solid #333; border-radius: 5px; padding: 15px; }")
        additional_layout = QFormLayout(additional_group)
        additional_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        additional_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        additional_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        additional_layout.setSpacing(10)
        
        # Country dropdown
        self.country_combo = QComboBox()
        self.country_combo.setFixedHeight(40)
        self.country_combo.setStyleSheet("""
            QComboBox {
                background-color: #333;
                border-radius: 3px;
                padding: 5px;
                color: white;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 16px;
                height: 16px;
            }
        """)
        # Add countries from loaded list
        self.country_combo.addItems(self.countries)
        additional_layout.addRow("Country:", self.country_combo)
        
        # Primary Genre dropdown
        self.primary_genre_combo = QComboBox()
        self.primary_genre_combo.setFixedHeight(40)
        self.primary_genre_combo.setStyleSheet("""
            QComboBox {
                background-color: #333;
                border-radius: 3px;
                padding: 5px;
                color: white;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 16px;
                height: 16px;
            }
        """)
        # Add genres from loaded list
        self.primary_genre_combo.addItems(self.genres)
        additional_layout.addRow("Primary Genre:", self.primary_genre_combo)
        
        # Secondary Genre dropdown
        self.secondary_genre_combo = QComboBox()
        self.secondary_genre_combo.setFixedHeight(40)
        self.secondary_genre_combo.setStyleSheet("""
            QComboBox {
                background-color: #333;
                border-radius: 3px;
                padding: 5px;
                color: white;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 16px;
                height: 16px;
            }
        """)
        self.secondary_genre_combo.addItems(self.genres)
        additional_layout.addRow("Secondary Genre:", self.secondary_genre_combo)
        
        # Comments text area
        self.comments_input = QTextEdit()
        self.comments_input.setPlaceholderText("Add any additional comments (optional)")
        self.comments_input.setMaximumHeight(80)
        self.comments_input.setStyleSheet("background-color: #333; border-radius: 3px; padding: 5px; color: white;")
        additional_layout.addRow("Comments:", self.comments_input)
        
        main_layout.addWidget(additional_group)
        
        # Add Album button
        self.add_album_btn = QPushButton("Add Album")
        self.add_album_btn.setFixedHeight(50)
        self.add_album_btn.setStyleSheet("""
            QPushButton {
                background-color: #00C853;
                border-radius: 25px;
                padding: 10px;
                color: white;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #00E676;
            }
        """)
        
        # Add some spacing and center the button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.add_album_btn)
        button_layout.addStretch()
        
        main_layout.addLayout(button_layout)
        
        # Connect signals
        self.choose_cover_btn.clicked.connect(self.open_file_dialog)
        self.add_album_btn.clicked.connect(self.on_add_album_clicked)
    
    def load_countries(self):
        """Load countries from file"""
        try:
            countries = []
            # First try to find countries file in the same directory
            countries_file = os.path.join(os.path.dirname(__file__), "countries.txt")
            
            # If not found, try common locations
            if not os.path.exists(countries_file):
                possible_paths = [
                    os.path.join(os.path.dirname(__file__), "data", "countries.txt"),
                    os.path.join(os.path.dirname(__file__), "resources", "countries.txt"),
                    "countries.txt"  # Try current working directory
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        countries_file = path
                        break
            
            # Load countries if file exists
            if os.path.exists(countries_file):
                with open(countries_file, 'r', encoding='utf-8') as file:
                    countries = [line.strip() for line in file if line.strip()]
            
            # Fallback if file not found or empty
            if not countries:
                logging.warning("Countries file not found or empty. Using default countries list.")
                countries = ["United States", "United Kingdom", "Canada", "Japan", "Germany", "France"]
                
            return countries
        except Exception as e:
            logging.error(f"Error loading countries: {e}")
            return ["United States", "United Kingdom", "Canada", "Japan", "Germany", "France"]
    
    def load_genres(self):
        """Load genres from file"""
        try:
            genres = []
            # First try to find genres file in the same directory
            genres_file = os.path.join(os.path.dirname(__file__), "genres.txt")
            
            # If not found, try common locations
            if not os.path.exists(genres_file):
                possible_paths = [
                    os.path.join(os.path.dirname(__file__), "data", "genres.txt"),
                    os.path.join(os.path.dirname(__file__), "resources", "genres.txt"),
                    "genres.txt"  # Try current working directory
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        genres_file = path
                        break
            
            # Load genres if file exists
            if os.path.exists(genres_file):
                with open(genres_file, 'r', encoding='utf-8') as file:
                    genres = [line.strip() for line in file if line.strip()]
            
            # Fallback if file not found or empty
            if not genres:
                logging.warning("Genres file not found or empty. Using default genres list.")
                genres = ["Rock", "Pop", "Hip-Hop", "Jazz", "Classical", "Electronic", "R&B", "Country"]
                
            return genres
        except Exception as e:
            logging.error(f"Error loading genres: {e}")
            return ["Rock", "Pop", "Hip-Hop", "Jazz", "Classical", "Electronic", "R&B", "Country"]
    
    def open_file_dialog(self):
        """Open file dialog to select album cover"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Album Cover", 
            "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        
        if file_path:
            # Handle the selected image
            pixmap = QPixmap(file_path).scaled(
                self.cover_placeholder.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.cover_placeholder.setPixmap(pixmap)
            self.cover_placeholder.setText("")  # Clear the "No image selected" text
            # Store the file path for later use
            self.selected_cover_path = file_path
    
    def on_add_album_clicked(self):
        """Validate form data and accept the dialog if valid"""
        # Check required fields
        if not self.artist_input.text().strip():
            QMessageBox.warning(self, "Missing Information", "Please enter an artist name.")
            self.artist_input.setFocus()
            return
            
        if not self.album_input.text().strip():
            QMessageBox.warning(self, "Missing Information", "Please enter an album title.")
            self.album_input.setFocus()
            return
        
        # Store the album data for later retrieval
        self.album_data = self.get_album_data()
        
        # Log the addition
        logging.info(f"Manually adding album: {self.album_data['artist']} - {self.album_data['album']}")
        
        # Close the dialog with accept status
        self.accept()
            
    def get_album_data(self):
        """Return the collected data"""
        data = {
            "artist": self.artist_input.text().strip(),
            "album": self.album_input.text().strip(),
            "release_date": self.release_date_input.text().strip(),
            "country": self.country_combo.currentText(),
            "primary_genre": self.primary_genre_combo.currentText(),
            "secondary_genre": self.secondary_genre_combo.currentText(),
            "comments": self.comments_input.toPlainText().strip()
        }
        
        # Add cover image path if selected
        if self.selected_cover_path:
            data["cover_path"] = self.selected_cover_path
            
        return data


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