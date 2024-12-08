# setup_wizard.py

from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QLabel, QLineEdit, QVBoxLayout, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt
import json
import os
import logging
import sys

class SetupWizard(QWizard):
    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.setWindowTitle("SuSheApp Setup Wizard")

        # Add pages
        self.addPage(SpotifyCredentialsPage())
        self.addPage(TelegramCredentialsPage())
        self.addPage(ApplicationSettingsPage())

        # Customize button text
        self.setButtonText(QWizard.Button.NextButton, "Next")
        self.setButtonText(QWizard.Button.BackButton, "Back")
        self.setButtonText(QWizard.Button.FinishButton, "Finish")

    def accept(self):
        # Gather data from all pages and save to config.json
        spotify_page = self.page(0)
        telegram_page = self.page(1)
        app_settings_page = self.page(2)

        config = {
            "spotify": {
                "client_id": spotify_page.client_id_input.text().strip(),
                "client_secret": spotify_page.client_secret_input.text().strip()
            },
            "telegram": {
                "bot_token": telegram_page.bot_token_input.text().strip(),
                "chat_id": telegram_page.chat_id_input.text().strip(),
                "message_thread_id": telegram_page.message_thread_id_input.text().strip()
            },
            "application": {
                "preferred_music_player": app_settings_page.music_player_combo.currentText()
            }
        }

        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as config_file:
                json.dump(config, config_file, indent=4)
            logging.info("Configuration saved successfully via Setup Wizard.")
            QMessageBox.information(self, "Setup Complete", "Configuration saved successfully!")
            super().accept()
        except Exception as e:
            logging.error(f"Failed to save configuration: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")

class SpotifyCredentialsPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Spotify API Credentials")

        layout = QVBoxLayout()

        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("Enter Spotify Client ID")
        layout.addWidget(QLabel("Client ID:"))
        layout.addWidget(self.client_id_input)

        self.client_secret_input = QLineEdit()
        self.client_secret_input.setPlaceholderText("Enter Spotify Client Secret")
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(QLabel("Client Secret:"))
        layout.addWidget(self.client_secret_input)

        self.setLayout(layout)

    def validatePage(self):
        if not self.client_id_input.text().strip() or not self.client_secret_input.text().strip():
            QMessageBox.warning(self, "Input Error", "Please provide both Client ID and Client Secret.")
            return False
        return True

class TelegramCredentialsPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Telegram Submission Settings")

        layout = QVBoxLayout()

        self.bot_token_input = QLineEdit()
        self.bot_token_input.setPlaceholderText("Enter Telegram Bot Token")
        layout.addWidget(QLabel("Bot Token:"))
        layout.addWidget(self.bot_token_input)

        self.chat_id_input = QLineEdit()
        self.chat_id_input.setPlaceholderText("Enter Telegram Chat ID")
        layout.addWidget(QLabel("Chat ID:"))
        layout.addWidget(self.chat_id_input)

        self.message_thread_id_input = QLineEdit()
        self.message_thread_id_input.setPlaceholderText("Enter Telegram Message Thread ID")
        layout.addWidget(QLabel("Message Thread ID:"))
        layout.addWidget(self.message_thread_id_input)

        self.setLayout(layout)

    def validatePage(self):
        if not self.bot_token_input.text().strip() or not self.chat_id_input.text().strip():
            QMessageBox.warning(self, "Input Error", "Please provide both Bot Token and Chat ID.")
            return False
        return True

class ApplicationSettingsPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Application Settings")

        layout = QVBoxLayout()

        self.music_player_combo = QComboBox()
        self.music_player_combo.addItems(["Spotify", "Tidal"])
        layout.addWidget(QLabel("Preferred Music Player:"))
        layout.addWidget(self.music_player_combo)

        self.setLayout(layout)

    def validatePage(self):
        # Additional validation if needed
        return True

