import os
import shutil
import zipfile
import time
import threading
import requests
import json

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QMessageBox
from PySide6.QtCore import Signal, QObject, Qt, QTimer

import Util
from Constants import APP_VERSION, BROWSER_USER_AGENT
import PakInspector

# --- Handle optional archive dependencies ---
try:
    import py7zr
    PY7ZR_SUPPORT = True
except ImportError:
    PY7ZR_SUPPORT = False

try:
    import rarfile
    RARFILE_SUPPORT = True
except ImportError:
    RARFILE_SUPPORT = False

class DownloadSignals(QObject):
    """Defines signals for communicating from the worker thread to the GUI."""
    progress = Signal(int)
    progress_text = Signal(str)
    label_text = Signal(str)
    finished = Signal()
    error = Signal(str)
    request_progress_dialog = Signal(str, str)

class ProgressDialog(QDialog):
    """A simple dialog to show download and extraction progress."""
    def __init__(self, parent, title):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(350)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False) # No close button

        layout = QVBoxLayout(self)
        self.label = QLabel("Initializing...")
        layout.addWidget(self.label)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.progress_text_label = QLabel("0.00 MB / 0.00 MB")
        layout.addWidget(self.progress_text_label)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_progress_text(self, text):
        self.progress_text_label.setText(text)

    def update_label(self, text):
        self.label.setText(text)

