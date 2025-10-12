
import os
import ctypes
import threading
import platform
import requests
import subprocess
import sys
import tkinter as tk
import shutil
import zipfile
from tkinter import filedialog, messagebox, ttk, simpledialog
from tkinterdnd2 import TkinterDnD, DND_FILES

from Credits import CreditsWindow
from ModUpdatePrompt import ModUpdatePromptWindow
from DownloadManager import DownloadManager
from ConflictDialog import ConflictDialog
from FileSelectDialog import FileSelectDialog
from OneClickInstallDialog import OneClickInstallDialog
from EditMod import EditModWindow
from ProfileManager import ProfileManager
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
    if platform.system() == "Windows":
        # --- Point rarfile to the bundled UnRAR.exe on Windows ---
        if getattr(sys, 'frozen', False):
            # Packaged app: UnRAR.exe is in the 'assets' folder next to the executable
            unrar_path = os.path.join(os.path.dirname(sys.executable), 'assets', 'UnRAR.exe')
        else:
            # Development: UnRAR.exe is in the 'assets' folder in the project root
            unrar_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'UnRAR.exe')
        
        if os.path.exists(unrar_path):
            rarfile.UNRAR_TOOL = unrar_path
            print(f"Found bundled UnRAR at: {unrar_path}")
        else:
            print("Bundled UnRAR.exe not found, falling back to system PATH.")
    # On Linux/macOS, rarfile will look for 'unrar' in the system PATH.
except ImportError:
    RARFILE_SUPPORT = False

