# workers.py

import os
import logging
import tempfile
import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from telegram_bot import TelegramBot


class DownloadWorker(QObject):
    progress_changed = pyqtSignal(int)
    download_finished = pyqtSignal(str)
    download_failed = pyqtSignal(str)

    def __init__(self, download_url, github_token):
        super().__init__()
        self.download_url = download_url
        self.github_token = github_token
        self.is_cancelled = False

    def start_download(self):
        try:
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/octet-stream",
            }
            logging.debug(f"Starting download from URL: {self.download_url}")
            response = requests.get(self.download_url, headers=headers, stream=True)
            if response.status_code != 200:
                logging.error(f"Failed to download update. HTTP status code: {response.status_code}")
                self.download_failed.emit(f"Failed to download update. HTTP status code: {response.status_code}")
                return

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            chunk_size = 8192  # 8 KB

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
            with open(temp_file.name, 'wb') as f:
                for chunk in response.iter_content(chunk_size):
                    if self.is_cancelled:
                        logging.info("Update download canceled.")
                        temp_file.close()
                        os.unlink(temp_file.name)
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        progress = int(downloaded_size * 100 / total_size) if total_size else 0
                        self.progress_changed.emit(progress)
            logging.info("Update downloaded successfully.")
            self.download_finished.emit(temp_file.name)
        except Exception as e:
            logging.error(f"Failed to download update: {e}")
            self.download_failed.emit(str(e))


class SubmitWorker(QThread):
    submission_finished = pyqtSignal(bool, str)  # Signal to indicate submission status

    def __init__(self, bot_token, chat_id, message_thread_id, file_path, caption, parent=None):
        super().__init__(parent)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id
        self.file_path = file_path
        self.caption = caption

    def run(self):
        try:
            logging.info("Starting submission to Telegram.")
            # Initialize TelegramBot
            telegram_bot = TelegramBot(
                token=self.bot_token,
                chat_id=self.chat_id,
                message_thread_id=self.message_thread_id
            )

            # Ensure the file exists
            if not self.file_path or not os.path.exists(self.file_path):
                raise FileNotFoundError("Album file not found.")

            # Send the JSON file with an optional caption
            telegram_bot.send_json_file(self.file_path, caption=self.caption)

            logging.info("Submission to Telegram completed successfully.")
            self.submission_finished.emit(True, "Submission successful.")
        except Exception as e:
            logging.error(f"Error during submission: {e}")
            self.submission_finished.emit(False, str(e))


class Worker(QThread):
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            logging.error(f"Error in worker thread: {e}")
            self.error.emit(e)
