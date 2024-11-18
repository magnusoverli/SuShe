# workers.py

import os
import json
import logging
import tempfile
from pathlib import Path
import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThread


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
    submission_finished = pyqtSignal(bool, str)  # Signal to emit the result

    def __init__(self, bot_token, chat_id, message_thread_id, file_path, caption):
        super().__init__()
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id
        self.file_path = file_path
        self.caption = caption  # New attribute for the caption

    def run(self):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        try:
            with open(self.file_path, 'rb') as file:
                files = {'document': (Path(self.file_path).name, file)}
                data = {
                    'chat_id': self.chat_id,
                    'message_thread_id': int(self.message_thread_id),  # Ensure it's an integer
                    'caption': self.caption  # Include the caption in the data
                }

                logging.info(f"Submitting file {self.file_path} to Telegram with caption: {self.caption}")
                response = requests.post(url, files=files, data=data)
                response.raise_for_status()
                logging.info(f"File {self.file_path} submitted successfully")
                self.submission_finished.emit(True, "File submitted successfully.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to submit file {self.file_path}: {e}")
            error_info = ""
            try:
                error_info = response.json().get('description', 'No error description provided.')
            except:
                error_info = str(e)
            self.submission_finished.emit(False, error_info)
        except ValueError as ve:
            logging.error(f"Invalid message_thread_id: {self.message_thread_id}. It must be an integer.")
            self.submission_finished.emit(False, "Invalid message_thread_id. It must be an integer.")
        except Exception as e:
            logging.error(f"An unexpected error occurred while submitting the file: {e}")
            self.submission_finished.emit(False, f"An unexpected error occurred: {e}")


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
