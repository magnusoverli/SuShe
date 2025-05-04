# image_handler.py

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QProgressBar
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThread
from PyQt6.QtGui import QPixmap, QImage
from io import BytesIO
from PIL import Image
import logging
import base64
from collections import OrderedDict

class ImageProcessor(QObject):
    """
    Worker class to process images asynchronously.
    """
    processing_finished = pyqtSignal(str, QPixmap)  # Emits base64 string and QPixmap
    processing_failed = pyqtSignal(str)             # Emits error message

    def __init__(self, image_data, size=(100, 100), format="WEBP"):
        super().__init__()
        self.image_data = image_data
        self.size = size
        self.format = format.upper()  # Store format as an instance variable

    def process_image(self):
        try:
            # Open and resize the image
            image = Image.open(BytesIO(self.image_data))
            image = image.convert("RGB") if self.format in ["JPEG", "WEBP"] else image  # Ensure compatibility
            image = image.resize(self.size, Image.Resampling.LANCZOS)

            # Save to bytes with optimization
            buffered = BytesIO()
            if self.format == "JPEG":
                image.save(buffered, format=self.format, optimize=True, quality=55)  # Reduced quality
            elif self.format == "WEBP":
                image.save(buffered, format=self.format, optimize=True, quality=55)  # Quality can be adjusted
            else:
                image.save(buffered, format=self.format, optimize=True)
            image_bytes = buffered.getvalue()
            
            # Encode to base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            # Convert to QPixmap
            qt_image = QImage.fromData(image_bytes, self.format.lower())
            if qt_image.isNull():
                raise ValueError("Failed to convert image to QImage.")
            pixmap = QPixmap.fromImage(qt_image)

            self.processing_finished.emit(base64_image, pixmap)
        except Exception as e:
            logging.error(f"Error processing image in thread: {e}")
            self.processing_failed.emit(str(e))

class ImageCache:
    """
    Simple in-memory cache for storing scaled pixmaps.
    Implements a Least Recently Used (LRU) eviction policy.
    """
    def __init__(self, capacity=100):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)  # Mark as recently used
            return self.cache[key]
        return None

    def set(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            evicted = self.cache.popitem(last=False)  # Evict least recently used item
            logging.debug(f"Evicted from cache: {evicted[0]}")