import configparser
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QDialogButtonBox,
    QFormLayout, QWidget, QScrollArea, QSizePolicy
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
        self.setMinimumWidth(500)

        main_layout = QVBoxLayout(self)

        # --- Scroll Area for dynamic content ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        container_widget = QWidget()
        form_layout = QFormLayout(container_widget)
        form_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # --- Dynamically create widgets ---
        for category, options in self.config_data.items():
            # Create a combo box for the category
            combo_box = QComboBox()
            
            # Store a mapping from display name to folder name
            combo_box.option_map = {}
            
            # Populate the combo box
            for option_folder, option_details in options.items():
                display_name = option_details.get('name', option_folder)
                description = option_details.get('description', 'No description.')
                combo_box.addItem(display_name, userData=option_folder)
                combo_box.setItemData(combo_box.count() - 1, description, Qt.ToolTipRole)
                combo_box.option_map[option_folder] = display_name

            # Set the current selection
            current_option_folder = self.current_selections.get(category)
            if current_option_folder and current_option_folder in combo_box.option_map:
                # Find the index corresponding to the saved option folder
                index = combo_box.findData(current_option_folder)
                if index != -1:
                    combo_box.setCurrentIndex(index)
            
            # Add to layout and store widget
            form_layout.addRow(QLabel(f"<b>{category}:</b>"), combo_box)
            self.widgets[category] = combo_box

        scroll_area.setWidget(container_widget)
        main_layout.addWidget(scroll_area)

        # --- Description/Help Text ---
        help_label = QLabel("Hover over an option in the dropdown to see its description.")
        help_label.setStyleSheet("font-style: italic; color: grey;")
        main_layout.addWidget(help_label)

        # --- OK and Cancel buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        self.adjustSize()

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