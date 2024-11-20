# telegram_bot.py
import logging
import time
import requests
import os

class TelegramBot:
    """
    A bot to send album lists or files to a specified Telegram chat.

    Attributes:
        token (str): Telegram bot token.
        chat_id (str): Telegram chat ID.
        message_thread_id (str): Telegram message thread ID (optional).
    """
    def __init__(self, token, chat_id, message_thread_id=None):
        """
        Initializes the TelegramBot with token, chat_id, and optional message_thread_id.

        Args:
            token (str): Telegram bot token.
            chat_id (str): Telegram chat ID.
            message_thread_id (str, optional): Telegram message thread ID.
        """
        self.token = token
        self.chat_id = chat_id
        self.message_thread_id = message_thread_id
        self.base_url = f"https://api.telegram.org/bot{token}/"

    def send_album_list(self, album_list, caption=None):
        """
        Sends a formatted album list as a plain text message to the Telegram chat.

        Args:
            album_list (list): List of albums to format and send.
            caption (str, optional): Optional caption to prepend to the message.
        """
        try:
            message = self._format_album_list(album_list, caption)
            self._send_message(message)
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error: {e}")
            # Retry mechanism
            self._retry_send_message(message)
        except Exception as e:
            logging.error(f"Unexpected error: {e}")

    def send_json_file(self, file_path, caption=None):
        """
        Sends a JSON file to the Telegram chat.

        Args:
            file_path (str): Path to the JSON file to send.
            caption (str, optional): Optional caption to include with the file.
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"The file {file_path} does not exist.")

            with open(file_path, 'rb') as file:
                files = {'document': file}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption or 'Here is the album list in JSON format.'
                }
                if self.message_thread_id:
                    data['message_thread_id'] = self.message_thread_id  # For threaded messages

                url = f"{self.base_url}sendDocument"
                response = requests.post(url, data=data, files=files)
                response.raise_for_status()
                logging.info(f"Successfully sent file {file_path} to Telegram.")
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error while sending file: {e}")
            self._retry_send_file(file_path, caption, retries=3, delay=2)
        except Exception as e:
            logging.error(f"Unexpected error while sending file: {e}")

    def _send_message(self, message):
        """
        Sends a plain text message to the Telegram chat.

        Args:
            message (str): The message to send.
        """
        url = f"{self.base_url}sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"  # Enable Markdown formatting
        }
        if self.message_thread_id:
            payload["message_thread_id"] = self.message_thread_id  # For threaded messages
        response = requests.post(url, data=payload)
        response.raise_for_status()

    def _retry_send_message(self, message, retries=3, delay=2):
        """
        Retries sending a plain text message in case of failure.

        Args:
            message (str): The message to send.
            retries (int, optional): Number of retry attempts. Defaults to 3.
            delay (int, optional): Delay between retries in seconds. Defaults to 2.
        """
        for attempt in range(retries):
            try:
                self._send_message(message)
                logging.info("Message sent successfully on retry.")
                return
            except requests.exceptions.RequestException as e:
                logging.warning(f"Retry {attempt + 1}/{retries} failed: {e}")
                time.sleep(delay)
        logging.error("All retries for sending message failed.")

    def _retry_send_file(self, file_path, caption, retries=3, delay=2):
        """
        Retries sending a file in case of failure.

        Args:
            file_path (str): Path to the JSON file to send.
            caption (str, optional): Optional caption to include with the file.
            retries (int, optional): Number of retry attempts. Defaults to 3.
            delay (int, optional): Delay between retries in seconds. Defaults to 2.
        """
        for attempt in range(retries):
            try:
                self.send_json_file(file_path, caption)
                logging.info("File sent successfully on retry.")
                return
            except requests.exceptions.RequestException as e:
                logging.warning(f"Retry {attempt + 1}/{retries} for file sending failed: {e}")
                time.sleep(delay)
            except Exception as e:
                logging.error(f"Unexpected error on retry {attempt + 1}/{retries}: {e}")
        logging.error("All retries for sending file failed.")

    def _format_album_list(self, album_list, caption=None):
        """
        Formats the album list into a string message with an optional caption.

        Args:
            album_list (list): List of albums to format.
            caption (str, optional): Optional caption to prepend to the message.

        Returns:
            str: Formatted album list.
        """
        message_lines = []
        if caption:
            message_lines.append(f"*{caption}*")
            message_lines.append("")  # Add a newline for spacing
        for idx, album in enumerate(album_list, start=1):
            artist = album.get("artist", "Unknown Artist")
            title = album.get("title", "Unknown Album")
            message_lines.append(f"{idx}. *{artist}* - _{title}_")
        return "\n".join(message_lines)