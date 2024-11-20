# test_telegram_bot.py
import unittest
from unittest.mock import patch, Mock
import requests
from telegram_bot import TelegramBot

class TestTelegramBot(unittest.TestCase):
    @patch('telegram_bot.requests.post')
    def test_send_album_list_success(self, mock_post):
        mock_post.return_value.status_code = 200
        bot = TelegramBot('fake_token', 'fake_chat_id')
        album_list = [{'artist': 'Artist', 'title': 'Album'}]
        bot.send_album_list(album_list)
        mock_post.assert_called_once_with(
            f"https://api.telegram.org/botfake_token/sendMessage",
            data={"chat_id": "fake_chat_id", "text": "Artist - Album"}
        )

    @patch('telegram_bot.requests.post')
    def test_send_album_list_network_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException
        bot = TelegramBot('fake_token', 'fake_chat_id')
        album_list = [{'artist': 'Artist', 'title': 'Album'}]
        with self.assertLogs('root', level='ERROR') as cm:
            bot.send_album_list(album_list)
            self.assertIn('Network error', cm.output[0])

    @patch('telegram_bot.requests.post')
    def test_retry_send_message(self, mock_post):
        mock_post.side_effect = [requests.exceptions.RequestException, Mock(status_code=200)]
        bot = TelegramBot('fake_token', 'fake_chat_id')
        message = "Test message"
        bot._retry_send_message(message)
        self.assertEqual(mock_post.call_count, 2)
        mock_post.assert_called_with(
            f"https://api.telegram.org/botfake_token/sendMessage",
            data={"chat_id": "fake_chat_id", "text": "Test message"}
        )

if __name__ == '__main__':
    unittest.main()