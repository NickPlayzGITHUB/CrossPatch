from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox,
    QPushButton, QMessageBox, QHBoxLayout, QLabel
)
from PySide6.QtCore import Qt
from Util import load_ignored_conflicts, save_ignored_conflicts


class IgnoredConflictsDialog(QDialog):
    """Dialog to view and clear ignored conflict pairs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ignored Conflicts")
        self.resize(600, 400)

        main_layout = QVBoxLayout(self)

        header = QLabel("Ignored conflict pairs (mod ⇄ provider).\nUse the controls below to remove individual entries or clear all.")
        main_layout.addWidget(header)

        self.list_widget = QListWidget()
        main_layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected)
        btn_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_all)
        btn_layout.addWidget(self.clear_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        main_layout.addLayout(btn_layout)

        self._load_entries()

    def _load_entries(self):
        self.list_widget.clear()
        data = load_ignored_conflicts()
        for entry in data:
            mod = entry.get("mod")
            provider = entry.get("provider")
            item = QListWidgetItem(f"{mod} ⇄ {provider}")
            item.setData(Qt.UserRole, entry)
            self.list_widget.addItem(item)

    def remove_selected(self):
        to_remove = []
        for item in self.list_widget.selectedItems():
            to_remove.append(item.data(Qt.UserRole))
        if not to_remove:
            return
        data = load_ignored_conflicts()
        new_data = [d for d in data if d not in to_remove]
        save_ignored_conflicts(new_data)
        self._load_entries()

    def clear_all(self):
        reply = QMessageBox.question(self, "Clear All", "Clear all ignored conflict entries? This cannot be undone.")
        if reply != QMessageBox.Yes:
            return
        save_ignored_conflicts([])
        self._load_entries()
