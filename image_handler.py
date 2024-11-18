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
            image = image.resize(self.size, Image.LANCZOS)
            
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
            
            logging.debug(f"Image processed to size: {self.size} and format: {self.format}")
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

class ImageWidget(QWidget):
    """
    A widget to display images, automatically scaling them to fit the widget's size while maintaining aspect ratio.
    Handles asynchronous image processing to ensure UI responsiveness.
    """
    def __init__(self, image_data=None, size=(100, 100), format="WEBP", parent=None):
        super().__init__(parent)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.hide()
        
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.progress_bar)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.base64_image = None  # To store the base64 image if needed
        self.scaled_pixmap_cache = ImageCache(capacity=100)
        self.image_processor_thread = None
        self.image_processor = None
        
        if image_data:
            self.setImageAsync(image_data=image_data, size=size, format=format)

    def setImageAsync(self, image_data, size=(100, 100), format="WEBP"):
        """
        Sets the image asynchronously to prevent blocking the UI.

        Args:
            image_data (bytes): Raw image data.
            size (tuple): Desired image size.
            format (str): Image format ('WEBP' or 'JPEG').
        """
        self.progress_bar.show()
        
        self.image_processor_thread = QThread()
        self.image_processor = ImageProcessor(image_data, size, format)
        self.image_processor.moveToThread(self.image_processor_thread)
        
        self.image_processor_thread.started.connect(self.image_processor.process_image)
        self.image_processor.processing_finished.connect(self.on_processing_finished)
        self.image_processor.processing_failed.connect(self.on_processing_failed)
        
        self.image_processor.processing_finished.connect(self.image_processor_thread.quit)
        self.image_processor.processing_failed.connect(self.image_processor_thread.quit)
        
        self.image_processor_thread.finished.connect(self.image_processor.deleteLater)
        self.image_processor_thread.finished.connect(self.image_processor_thread.deleteLater)
        
        self.image_processor_thread.start()

    def on_processing_finished(self, base64_image, pixmap):
        """
        Slot to handle the completion of image processing.

        Args:
            base64_image (str): Base64 encoded image string.
            pixmap (QPixmap): Processed QPixmap.
        """
        self.progress_bar.hide()
        self.base64_image = base64_image
        self.original_pixmap = pixmap
        self.updateScaledPixmap()

    def on_processing_failed(self, error_message):
        """
        Slot to handle image processing failure.

        Args:
            error_message (str): Description of the error.
        """
        self.progress_bar.hide()
        logging.error(f"Image processing failed: {error_message}")
        # Optionally, display an error message to the user
        self.label.setText("Failed to load image.")

    def setPixmap(self, pixmap):
        """
        Sets the pixmap directly (synchronous).

        Args:
            pixmap (QPixmap): QPixmap to display.
        """
        self.original_pixmap = pixmap
        self.updateScaledPixmap()

    def resizeEvent(self, event):
        """
        Overrides the resize event to update the pixmap scaling.
        """
        super().resizeEvent(event)
        self.updateScaledPixmap()

    def updateScaledPixmap(self):
        """
        Scales the original pixmap to fit the current widget size while maintaining aspect ratio.
        Utilizes caching to improve performance.
        """
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            size = self.size()
            cached_pixmap = self.scaled_pixmap_cache.get(size)
            if cached_pixmap:
                self.label.setPixmap(cached_pixmap)
                logging.debug(f"Loaded pixmap from cache for size: {size}")
            else:
                scaled_pixmap = self.original_pixmap.scaled(
                    size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.scaled_pixmap_cache.set(size, scaled_pixmap)
                self.label.setPixmap(scaled_pixmap)
                logging.debug(f"Scaled pixmap to size: {size} and cached.")
