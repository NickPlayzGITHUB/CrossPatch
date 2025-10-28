import threading

class TreeUpdateLock:
    """A simple lock for tree updates to prevent concurrent modifications."""
    def __init__(self, tree_widget):
        self.tree = tree_widget
        self.lock = threading.Lock()
    
    def __enter__(self):
        if not self.lock.acquire(timeout=1.0):
            raise TimeoutError("Could not acquire tree update lock")
        self.tree.blockSignals(True)
        try:
            self.tree.setUpdatesEnabled(False)
        except Exception:
            pass
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.tree.setUpdatesEnabled(True)
        except Exception:
            pass
        self.tree.blockSignals(False)
        self.lock.release()