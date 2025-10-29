import configparser
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDialogButtonBox,
    QFormLayout, QWidget, QScrollArea, QSizePolicy, QGroupBox, QTextEdit
)
from PySide6.QtCore import Qt

class ModConfigDialog(QDialog):
    """
    A dialog for configuring a mod's optional files.
    It dynamically generates a UI based on a discovered configuration structure.
    """
    def __init__(self, parent, mod_name, config_data, current_selections):
        super().__init__(parent)
        self.mod_name = mod_name
        self.config_data = config_data
        self.current_selections = current_selections.copy() # Make a mutable copy
        self.widgets = {}

        self.setWindowTitle(f"Configure '{self.mod_name}'")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        main_layout = QVBoxLayout(self)

        # --- Scroll Area for dynamic content ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_layout.setSpacing(15)

        # --- Dynamically create widgets ---
        for category, options in self.config_data.items():
            group_box = QGroupBox(category)
            group_layout = QVBoxLayout(group_box)

            combo_box = QComboBox()
            desc_label = QLabel("Select an option to see its description.")
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #cccccc; padding: 5px; border-radius: 3px; background-color: #2a2a2a;")
            desc_label.setMinimumHeight(60)
            desc_label.setAlignment(Qt.AlignTop)

            for option_folder, option_details in options.items():
                display_name = option_details.get('name', option_folder)
                description = option_details.get('description', 'No description.')
                combo_box.addItem(display_name, userData=option_folder)
                combo_box.setItemData(combo_box.count() - 1, description, Qt.UserRole + 1)

            # Connect signal to update description
            combo_box.currentIndexChanged.connect(
                lambda index, cb=combo_box, dl=desc_label: dl.setText(cb.itemData(index, Qt.UserRole + 1))
            )

            # Set current selection and initial description
            current_option_folder = self.current_selections.get(category)
            if current_option_folder:
                index = combo_box.findData(current_option_folder)
                if index != -1:
                    combo_box.setCurrentIndex(index)
                    desc_label.setText(combo_box.itemData(index, Qt.UserRole + 1))
                else:
                    # Fallback if saved option is not found
                    desc_label.setText(combo_box.itemData(0, Qt.UserRole + 1))
            else:
                # Set initial description for the default (first) item
                desc_label.setText(combo_box.itemData(0, Qt.UserRole + 1))

            group_layout.addWidget(combo_box)
            group_layout.addWidget(desc_label)
            container_layout.addWidget(group_box)

            self.widgets[category] = combo_box

        scroll_area.setWidget(container_widget)
        main_layout.addWidget(scroll_area)

        # --- OK and Cancel buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def accept(self):
        """Update the selections dictionary when 'Save' is clicked."""
        for category, combo_box in self.widgets.items():
            # Get the folder name (stored in userData) of the selected item
            selected_option_folder = combo_box.currentData()
            self.current_selections[category] = selected_option_folder
        super().accept()

    def get_selections(self):
        """Return the final selections."""
        return self.current_selections

def read_desc_ini(file_path):
    """
    Reads a simple INI file to get Name and Description.
    Returns a dictionary.
    """
    config = configparser.ConfigParser()
    try:
        config.read(file_path)
        name = config.get('Description', 'Name', fallback=None)
        description = config.get('Description', 'Description', fallback='')
        if name:
            return {'name': name, 'description': description}
    except Exception as e:
        print(f"Could not read or parse desc.ini at {file_path}: {e}")
    return None