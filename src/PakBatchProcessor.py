"""Module for batch processing pak files with progress reporting."""

from typing import List, Dict, Tuple, Optional
import os 
import shutil
import re
import threading 
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, Signal, QObject
import PakInspector
from ConflictDialog import ConflictDialog

class BatchProcessSignals(QObject):
    """Signals for batch processing operations."""
    progress = Signal(int)  # percentage progress
    progress_text = Signal(str)  # status message
    finished = Signal(dict)  # results dictionary
    error = Signal(str)  # error message
    conflicts_found = Signal(dict) # conflicts dictionary

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
                all_conflicts = {}
                pak_dst = self._get_pak_dst()

                # --- Absolute Cleanup: Remove all managed pak mod folders before processing ---
                self._clean_all_managed_folders(pak_dst)

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
                            # Perform conflict check before enabling
                            mod_conflicts = self._check_conflicts_for_mod(mod_name, mod_list)
                            if mod_conflicts:
                                for file, providers in mod_conflicts.items():
                                    all_conflicts.setdefault(file, set()).update(providers)

                            self._enable_mod(mod_name, priority, pak_dst)
                        results["successful"].append(mod_name)

                    except Exception as e:
                        results["failed"].append({"name": mod_name, "error": str(e)})

                # After processing, if there are any conflicts, show the dialog
                if all_conflicts:
                    self.signals.conflicts_found.emit({k: list(v) for k, v in all_conflicts.items()})
                self.signals.progress.emit(100)
                self.signals.progress_text.emit("Operation complete")
                self.signals.finished.emit(results)

            except Exception as e:
                self.signals.error.emit(str(e))

        # Connect signals
        self.signals.progress.connect(dialog.update_progress)
        self.signals.progress_text.connect(dialog.update_text)
        self.signals.finished.connect(dialog.accept)
        
        # Connect the new conflicts signal to a handler that can show the dialog
        def show_conflict_dialog(conflicts):
            ConflictDialog(parent_window, "Multiple Mods", conflicts).exec()
        self.signals.conflicts_found.connect(show_conflict_dialog)
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
        # First, ensure any old versions of this mod's folder are removed to guarantee a clean install.
        self._remove_mod_folders(pak_dst, mod_name)
        
        priority_prefix = str(priority).zfill(3)
        target_folder = f"{priority_prefix}.{mod_name}"
        target_path = os.path.join(pak_dst, target_folder)

        # Failsafe: Clean target directory if it exists to prevent orphaned files
        # from previous versions or failed cleanups.
        if os.path.exists(target_path):
            shutil.rmtree(target_path)

        # Create target directory
        os.makedirs(target_path, exist_ok=True)

        # Copy pak files from mod to target
        source_path = os.path.join(self.cfg["mods_folder"], mod_name)
        self._copy_mod_files(source_path, target_path, mod_name)

    def _copy_mod_files(self, source_path: str, target_path: str, mod_name: str) -> None:
        """Copy mod files from source to target, respecting file-based configurations."""
        import Util # Local import to avoid circular dependency issues

        file_config = Util.discover_mod_configuration(source_path)

        if file_config:
            # --- Logic for Configurable Mods ---
            # First, copy all base files/folders that are NOT part of the configuration structure.
            for item in os.listdir(source_path):
                s_item = os.path.join(source_path, item)
                # Ignore info.json and any directory that is a configuration category.
                if item.lower() == "info.json" or item in file_config:
                    continue
                
                d_item = os.path.join(target_path, item)
                if os.path.isdir(s_item):
                    shutil.copytree(s_item, d_item, dirs_exist_ok=True)
                elif os.path.isfile(s_item):
                    shutil.copy2(s_item, d_item)

            # Second, copy files from the selected configuration options.
            mod_configs = self.profile_data.get("mod_configurations", {}).get(mod_name, {})
            for category, options in file_config.items():
                selected_option_folder = mod_configs.get(category, next(iter(options.keys()), None))
                if selected_option_folder:
                    option_path = os.path.join(source_path, category, selected_option_folder)
                    if os.path.isdir(option_path):
                        shutil.copytree(option_path, target_path, dirs_exist_ok=True)
        else:
            # --- Logic for Simple/Non-Configurable Mods ---
            shutil.copytree(source_path, target_path, ignore=shutil.ignore_patterns('info.json'), dirs_exist_ok=True)

    def _remove_mod_folders(self, pak_dst: str, mod_name: str) -> None:
        """Remove all priority folders for a given mod."""
        if not os.path.isdir(pak_dst):
            return

        # Pattern matches folders that start with digits followed by the mod name
        pattern = re.compile(r"^\d+\." + re.escape(mod_name) + r"$")
        
        for item in os.listdir(pak_dst):
            if pattern.match(item):
                folder_path = os.path.join(pak_dst, item)
                if os.path.isdir(folder_path):
                    shutil.rmtree(folder_path, ignore_errors=True)

    def _clean_all_managed_folders(self, pak_dst: str) -> None:
        """
        Removes all CrossPatch-managed mod folders from the game's mod directory.
        This is the primary cleanup mechanism.
        """
        self.signals.progress_text.emit("Cleaning game's mod directory...")
        if not os.path.isdir(pak_dst):
            return

        managed_folder_pattern = re.compile(r"^\d{3,}\..+")
        for item in os.listdir(pak_dst):
            item_path = os.path.join(pak_dst, item)
            if os.path.isdir(item_path) and managed_folder_pattern.match(item):
                shutil.rmtree(item_path, ignore_errors=True)

    def _check_conflicts_for_mod(self, mod_name_to_check: str, all_mods_list: List[Dict]) -> Dict:
        """
        Checks a single mod for conflicts against all other enabled mods in the list.
        This is a simplified version of Util.check_mod_conflicts, adapted for the batch processor.
        """
        import Util  # Local import
        conflicts = {}
        mods_folder = self.cfg["mods_folder"]

        # Get info for the mod we are checking
        mod_path_to_check = os.path.join(mods_folder, mod_name_to_check)
        mod_info_to_check = Util.read_mod_info(mod_path_to_check)

        # Get active paks for the mod being checked
        active_paks = Util.get_active_pak_files(mod_path_to_check, mod_info_to_check, self.profile_data)

        # Use the precise conflict check logic from Util
        other_conflicts = Util.check_mod_conflicts(
            mod_name_to_check, mod_info_to_check, self.cfg, self.profile_data, active_paks
        )

        return other_conflicts