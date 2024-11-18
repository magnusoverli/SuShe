# image_handler.py

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt
from io import BytesIO
import base64
from PIL import Image


class ImageWidget(QWidget):
    def __init__(self, pixmap: QPixmap = None, parent: QWidget = None):
        super().__init__(parent)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.original_pixmap = pixmap
        if pixmap:
            self.update_scaled_pixmap()

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self.original_pixmap = pixmap
        self.update_scaled_pixmap()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_scaled_pixmap()

    def update_scaled_pixmap(self) -> None:
        if self.original_pixmap:
            scaled_pixmap = self.original_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.label.setPixmap(scaled_pixmap)


def encode_image_to_base64(image_data: bytes) -> tuple[str, bytes]:
    """Resize the image and encode it to a base64 string."""
    with Image.open(BytesIO(image_data)) as image:
        image.thumbnail((300, 300), Image.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    return base64_image, image_bytes


def decode_base64_to_pixmap(base64_image: str) -> QPixmap:
    """Decode a base64 string back to QPixmap."""
    image_bytes = base64.b64decode(base64_image)
    qt_image = QImage.fromData(image_bytes)
    return QPixmap.fromImage(qt_image)


def process_image_data(image_data: bytes, size: tuple[int, int] = (200, 200)) -> Image.Image:
    """Resize the image to the specified size using high-quality resampling."""
    with Image.open(BytesIO(image_data)) as image:
        return image.resize(size, Image.LANCZOS)
