import sys
import threading
import requests
import platform
import ctypes

from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDialogButtonBox, QFrame
)
from PySide6.QtGui import QPixmap, QImage, QFont
from PySide6.QtCore import Qt, Signal, QObject

class ImageLoader(QObject):
    """Worker object to load an image in a separate thread."""
    image_loaded = Signal(QPixmap)
    image_failed = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            image = QImage()
            image.loadFromData(response.content)
            pixmap = QPixmap.fromImage(image)
            self.image_loaded.emit(pixmap)
        except Exception as e:
            print(f"Failed to load image for dialog: {e}")
            self.image_failed.emit("Failed to load image.")

class OneClickInstallDialog(QDialog):
    def __init__(self, parent, item_data):
        super().__init__(parent)

        self.item_data = item_data
        mod_name = self.item_data.get('_sName', 'Unknown Mod')

        self.setWindowTitle("Confirm Download")
        self.setModal(True)

        main_layout = QVBoxLayout(self)

        # --- Image ---
        self.image_label = QLabel("Loading image...")
        self.image_label.setFixedSize(360, 180)
        self.image_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.image_label)

        # --- Mod Name ---
        name_label = QLabel(mod_name)
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        name_label.setFont(font)
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(name_label)

        # --- Confirmation Text ---
        confirm_text = QLabel("Do you want to download this mod?")
        confirm_text.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(confirm_text)

        # --- Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        # --- Image Loading ---
        self._start_image_load()

        # --- Flash Window ---
        if platform.system() == "Windows":
            QApplication.alert(self)
        
        # Make the dialog non-resizable after all widgets are added
        self.setFixedSize(self.sizeHint())

    def _start_image_load(self):
        preview_media = self.item_data.get('_aPreviewMedia', {})
        images = preview_media.get('_aImages', [])
        if not images:
            self.on_image_failed("No preview image.")
            return

        base_url = images[0].get('_sBaseUrl')
        file_url = images[0].get('_sFile')
        if not base_url or not file_url:
            self.on_image_failed("Invalid image URL.")
            return

        image_url = f"{base_url}/{file_url}"
        self.image_loader = ImageLoader(image_url)
        self.thread = threading.Thread(target=self.image_loader.run, daemon=True)
        self.image_loader.image_loaded.connect(self.on_image_loaded)
        self.image_loader.image_failed.connect(self.on_image_failed)
        self.thread.start()

    def on_image_loaded(self, pixmap):
        self.image_label.setPixmap(pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))

    def on_image_failed(self, message):
        self.image_label.setText(message)