def find_assets_dir(max_up_levels=4, verbose=False):
    """
    Finds the 'assets' directory by searching from multiple candidate base paths.
    This is a robust method to handle different execution contexts like running
    from source, or as a packaged application (Nuitka, PyInstaller).
    """
    candidates = []

    # 1) If something set sys.frozen (PyInstaller-style)
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(sys.executable))

    # 2) PyInstaller _MEIPASS (safe to check)
    if hasattr(sys, "_MEIPASS"):
        candidates.append(sys._MEIPASS)

    # 3) The invoked executable/script
    try:
        argv0 = os.path.abspath(sys.argv[0])
        candidates.append(os.path.dirname(argv0))
    except Exception:
        pass

    # 4) This script's file location (useful for dev runs)
    try:
        file_dir = os.path.abspath(os.path.dirname(__file__))
        candidates.append(file_dir)
        candidates.append(os.path.abspath(os.path.join(file_dir, "..")))
    except NameError:
        pass

    # 5) Current working directory
    candidates.append(os.getcwd())

    # De-duplicate while preserving order
    seen = set()
    filtered_candidates = [c for c in candidates if c and c not in seen and not seen.add(c)]

    # For every candidate, look for 'assets' in that dir and up to parent levels
    for base in filtered_candidates:
        for up in range(max_up_levels + 1):
            check_path = os.path.abspath(os.path.join(base, *(['..'] * up)))
            assets_path = os.path.join(check_path, "assets")
            if os.path.isdir(assets_path):
                if verbose:
                    print(f"[find_assets_dir] Found assets at: {assets_path} (base='{base}', up={up})")
                return assets_path

    # Fallback if no assets directory is found
    print("[find_assets_dir] WARNING: Could not find assets directory. Falling back to a default path.")
    return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "assets")
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
            except rarfile.RarCannotExec:
                if platform.system() == "Linux":
                    messagebox.showerror(
                        "RAR Extraction Failed",
                        "To extract .rar files, please install the 'unrar' package using your distribution's package manager.\n\n"
                        "For Debian/Ubuntu: sudo apt-get install unrar\n"
                        "For Fedora: sudo dnf install unrar"
                    )
                else: # Windows or other
                    import webbrowser
                    if messagebox.askyesno(
                        "RAR Extraction Failed",
                        "Extracting .rar files requires the 'unrar' utility, which was not found.\n\n"
                        "The bundled version may be missing or corrupted. Would you like to open the official download page?",
                        icon='warning'
                    ):
                        webbrowser.open("https://www.rarlab.com/rar_add.htm")
            except Exception as e:
                messagebox.showerror("Error Adding Mod", f"Failed to add '{os.path.basename(file_path)}':\n{e}")

        self.refresh()
    
    def add_mod_from_url(self):
        from tkinter.simpledialog import askstring
        url = askstring("Add Mod from URL", "Enter the GameBanana Mod URL:", parent=self)
        if not url or "gamebanana.com" not in url:
            if url: # If user entered something, but it's not a GB link
                messagebox.showwarning("Invalid URL", "Please enter a valid GameBanana mod URL.")
            return

        try:
            # Fetch all item data, including the list of files
            item_data = Util.get_gb_item_data_from_url(url)
            mod_name = item_data.get('_sName', 'Unknown Mod')
            files = item_data.get('_aFiles')

            if not files:
                messagebox.showerror("No Files Found", "Could not find any downloadable files for this mod.", parent=self)
                return

            # Show the file selection dialog
            dialog = FileSelectDialog(self, item_data)
            selected_file = dialog.get_selection()

            # If the user selected a file, proceed with the download
            if selected_file:
                dm = DownloadManager(self, self.cfg["mods_folder"], on_complete=self.refresh)
                dm.download_specific_file(selected_file, mod_name)
            else:
                print("User cancelled file selection.")

        except Exception as e:
            messagebox.showerror("Download Error", f"Could not get mod details or start download.\n\n{e}", parent=self)

    def handle_protocol_url(self, url):
        """Handles a URL passed via the custom protocol (e.g., from another instance)."""
        print(f"Received URL from protocol: {url}")
        
        # New schema format: crosspatch:[URL_TO_ARCHIVE],[MOD_TYPE],[MOD_ID],[FILE_EXTENSION]
        if url.startswith("crosspatch:") and "," in url:
            try:
                # Remove protocol prefix and split the parts
                parts_str = url.replace("crosspatch:", "")
                parts = parts_str.split(',')
                
                download_url = parts[0]
                item_type = parts[1] # e.g., "Mod" or "Sound"
                item_id = parts[2]
                file_ext = parts[3] if len(parts) > 3 else 'zip' # Assume zip if not provided

                # Fetch full item data to get name and image for the confirmation dialog
                # The item_type from the schema might be singular ("Mod"), so we ensure it's plural for the URL.
                gb_page_url = f"https://gamebanana.com/{item_type.lower()}s/{item_id}"
                item_data = Util.get_gb_item_data_from_url(gb_page_url)

                dialog = OneClickInstallDialog(self, item_data)
                if not dialog.confirmed:
                    print("User cancelled download.")
                    return
                dm = DownloadManager(self, self.cfg["mods_folder"], on_complete=self.refresh)
                dm.download_from_schema(download_url, item_type, item_id, file_ext, page_url=gb_page_url)

            except (IndexError, ValueError) as e:
                messagebox.showerror("Download Error", f"Could not parse the received URL. It may be malformed.\n\nDetails: {e}")
        elif url.startswith("crosspatch://install?url="): # Fallback for simple URL format
            gb_url = url.replace("crosspatch://install?url=", "")
            item_data = Util.get_gb_item_data_from_url(gb_url)

            dialog = OneClickInstallDialog(self, item_data)
            if not dialog.confirmed:
                print("User cancelled download.")
                return
            dm = DownloadManager(self, self.cfg["mods_folder"], on_complete=self.refresh)
            dm.download_mod_from_url(gb_url)

    def update_mod_from_url(self, url, mod_folder_name):
        """Handles the process of updating an existing mod from a URL."""
        print(f"Starting update for '{mod_folder_name}' from URL: {url}")
        try:
            # Fetch all item data, including the list of files
            item_data = Util.get_gb_item_data_from_url(url)
            mod_name_from_gb = item_data.get('_sName', 'Unknown Mod')
            files = item_data.get('_aFiles')

            if not files:
                messagebox.showerror("No Files Found", "Could not find any downloadable files for this mod.", parent=self)
                return

            # Show the file selection dialog
            dialog = FileSelectDialog(self, item_data)
            selected_file = dialog.get_selection()

            # If the user selected a file, proceed with the download and update
            if selected_file:
                dm = DownloadManager(self, self.cfg["mods_folder"], on_complete=self.refresh)
                active_profile = self.profile_manager.get_active_profile()
                # Use the new update method in DownloadManager
                dm.update_specific_file(selected_file, mod_name_from_gb, mod_folder_name, active_profile)
            else:
                # If the user cancels the update, we should still re-check updates
                # to ensure the UI state is correct (e.g., if they manually updated).
                # We run this in a separate thread to avoid blocking the UI.
                threading.Thread(target=lambda: self.check_all_mod_updates(), daemon=True).start()
                print("User cancelled file selection for update.")

        except Exception as e:
            messagebox.showerror("Update Error", f"Could not get mod details or start update.\n\n{e}", parent=self)


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
        active_profile = self.profile_manager.get_active_profile()
        enabled_mods = active_profile.get("enabled_mods", {})
        updatable_mod_names = {v['name']: v for v in self.updatable_mods.values()}

        self.tree.delete(*self.tree.get_children())
        for mod in active_profile.get("mod_priority", []):
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
            check_char = "☑" if enabled else "☐"
            tags = ()
            
            if name in updatable_mod_names:
                update_char = "⬆️"
                tags = ('updatable',)
            else:
                update_char = ""
            
            self.tree.insert("", tk.END, iid=mod, values=(update_char, check_char, name, version, author, mod_type), tags=tags)
        print("Treeview updated")

    def refresh(self):
        # Get a sorted list of all mods
        all_mods = Util.list_mod_folders(self.cfg["mods_folder"])
        
        active_profile = self.profile_manager.get_active_profile()

        # Ensure all mods are in the priority list, append new ones
        priority_list = active_profile.get("mod_priority", [])
        for mod in all_mods:
            if mod not in priority_list:
                priority_list.append(mod)
        # Remove mods from priority list if they were deleted
        active_profile["mod_priority"] = [mod for mod in priority_list if mod in all_mods]
        enabled_mods = active_profile.get("enabled_mods", {})

        # Sort mods to move disabled ones to the bottom, preserving relative order.
        enabled_priority = [
            mod for mod in active_profile["mod_priority"] if enabled_mods.get(mod, False)
        ]
        # Disabled mods are now sorted alphabetically.
        disabled_priority = sorted(
            [mod for mod in active_profile["mod_priority"] if not enabled_mods.get(mod, False)],
            key=str.lower
        )
        
        self.profile_manager.set_mod_priority(enabled_priority + disabled_priority)

        Util.clean_mods_folder(self.cfg)
        # Enable mods in the correct priority order
        for i, mod in enumerate(enabled_priority):
            Util.enable_mod_with_ui(mod, self.cfg, i, self, active_profile)

        # Re-check for updates to clear any green highlights for mods that are now up-to-date
        threading.Thread(target=lambda: self.check_all_mod_updates(), daemon=True).start()

        self._update_treeview()
        print("Saved and refreshed.")

        # Mod conflict detection
        conflicts = self.detect_mod_conflicts()
        if conflicts:
            ConflictDialog(self, conflicts)
    def detect_mod_conflicts(self):
        # Scan enabled mods for file conflicts
        mods_folder = self.cfg["mods_folder"]
        active_profile = self.profile_manager.get_active_profile()
        enabled_mods_dict = active_profile.get("enabled_mods", {})
        enabled_mods = [mod for mod in active_profile.get("mod_priority", []) if enabled_mods_dict.get(mod, False)]
        file_map = {}
        conflicts = {}

        # Define a set of filenames to ignore during conflict detection.
        # These are often config or metadata files that don't cause actual in-game conflicts.
        conflict_blacklist = {"info.json", "config.ini", "readme.txt", "readme.md", "changelog.txt"}

        for mod in enabled_mods:
            mod_path = os.path.join(mods_folder, mod)

            # Read mod info to check its type
            mod_info = Util.read_mod_info(mod_path)
            mod_type = mod_info.get("mod_type", "pak")

            # Skip conflict detection for all UE4SS mod types
            if mod_type.startswith("ue4ss"):
                continue

            for root, _, files in os.walk(mod_path):
                for f in files:
                    if f.lower() in conflict_blacklist:
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
        super().__init__(className="crosspatch")
        self.instance_socket = instance_socket

        self.withdraw()

        # Use the robust find_assets_dir function to locate the assets folder
        asset_path = find_assets_dir(verbose=True)
        print("Using assets folder:", asset_path)

        # Theme: Azure dark
        self.tk.call('source', os.path.join(asset_path, 'themes', 'azure', 'azure.tcl'))
        self.tk.call('set_theme', 'dark')

        # --- Custom Style Configuration for Sleek Tabs ---
        style = ttk.Style(self)

        # Get theme colors to ensure the new style matches the dark theme
        selected_bg = style.lookup('TNotebook.Tab', 'background', ('selected',))
        unselected_bg = style.lookup('TFrame', 'background') # Use the main window background for unselected tabs
        border_color = style.lookup('TFrame', 'background')

        # Configure the tab style for a modern look
        style.configure('TNotebook.Tab',
                        padding=[10, 3],          # [padx, pady]
                        background=unselected_bg, # Make unselected tabs blend in
                        borderwidth=1)
        style.map('TNotebook.Tab',
                  background=[('selected', selected_bg)]) # Highlight the selected tab

        # Remove the outer border of the notebook widget itself for a cleaner look
        style.configure('TNotebook', borderwidth=0)

        self.cfg = Config.config
        self.profile_manager = ProfileManager(self.cfg)
        self.geometry(self.cfg.get("window_size", "580x720"))
        self.updatable_mods = {} # To store mods with available updates
        self.resizable(True, True)
        self.title(APP_TITLE)

        # --- Tabbed Interface ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=8, pady=8)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

        self.mods_tab_frame = ttk.Frame(self.notebook)
        self.settings_tab_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.mods_tab_frame, text="Mods")
        self.notebook.add(self.settings_tab_frame, text="Settings")

        # FIXME: Config.hide_console currently crashes print functions.
        # Disabled during refactor for stability.
        # if self.cfg.get("show_cmd_logs"):
        #      Config.show_console()
        # else:
        #      Config.hide_console()

        # --- Profile Management UI ---
        profile_frame = ttk.Frame(self.settings_tab_frame, padding=(0, 0, 0, 8))
        profile_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(profile_frame, text="Profile:").pack(side=tk.LEFT)
        
        self.profile_var = tk.StringVar()
        self.profile_selector = ttk.Combobox(profile_frame, textvariable=self.profile_var, state="readonly", width=30)
        self.profile_selector.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.profile_selector.bind("<<ComboboxSelected>>", self.on_profile_change)
        
        # Prevent text selection/highlighting in the combobox
        self.profile_selector.bind("<B1-Motion>", lambda e: "break")
        self.profile_selector.bind("<Shift-Button-1>", lambda e: "break")
        self.profile_selector.bind("<Double-Button-1>", lambda e: "break")
        self.profile_selector.bind("<FocusIn>", lambda e: self.profile_selector.selection_clear())

        # Add profile management buttons
        profile_btn_frame = ttk.Frame(profile_frame)
        profile_btn_frame.pack(side=tk.RIGHT, padx=(5,0))
        ttk.Button(profile_btn_frame, text="+", command=self.add_profile, width=3).pack(side=tk.LEFT)
        ttk.Button(profile_btn_frame, text="Edit", command=self.rename_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(profile_btn_frame, text="Delete", command=self.delete_profile).pack(side=tk.LEFT)
        self.update_profile_selector()
        
        # --- Settings UI (integrated from former SettingsWindow) ---
        settings_content_frame = ttk.Frame(self.settings_tab_frame, padding=(0, 8, 0, 0))
        settings_content_frame.pack(fill=tk.BOTH, expand=True)
        
        self.show_logs_var = tk.BooleanVar(
            value=self.cfg.get("show_cmd_logs", False)
        )
        chk = ttk.Checkbutton(
            settings_content_frame,
            text="Show console logs",
            variable=self.show_logs_var,
            command=self.on_toggle_logs
        )
        if platform.system() == "Windows":
            chk.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,8))

        ttk.Label(settings_content_frame, text="Game Directory:").grid(row=1, column=0, sticky="w")
        self.game_root_var = tk.StringVar(value=self.cfg["game_root"])
        entry = ttk.Entry(settings_content_frame, textvariable=self.game_root_var, width=50, state="readonly")
        entry.grid(row=1, column=1, sticky="we", padx=(5,0))
        pick_btn = ttk.Button(settings_content_frame, text="...", width=3, command=self.on_change_game_root)
        pick_btn.grid(row=1, column=2, sticky="e", padx=(5,0))

        ttk.Label(settings_content_frame, text="Mods Folder:").grid(row=2, column=0, sticky="w", pady=(8,0))
        self.mods_folder_var = tk.StringVar(value=self.cfg["mods_folder"])
        mods_entry = ttk.Entry(settings_content_frame, textvariable=self.mods_folder_var, width=50, state="readonly")
        mods_entry.grid(row=2, column=1, sticky="we", padx=(5,0), pady=(8,0))
        mods_pick_btn = ttk.Button(settings_content_frame, text="...", width=3, command=self.on_change_mods_folder)
        mods_pick_btn.grid(row=2, column=2, sticky="e", padx=(5,0), pady=(8,0))
        settings_content_frame.columnconfigure(1, weight=1)

        # Settings action buttons
        settings_btn_frame = ttk.Frame(settings_content_frame)
        settings_btn_frame.grid(row=3, column=0, columnspan=3, pady=(12,0), sticky="w")
        
        ttk.Button(settings_btn_frame, text="Check for Mod Updates", command=self.on_check_mod_updates).pack(anchor="w")
        ttk.Button(settings_btn_frame, text="Credits", command=lambda: self.open_credits()).pack(anchor="w", pady=(5, 0))


        # Search bar (hidden by default)
        self.search_frame = ttk.Frame(self.mods_tab_frame, padding=(0, 0, 0, 8))
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *args: self._update_treeview())
        ttk.Label(self.search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(self.search_frame, textvariable=self.search_var, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_frame.pack_forget()
        
        # --- Mods List (Treeview) ---
        mid = ttk.Frame(self.mods_tab_frame)
        mid.pack(fill=tk.BOTH, expand=True)

        cols = ("update", "enabled", "name", "version", "author", "type")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings")
        self.tree.heading("update", text="")
        self.tree.heading("enabled", text="")
        self.tree.heading("name",    text="Mod Name")
        self.tree.heading("version", text="Version")
        self.tree.heading("author",  text="Author")
        self.tree.heading("type", text="Type")
        self.tree.column("update", width=30, anchor=tk.CENTER, stretch=False)
        self.tree.column("enabled", width=30, anchor=tk.CENTER, stretch=False)
        self.tree.column("name",    width=180, anchor=tk.W)
        self.tree.column("version", width=80,  anchor=tk.CENTER)
        self.tree.column("author",  width=120, anchor=tk.W)
        self.tree.column("type", width=50, anchor=tk.CENTER)
        
        # Configure a tag for the drop indicator highlight
        self.tree.tag_configure('drop_indicator', background='dodgerblue')
        self.tree.tag_configure('updatable', foreground='springgreen')

        tree_scrollbar = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bindings for drag-and-drop reordering and clicks
        self.tree.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree.bind("<B1-Motion>", self.on_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self.on_drag_end)

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
        self.context_menu.add_command(
            label="Delete mod",
            command=self.delete_mod
        )
        self.tree.bind("<Button-3>", self.on_right_click)
        self.refresh()
        btn_frame = ttk.Frame(self, padding=8)
        btn_frame.pack(fill=tk.X)
        
        # Configure grid columns to control button positions
        btn_frame.columnconfigure(0, weight=0) # Refresh
        btn_frame.columnconfigure(1, weight=0) # Save
        btn_frame.columnconfigure(2, weight=0) # Add Mod
        btn_frame.columnconfigure(3, weight=1) # Spacer
        btn_frame.columnconfigure(4, weight=0) # Search

        # Settings button (currently hidden)
        # To show it again, uncomment the line below.
        self.settings_btn = ttk.Button(
            btn_frame, text="⚙", width=3,
            command=self.open_settings
        )
        # self.settings_btn.pack(side=tk.RIGHT, padx=5)
        # Search button
        self.search_btn = ttk.Button(
            btn_frame, text="🔍", width=3,
            command=self.toggle_search_bar
        )
        self.search_btn.grid(row=0, column=4, sticky="e", padx=5)

        # --- Load button icons ---
        try:
            # Refresh and Save icons
            refresh_icon_path = os.path.join(asset_path, "refresh_icon.png")
            self.refresh_icon = tk.PhotoImage(file=refresh_icon_path).subsample(3, 3)
            save_icon_path = os.path.join(asset_path, "save_icon.png")
            self.save_icon = tk.PhotoImage(file=save_icon_path).subsample(3, 3)
            # GameBanana icon for the "Add Mod" button
            gb_icon_path = os.path.join(asset_path, "gb_icon.png")
            self.gb_icon = tk.PhotoImage(file=gb_icon_path).subsample(2, 2) # Adjust subsample as needed for icon size
            add_mod_compound = tk.LEFT
        except tk.TclError:
            print("Could not load one or more icon files. Buttons may be text-only.")
            self.refresh_icon = None
            self.save_icon = None
            self.gb_icon = None
            add_mod_compound = tk.NONE

        # Create icon-based buttons for Refresh and Save
        self.refresh_btn = ttk.Button(btn_frame, image=self.refresh_icon, width=3, command=self.refresh)
        self.refresh_btn.grid(row=0, column=0, sticky="w", padx=5)
        self.save_btn = ttk.Button(btn_frame, image=self.save_icon, width=3, command=self.save_and_refresh)
        self.save_btn.grid(row=0, column=1, sticky="w")

        self.add_mod_btn = ttk.Button(btn_frame, text="Add Mod from URL", image=self.gb_icon, compound=add_mod_compound, command=self.add_mod_from_url)
        self.add_mod_btn.grid(row=0, column=2, sticky="w", padx=5)
        ttk.Label(self, text=f"CrossPatch {APP_VERSION}",
                  font=("Segoe UI", 8)).pack(pady=(0,8))

        # --- Bottom action buttons ---
        bottom_action_frame = ttk.Frame(self, padding=(8, 0, 8, 8))
        bottom_action_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Configure column to make the button expand
        bottom_action_frame.columnconfigure(0, weight=1)

        launch_btn = ttk.Button(bottom_action_frame, text="Launch Game", command=self.save_and_launch)
        launch_btn.grid(row=0, column=0, sticky="ew")

        # --- Final Window Setup ---
        # Set the icon and center the window before showing it.
        if platform.system() == "Windows":
            icon_path = os.path.join(asset_path, "CrossP.ico")
            self.iconbitmap(icon_path)

        # This needs to run before deiconify to prevent a white flash.
        self.update_idletasks()
        Util.center_window(self)

        # Show the window.
        self.deiconify()

        # Set dark title bar on Windows after the window is visible and has a handle.
        if platform.system() == "Windows":
            try:
                hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                value = ctypes.c_int(1) # 1 for True/dark
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(value), ctypes.sizeof(value)
                )
            except Exception as e:
                print(f"Could not set dark title bar: {e}")

        # Drag and drop support
        self.tree.drop_target_register(DND_FILES)
        self.tree.dnd_bind('<<Drop>>', self.on_drop_mod)

        # Bind CTRL+F to toggle search bar
        self.bind_all('<Control-f>', lambda e: self.toggle_search_bar())
        
        # Add protocol for saving window size on close
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Start listening for connections from other instances (for one-click installs)
        if self.instance_socket:
            threading.Thread(target=self._socket_listener, daemon=True).start()
        
        # --- Performance Fix for Resizing ---
        # The tkinterdnd2 library can cause severe lag on window resize on Windows.
        # Unbinding this specific event fixes the issue without affecting drag-and-drop functionality.
        self.unbind('<Configure>')

    def on_tab_change(self, event):
        """Shows or hides mod-related buttons based on the selected tab."""
        selected_tab_index = self.notebook.index(self.notebook.select())
        
        # Index 0 is the "Mods" tab, Index 1 is the "Settings" tab.
        if selected_tab_index == 0:
            # Show the buttons by packing them back into the frame.
            self.refresh_btn.grid(row=0, column=0, sticky="w", padx=5)
            self.save_btn.grid(row=0, column=1, sticky="w")
            self.add_mod_btn.grid(row=0, column=2, sticky="w", padx=5)
            self.search_btn.grid(row=0, column=4, sticky="e", padx=5)
        else:
            # Hide the buttons.
            self.refresh_btn.grid_remove()
            self.save_btn.grid_remove()
            self.add_mod_btn.grid_remove()
            self.search_btn.grid_remove()


    def on_closing(self):
        """Saves window size and closes the application."""
        print("Saving configuration before exiting...")
        self.refresh()  # This saves the mod order and applies enabled mods.
        self.cfg["window_size"] = self.geometry()  # Save window size
        self.profile_manager.save()  # Save all profile and config data
        self.destroy()

    def _socket_listener(self):
        """Listens for incoming connections on the instance socket."""
        self.instance_socket.listen(1)
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

    def on_drag_start(self, event):
        """Initiates a drag operation or handles a checkbox click."""
        self._drag_data = {}
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        clicked_col = self.tree.identify_column(event.x)
        
        # Column #1 is 'update', Column #2 is 'enabled'
        if clicked_col == '#1': # Update column
            self.on_update_column_click(item_id)
            return # Prevent drag
        elif clicked_col == '#2': # Enabled column
            self.on_enable_column_click(item_id)
            return

        # Otherwise, it's a drag operation.
        # It's a drag operation. Store item info.
        self._drag_data['item'] = item_id
        self._drag_data['index'] = self.tree.index(item_id)

        # Create a semi-transparent "ghost" window that follows the cursor
        self._drag_data['ghost'] = ghost = tk.Toplevel(self)
        ghost.transient(self) # Make it a transient window of the main app
        ghost.overrideredirect(True)
        ghost.attributes('-alpha', 0.7)
        ghost.attributes('-topmost', True)
        label = ttk.Label(ghost, text=self.tree.item(item_id, 'values')[2], padding=5, background='grey15', foreground='white')
        label.pack()
        ghost.update_idletasks()
        # Position the ghost window at the cursor
        ghost.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")

    def on_drag_motion(self, event):
        """Handles moving the item during a drag, updating the ghost and indicator."""
        if not hasattr(self, '_drag_data') or not self._drag_data.get('item'):
            return

        # Move the ghost window
        ghost = self._drag_data.get('ghost')
        if ghost:
            ghost.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")

        # Manage the drop indicator highlight
        target_item = self.tree.identify_row(event.y)
        last_indicator = self._drag_data.get('last_indicator')

        # Remove old indicator if it exists and is not the new target
        if last_indicator and last_indicator != target_item and self.tree.exists(last_indicator):
            self.tree.item(last_indicator, tags=())

        # Add new indicator if target is valid
        if target_item and target_item != self._drag_data['item']:
            self.tree.item(target_item, tags=('drop_indicator',))
            self._drag_data['last_indicator'] = target_item
        else:
            self._drag_data['last_indicator'] = None

    def on_drag_end(self, event):
        """Finalizes the drag operation, moving the item and saving the new order."""
        if not hasattr(self, '_drag_data') or not self._drag_data.get('item'):
            return

        # Destroy the ghost window
        ghost = self._drag_data.get('ghost')
        if ghost:
            ghost.destroy()

        # Clean up any lingering indicator
        last_indicator = self._drag_data.get('last_indicator')
        if last_indicator and self.tree.exists(last_indicator):
            self.tree.item(last_indicator, tags=())

        # Determine the drop target and move the item
        target_item = self.tree.identify_row(event.y)
        dragged_item = self._drag_data.get('item')

        if target_item and target_item != dragged_item:
            self.tree.move(dragged_item, '', self.tree.index(target_item))

        # Reset drag data
        self._drag_data = {}

        # Check if the order actually changed and save if it did
        new_priority = list(self.tree.get_children())
        if self.profile_manager.get_active_profile().get("mod_priority") != new_priority:
            self.profile_manager.set_mod_priority(new_priority)

    def on_update_column_click(self, mod_folder_name):
        """Handles clicks on the update icon column."""
        if mod_folder_name in self.updatable_mods:
            mod_update_info = self.updatable_mods[mod_folder_name]
            url = mod_update_info['url']
            print(f"Starting update for '{mod_folder_name}' from action column click.")
            self.update_mod_from_url(url, mod_folder_name)

    def on_enable_column_click(self, mod_folder_name):
        """Handles clicks on the enable/disable checkbox column."""
        active_profile = self.profile_manager.get_active_profile()
        is_enabling = not active_profile.get("enabled_mods", {}).get(mod_folder_name, False)

        # Toggle the mod's state in the config
        self.profile_manager.set_mod_enabled(mod_folder_name, is_enabling)

        # Update the checkbox character in the treeview instantly
        current_values = list(self.tree.item(mod_folder_name, "values"))
        # The checkbox is now in the second column (index 1)
        current_values[1] = "☑" if is_enabling else "☐"
        self.tree.item(mod_folder_name, values=tuple(current_values))

    def update_profile_selector(self):
        """Updates the profile combobox with the latest list of profiles."""
        profiles = self.profile_manager.get_profile_names()
        active_profile = self.profile_manager.get_active_profile_name()
        
        self.profile_selector['values'] = profiles
        self.profile_var.set(active_profile)

    def on_profile_change(self, event=None):
        """Handles switching to a new profile."""
        new_profile = self.profile_var.get()
        if self.profile_manager.set_active_profile(new_profile):
            self.refresh() # A full refresh is needed to apply the new profile

    def add_profile(self):
        """Creates a new profile."""
        new_name = simpledialog.askstring("New Profile", "Enter a name for the new profile:", parent=self)
        if self.profile_manager.create_profile(new_name):
            self.update_profile_selector()
            self.refresh()
        elif new_name: # If they entered a name but it failed (e.g., duplicate)
            messagebox.showerror("Error", "A profile with this name already exists or the name is invalid.", parent=self)

    def rename_profile(self):
        """Renames the currently active profile."""
        old_name = self.profile_manager.get_active_profile_name()
        
        if old_name == self.profile_manager.DEFAULT_PROFILE_NAME:
            messagebox.showerror("Error", "The 'Default' profile cannot be renamed.", parent=self)
            return

        new_name = simpledialog.askstring("Rename Profile", f"Enter a new name for '{old_name}':", initialvalue=old_name, parent=self)
        
        if self.profile_manager.rename_profile(old_name, new_name):
            self.update_profile_selector()
        elif new_name and new_name != old_name: # If they entered a new name but it failed
            messagebox.showerror("Error", "A profile with this name already exists or the name is invalid.", parent=self)

    def delete_profile(self):
        """Deletes the currently active profile."""
        profile_to_delete = self.profile_manager.get_active_profile_name()

        if profile_to_delete == self.profile_manager.DEFAULT_PROFILE_NAME:
            messagebox.showerror("Error", "The 'Default' profile cannot be deleted.", parent=self)
            return
        if len(self.profile_manager.get_profile_names()) <= 1:
            messagebox.showerror("Error", "You cannot delete the last profile.", parent=self)
            return

        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the active profile '{profile_to_delete}'?", parent=self):
            return

        if self.profile_manager.delete_profile(profile_to_delete):
            self.update_profile_selector()
            self.refresh() # Refresh to load the new active profile

    def on_right_click(self, event):
        """Handles right-clicks on the treeview to show the context menu."""
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def launch_game(self):
        """Just launches the game. Kept for internal use if needed."""
        Util.launch_game()

    def save_and_refresh(self):
        self.refresh()

    def save_and_launch(self):
        self.refresh()
        self.launch_game()

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

    def delete_mod(self):
        selected = self.tree.selection()
        if not selected:
            return
        mod_id = selected[0]
        # Confirm mod deletion
        deletemod_confirm = tk.messagebox.askyesno(f"Mod Deletion", f"Are you sure you want to delete {mod_id}?",)
        if deletemod_confirm:
            print(f"Deleting mod {mod_id} from game folder (if exists)")
            Util.remove_mod_from_game_folders(mod_id, self.cfg)

            print(f"Deleting mod {mod_id} from mods folder")
            shutil.rmtree(os.path.join(self.cfg["mods_folder"], mod_id))

            print(f"Refreshing mod list")
            self.refresh()


    def check_all_mod_updates(self, manual_check=False):
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
            mod_folder_name = mod
                
            try:
                # Use the new centralized function to get the version
                gb_version = Util.get_gb_mod_version(mod_page)
                
                if not gb_version:
                    print(f"No version info found for {mod_name}")
                    continue
                if Util.is_newer_version(mod_version, gb_version):
                    updates[mod_folder_name] = {
                        'name': mod_name,
                        'current': mod_version,
                        'new': gb_version,
                        'url': mod_page,
                        'folder_name': mod_folder_name
                    }
                    print(f"Update found for {mod_name}: {mod_version} -> {gb_version}")
                
            except Exception as e:
                print(f"Error checking {mod_name}: {str(e)}")
                continue
        
        self.updatable_mods = updates
        
        # Schedule the UI update on the main thread.
        self.after(0, self._update_treeview)

        if updates:
            print(f"Found {len(updates)} mod(s) with available updates.")
            if manual_check:
                self.after(0, lambda: messagebox.showinfo("Updates Found", f"{len(updates)} mod(s) have updates available and are now highlighted in green.", parent=self))
        else:
            print("No mod updates found.")
            if manual_check:
                self.after(0, lambda: messagebox.showinfo("Update Check", "No mod updates available.", parent=self))
    
    def check_mod_updates(self):
        print("Checking for mod updates...")
        sel = self.tree.selection()
        if not sel:
            return
        
        tree_id = sel[0]
        display_name = self.tree.item(tree_id, "values")[2]
        
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
            # Use the new centralized function to get the version
            gb_version = Util.get_gb_mod_version(mod_page)
            if not gb_version:
                messagebox.showwarning("Update Check", "Could not find version information for this mod on GameBanana.", parent=self)
                return

            print(f"Found version: {gb_version}")
            local_version = mod_info.get("version", "1.0")
            
            if Util.is_newer_version(local_version, gb_version):
                self.show_mod_update_prompt(mod_page, display_name, local_version, gb_version, mod_folder)
            else:
                messagebox.showinfo("No Updates Found", f"'{display_name}' is already up to date (v{local_version}).", parent=self)
                
        except Exception as e:
            messagebox.showerror("Update Check Error", f"Failed to check for updates: {str(e)}", parent=self)
            
    def show_mod_update_prompt(self, mod_page, mod_name, current_version, new_version, mod_folder_name):
        ModUpdatePromptWindow(self, mod_page, mod_name, current_version, new_version, mod_folder_name)

    def edit_selected_mod_info(self):
        print("Editing mod info.json")
        sel = self.tree.selection()
        if not sel:
            return
        tree_id = sel[0]
        # The tree_id is the folder name
        folder_name = tree_id
        display_name = self.tree.item(tree_id, "values")[2]

        mod_folder = os.path.join(self.cfg["mods_folder"], folder_name)
        info_path  = os.path.join(mod_folder, "info.json")
        data = Util.read_mod_info(mod_folder) or {} # Ensure data is a dict

        EditModWindow(self, display_name, data, folder_name, tree_id)

    def open_settings(self):
        """Switches to the settings tab."""
        self.notebook.select(self.settings_tab_frame)

    def open_credits(self, settings_win=None):
        if settings_win:
            settings_win.destroy()
        CreditsWindow(self)

    # --- Methods moved from SettingsWindow ---
    def on_check_mod_updates(self): # Renamed from on_check_mod_updates in SettingsWindow
        self.check_all_mod_updates(manual_check=True)

    def on_toggle_logs(self):
        enabled = self.show_logs_var.get()
        self.cfg["show_cmd_logs"] = enabled
        Config.save_config(self.cfg)
        if enabled:
            Config.show_console()
        else:
            Config.hide_console() 
    
    def on_change_mods_folder(self):
        new_folder = filedialog.askdirectory(
            title="Select a folder to store your mods",
            initialdir=self.cfg["mods_folder"]
        )
        if not new_folder:
            return
        self.mods_folder_var.set(new_folder)
        self.cfg["mods_folder"] = new_folder
        Config.save_config(self.cfg)
        # Trigger a refresh on the main window to reflect the change
        self.refresh()

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
        Config.save_config(self.cfg)
        print("Updated root folder")
