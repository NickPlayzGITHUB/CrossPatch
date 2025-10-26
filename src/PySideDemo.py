import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel

class HelloWorldWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PySide6 Hello World')
        self.setGeometry(100, 100, 280, 80)
        hello_label = QLabel('Hello, PySide6!', self)
        hello_label.move(60, 20)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = HelloWorldWindow()
    window.show()
    sys.exit(app.exec())
