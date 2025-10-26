import os
import sys
import platform
import shutil
import subprocess
import threading
import time
import requests

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QMessageBox
from PySide6.QtCore import Signal, QObject, Qt

from Constants import APP_VERSION
import Util

class UpdaterSignals(QObject):
    """Defines signals for communicating from the worker thread to the GUI."""
    progress = Signal(int)
    label_text = Signal(str)
    finished = Signal()
    error = Signal(str)
    request_progress_dialog = Signal()

class ProgressDialog(QDialog):
    """A simple dialog to show update progress."""
    def __init__(self, parent, title):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(350)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        layout = QVBoxLayout(self)
        self.label = QLabel("Initializing...")
        layout.addWidget(self.label)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_label(self, text):
        self.label.setText(text)

class Updater:
    def __init__(self, parent, remote_version_info):
        self.parent = parent
        self.remote_version_info = remote_version_info
        self.temp_dir = os.path.join(os.path.dirname(sys.executable) if Util.is_packaged() else os.path.dirname(__file__), 'update_temp')
        self.signals = UpdaterSignals()
        self.progress_dialog = None

        self.signals.finished.connect(self._on_finish)
        self.signals.error.connect(self._on_error)
        self.signals.request_progress_dialog.connect(self._start_progress_dialog)

    def start_update(self):
        """Starts the update process in a new thread."""
        threading.Thread(target=self._update_thread, daemon=True).start()

    def _start_progress_dialog(self):
        self.progress_dialog = ProgressDialog(self.parent, "Updating CrossPatch...")
        self.signals.progress.connect(self.progress_dialog.update_progress)
        self.signals.label_text.connect(self.progress_dialog.update_label)
        self.progress_dialog.show()

    def _on_finish(self):
        if self.progress_dialog:
            self.progress_dialog.accept()
        self.parent.close()

    def _on_error(self, error_message):
        if self.progress_dialog:
            self.progress_dialog.reject()
        QMessageBox.critical(self.parent, "Update Failed", f"An error occurred during the update process:\n\n{error_message}")
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _update_thread(self):
        try:
            # Request the main thread to create the dialog
            self.signals.request_progress_dialog.emit()

            self.signals.label_text.emit("Finding release asset...")
            asset = self._find_release_asset()
            if not asset:
                raise ValueError("Could not find a suitable release package for this OS.")

            download_url = asset['browser_download_url']
            file_name = asset['name']
            archive_path = os.path.join(self.temp_dir, file_name)
            os.makedirs(self.temp_dir, exist_ok=True)

            self.signals.label_text.emit(f"Downloading {file_name}...")
            self._download_file_with_progress(download_url, archive_path)

            extract_path = os.path.join(self.temp_dir, 'extracted')
            Util.extract_archive(archive_path, extract_path, self.signals.label_text)

            self.signals.label_text.emit("Finalizing...")
            self._run_updater_script(extract_path)
            self.signals.finished.emit()

        except Exception as e:
            self.signals.error.emit(str(e))

    def _find_release_asset(self):
        is_windows = platform.system() == "Windows"
        available_assets = self.remote_version_info.get('assets', [])
        if not available_assets:
            return None

        for asset in available_assets:
            asset_name = asset.get('name', '').lower()
            if not asset_name.endswith('.zip'):
                continue
            is_linux_asset = 'linux' in asset_name
            if (is_windows and not is_linux_asset) or (not is_windows and is_linux_asset):
                return asset
        return None

    def _download_file_with_progress(self, url, destination_path):
        # Wait for the progress dialog to be created by the main thread
        while not self.progress_dialog:
            threading.sleep(0.05)
        with requests.get(url, stream=True, headers={'User-Agent': f'CrossPatch-Updater/{APP_VERSION}'}) as r:
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
            self.signals.progress.emit(100)

    def _run_updater_script(self, source_path):
        app_path = os.path.dirname(sys.executable) if Util.is_packaged() else os.path.dirname(os.path.abspath(__file__))
        app_executable = os.path.basename(sys.executable)
        pid = os.getpid()

        if platform.system() == "Windows":
            script_path = os.path.join(self.temp_dir, 'updater.bat')
            script_content = f"""
@echo off & title CrossPatch Updater
echo Waiting for CrossPatch (PID: {pid}) to close...
taskkill /F /PID {pid} > nul 2>&1
timeout /t 1 /nobreak > nul
echo.
echo Updating files...
xcopy "{source_path}" "{app_path}" /E /Y /I /Q
echo.
echo Update successful! Press any key to exit.
echo.
pause > nul & start /b "" cmd /c "timeout /t 1 /nobreak > nul && rmdir /s /q "{self.temp_dir}"" & exit
"""
            with open(script_path, 'w') as f:
                f.write(script_content)
            subprocess.Popen(f'start "" "{script_path}"', creationflags=subprocess.DETACHED_PROCESS, shell=True)
            time.sleep(1)

        else: # Linux
            script_path = os.path.join(self.temp_dir, 'updater.sh')
            script_content = f"""#!/bin/bash
echo "Waiting for CrossPatch (PID: {pid}) to close..."
while kill -0 {pid} 2>/dev/null; do
    sleep 1
done

echo "Updating files..."
if [ $(ls -1 "{source_path}" | wc -l) -eq 1 ]; then
    echo "Single-file update detected. Replacing binary..."
    mv -f "{source_path}/{app_executable}" "{os.path.join(app_path, app_executable)}"
else
    echo "Directory update detected. Copying files..."
    cp -rf "{source_path}/"* "{app_path}/"
fi

echo "Relaunching CrossPatch..."
chmod +x "{os.path.join(app_path, app_executable)}"
"{os.path.join(app_path, app_executable)}" &

echo "Cleaning up temporary files..."
rm -rf "{self.temp_dir}"
"""
            with open(script_path, 'w') as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)
            subprocess.Popen([script_path], start_new_session=True)