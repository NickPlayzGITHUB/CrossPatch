import sys
import datetime
import threading
import requests
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel, QTextBrowser,
    QTreeWidget, QTreeWidgetItem, QPushButton, QSplitter, QDialogButtonBox, QHeaderView, QMessageBox,
    QWidget, QFrame, QStyle
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
        # This method will be executed in a separate thread
        pass

class FileSelectDialog(QDialog):
    def __init__(self, parent, item_data):
        super().__init__(parent)

        self.item_data = item_data
        self.mod_name = self.item_data.get('_sName', 'Unknown Mod')
        self.files_data = sorted(
            self.item_data.get('_aFiles', []),
            key=lambda f: f.get('_tsDateAdded', 0),
            reverse=True
        )
        self.result = None

        self.setWindowTitle(f"Download Options for '{self.mod_name}'")
        self.resize(1100, 600)

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- Left Pane (Info) ---
        left_pane = QFrame()
        left_pane.setFrameShape(QFrame.StyledPanel)
        left_layout = QVBoxLayout(left_pane)
        splitter.addWidget(left_pane)

        self.image_label = QLabel("Loading image...")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedHeight(200)
        left_layout.addWidget(self.image_label)

        desc_label = QLabel("<b>Description</b>")
        left_layout.addWidget(desc_label)
        description = self.item_data.get('_sDescription', 'No description available.')
        desc_browser = QTextBrowser()
        desc_browser.setHtml(description)
        # Set a maximum height to keep the description area concise
        doc_height = desc_browser.document().size().toSize().height()
        desc_browser.setFixedHeight(doc_height + 5) # Add a small margin
        left_layout.addWidget(desc_browser)

        body_label = QLabel("<b>Readme</b>")
        left_layout.addWidget(body_label)
        
        body_text = QTextBrowser()
        body_text.setOpenExternalLinks(True)
        body_content = self.item_data.get('_sText', 'No readme content available.')
        body_text.setHtml(body_content)
        left_layout.addWidget(body_text)

        # --- Right Pane (Downloads) ---
        right_pane = QFrame()
        right_pane.setFrameShape(QFrame.StyledPanel)
        right_layout = QVBoxLayout(right_pane)
        splitter.addWidget(right_pane)

        # Set initial sizes for the splitter panes
        splitter.setSizes([350, 750])

        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["", "File Name", "Version", "Size", "Date Added", "Description"])
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Radio button column
        header.setSectionResizeMode(1, QHeaderView.Stretch)          # File Name
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Version
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Size
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents) # Date
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents) # Description
        self.tree.setSortingEnabled(True)
        self.tree.setSelectionMode(QTreeWidget.NoSelection) # We use checkboxes for selection

        for i, file_info in enumerate(self.files_data):
            file_name = file_info.get('_sFile', 'N/A')
            file_version = file_info.get('_sVersion', '')
            file_size_bytes = file_info.get('_nFilesize', 0)
            file_size_mb = f"{file_size_bytes / (1024*1024):.2f} MB" if file_size_bytes > 0 else "N/A"
            timestamp = file_info.get('_tsDateAdded', 0)
            date_added = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M') if timestamp > 0 else "N/A"
            description = file_info.get('_sDescription', '')
            
            item = QTreeWidgetItem(["", file_name, file_version, file_size_mb, date_added, description])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Unchecked)
            self.tree.addTopLevelItem(item)

        right_layout.addWidget(self.tree)
        # Connect itemChanged to handle the radio button logic
        self.tree.itemChanged.connect(self._on_item_changed)

        if self.tree.topLevelItemCount() > 0:
            # Check the first item by default
            self.tree.topLevelItem(0).setCheckState(0, Qt.Checked)

        # --- Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_button = button_box.button(QDialogButtonBox.Ok)
        ok_button.setText("Download")
        ok_button.setIcon(self.style().standardIcon(QStyle.SP_DialogOkButton))
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        cancel_button.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))

        button_box.accepted.connect(self.on_download)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        # --- Image Loading ---
        self._start_image_load()

    def _start_image_load(self):
        try:
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

            self.image_loader = ImageLoader(f"{base_url}/{file_url}")
            self.image_loader.image_loaded.connect(self.on_image_loaded)
            self.image_loader.image_failed.connect(self.on_image_failed)
            
            # Run the image loading in a background thread
            self.thread = threading.Thread(target=self._load_image_worker, daemon=True)
            self.thread.start()

        except Exception as e:
            print(f"Failed to load image: {e}")
            self.on_image_failed("Failed to load image.")

    def _load_image_worker(self):
        """Worker function to download and emit image data."""
        response = requests.get(self.image_loader.url, timeout=10)
        response.raise_for_status()
        image = QImage()
        image.loadFromData(response.content)
        self.image_loader.image_loaded.emit(QPixmap.fromImage(image))

    def on_image_loaded(self, pixmap):
        self.image_label.setPixmap(pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        ))

    def on_image_failed(self, message):
        self.image_label.setText(message)

    def _on_item_changed(self, item, column):
        """Ensures only one item can be checked at a time, simulating radio buttons."""
        if column == 0 and item.checkState(0) == Qt.Checked:
            # Block signals to prevent recursive calls while we change other items
            self.tree.blockSignals(True)
            for i in range(self.tree.topLevelItemCount()):
                other_item = self.tree.topLevelItem(i)
                if other_item is not item:
                    other_item.setCheckState(0, Qt.Unchecked)
            # Unblock signals
            self.tree.blockSignals(False)

    def on_download(self):
        checked_item = None
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                checked_item = item
                break

        if not checked_item:
            QMessageBox.warning(self, "No Selection", "Please select a file to download.")
            return

        selected_index = self.tree.indexOfTopLevelItem(checked_item)
        self.result = self.files_data[selected_index]
        self.accept()

    def get_selection(self):
        return self.result

if __name__ == '__main__':
    # This is for testing purposes
    app = QApplication(sys.argv)
    # You would need to provide some sample item_data here to run this directly
    sample_data = {
        '_sName': 'Test Mod',
        '_sDescription': 'This is a test description.',
        '_sText': '<h1>Readme</h1><p>This is the readme content.</p>',
        '_aFiles': [
            {'_sFile': 'test_mod_v1.zip', '_sVersion': '1.0', '_nFilesize': 1024, '_tsDateAdded': 1672531200, '_sDescription': 'Version 1.0'},
            {'_sFile': 'test_mod_v2.zip', '_sVersion': '2.0', '_nFilesize': 2048, '_tsDateAdded': 1675209600, '_sDescription': 'Version 2.0'},
        ]
    }
    dialog = FileSelectDialog(None, sample_data)
    if dialog.exec():
        print("Selected file:", dialog.get_selection())
    sys.exit(app.exec())
