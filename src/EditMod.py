import sys
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QDialogButtonBox, QLabel
)

class EditModWindow(QDialog):
    def __init__(self, parent, display_name, data):
        super().__init__(parent)

        self.setWindowTitle(f"Edit {display_name} info.json")
        self.setModal(True)
        self.setFixedSize(400, 250)  

        self.original_mod_type = data.get("mod_type", "pak")
        self.new_data = None

        # --- Layouts ---
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        main_layout.addLayout(form_layout)

        # --- Widgets ---
        self.name_edit = QLineEdit(data.get("name", display_name))
        self.version_edit = QLineEdit(data.get("version", "1.0"))
        self.author_edit = QLineEdit(data.get("author", "Unknown"))
        self.mod_page_edit = QLineEdit(data.get("mod_page", ""))

        self.mod_type_combo = QComboBox()
        self.mod_type_combo.addItems(["pak", "ue4ss-script", "ue4ss-logic"])
        self.mod_type_combo.setCurrentText(self.original_mod_type)

        form_layout.addRow(QLabel("Name:"), self.name_edit)
        form_layout.addRow(QLabel("Version:"), self.version_edit)
        form_layout.addRow(QLabel("Author:"), self.author_edit)
        form_layout.addRow(QLabel("Mod Type:"), self.mod_type_combo)
        form_layout.addRow(QLabel("Mod Page:"), self.mod_page_edit)

        # --- Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.on_save)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def on_save(self):
        self.new_data = {
            "name": self.name_edit.text().strip(),
            "version": self.version_edit.text().strip(),
            "author": self.author_edit.text().strip(),
            "mod_type": self.mod_type_combo.currentText(),
            "mod_page": self.mod_page_edit.text().strip()
        }
        # Clean up empty fields
        if not self.new_data["mod_page"]:
            del self.new_data["mod_page"]

        self.accept()

    def get_data(self):
        return self.new_data

if __name__ == '__main__':
    # Example usage for testing
    app = QApplication(sys.argv)
    sample_data = {
        "name": "My Awesome Mod",
        "version": "1.2.3",
        "author": "A. Coder",
        "mod_type": "pak",
        "mod_page": "https://gamebanana.com/mods/12345"
    }
    dialog = EditModWindow(None, "My Awesome Mod", sample_data)
    if dialog.exec():
        print("Saved data:", dialog.get_data())
        print("Original mod type:", dialog.original_mod_type)
    else:
        print("Cancelled")
    sys.exit(app.exec())