class DownloadManager:
    def __init__(self, parent, mods_folder, on_complete=None):
        self.parent = parent
        self.mods_folder = mods_folder
        self.on_complete = on_complete
        self.progress_dialog = None
        self.signals = DownloadSignals()

        # Connect signals to slots
        self.signals.finished.connect(self._on_finish)
        self.signals.error.connect(self._on_error)

    def _setup_and_start_thread(self, thread_target, thread_args, dialog_title, dialog_file_name):
        """Creates dialog, connects signals, and starts the worker thread."""
        self.progress_dialog = ProgressDialog(self.parent, dialog_title)
        self.progress_dialog.update_label(f"Downloading {dialog_file_name}...")
        self.signals.progress.connect(self.progress_dialog.update_progress)
        self.signals.progress_text.connect(self.progress_dialog.update_progress_text)
        self.signals.label_text.connect(self.progress_dialog.update_label)
        self.progress_dialog.show()
        
        threading.Thread(target=thread_target, args=thread_args, daemon=True).start()

    def _on_finish(self):
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.accept()
        # Schedule the on_complete callback to run after the dialog has had a chance to close,
        # preventing the UI from freezing before the window disappears.
        if hasattr(self, 'on_complete') and self.on_complete:
            QTimer.singleShot(100, self.on_complete)
        # Also refresh the browse tab if it exists on the parent, to reflect any changes.
        if hasattr(self.parent, 'fetch_browse_mods'):
            print("[DEBUG] Download finished. Triggering browse tab refresh.")
            QTimer.singleShot(100, lambda: self.parent.fetch_browse_mods(page=self.parent.browse_current_page))

    def _on_error(self, error_message):
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.reject()
        QMessageBox.critical(self.parent, "Download Failed", error_message)
        if hasattr(self, 'on_complete') and self.on_complete: # Refresh UI even on failure
            QTimer.singleShot(100, self.on_complete)

    def download_specific_file(self, file_info, full_item_data, extract_path_override=None):
        dialog_title = f"Downloading {full_item_data.get('_sName', 'Mod')}..."
        dialog_file_name = file_info.get('_sFile', 'download.zip')
        thread_args = (file_info, full_item_data, None, None, extract_path_override)
        self._setup_and_start_thread(self._download_and_extract_thread, thread_args, dialog_title, dialog_file_name)

    def update_specific_file(self, file_info, full_item_data, mod_folder_name, active_profile):
        dialog_title = f"Updating {full_item_data.get('_sName', 'Mod')}..."
        dialog_file_name = file_info.get('_sFile', 'download.zip')
        thread_args = (file_info, full_item_data, mod_folder_name, active_profile)
        self._setup_and_start_thread(self._download_and_extract_thread, thread_args, dialog_title, dialog_file_name)

    def download_from_schema(self, download_url, item_type, item_id, file_ext, page_url=None):
        # We don't know the name yet, so we'll pass a placeholder and update it in the thread
        dialog_title = "Downloading..."
        dialog_file_name = "..."
        thread_args = (download_url, item_type, item_id, file_ext, page_url)
        self._setup_and_start_thread(self._schema_download_thread, thread_args, dialog_title, dialog_file_name)

    def _start_progress_dialog(self, title, file_name):
        """DEPRECATED: This is now handled by _setup_and_start_thread."""
        pass
        
    def _download_and_extract_thread(self, file_info, full_item_data, mod_folder_name=None, active_profile=None, extract_path_override=None):
        temp_archive_path = None
        try:
            download_url = file_info.get('_sDownloadUrl')
            file_name = file_info.get('_sFile', 'download.zip')
            item_name = full_item_data.get('_sName', 'Unknown Mod')
            clean_item_name = item_name.replace(" ", "_")

            if not download_url:
                raise ValueError("Could not find a download URL for the selected file.")

            temp_archive_path = os.path.join(self.mods_folder, file_name)
            self._download_file_with_progress(download_url, temp_archive_path)

            self.signals.label_text.emit("Extracting...")
            extract_path = extract_path_override or os.path.join(self.mods_folder, mod_folder_name or clean_item_name)

            existing_mod_page = None
            if mod_folder_name:
                existing_info = Util.read_mod_info(extract_path)
                existing_mod_page = existing_info.get('mod_page')

            if mod_folder_name and os.path.isdir(extract_path):
                shutil.rmtree(extract_path)

            Util.extract_archive(temp_archive_path, extract_path, self.signals.label_text, clean_destination=not extract_path_override, finished_signal=self.signals.finished)
            
            # Update info.json with all available data
            page_url = existing_mod_page or Util.get_gb_page_url_from_item_data(full_item_data)
            self._create_and_update_mod_info(extract_path, full_item_data, file_info, page_url)

            os.remove(temp_archive_path)
            # If we were downloading to a temp folder (like for UE4SS), clean it up.
            if "temp_downloads" in self.mods_folder:
                shutil.rmtree(self.mods_folder, ignore_errors=True)

        except Exception as e:
            if temp_archive_path and os.path.exists(temp_archive_path):
                os.remove(temp_archive_path)
            if not isinstance(e, InterruptedError):
                self.signals.error.emit(f"An error occurred: {e}")
            else:
                self.signals.finished.emit() # User cancelled, just close dialog

    def _schema_download_thread(self, download_url, item_type, item_id, file_ext, page_url=None):
        temp_archive_path = None
        try:
            api_item_type = item_type.capitalize()
            api_url = f"https://gamebanana.com/apiv11/{api_item_type}/{item_id}?_csvProperties=_sName,_aFiles"
            response = requests.get(api_url, headers={'User-Agent': BROWSER_USER_AGENT})
            response.raise_for_status()
            item_data = response.json()
            item_name = item_data.get('_sName', f"mod_{item_id}").replace(" ", "")
            file_name = f"{item_name}_download.{file_ext}"

            # Update the dialog with the correct name now that we have it
            self.signals.label_text.emit(f"Downloading {file_name}...")

            item_version = next((f.get('_sVersion') for f in item_data.get('_aFiles', []) if f.get('_sDownloadUrl') == download_url), item_data.get('_sVersion'))

            temp_archive_path = os.path.join(self.mods_folder, file_name)
            self._download_file_with_progress(download_url, temp_archive_path)

            self.signals.label_text.emit("Extracting...")
            extract_path = os.path.join(self.mods_folder, item_name)
            Util.extract_archive(temp_archive_path, extract_path, self.signals.label_text, finished_signal=self.signals.finished)

            self._update_mod_info_with_version(extract_path, item_version)
            self._update_mod_info_with_page(extract_path, page_url)

            # Also create a rich info.json using the same helper so we include pak metadata
            try:
                # Find the specific file entry from the item data that matches the download URL
                file_info = next((f for f in item_data.get('_aFiles', []) if f.get('_sDownloadUrl') == download_url), None)
                # If not found, take the first file entry as a best-effort
                if file_info is None:
                    file_info = item_data.get('_aFiles', [None])[0]
                # Create/update info.json with pak_data and other metadata
                self._create_and_update_mod_info(extract_path, item_data, file_info or {}, page_url)
            except Exception as e:
                print(f"Warning: failed to create detailed info.json for {extract_path}: {e}")

            os.remove(temp_archive_path)

        except Exception as e:
            if temp_archive_path and os.path.exists(temp_archive_path):
                os.remove(temp_archive_path)
            if not isinstance(e, InterruptedError):
                self.signals.error.emit(f"An error occurred: {e}")
            else:
                self.signals.finished.emit()

    def _download_file_with_progress(self, url, destination_path):
        with requests.get(url, stream=True, headers={'User-Agent': BROWSER_USER_AGENT}) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            bytes_downloaded = 0
            with open(destination_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    if total_size > 0:
                        progress = (bytes_downloaded / total_size) * 100
                        self.signals.progress.emit(int(progress))
                        self.signals.progress_text.emit(f"{bytes_downloaded/1024/1024:.2f} MB / {total_size/1024/1024:.2f} MB")

    def _create_and_update_mod_info(self, mod_path, full_item_data, file_info, page_url):
        """Creates or overwrites the info.json file with comprehensive data after download."""
        if not os.path.isdir(mod_path): return
        try:
            info_path = os.path.join(mod_path, "info.json")
            
            # Build the info dict from scratch using the rich data we have.
            new_info = {
                "name": full_item_data.get('_sName', os.path.basename(mod_path)),
                "version": file_info.get('_sVersion') or full_item_data.get('_sVersion') or "1.0",
                "author": full_item_data.get('_aSubmitter', {}).get('_sName', 'Unknown'),
                "mod_page": page_url or "",
                "mod_type": Util.read_mod_info(mod_path).get('mod_type', 'pak'), # Preserve auto-detected type
                "replaced_files": Util.generate_mod_file_list(mod_path) # Generate file manifest
            }

            # If the parser exe is available, augment info.json with pak_data
            try:
                pak_data = PakInspector.generate_mod_pak_manifest(mod_path)
                if pak_data:
                    new_info['pak_data'] = pak_data
            except Exception as e:
                # Non-fatal: log warning and proceed without pak data
                print(f"Warning: PakInspector failed for {os.path.basename(mod_path)}: {e}")

            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(new_info, f, indent=2)
            print(f"Generated info.json with {len(new_info['replaced_files'])} files for {new_info['name']}.")
        except Exception as e:
            print(f"Could not update info.json for {os.path.basename(mod_path)}: {e}")

    def _update_mod_info_with_version(self, mod_path, version):
        """Updates the version in a mod's info.json file."""
        if not os.path.isdir(mod_path) or not version:
            return
        try:
            info_path = os.path.join(mod_path, "info.json")
            mod_info = Util.read_mod_info(mod_path)  # Handles non-existent files
            mod_info['version'] = version
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(mod_info, f, indent=2)
        except Exception as e:
            print(f"Could not update version for {os.path.basename(mod_path)}: {e}")

    def _update_mod_info_with_page(self, mod_path, page_url):
        """Updates the mod_page in a mod's info.json file."""
        if not os.path.isdir(mod_path) or not page_url:
            return
        try:
            info_path = os.path.join(mod_path, "info.json")
            mod_info = Util.read_mod_info(mod_path)  # Handles non-existent files
            mod_info['mod_page'] = page_url
            with open(info_path, "w", encoding="utf-8") as f:
                json.dump(mod_info, f, indent=2)
        except Exception as e:
            print(f"Could not update mod page for {os.path.basename(mod_path)}: {e}")