import sys
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QVBoxLayout
from PySide6.QtGui import QFont

class CreditsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Credits")
        self.setModal(True)

        layout = QVBoxLayout()

        credits_data = [
            ("NockCS", "Lead Developer/Programmer", True),
            ("RED1", "Secondary Main Programmer", True),
            ("AntiApple4life", "Linux Support Programmer", True),
            ("Ben Thalmann", "Cleaned Up Codebase", True),
        ]

        for name, title, is_bold in credits_data:
            name_label = QLabel(name)
            name_font = QFont()
            name_font.setPointSize(16)
            name_font.setBold(is_bold)
            name_label.setFont(name_font)
            layout.addWidget(name_label)

            title_label = QLabel(title)
            title_font = QFont()
            title_font.setPointSize(10)
            title_label.setFont(title_font)
            layout.addWidget(title_label)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.setLayout(layout)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CreditsWindow()
    window.show()
    sys.exit(app.exec())
