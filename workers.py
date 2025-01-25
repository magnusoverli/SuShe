import os
import logging
import tempfile
from pathlib import Path

import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThread

class DownloadWorker(QObject):
    """
    Downloads a file from GitHub, emits progress, success, or failure signals.
    """
    progress_changed = pyqtSignal(int)
    download_finished = pyqtSignal(str)
    download_failed = pyqtSignal(str)

    def __init__(self, download_url: str, github_token: str):
        super().__init__()
        self.download_url = download_url
        self.github_token = github_token
        self.is_cancelled = False

    def start_download(self, timeout: int = 30):
        try:
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/octet-stream",
            }
            resp = requests.get(self.download_url, headers=headers, stream=True, timeout=timeout)
            resp.raise_for_status()

            total_size = int(resp.headers.get('content-length', 0))
            downloaded_size = 0
            chunk_size = 1024 * 256  # 256 KB chunks for performance

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".exe")
            with temp_file, open(temp_file.name, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if self.is_cancelled:
                        os.unlink(temp_file.name)
                        return
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        progress = int((downloaded_size / total_size) * 100) if total_size else 0
                        self.progress_changed.emit(progress)
            self.download_finished.emit(temp_file.name)

        except requests.exceptions.RequestException as e:
            logging.error(f"Download failed: {e}")
            self.download_failed.emit(str(e))
        except Exception as e:
            logging.error(f"Unexpected download error: {e}")
            self.download_failed.emit(str(e))

class SubmitWorker(QThread):
    """
    Submits a file to a Telegram chat, emits success or failure signals.
    """
    submission_finished = pyqtSignal(bool, str)

    def __init__(self, bot_token: str, chat_id: str, message_thread_id: str, file_path: str, caption: str):
        super().__init__()
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id
        self.file_path = file_path
        self.caption = caption

    def run(self):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        try:
            with open(self.file_path, 'rb') as file:
                files = {'document': (Path(self.file_path).name, file)}
                data = {
                    'chat_id': self.chat_id,
                    'message_thread_id': int(self.message_thread_id),
                    'caption': self.caption
                }
                resp = requests.post(url, files=files, data=data, timeout=30)
                resp.raise_for_status()
            self.submission_finished.emit(True, "File submitted successfully.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Submission failed: {e}")
            desc = None
            try:
                desc = resp.json().get('description', str(e))
            except Exception:
                desc = str(e)
            self.submission_finished.emit(False, desc)
        except ValueError:
            msg = "Invalid message_thread_id; must be integer."
            logging.error(msg)
            self.submission_finished.emit(False, msg)
        except Exception as e:
            logging.error(f"Unexpected submit error: {e}")
            self.submission_finished.emit(False, str(e))

class Worker(QThread):
    """
    Executes a given function in a separate thread.
    """
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
            logging.error(f"Worker error: {e}")
            self.error.emit(e)
