from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, Signal, QObject
import threading
import queue
import time
import PakInspector

class ParseSignals(QObject):
    """Signals for communicating parse progress to the UI."""
    progress = Signal(int)
    progress_text = Signal(str)
    finished = Signal()
    error = Signal(str)

class ParseProgressDialog(QDialog):
    """Dialog to show pak parsing progress."""
    def __init__(self, parent, total_mods):
        super().__init__(parent)
        self.setWindowTitle("Processing Mods")
        self.setMinimumWidth(400)
        self.setModal(True)
        layout = QVBoxLayout(self)
        
        self.status_label = QLabel("Starting...")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(total_mods)
        layout.addWidget(self.progress_bar)
        
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def update_text(self, text):
        self.status_label.setText(text)

class BatchParser:
    """Handles parsing multiple pak files in batches with progress reporting."""
    def __init__(self, parent, mods_to_parse):
        self.parent = parent
        self.mods_to_parse = mods_to_parse
        self.signals = ParseSignals()
        self.progress_dialog = None
        self.results = {}
        self.error = None
        self._parse_queue = queue.Queue()
        self._batch_size = 5  # Process 5 mods at a time
        
    def start(self):
        """Start the parsing process in a background thread with UI feedback."""
        total_mods = len(self.mods_to_parse)
        self.progress_dialog = ParseProgressDialog(self.parent, total_mods)
        
        # Connect signals
        self.signals.progress.connect(self.progress_dialog.update_progress)
        self.signals.progress_text.connect(self.progress_dialog.update_text)
        self.signals.finished.connect(self._on_complete)
        self.signals.error.connect(self._on_error)
        
        # Start worker thread
        threading.Thread(target=self._parse_worker, daemon=True).start()
        
        # Show dialog
        self.progress_dialog.exec()
        
        if self.error:
            raise Exception(self.error)
        return self.results
    
    def _parse_worker(self):
        """Worker thread that processes mods in batches."""
        try:
            mods_processed = 0
            current_batch = []
            
            for mod_path, mod_name in self.mods_to_parse:
                current_batch.append((mod_path, mod_name))
                
                if len(current_batch) >= self._batch_size or mod_path == self.mods_to_parse[-1][0]:
                    # Process current batch
                    for batch_mod_path, batch_mod_name in current_batch:
                        try:
                            self.signals.progress_text.emit(f"Parsing {batch_mod_name}...")
                            self.results[batch_mod_path] = PakInspector.get_pak_data(batch_mod_path)
                            mods_processed += 1
                            self.signals.progress.emit(mods_processed)
                        except Exception as e:
                            print(f"Error parsing {batch_mod_name}: {e}")
                            self.results[batch_mod_path] = None
                    
                    # Short delay between batches to let the UI breathe
                    time.sleep(0.1)
                    current_batch = []
            
            self.signals.finished.emit()
            
        except Exception as e:
            self.signals.error.emit(str(e))
    
    def _on_complete(self):
        if self.progress_dialog:
            self.progress_dialog.accept()
    
    def _on_error(self, error_message):
        self.error = error_message
        if self.progress_dialog:
            self.progress_dialog.accept()