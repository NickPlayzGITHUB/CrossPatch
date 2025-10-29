import sys
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QListWidget, QListWidgetItem,
    QDialogButtonBox, QWidget, QHBoxLayout, QPushButton, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from Util import add_ignored_conflict


class ConflictDialog(QDialog):
    """
    A dialog to inform the user about mod conflicts. It presents a summary
    of conflicting mods with an option to view detailed file lists.
    """
    def __init__(self, parent, title, conflicts):
        """
        Args:
            parent: parent widget
            title: The title for the dialog, often the mod being enabled.
            conflicts: dict mapping game file path -> list of (provider_mod, pak_name) tuples
        """
        super().__init__(parent)
        self.setWindowTitle("Mod Conflict Detected")
        self.setModal(True)
        self.setMinimumWidth(850)

        self.title = title
        self.conflicts = conflicts

        main_layout = QVBoxLayout(self)

        # --- Summary ---
        summary_text = f"The following mods conflict with each other (they modify the same game files):"
        main_layout.addWidget(QLabel(summary_text))

        # --- Conflicting Mods Summary ---
        self.conflicting_mods_list = QTreeWidget()
        self.conflicting_mods_list.setHeaderHidden(True)
        main_layout.addWidget(self.conflicting_mods_list)
        self._populate_summary_list()

        # --- Details Section (collapsible) ---
        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(0, 5, 0, 0)
        details_layout.addWidget(QLabel("<b>Conflicting Files:</b>"))

        self.details_tree = QTreeWidget()
        self.details_tree.setColumnCount(2)
        self.details_tree.setHeaderLabels(["File Path", "Provided By"])
        self.details_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.details_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.details_tree.setMinimumHeight(200)
        details_layout.addWidget(self.details_tree)
        self.details_widget.setVisible(False) # Hidden by default
        main_layout.addWidget(self.details_widget)
        self._populate_details_tree()

        # --- Buttons ---
        button_layout = QHBoxLayout()

        self.details_button = QPushButton("View Details")
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self.details_widget.setVisible)
        button_layout.addWidget(self.details_button)

        button_layout.addStretch()

        button_box = QDialogButtonBox()
        self.ignore_button = button_box.addButton("Ignore Future Conflicts", QDialogButtonBox.ActionRole)
        self.ok_button = button_box.addButton("OK", QDialogButtonBox.AcceptRole)
        self.ignore_button.clicked.connect(self.on_ignore)
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(button_box)

        main_layout.addLayout(button_layout)
        self.adjustSize()

    def _populate_summary_list(self):
        """Fills the summary list with pairs of conflicting mods."""
        mod_pairs = set()
        for providers in self.conflicts.values():
            mod_names = sorted([p[0] for p in providers])
            for i in range(len(mod_names)):
                for j in range(i + 1, len(mod_names)):
                    mod_pairs.add(tuple(sorted((mod_names[i], mod_names[j]))))
        
        if not mod_pairs:
            self.conflicting_mods_list.addTopLevelItem(QTreeWidgetItem(["No conflicts found."]))
            return

        for mod1, mod2 in sorted(list(mod_pairs)):
            item = QTreeWidgetItem([f"'{mod1}' ⇄ '{mod2}'"])
            item.setData(0, Qt.UserRole, (mod1, mod2)) # Store the pair
            self.conflicting_mods_list.addTopLevelItem(item)

    def _populate_details_tree(self):
        """Fills the collapsible details tree with specific file conflicts."""
        # A dictionary to keep track of tree items to avoid creating duplicates
        # The key will be the full path of the node as a tuple (e.g., ('Content', 'Characters'))
        # The value will be the QTreeWidgetItem
        nodes = {}
        root = self.details_tree.invisibleRootItem()

        for file_path, providers in sorted(self.conflicts.items()):
            # Split the path into components, ensuring consistent separators
            path_parts = file_path.replace('\\', '/').split('/')
            parent_item = root

            # Traverse the path components, creating folder nodes as needed
            for i in range(len(path_parts)):
                current_path_tuple = tuple(path_parts[:i+1])
                
                if current_path_tuple in nodes:
                    parent_item = nodes[current_path_tuple]
                else:
                    node_text = path_parts[i]
                    new_item = QTreeWidgetItem([node_text])
                    
                    # If this is the last part (the file itself), add the provider info
                    if i == len(path_parts) - 1:
                        provider_str = ", ".join([f"{mod} ({pak.split('/')[-1]})" for mod, pak in providers])
                        new_item.setText(1, provider_str)
                    
                    parent_item.addChild(new_item)
                    nodes[current_path_tuple] = new_item
                    parent_item = new_item

    def on_ignore(self):
        """Saves the selected mod pairs to the ignored list and closes."""
        selected_items = self.conflicting_mods_list.selectedItems()
        if not selected_items:
            for i in range(self.conflicting_mods_list.topLevelItemCount()):
                selected_items.append(self.conflicting_mods_list.topLevelItem(i))

        for item in selected_items:
            mod1, mod2 = item.data(0, Qt.UserRole)
            add_ignored_conflict(mod1, mod2)
            add_ignored_conflict(mod2, mod1) # Add the reverse pair too
        
        self.accept()