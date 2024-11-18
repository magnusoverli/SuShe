# image_handler.py

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt
from io import BytesIO
import base64
from PIL import Image

class ImageWidget(QWidget):
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
        self.original_pixmap = pixmap
        self.updateScaledPixmap()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateScaledPixmap()

    def updateScaledPixmap(self):
        if hasattr(self, 'original_pixmap') and self.original_pixmap:
            scaled_pixmap = self.original_pixmap.scaled(
                self.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.label.setPixmap(scaled_pixmap)

def encode_image_to_base64(image_data):
    """Resize the image and encode it to a base64 string."""
    image = Image.open(BytesIO(image_data))
    image.thumbnail((200, 200), Image.LANCZOS)  # Resize while keeping aspect ratio
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    image_bytes = buffered.getvalue()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    return base64_image, image_bytes

def decode_base64_to_pixmap(base64_image):
    """Decode a base64 string back to QPixmap."""
    image_bytes = base64.b64decode(base64_image)
    qt_image = QImage.fromData(image_bytes)
    pixmap = QPixmap.fromImage(qt_image)
    return pixmap