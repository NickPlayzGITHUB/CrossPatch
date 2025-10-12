import tkinter as tk
from tkinter import ttk, messagebox
import requests
import os
import shutil
import zipfile
import threading

import Util
from Constants import GB_API_URL, APP_VERSION

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

class DownloadManager:
    def __init__(self, parent, mods_folder, on_complete=None):
        self.parent = parent
        self.mods_folder = mods_folder
        self.on_complete = on_complete

    def download_mod_from_url(self, mod_url):
        threading.Thread(target=self._download_thread, args=(mod_url,), daemon=True).start()

    def download_specific_file(self, file_info, item_name):
        threading.Thread(target=self._specific_download_thread, args=(file_info, item_name), daemon=True).start()

    def update_specific_file(self, file_info, item_name, mod_folder_name, active_profile):
        threading.Thread(target=self._specific_download_thread, args=(file_info, item_name, mod_folder_name, active_profile), daemon=True).start()

    def download_and_extract_to(self, url, extract_destination):
        """Synchronously downloads and extracts an archive to a specific destination."""
        self._download_thread(url, extract_destination)
    
    def download_from_schema(self, download_url, item_type, item_id, file_ext, page_url=None):
        """Starts a download thread using information from a URL schema."""
        threading.Thread(target=self._schema_download_thread, args=(download_url, item_type, item_id, file_ext, page_url), daemon=True).start()

    def _specific_download_thread(self, file_info, item_name, mod_folder_name=None, active_profile=None):
        """
        Downloads a specific file chosen by the user from the file selection dialog.
        If `mod_folder_name` is provided, it performs an update by overwriting that folder.
        """
        try:
            download_url = file_info.get('_sDownloadUrl')
            file_name = file_info.get('_sFile', 'download.zip')
            clean_item_name = item_name.replace(" ", "")

            if not download_url:
                raise ValueError("Could not find a download URL for the selected file.")

            # 1. Download the file with progress
            self._show_progress_window(f"Downloading {item_name}...", file_name)
            temp_archive_path = os.path.join(self.mods_folder, file_name)
            self._download_file_with_progress(download_url, temp_archive_path)

            # 2. Security Scan
            self.progress_label_var.set("Scanning for unsafe files...")
            if not self._security_scan(temp_archive_path):
                raise InterruptedError("Installation cancelled by user due to security warning.")

            # 3. Extract the archive
            self.progress_label_var.set("Extracting...")
            # If updating, use the existing folder name. Otherwise, create a new one.
            extract_path = os.path.join(self.mods_folder, mod_folder_name or clean_item_name)

            # Preserve mod_page URL during update
            existing_mod_page = None
            if mod_folder_name:
                existing_info = Util.read_mod_info(extract_path)
                existing_mod_page = existing_info.get('mod_page')

            # If this is an update, clear the old mod folder first for a clean install
            if mod_folder_name and os.path.isdir(extract_path):
                print(f"Update mode: Clearing old files from {extract_path}")
                for item in os.listdir(extract_path):
                    item_path = os.path.join(extract_path, item)
                    shutil.rmtree(item_path) if os.path.isdir(item_path) else os.remove(item_path)
            self._extract_archive(temp_archive_path, extract_path)

            # Update info.json with the version from the downloaded file
            self._update_mod_info_with_version(extract_path, file_info.get('_sVersion'))

            # Restore mod_page URL if it existed
            if existing_mod_page:
                self._update_mod_info_with_page(extract_path, existing_mod_page)

            # If the mod was enabled, reinstall it to update the game files
            if mod_folder_name and active_profile and active_profile.get("enabled_mods", {}).get(mod_folder_name):
                self._reinstall_enabled_mod(mod_folder_name, active_profile)

            # 4. Clean up
            os.remove(temp_archive_path)
            self.progress_window.destroy()

            if self.on_complete:
                self.parent.after(0, self.on_complete)

        except (InterruptedError, Exception) as e:
            print(e)
            if 'temp_archive_path' in locals() and os.path.exists(temp_archive_path):
                os.remove(temp_archive_path)
            if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                self.progress_window.destroy()
            if not isinstance(e, InterruptedError):
                messagebox.showerror("Download Failed", f"An error occurred: {e}")
            # Always call on_complete to refresh the UI state, even on failure/cancellation
            if self.on_complete:
                self.parent.after(0, self.on_complete)

    def _download_thread(self, url, extract_override=None):
        """
        Internal download handler.
        If extract_override is provided, it extracts to that path.
        Otherwise, it extracts to the standard mods_folder.
        """
        try:
            # 1. Get Item Info from GameBanana API from a page URL
            item_type, item_id = Util.get_gb_item_details_from_url(url)
            if not item_type or not item_id:
                raise ValueError("Could not extract a valid item type and ID from the URL.")

            api_item_type = item_type.rstrip('s').capitalize()
            api_url = f"https://gamebanana.com/apiv11/{api_item_type}/{item_id}?_csvProperties=_sName,_aFiles"
            response = requests.get(api_url, headers={'User-Agent': f'CrossPatch/{APP_VERSION}'})
            response.raise_for_status()
            item_data = response.json()

            # 2. Find the download file
            files = item_data.get('_aFiles')
            if not files:
                raise ValueError("No files found for this item in the API response.")
            
            best_file = max(files, key=lambda f: f.get('_nFilesize', 0))
            download_url = best_file.get('_sDownloadUrl')
            file_name = best_file.get('_sFile')
            item_name = item_data.get('_sName').replace(" ", "")

            if not download_url:
                raise ValueError("Could not find a download URL for the primary file.")

            # 3. Download the file with progress
            self._show_progress_window(f"Downloading {item_name}...", file_name)
            temp_archive_path = os.path.join(self.mods_folder, file_name) # Always download to a temp location
            self._download_file_with_progress(download_url, temp_archive_path)

            # 3.5 Security Scan
            self.progress_label_var.set("Scanning for unsafe files...")
            if not self._security_scan(temp_archive_path):
                # User cancelled the installation
                raise InterruptedError("Installation cancelled by user due to security warning.")

            # 4. Extract the archive
            self.progress_label_var.set("Extracting...")
            extract_path = extract_override if extract_override else os.path.join(self.mods_folder, item_name)
            self._extract_archive(temp_archive_path, extract_path)

            # Update info.json with the version from the downloaded file
            self._update_mod_info_with_version(extract_path, best_file.get('_sVersion'))

            # Add mod_page to info.json
            self._update_mod_info_with_page(extract_path, url)

            # 5. Clean up
            os.remove(temp_archive_path)
            self.progress_window.destroy()

            if not extract_override and self.on_complete:
                self.parent.after(0, self.on_complete)

        except InterruptedError as e:
            # Handle user cancellation gracefully
            print(e)
            if 'temp_archive_path' in locals() and os.path.exists(temp_archive_path):
                os.remove(temp_archive_path)
        except Exception as e:
            if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                self.progress_window.destroy()
            # If running synchronously, we need to re-raise the exception
            if extract_override:
                raise e
            messagebox.showerror("Download Failed", f"An error occurred: {e}")

    def _schema_download_thread(self, download_url, item_type, item_id, file_ext, page_url=None):
        """
        Handles a download where the URL, type, and ID are already known from the protocol schema.
        This is more direct and avoids an extra API call to get the item name.
        """
        temp_archive_path = None
        try:
            # 1. Get Item Name from GameBanana API (we still need this for the folder name)
            api_item_type = item_type.capitalize()
            # We fetch _aFiles to find the specific version of the file being downloaded.
            api_url = f"https://gamebanana.com/apiv11/{api_item_type}/{item_id}?_csvProperties=_sName,_aFiles"
            response = requests.get(api_url, headers={'User-Agent': f'CrossPatch/{APP_VERSION}'})
            response.raise_for_status()
            item_data = response.json()
            item_name = item_data.get('_sName', f"mod_{item_id}").replace(" ", "")

            # Find the specific file being downloaded to get its version
            item_version = None
            files = item_data.get('_aFiles', [])
            found_file = next((f for f in files if f.get('_sDownloadUrl') == download_url), None)

            if found_file:
                item_version = found_file.get('_sVersion')
                print(f"Found specific file version for 1-click install: {item_version}")
            else:
                # Fallback for safety, though this case is unlikely
                print("Could not find matching file for 1-click URL, falling back to main mod version.")
                item_version = item_data.get('_sVersion')

            # The download URL from the schema might not have a clear filename.
            # We'll create a temporary one using the provided file extension.
            file_name = f"{item_name}_download.{file_ext}"

            # 2. Download the file with progress
            self._show_progress_window(f"Downloading {item_name}...", file_name)
            temp_archive_path = os.path.join(self.mods_folder, file_name)
            self._download_file_with_progress(download_url, temp_archive_path)

            # 3. Security Scan
            self.progress_label_var.set("Scanning for unsafe files...")
            if not self._security_scan(temp_archive_path):
                raise InterruptedError("Installation cancelled by user due to security warning.")

            # 4. Extract the archive
            self.progress_label_var.set("Extracting...")
            extract_path = os.path.join(self.mods_folder, item_name)
            self._extract_archive(temp_archive_path, extract_path)

            # Update info.json with the version from the main item data
            self._update_mod_info_with_version(extract_path, item_version)

            # Add mod_page to info.json if a page_url was provided
            self._update_mod_info_with_page(extract_path, page_url)

            # 5. Clean up
            os.remove(temp_archive_path)
            self.progress_window.destroy()

            if self.on_complete:
                self.parent.after(0, self.on_complete)

        except (InterruptedError, Exception) as e:
            if temp_archive_path and os.path.exists(temp_archive_path):
                os.remove(temp_archive_path)
            if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                self.progress_window.destroy()
            if not isinstance(e, InterruptedError):
                messagebox.showerror("Download Failed", f"An error occurred: {e}")

    def _show_progress_window(self, title, file_name):
        self.progress_window = tk.Toplevel(self.parent)
        self.progress_window.transient(self.parent)
        self.progress_window.title(title)
        self.progress_window.resizable(False, False)

        ttk.Label(self.progress_window, text=f"Downloading {file_name}", padding=10).pack()
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_window, variable=self.progress_var, length=300, mode='determinate')
        self.progress_bar.pack(padx=10, pady=5)

        self.progress_label_var = tk.StringVar(value="0.00 MB / 0.00 MB")
        ttk.Label(self.progress_window, textvariable=self.progress_label_var).pack(pady=5)
        Util.center_window(self.progress_window)
        self.progress_window.update()

    def _download_file_with_progress(self, url, destination_path):
        with requests.get(url, stream=True, headers={'User-Agent': f'CrossPatch/{APP_VERSION}'}) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            bytes_downloaded = 0
            with open(destination_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    if total_size > 0:
                        progress = (bytes_downloaded / total_size) * 100
                        self.progress_var.set(progress)
                        self.progress_label_var.set(f"{bytes_downloaded/1024/1024:.2f} MB / {total_size/1024/1024:.2f} MB")
                        self.progress_window.update_idletasks()

    def _security_scan(self, archive_path):
        """
        Scans the contents of an archive for potentially unsafe file types.
        Returns True if the scan passes or the user accepts the risk, False otherwise.
        """
        unsafe_extensions = {'.exe', '.bat', '.cmd', '.ps1', '.sh', '.vbs', '.js', '.jar', '.pyc'}
        suspicious_files = []

        try:
            if archive_path.lower().endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as z:
                    suspicious_files = [f for f in z.namelist() if os.path.splitext(f)[1].lower() in unsafe_extensions]
            elif archive_path.lower().endswith('.7z') and PY7ZR_SUPPORT:
                with py7zr.SevenZipFile(archive_path, 'r') as z:
                    suspicious_files = [f.filename for f in z.list() if os.path.splitext(f.filename)[1].lower() in unsafe_extensions]
            elif archive_path.lower().endswith('.rar') and RARFILE_SUPPORT:
                with rarfile.RarFile(archive_path, 'r') as z:
                    suspicious_files = [f.filename for f in z.infolist() if os.path.splitext(f.filename)[1].lower() in unsafe_extensions]
        except Exception as e:
            print(f"Security scan failed: {e}")
            return messagebox.askyesno("Scan Failed", "Could not scan the archive for unsafe files. Continue with installation anyway?")

        if suspicious_files:
            file_list = "\n - ".join(suspicious_files)
            message = (
                "This mod contains potentially unsafe files that could harm your computer:\n\n"
                f" - {file_list}\n\n"
                "Only proceed if you trust the author of this mod.\n\n"
                "Do you want to continue with the installation?"
            )
            # This needs to run on the main thread
            return messagebox.askyesno("Security Warning", message, icon='warning')
        
        # No suspicious files found
        return True

    def _extract_archive(self, archive_path, dest_path):
        if archive_path.lower().endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(dest_path)
        elif archive_path.lower().endswith('.7z') and PY7ZR_SUPPORT:
            with py7zr.SevenZipFile(archive_path, 'r') as z_ref:
                z_ref.extractall(path=dest_path)
        elif archive_path.lower().endswith('.rar') and RARFILE_SUPPORT:
            rarfile.RarFile(archive_path).extractall(path=dest_path)
        else:
            raise NotImplementedError(f"Unsupported archive format for: {os.path.basename(archive_path)}")
        
        self._handle_nested_folder(dest_path)

    def _handle_nested_folder(self, extract_path):
        items = os.listdir(extract_path)
        if len(items) == 1 and os.path.isdir(os.path.join(extract_path, items[0])):
            nested_folder = os.path.join(extract_path, items[0])
            temp_dir = extract_path + "_temp"
            shutil.move(nested_folder, temp_dir)
            os.rmdir(extract_path)
            os.rename(temp_dir, extract_path)

    def _update_mod_info_with_page(self, mod_path, page_url):
        """Reads, updates, and saves the info.json for a mod to include the mod_page."""
        if not page_url or not os.path.isdir(mod_path):
            return

        try:
            info_path = os.path.join(mod_path, "info.json")
            # Use Util.read_mod_info to ensure an info.json is created if it doesn't exist
            mod_info = Util.read_mod_info(mod_path)
            
            mod_info['mod_page'] = page_url

            with open(info_path, "w", encoding="utf-8") as f:
                import json
                json.dump(mod_info, f, indent=2)
            print(f"Updated info.json for '{os.path.basename(mod_path)}' with mod page.")
        except Exception as e:
            print(f"Could not update info.json for {os.path.basename(mod_path)}: {e}")

    def _update_mod_info_with_version(self, mod_path, version_str):
        """Reads, updates, and saves the info.json for a mod to include the version."""
        if not os.path.isdir(mod_path):
            return

        try:
            info_path = os.path.join(mod_path, "info.json")
            mod_info = Util.read_mod_info(mod_path)

            # Only update the version if it's not already set or if a new one is provided.
            # Default to '1.0' if no version is found.
            mod_info['version'] = version_str or mod_info.get('version') or "1.0"

            with open(info_path, "w", encoding="utf-8") as f:
                import json
                json.dump(mod_info, f, indent=2)
            print(f"Updated info.json for '{os.path.basename(mod_path)}' with version '{mod_info['version']}'.")
        except Exception as e:
            print(f"Could not update info.json for {os.path.basename(mod_path)} with version: {e}")

    def _reinstall_enabled_mod(self, mod_folder_name, active_profile):
        """Removes the old installed files and reinstalls the mod to reflect an update."""
        print(f"Re-installing updated enabled mod: {mod_folder_name}")
        try:
            cfg = self.parent.cfg
            # 1. Remove the old installation from game folders
            Util.remove_mod_from_game_folders(mod_folder_name, cfg)
            # 2. Re-install the new version
            priority = active_profile.get("mod_priority", []).index(mod_folder_name)
            Util.enable_mod_with_ui(mod_folder_name, cfg, priority, self.parent, active_profile)
            print(f"Successfully re-installed {mod_folder_name}.")
        except Exception as e:
            print(f"Failed to automatically re-install updated mod '{mod_folder_name}': {e}")
            messagebox.showwarning("Re-install Failed", f"Could not automatically re-install '{mod_folder_name}'. Please disable and re-enable it manually.")