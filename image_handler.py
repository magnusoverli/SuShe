# image_handler.py

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt
from io import BytesIO
from PIL import Image
import logging

class ImageWidget(QWidget):
    """
    A widget to display images, automatically scaling them to fit the widget's size while maintaining aspect ratio.
    """
    def __init__(self, pixmap=None, parent=None):
        super().__init__(parent)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.base64_image = None  # To store the base64 image if needed
        if pixmap:
            self.setPixmap(pixmap)

    def setPixmap(self, pixmap):
        """
        Sets the pixmap for the label and updates the display.
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
        """
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            scaled_pixmap = self.original_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.label.setPixmap(scaled_pixmap)

def process_image_data(image_data, size=(200, 200)):
    """
    Processes raw image data by resizing it to the specified size.

    Args:
        image_data (bytes): The raw image data.
        size (tuple): The desired size as (width, height).

    Returns:
        PIL.Image.Image: The resized image.
    """
    try:
        image = Image.open(BytesIO(image_data))
        image = image.resize(size, Image.LANCZOS)
        logging.debug(f"Image processed to size: {size}")
        return image
    except Exception as e:
        logging.error(f"Error processing image data: {e}")
        return None
