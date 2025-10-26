import sys
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class ConflictDialog(QDialog):
    def __init__(self, parent, conflicts):
        """
        A dialog window to display mod file conflicts in a clear, sortable table.

        Args:
            parent: The parent Qt widget.
            conflicts (dict): A dictionary where keys are conflicting file paths
                              and values are lists of mod folder names.
        """
        super().__init__(parent)
        self.setWindowTitle("Mod Conflicts Detected")
        self.setModal(True)
        self.resize(900, 400)

        # --- Layouts & Widgets ---
        layout = QVBoxLayout(self)

        info_label1 = QLabel("The following files are present in multiple enabled mods.")
        font = QFont()
        font.setBold(True)
        info_label1.setFont(font)
        layout.addWidget(info_label1)

        info_label2 = QLabel("The mod with the highest priority (top of the list) will take precedence.")
        layout.addWidget(info_label2)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Conflicting File", "Provided by Mods"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.setSortingEnabled(True)
        layout.addWidget(self.tree)

        # --- Populate Data ---
        for file, mods in sorted(conflicts.items()):
            item = QTreeWidgetItem([file, ", ".join(mods)])
            self.tree.addTopLevelItem(item)

        self.tree.sortByColumn(0, Qt.AscendingOrder)