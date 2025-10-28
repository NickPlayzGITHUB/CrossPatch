import sys
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QListWidget, QListWidgetItem,
    QDialogButtonBox, QWidget, QHBoxLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class ConflictDialog(QDialog):
    """Unified conflict dialog showing conflicted game files and provider mods.

    Left pane: concise list of conflicting game file paths with a preview of providers.
    Right pane: checklist of provider mods (with pak names) where the user can
                select providers to "don't remind me" for this specific mod.
    """
    def __init__(self, parent, mod_name, conflicts):
        """
        Args:
            parent: parent widget
            mod_name: the mod being enabled (string)
            conflicts: dict mapping game file path -> list of (provider_mod, pak_name) tuples
        """
        super().__init__(parent)
        self.setWindowTitle("Conflicts Detected")
        self.setModal(True)
        self.resize(900, 450)

        self.mod_name = mod_name
        self.conflicts = conflicts

        main_layout = QVBoxLayout(self)

        header = QLabel("The following game files are provided by multiple enabled mods.")
        font = QFont()
        font.setBold(True)
        header.setFont(font)
        main_layout.addWidget(header)

        sublabel = QLabel("Select provider mods on the right to stop being reminded about them for this mod.")
        main_layout.addWidget(sublabel)

        content = QWidget()
        content_layout = QHBoxLayout(content)

        # Left: file list
        self.file_tree = QTreeWidget()
        self.file_tree.setColumnCount(2)
        self.file_tree.setHeaderLabels(["Game File", "Providers"])
        self.file_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.file_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.file_tree.setSortingEnabled(True)

        # Populate file tree with concise provider preview
        for fp, provs in sorted(conflicts.items()):
            # provs is list of tuples (provider_mod, pak_name)
            prov_texts = []
            for pm, pak in provs:
                if pm == mod_name:
                    continue
                prov_texts.append(f"{pm} ({pak})")
            providers_str = ", ".join(prov_texts) if prov_texts else "(self)"
            item = QTreeWidgetItem([fp, providers_str])
            self.file_tree.addTopLevelItem(item)

        content_layout.addWidget(self.file_tree, 3)

        # Right: provider checklist
        self.provider_list = QListWidget()
        provider_map = {}
        for fp, provs in conflicts.items():
            for pm, pak in provs:
                if pm == mod_name:
                    continue
                provider_map.setdefault(pm, set()).add(pak)

        for provider_mod, pak_set in sorted(provider_map.items()):
            pak_list = ", ".join(sorted(pak_set))
            text = f"{provider_mod} — {pak_list}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, provider_mod)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.provider_list.addItem(item)

        content_layout.addWidget(self.provider_list, 1)

        main_layout.addWidget(content)

        # Action buttons: Rollback, Disable selected providers, Ignore and Close, Cancel
        from PySide6.QtWidgets import QPushButton
        self._action = None

        btn_layout = QHBoxLayout()

        rollback_btn = QPushButton("Rollback (Disable this mod)")
        rollback_btn.clicked.connect(self._on_rollback)
        btn_layout.addWidget(rollback_btn)

        disable_providers_btn = QPushButton("Disable selected providers")
        disable_providers_btn.clicked.connect(self._on_disable_providers)
        btn_layout.addWidget(disable_providers_btn)

        ignore_btn = QPushButton("Ignore and close")
        ignore_btn.clicked.connect(self._on_ignore_and_close)
        btn_layout.addWidget(ignore_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        main_layout.addLayout(btn_layout)

    def _gather_selected_providers(self):
        res = []
        for i in range(self.provider_list.count()):
            item = self.provider_list.item(i)
            if item.checkState() == Qt.Checked:
                res.append(item.data(Qt.UserRole))
        return res

    def _on_rollback(self):
        # Rollback to disabling the newly enabled mod
        self._action = "rollback"
        self.accept()

    def _on_disable_providers(self):
        # Disable provider mods selected in the checklist
        self._action = "disable_providers"
        self._selected_providers = self._gather_selected_providers()
        self.accept()

    def _on_ignore_and_close(self):
        # Add the selected providers to the ignore list for this mod
        self._action = "ignore"
        self._selected_providers = self._gather_selected_providers()
        self.accept()

    def get_action(self):
        return getattr(self, '_action', None)

    def get_selected_providers(self):
        return getattr(self, '_selected_providers', [])

    def get_ignored(self):
        res = []
        for i in range(self.provider_list.count()):
            item = self.provider_list.item(i)
            if item.checkState() == Qt.Checked:
                res.append(item.data(Qt.UserRole))
        return res