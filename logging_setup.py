# logging_setup.py

import logging
import sys
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import QObject, pyqtSignal

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
        print("Uncaught exception:", exc_type, exc_value, exc_traceback)  # Optional: Print to console
    sys.excepthook = handle_exception
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Logging setup complete")
    return text_edit_logger
