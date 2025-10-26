from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialogButtonBox
)
from PySide6.QtCore import Qt

class ModUpdatePromptWindow(QDialog):
    def __init__(self, parent, mod_name, current_version, new_version):
        super().__init__(parent)

        self.setWindowTitle("Update Available")
        self.setModal(True)

        layout = QVBoxLayout(self)

        message = (
            f"A new version of {mod_name} is available!\n\n"
            f"Current version: v{current_version}\n"
            f"New version: v{new_version}"
        )
        layout.addWidget(QLabel(message))

        button_box = QDialogButtonBox()
        update_button = button_box.addButton("Update", QDialogButtonBox.AcceptRole)
        ignore_button = button_box.addButton("Ignore", QDialogButtonBox.RejectRole)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

        self.setAttribute(Qt.WA_DeleteOnClose)