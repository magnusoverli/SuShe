# utils.py

import sys
import os
import logging
import re
from html import unescape
from PIL import Image
from io import BytesIO

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def read_file_lines(filepath):
    correct_path = resource_path(filepath)
    logging.debug(f"Reading file: {correct_path}")
    with open(correct_path, 'r', encoding='utf-8') as file:
        lines = set(line.strip() for line in file)
        if 'genres.txt' in filepath:
            lines = {line.title() for line in lines}
        logging.debug(f"Read {len(lines)} lines from {filepath}")
        return sorted(lines)

def strip_html_tags(text):
    clean = re.compile('<.*?>')
    return unescape(re.sub(clean, '', text))