
import os
import threading
import platform
import requests
import subprocess
import sys
import tkinter as tk
import shutil
import zipfile
from tkinter import filedialog, messagebox, ttk
from tkinterdnd2 import TkinterDnD, DND_FILES

from Credits import CreditsWindow
from Settings import SettingsWindow
from ModUpdatePrompt import ModUpdatePromptWindow
from DownloadManager import DownloadManager
from EditMod import EditModWindow
from UpdateList import UpdateListWindow
import Config
import Util
from Constants import APP_TITLE, APP_VERSION

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
class CrossPatchWindow(TkinterDnD.Tk):
    def on_drop_mod(self, event):
        """Handles drag-and-drop of mods (folders or zips) onto the treeview."""
        files = self.tk.splitlist(event.data)
        mods_folder = self.cfg["mods_folder"]
        
        for file_path in files:
            try:
                if os.path.isdir(file_path):
                    dest = os.path.join(mods_folder, os.path.basename(file_path))
                    if not os.path.exists(dest):
                        shutil.copytree(file_path, dest)
                elif any(file_path.lower().endswith(ext) for ext in ['.zip', '.7z', '.rar']):
                    # Use DownloadManager to handle extraction for consistency
                    dm = DownloadManager(self, self.cfg["mods_folder"])
                    mod_name = os.path.splitext(os.path.basename(file_path))[0]
                    dest_path = os.path.join(self.cfg["mods_folder"], mod_name)
                    if not os.path.exists(dest_path):
                        dm._extract_archive(file_path, dest_path)
            except rarfile.RarCannotExec as e:
                messagebox.showerror("Error Adding Mod", f"Failed to extract RAR file. Please ensure the 'unrar' utility is installed and accessible in your system's PATH.\n\nDetails: {e}")
            except Exception as e:
                messagebox.showerror("Error Adding Mod", f"Failed to add '{os.path.basename(file_path)}':\n{e}")

        self.refresh()
    
    def add_mod_from_url(self):
        from tkinter.simpledialog import askstring
        url = askstring("Add Mod from URL", "Enter the GameBanana Mod URL:", parent=self)
        if url and "gamebanana.com" in url:
            dm = DownloadManager(self, self.cfg["mods_folder"], on_complete=self.refresh)
            dm.download_mod_from_url(url)
        elif url:
            messagebox.showwarning("Invalid URL", "Please enter a valid GameBanana mod URL.")

    def handle_protocol_url(self, url):
        """Handles a URL passed via the custom protocol (e.g., from another instance)."""
        print(f"Received URL from protocol: {url}")
        # The URL will be like "crosspatch://install?url=https://gamebanana.com/mods/12345"
        if url.startswith("crosspatch://install?url="):
            gb_url = url.replace("crosspatch://install?url=", "")
            dm = DownloadManager(self, self.cfg["mods_folder"], on_complete=self.refresh)
            dm.download_mod_from_url(gb_url)

    def toggle_search_bar(self):
        if self.search_frame.winfo_ismapped():
            self.search_frame.pack_forget()
            self.search_entry.config(state='disabled')
            self.search_var.set("")
            self.focus_set() # Return focus to the main window
        else:
            self.search_frame.pack(fill=tk.X)
            self.search_entry.config(state='normal')
            self.search_entry.focus_set()
    def _update_treeview(self):
        """Updates the Treeview with the current mod state without heavy file I/O."""
        # Only get search text if the search bar is actually visible
        if hasattr(self, 'search_frame') and self.search_frame.winfo_ismapped():
            search_text = self.search_var.get().lower() if hasattr(self, 'search_var') else ""
        else:
            search_text = ""
        enabled_mods = self.cfg.get("enabled_mods", {})

        self.tree.delete(*self.tree.get_children())
        for mod in self.cfg["mod_priority"]:
            info    = Util.read_mod_info(os.path.join(self.cfg["mods_folder"], mod))
            name    = info.get("name", mod)
            version = info.get("version", "1.0")
            author  = info.get("author", "Unknown")
            mod_type = info.get("mod_type", "pak").upper()

            # Apply search filter
            if search_text:
                if not (search_text in name.lower() or search_text in author.lower() or search_text in version.lower() or search_text in mod_type.lower()):
                    continue
            
            enabled = enabled_mods.get(mod, False)
            check   = "☑" if enabled else "☐"
            
            self.tree.insert(
                "", tk.END, iid=mod,
                values=(check, name, version, author, mod_type)
            )
        print("Treeview updated")

    def refresh(self):
        # Get a sorted list of all mods
        all_mods = Util.list_mod_folders(self.cfg["mods_folder"])
        
        # Ensure all mods are in the priority list, append new ones
        priority_list = self.cfg.get("mod_priority", [])
        for mod in all_mods:
            if mod not in priority_list:
                priority_list.append(mod)
        # Remove mods from priority list if they were deleted
        self.cfg["mod_priority"] = [mod for mod in priority_list if mod in all_mods]

        Util.clean_mods_folder(self.cfg)
        enabled_mods = self.cfg.get("enabled_mods", {})
        # Enable mods in the correct priority order
        for i, mod in enumerate(self.cfg["mod_priority"]):
            if enabled_mods.get(mod, False):
                Util.enable_mod(mod, self.cfg, i)

        self._update_treeview()
        print("Refreshed")

        # Mod conflict detection
        conflicts = self.detect_mod_conflicts()
        if conflicts:
            msg = "Mod Conflict Detected!\n\nThe following files are provided by multiple enabled mods:\n\n"
            for file, mods in conflicts.items():
                msg += f"{file}: {', '.join(mods)}\n"
            messagebox.showwarning("Mod Conflict Detected", msg)
    def detect_mod_conflicts(self):
        # Scan enabled mods for file conflicts
        mods_folder = self.cfg["mods_folder"]
        enabled_mods_dict = self.cfg.get("enabled_mods", {})
        enabled_mods = [mod for mod in Util.list_mod_folders(mods_folder) if enabled_mods_dict.get(mod, False)]
        file_map = {}
        conflicts = {}
        for mod in enabled_mods:
            mod_path = os.path.join(mods_folder, mod)
            for root, _, files in os.walk(mod_path):
                for f in files:
                    if f.lower() == "info.json":
                        continue
                    rel_path = os.path.relpath(os.path.join(root, f), mod_path)
                    if rel_path not in file_map:
                        file_map[rel_path] = [mod]
                    else:
                        file_map[rel_path].append(mod)
        for rel_path, mods in file_map.items():
            if len(mods) > 1:
                conflicts[rel_path] = mods
        return conflicts
    def __init__(self, instance_socket=None):
        super().__init__()
        self.instance_socket = instance_socket

        self.withdraw()

        # Determine the base path for assets, for both development and packaged (PyInstaller) versions
        if getattr(sys, 'frozen', False):
            # Packaged version: assets are next to the exe
            base_path = os.path.dirname(sys.executable)
            asset_path = os.path.join(base_path, 'assets')
        else:
            # Development version: assets are in the project root, relative to this script in 'src'
            base_path = os.path.dirname(os.path.abspath(__file__))
            asset_path = os.path.join(base_path, '..', 'assets')

        # Theme: Azure dark
        self.tk.call('source', os.path.join(asset_path, 'themes', 'azure', 'azure.tcl'))
        self.tk.call('set_theme', 'dark')

        if platform.system() == "Windows":
            icon_path = os.path.join(asset_path, "CrossP.ico")
            self.iconbitmap(icon_path)
        
        self.cfg  = Config.config
        self.geometry(self.cfg.get("window_size", "580x700"))
        self.resizable(True, True)
        self.title(APP_TITLE)

        # FIXME: Config.hide_console currently crashes print functions.
        # Disabled during refactor for stability.
        # if self.cfg.get("show_cmd_logs"):
        #      Config.show_console()
        # else:
        #      Config.hide_console()

        # Search bar (hidden by default)
        self.search_frame = ttk.Frame(self, padding=(8, 8, 8, 0))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *args: self._update_treeview())
        ttk.Label(self.search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(self.search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_frame.pack_forget()

        mid = ttk.Frame(self, padding=8)
        mid.pack(fill=tk.BOTH, expand=True)

        # Priority buttons
        priority_frame = ttk.Frame(mid)
        priority_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        ttk.Button(priority_frame, text="▲", width=3, command=self.move_mod_up).pack(pady=2)
        ttk.Button(priority_frame, text="▼", width=3, command=self.move_mod_down).pack(pady=2)

        cols = ("enabled", "name", "version", "author", "type")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings")
        self.tree.heading("enabled", text="")
        self.tree.heading("name",    text="Mod Name")
        self.tree.heading("version", text="Version")
        self.tree.heading("author",  text="Author")
        self.tree.heading("type", text="Type")
        self.tree.column("enabled", width=30, anchor=tk.CENTER, stretch=False)
        self.tree.column("name",    width=180, anchor=tk.W)
        self.tree.column("version", width=80,  anchor=tk.CENTER)
        self.tree.column("author",  width=120, anchor=tk.W)
        self.tree.column("type", width=50, anchor=tk.CENTER)
        
        tree_scrollbar = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.bind("<Button-1>", self.on_tree_click)
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu = tk.Menu(
            self,
            tearoff=0,
            bd=0,
            relief="flat"
        )
        self.context_menu.add_command(
            label="Open containing folder",
            command=self.open_selected_mod_folder
        )
        self.context_menu.add_command(
            label="Edit mod info",
            command=self.edit_selected_mod_info
        )
        self.context_menu.add_command(
            label="Check for updates",
            command=self.check_mod_updates
        )
        self.tree.bind("<Button-3>", self.on_right_click)
        self.refresh()
        btn_frame = ttk.Frame(self, padding=8)
        btn_frame.pack(fill=tk.X)
        # Magnifying glass button
        mag_btn = ttk.Button(
            btn_frame, text="🔍", width=3,
            command=self.toggle_search_bar
        )
        mag_btn.pack(side=tk.RIGHT, padx=5)
        settings_btn = ttk.Button(
            btn_frame, text="⚙", width=3,
            command=self.open_settings
        )
        settings_btn.pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Check for Updates",
                  command=self.check_all_mod_updates).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Add Mod from URL",
                  command=self.add_mod_from_url).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh Mods",
                  command=self.refresh).pack(side=tk.LEFT, padx=5)
        ttk.Label(self, text=f"CrossPatch {APP_VERSION}",
                  font=("Segoe UI", 8)).pack(pady=(0,8))

        # Launch Game button at the very bottom
        launch_btn = ttk.Button(self, text="Launch Game", command=self.launch_game)
        launch_btn.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 8))

        Util.center_window(self)
        self.deiconify()
        self.grab_set()
        # Drag and drop support
        self.tree.drop_target_register(DND_FILES)
        self.tree.dnd_bind('<<Drop>>', self.on_drop_mod)

        # Bind CTRL+F to toggle search bar
        self.bind_all('<Control-f>', lambda e: self.toggle_search_bar())
        
        # Add protocol for saving window size on close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Start listening for connections from other instances
        if self.instance_socket:
            self.instance_socket.listen(1)
            threading.Thread(target=self._socket_listener, daemon=True).start()

    def _socket_listener(self):
        """Listens for incoming connections on the instance socket."""
        while True:
            try:
                conn, addr = self.instance_socket.accept()
                with conn:
                    data = conn.recv(1024)
                    if data:
                        url = data.decode('utf-8')
                        # The socket runs in a separate thread, so we must use 'after'
                        # to schedule the UI-related task on the main thread.
                        self.after(0, self.handle_protocol_url, url)
            except Exception as e:
                print(f"Socket listener error: {e}")
                break

    def on_tree_click(self, event):
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row or col != "#1":
            return

        mod_id = row # Use the identified row directly
        if not mod_id: # Double-check that we have a valid mod ID
            return

        # --- Immediate UI Feedback ---
        is_enabling = not self.cfg["enabled_mods"].get(mod_id, False)
        action_message = "Enabling mod..." if is_enabling else "Disabling mod..."

        # Toggle the mod's state in the config
        self.cfg["enabled_mods"][mod_id] = is_enabling
        Config.save_config(self.cfg)

        # Update the checkbox in the treeview instantly
        current_values = list(self.tree.item(mod_id, "values"))
        current_values[0] = "☑" if is_enabling else "☐"
        self.tree.item(mod_id, values=tuple(current_values))

        # --- Deferred Heavy Lifting ---
        def do_refresh():
            # Create and show a simple loading popup
            popup = tk.Toplevel(self)
            popup.transient(self)
            popup.title("Working...")
            popup.resizable(False, False)
            ttk.Label(popup, text=action_message, padding=20).pack()
            popup.update_idletasks()
            self.update_idletasks() # Show the popup

            self.refresh() # This is the slow part
            popup.destroy()

        # Schedule the slow refresh to run after the UI has had time to update
        self.after(100, do_refresh)

    def on_closing(self):
        self.cfg["window_size"] = self.geometry()
        Config.save_config(self.cfg)
        self.destroy()

    def on_right_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def move_mod_up(self):
        selection = self.tree.selection()
        if not selection:
            return
        
        mod_id = selection[0]
        index = self.cfg["mod_priority"].index(mod_id)
        
        if index > 0:
            self.cfg["mod_priority"].pop(index)
            self.cfg["mod_priority"].insert(index - 1, mod_id)
            Config.save_config(self.cfg)
            self.refresh()
            self.tree.selection_set(mod_id)
            self.tree.focus(mod_id)

    def move_mod_down(self):
        selection = self.tree.selection()
        if not selection:
            return

        mod_id = selection[0]
        index = self.cfg["mod_priority"].index(mod_id)

        if index < len(self.cfg["mod_priority"]) - 1:
            self.cfg["mod_priority"].pop(index)
            self.cfg["mod_priority"].insert(index + 1, mod_id)
            Config.save_config(self.cfg)
            self.refresh()
            self.tree.selection_set(mod_id)
            self.tree.focus(mod_id)

    def launch_game(self):
        Util.launch_game()

    def open_selected_mod_folder(self):
        print("Opening mod folder")
        selected = self.tree.selection()
        if not selected:
            return
        mod_id = selected[0]
        folder = os.path.join(self.cfg["mods_folder"], mod_id)
        if platform.system() == "Windows":
            os.startfile(folder)
        elif platform.system() == "Darwin": # macOS
            subprocess.Popen(["open", folder])
        else: # Linux and other UNIX-like systems
            try:
                subprocess.Popen(["xdg-open", folder])
            except FileNotFoundError:
                messagebox.showerror("Error", f"Could not open folder. Please ensure xdg-open is installed.")


    def check_all_mod_updates(self):
        print("Checking all mods for updates...")
        updates = {}
        
        for mod in Util.list_mod_folders(self.cfg["mods_folder"]):
            mod_info = Util.read_mod_info(os.path.join(self.cfg["mods_folder"], mod))
            mod_name = mod_info.get("name", mod)
            mod_version = mod_info.get("version", "1.0")
            mod_page = mod_info.get("mod_page")
            
            if not mod_page or not mod_page.startswith("https://gamebanana.com"):
                print(f"Skipping {mod_name} - no Gamebanana page")
                continue
                
            try:
                
                item_id = None
                for type_path in ["mods", "wips", "updates"]:
                    if f"/{type_path}/" in mod_page:
                        parts = mod_page.split(f"/{type_path}/")[1].split("/")
                        if parts and parts[0].isdigit():
                            item_id = parts[0]
                            break
                
                if not item_id:
                    parts = [p for p in mod_page.split("/") if p.isdigit()]
                    if parts:
                        item_id = parts[0]
                    else:
                        print(f"Could not extract mod ID for {mod_name}")
                        continue
                
                api_url = f"https://gamebanana.com/apiv11/Mod/{item_id}?_csvProperties=_sVersion"
                headers = {
                    'User-Agent': 'CrossPatch/1.0.6',
                    'Accept': 'application/json'
                }
                
                response = requests.get(api_url, headers=headers)
                response.raise_for_status()
                item_data = response.json()
                
                gb_version = item_data.get("_sVersion")
                if not gb_version:
                    print(f"No version info found for {mod_name}")
                    continue
                
                if Util.is_newer_version(mod_version, gb_version):
                    updates[mod_name] = {
                        'current': mod_version,
                        'new': gb_version,
                        'url': mod_page
                    }
                    print(f"Update found for {mod_name}: {mod_version} -> {gb_version}")
                
            except Exception as e:
                print(f"Error checking {mod_name}: {str(e)}")
                continue
        
        UpdateListWindow(self, updates)
    
    def check_mod_updates(self):
        print("Checking for mod updates...")
        sel = self.tree.selection()
        if not sel:
            return
        
        tree_id = sel[0]
        display_name = self.tree.item(tree_id, "values")[1]
        
        mod_folder = None
        mod_info = None
        for mod in Util.list_mod_folders(self.cfg["mods_folder"]):
            info = Util.read_mod_info(os.path.join(self.cfg["mods_folder"], mod))
            if info.get("name", mod) == display_name:
                mod_folder = mod
                mod_info = info
                break
                
        if not mod_folder or not mod_info:
            print(f"Could not find mod info for {display_name}")
            return
            
        mod_page = mod_info.get("mod_page")
        if not mod_page or not mod_page.startswith("https://gamebanana.com"):
            messagebox.showinfo("Update Check", "This mod does not support updating.")
            return
            
        try:
            # (Hopefully) supported URLS:
            # https://gamebanana.com/mods/something
            # https://gamebanana.com/wips/something
            # https://gamebanana.com/updates/something
            
            item_type = None
            item_id = None
            
            for type_path in ["mods", "wips", "updates"]:
                if f"/{type_path}/" in mod_page:
                    parts = mod_page.split(f"/{type_path}/")[1].split("/")
                    if parts and parts[0].isdigit():
                        item_type = type_path
                        item_id = parts[0]
                        break
            
            if not item_id:
                parts = [p for p in mod_page.split("/") if p.isdigit()]
                if parts:
                    item_id = parts[0]
                    item_type = "mods"  # Default to mods because who the fuck uses anything else
                else:
                    messagebox.showwarning("Update Check", "I can't find the ID fix this shit")
                    return

            print(f"Checking {item_type} ID: {item_id}")
            
    
            api_url = f"https://gamebanana.com/apiv11/Mod/{item_id}?_csvProperties=_sVersion"
            print(f"Making request to: {api_url}")
            
            headers = {
                'User-Agent': 'CrossPatch/1.0.7',
                'Accept': 'application/json'
            }
            
            response = requests.get(api_url, headers=headers)
            print(f"Response status code: {response.status_code}")
            print(f"Response headers: {response.headers}")
            print(f"Response content: {response.text[:200]}...")  # Print first 200 chars
            
            response.raise_for_status()
            
            try:
                item_data = response.json()
                print(f"Parsed JSON data: {item_data}")
                
                # Get the version
                gb_version = item_data.get("_sVersion")
                if not gb_version:
                    messagebox.showwarning("Update Check", "Could not find _sVersion in API response")
                    return
                    
                print(f"Found version: {gb_version}")
            except ValueError as e:
                print(f"Failed to parse JSON response. Full response:\n{response.text}")
                raise Exception(f"Failed to parse Gamebanana API response: {str(e)}")
            local_version = mod_info.get("version", "1.0")
            
            if Util.is_newer_version(local_version, gb_version):
                self.show_mod_update_prompt(mod_page, display_name, local_version, gb_version)
            else:
                messagebox.showinfo("Update Check", f"{display_name} is up to date (v{local_version})")
                
        except Exception as e:
            messagebox.showerror("Update Check Error", f"Failed to check for updates: {str(e)}")
            
    def show_mod_update_prompt(self, mod_page, mod_name, current_version, new_version):
        ModUpdatePromptWindow(self, mod_page, mod_name, current_version, new_version)

    def edit_selected_mod_info(self):
        print("Editing mod info.json")
        sel = self.tree.selection()
        if not sel:
            return
        tree_id = sel[0]
        # The tree_id is the folder name
        folder_name = tree_id
        display_name = self.tree.item(tree_id, "values")[1]

        mod_folder = os.path.join(self.cfg["mods_folder"], folder_name)
        info_path  = os.path.join(mod_folder, "info.json")
        data = Util.read_mod_info(mod_folder) or {} # Ensure data is a dict

        EditModWindow(self, display_name, data, folder_name, tree_id)

    def open_settings(self):
        SettingsWindow(self)

    def open_credits(self, settings_win=None):
        if settings_win:
            settings_win.destroy()
        CreditsWindow(self)
        
    # Something is going wrong here
    def on_toggle_logs(self):
        enabled = self.show_logs_var.get()
        self.cfg["show_cmd_logs"] = enabled
        Config.save_config(self.cfg)
        if enabled:
            Config.show_console()
        else:
            Config.hide_console() 

    def on_change_game_root(self):
        new_root = filedialog.askdirectory(
            title="Select Crossworlds Install Folder",
            initialdir=self.cfg["game_root"]
        )
        if not new_root:
            return
        self.game_root_var.set(new_root)
        self.cfg["game_root"] = new_root
        self.cfg["game_mods_folder"] = os.path.join(new_root, "UNION", "Content", "Paks", "~mods")
        self.cfg["ue4ss_mods_folder"] = os.path.join(new_root, "UNION", "Binaries", "Win64", "ue4ss", "Mods")
        self.cfg["ue4ss_logic_mods_folder"] = os.path.join(new_root, "UNION", "Content", "Paks", "LogicMods")
        Config.save_config(self.cfg)
        global GAME_ROOT, GAME_EXE
        GAME_ROOT  = new_root
        GAME_EXE   = os.path.join(GAME_ROOT, "SonicRacingCrossWorlds.exe")
        print("Updated root folder")