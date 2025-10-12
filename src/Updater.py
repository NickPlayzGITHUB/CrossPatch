import tkinter as tk
from tkinter import ttk, messagebox
import requests
import os
import sys
import platform
import shutil
import subprocess
import threading
import time

from Constants import APP_VERSION
import Util

class Updater:
    def __init__(self, parent, remote_version_info):
        self.parent = parent
        self.remote_version_info = remote_version_info
        self.temp_dir = os.path.join(os.path.dirname(sys.executable) if Util.is_packaged() else os.path.dirname(__file__), 'update_temp')

    def start_update(self):
        """Starts the update process in a new thread."""
        threading.Thread(target=self._update_thread, daemon=True).start()

    def _show_progress_window(self, title):
        self.progress_window = tk.Toplevel(self.parent)
        self.progress_window.transient(self.parent)
        self.progress_window.title(title)
        self.progress_window.resizable(False, False)
        self.progress_window.grab_set() # Prevent interaction with main window

        self.progress_label_var = tk.StringVar(value="Initializing...")
        ttk.Label(self.progress_window, textvariable=self.progress_label_var, padding=10).pack()

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_window, variable=self.progress_var, length=300, mode='determinate')
        self.progress_bar.pack(padx=10, pady=5)

        # Center window
        self.parent.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (self.progress_window.winfo_reqwidth() // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (self.progress_window.winfo_reqheight() // 2)
        self.progress_window.geometry(f"+{x}+{y}")
        self.progress_window.update()

    def _update_thread(self):
        try:
            print("--- Starting CrossPatch Update Process ---")
            self.parent.after(0, lambda: self._show_progress_window("Updating CrossPatch..."))
            print("Update progress window requested.")

            # 1. Find the correct release asset
            self.parent.after(0, lambda: self.progress_label_var.set("Finding release asset..."))
            print("Step 1: Finding release asset...")
            asset = self._find_release_asset()
            if not asset:
                raise ValueError("Could not find a suitable release package for this OS.")
            print(f"Step 1: Success. Found asset: {asset.get('name')}")

            # 2. Download the asset
            download_url = asset['browser_download_url']
            print(f"Attempting to download update from: {download_url}")
            file_name = asset['name']
            archive_path = os.path.join(self.temp_dir, file_name)
            print(f"Creating temporary directory: {self.temp_dir}")
            os.makedirs(self.temp_dir, exist_ok=True)

            self.parent.after(0, lambda: self.progress_label_var.set(f"Downloading {file_name}..."))
            print(f"Step 2: Downloading {file_name} to {archive_path}...")
            self._download_file_with_progress(download_url, archive_path)
            print("Step 2: Success. Download complete.")

            # 3. Extract the asset
            self.parent.after(0, lambda: self.progress_label_var.set("Extracting update..."))
            extract_path = os.path.join(self.temp_dir, 'extracted')
            print(f"Step 3: Extracting {archive_path} to {extract_path}...")
            shutil.unpack_archive(archive_path, extract_path)
            print("Step 3: Success. Extraction complete.")

            # 4. Prepare and run the updater script
            self.parent.after(0, lambda: self.progress_label_var.set("Finalizing..."))
            print("Step 4: Preparing and running updater script...")
            self._run_updater_script(extract_path)
            self.close_application()

        except Exception as e:
            print(f"Update failed: {e}")
            self.parent.after(0, lambda: messagebox.showerror("Update Failed", f"An error occurred during the update process:\n\n{e}"))
            if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                self.parent.after(0, self.progress_window.destroy)
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def close_application(self):
        """Closes the progress window and then the main application."""
        if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
            self.progress_window.destroy()
        self.parent.destroy()

    def _find_release_asset(self):
        """Finds the correct .zip asset from the release info."""
        is_windows = platform.system() == "Windows"
        print(f"Looking for a release package for your OS: '{'win' if is_windows else 'linux'}'")

        available_assets = self.remote_version_info.get('assets', [])
        if not available_assets:
            print("Error: The release information from GitHub contains no asset files.")
            return None

        print("Checking available release assets:")
        for asset in available_assets:
            asset_name = asset.get('name', '').lower()
            print(f" - Found asset: '{asset_name}'", end="")

            # Skip non-zip files
            if not asset_name.endswith('.zip'):
                print(" (skipping, not a .zip)")
                continue

            is_linux_asset = 'linux' in asset_name

            if (is_windows and not is_linux_asset) or (not is_windows and is_linux_asset):
                print(" -> Match found! Selecting this file for update.")
                return asset
            print() # Newline for non-matches

        print("\nNo matching asset was found for your OS.")
        return None

    def _download_file_with_progress(self, url, destination_path):
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
                        self.parent.after(0, lambda p=progress: self.progress_var.set(p))
            self.parent.after(0, lambda: self.progress_var.set(100))


    def _run_updater_script(self, source_path):
        app_path = os.path.dirname(sys.executable) if Util.is_packaged() else os.path.dirname(os.path.abspath(__file__))
        app_executable = os.path.basename(sys.executable) # e.g., 'CrossPatch.exe' or 'python.exe'
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
:: The 'pause' command will wait for a key press.
:: After the key press, it launches a new, detached cmd process to do the final cleanup.
:: This allows this window to close immediately.
pause > nul & start /b "" cmd /c "timeout /t 1 /nobreak > nul && rmdir /s /q "{self.temp_dir}"" & exit
"""
            with open(script_path, 'w') as f:
                f.write(script_content)
            print(f"Windows updater script created at: {script_path}")
            print("Attempting to launch updater script...")
            # Use DETACHED_PROCESS to ensure the script runs independently
            subprocess.Popen(f'start "" "{script_path}"', creationflags=subprocess.DETACHED_PROCESS, shell=True)
            
            # Give the batch script a moment to launch before the main app closes
            time.sleep(1)
            print("Updater script launched. Main application will now exit.")

        else: # Linux
            script_path = os.path.join(self.temp_dir, 'updater.sh')
            script_content = f"""#!/bin/bash
echo "Waiting for CrossPatch (PID: {pid}) to close..."
while kill -0 {pid} 2>/dev/null; do
    sleep 1
done

echo "Updating files..."

# Check if the extracted update is a single file (for single-binary builds)
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
            print(f"Linux updater script created at: {script_path}")
            subprocess.Popen([script_path], start_new_session=True)