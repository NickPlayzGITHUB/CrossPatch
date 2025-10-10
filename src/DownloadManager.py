import tkinter as tk
from tkinter import ttk, messagebox
import requests
import os
import shutil
import zipfile
import threading

import Util
from Constants import GB_API_URL

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

    def download_and_extract_to(self, url, extract_destination):
        """Synchronously downloads and extracts an archive to a specific destination."""
        self._download_thread(url, extract_destination)
    
    def download_from_schema(self, download_url, item_type, item_id, file_ext):
        """Starts a download thread using information from a URL schema."""
        threading.Thread(target=self._schema_download_thread, args=(download_url, item_type, item_id, file_ext), daemon=True).start()

    def _specific_download_thread(self, file_info, item_name):
        """
        Downloads a specific file chosen by the user from the file selection dialog.
        """
        try:
            download_url = file_info.get('_sDownloadUrl')
            file_name = file_info.get('_sFile')
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
            extract_path = os.path.join(self.mods_folder, clean_item_name)
            self._extract_archive(temp_archive_path, extract_path)

            # 4. Clean up
            os.remove(temp_archive_path)
            self.progress_window.destroy()

            if self.on_complete:
                self.parent.after(0, self.on_complete)

        except InterruptedError as e:
            print(e)
            if 'temp_archive_path' in locals() and os.path.exists(temp_archive_path):
                os.remove(temp_archive_path)
        except Exception as e:
            if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
                self.progress_window.destroy()
            messagebox.showerror("Download Failed", f"An error occurred: {e}")

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
            response = requests.get(api_url, headers={'User-Agent': 'CrossPatch/1.0.9'})
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

    def _schema_download_thread(self, download_url, item_type, item_id, file_ext):
        """
        Handles a download where the URL, type, and ID are already known from the protocol schema.
        This is more direct and avoids an extra API call to get the item name.
        """
        temp_archive_path = None
        try:
            # 1. Get Item Name from GameBanana API (we still need this for the folder name)
            api_item_type = item_type.capitalize()
            api_url = f"https://gamebanana.com/apiv11/{api_item_type}/{item_id}?_csvProperties=_sName"
            response = requests.get(api_url, headers={'User-Agent': 'CrossPatch/1.0.9'})
            response.raise_for_status()
            item_data = response.json()
            item_name = item_data.get('_sName', f"mod_{item_id}").replace(" ", "")

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
        with requests.get(url, stream=True, headers={'User-Agent': 'CrossPatch/1.0.9'}) as r:
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