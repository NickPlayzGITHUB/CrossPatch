"""Module for batch processing pak files with progress reporting."""

from typing import List, Dict, Tuple, Optional
import os
import shutil
import re
import threading
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, Signal, QObject
import PakInspector

class BatchProcessSignals(QObject):
    """Signals for batch processing operations."""
    progress = Signal(int)  # percentage progress
    progress_text = Signal(str)  # status message
    finished = Signal(dict)  # results dictionary
    error = Signal(str)  # error message

class BatchProgressDialog(QDialog):
    """Dialog to show batch processing progress."""
    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setModal(True)
        layout = QVBoxLayout(self)
        
        self.status_label = QLabel("Starting...")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)
        
        # Prevent closing with X button
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
    
    def update_progress(self, value: int):
        """Update progress bar value."""
        self.progress_bar.setValue(value)
    
    def update_text(self, text: str):
        """Update status text."""
        self.status_label.setText(text)

class PakBatchProcessor:
    """Handles batch processing of pak files with progress reporting."""
    def __init__(self, cfg: dict, profile_data: dict):
        self.cfg = cfg
        self.profile_data = profile_data
        self._cancel_flag = False
        self.signals = BatchProcessSignals()

    def cancel(self):
        """Cancel the current batch operation."""
        self._cancel_flag = True

    def process_mods_batch(self, parent_window, mod_list: List[Dict]) -> None:
        """
        Process a batch of mods asynchronously with progress updates.
        
        Args:
            parent_window: Parent window for the progress dialog
            mod_list: List of dictionaries containing mod info with format:
                     [{"name": str, "enabled": bool, "priority": int}, ...]
        """
        dialog = BatchProgressDialog(parent_window, "Processing Mods")

        def worker():
            try:
                total_mods = len(mod_list)
                results = {"successful": [], "failed": []}
                pak_dst = self._get_pak_dst()

                for i, mod in enumerate(mod_list):
                    if self._cancel_flag:
                        break

                    mod_name = mod["name"]
                    is_enabled = mod["enabled"]
                    priority = mod.get("priority", 0)
                    
                    try:
                        progress = int((i / total_mods) * 100)
                        status = f"{'Enabling' if is_enabled else 'Disabling'} {mod_name}..."
                        self.signals.progress.emit(progress)
                        self.signals.progress_text.emit(status)

                        if is_enabled:
                            self._enable_mod(mod_name, priority, pak_dst)
                        else:
                            self._disable_mod(mod_name, pak_dst)

                        results["successful"].append(mod_name)

                    except Exception as e:
                        results["failed"].append({"name": mod_name, "error": str(e)})

                self.signals.progress.emit(100)
                self.signals.progress_text.emit("Operation complete")
                self.signals.finished.emit(results)

            except Exception as e:
                self.signals.error.emit(str(e))

        # Connect signals
        self.signals.progress.connect(dialog.update_progress)
        self.signals.progress_text.connect(dialog.update_text)
        self.signals.finished.connect(dialog.accept)
        self.signals.error.connect(dialog.accept)

        # Start worker thread
        self._cancel_flag = False
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        # Show dialog and wait
        dialog.exec()

    def _get_pak_dst(self) -> str:
        """Get the destination path for pak files."""
        return os.path.join(
            self.cfg["game_root"],
            "UNION",
            "Content",
            "Paks",
            "~mods"
        )

    def _enable_mod(self, mod_name: str, priority: int, pak_dst: str) -> None:
        """Enable a mod by copying its pak files to the destination."""
        # Create priority-based folder name
        priority_prefix = str(priority).zfill(3)
        target_folder = f"{priority_prefix}.{mod_name}"
        target_path = os.path.join(pak_dst, target_folder)

        # Clean target directory if it exists
        if os.path.exists(target_path):
            shutil.rmtree(target_path)

        # Create target directory
        os.makedirs(target_path, exist_ok=True)

        # Copy pak files from mod to target
        source_path = os.path.join(self.cfg["mods_folder"], mod_name)
        self._copy_pak_files(source_path, target_path)

    def _disable_mod(self, mod_name: str, pak_dst: str) -> None:
        """Disable a mod by removing its pak files."""
        self._remove_mod_folders(pak_dst, mod_name)

    def _copy_pak_files(self, source_path: str, target_path: str) -> None:
        """Copy pak/utoc/ucas files from source to target directory.

        This will copy .pak, .utoc and .ucas files and preserve relative
        subdirectory structure from the source mod folder into the
        target priority folder.
        """
        # Walk through source directory
        for root, _, files in os.walk(source_path):
            for file in files:
                # Include pak, utoc and ucas files (case-insensitive)
                if file.lower().endswith(('.pak', '.utoc', '.ucas')):
                    src_file = os.path.join(root, file)
                    # Calculate relative path from source root
                    rel_path = os.path.relpath(src_file, source_path)
                    dst_file = os.path.join(target_path, rel_path)

                    # Create subdirectories if needed
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)

                    # Copy the file
                    shutil.copy2(src_file, dst_file)

    def _remove_mod_folders(self, pak_dst: str, mod_name: str) -> None:
        """Remove all priority folders for a given mod."""
        if not os.path.isdir(pak_dst):
            return

        # Pattern matches folders that start with digits followed by the mod name
        pattern = re.compile(rf"^\d+\.{re.escape(mod_name)}$")
        
        for item in os.listdir(pak_dst):
            if pattern.match(item):
                folder_path = os.path.join(pak_dst, item)
                if os.path.isdir(folder_path):
                    shutil.rmtree(folder_path, ignore_errors=True)