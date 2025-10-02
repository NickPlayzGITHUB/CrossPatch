import os
import tkinter as tk
import platform
import requests
from tkinter import filedialog, messagebox, ttk

from Credits import CreditsWindow
from Settings import SettingsWindow
from ModUpdatePrompt import ModUpdatePromptWindow
from EditMod import EditModWindow
from UpdateList import UpdateListWindow
import Config
import Util
from Constants import APP_TITLE, APP_VERSION

class CrossPatchWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        self.withdraw()

        # Theme: Azure dark
        self.tk.call('source', os.path.join(os.getcwd(), 'assets', 'themes', 'azure', 'azure.tcl'))
        self.tk.call('set_theme', 'dark')

        if platform.system() == "Windows":
            icon_path = os.path.join(os.getcwd(), "assets", "CrossP.ico")
            self.iconbitmap(icon_path)
        self.geometry("580x700")
        self.resizable(False, False)
        self.title(APP_TITLE)

        self.cfg  = Config.config
        # FIXME: Config.hide_console currently crashes print functions.
        # Disabled during refactor for stability.
        # if self.cfg.get("show_cmd_logs"):
        #      Config.show_console()
        # else:
        #      Config.hide_console()
        mid = ttk.Frame(self, padding=8)
        mid.pack(fill=tk.BOTH, expand=True)
        cols = ("enabled", "name", "version", "author")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings")
        self.tree.heading("enabled", text="")
        self.tree.heading("name",    text="Mod Name")
        self.tree.heading("version", text="Version")
        self.tree.heading("author",  text="Author")
        self.tree.column("enabled", width=30, anchor=tk.CENTER)
        self.tree.column("name",    width=220, anchor=tk.W)
        self.tree.column("version", width=80,  anchor=tk.CENTER)
        self.tree.column("author",  width=150, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True)
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
        ttk.Button(btn_frame, text="Refresh Mods",
                   command=self.refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Open Game",
                   command=Util.launch_game).pack(side=tk.LEFT, padx=5)
        settings_btn = ttk.Button(
            btn_frame, text="⚙", width=3,
            command=self.open_settings
        )
        settings_btn.pack(side=tk.RIGHT, padx=5)
        
        
        ttk.Button(btn_frame, text="Check for Updates",
                  command=self.check_all_mod_updates).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(self, text=f"CrossPatch {APP_VERSION}",
                  font=("Segoe UI", 8)).pack(pady=(0,8))
        
        Util.center_window(self)
        self.deiconify()
        self.grab_set()

    def refresh(self):
        
        Util.clean_mods_folder(self.cfg)
        
        for mod in Util.list_mod_folders(self.cfg["mods_folder"]):
            if self.cfg["enabled_mods"].get(mod, False):
                Util.enable_mod(mod, self.cfg)
        
        # Refresh the display
        self.tree.delete(*self.tree.get_children())
        for mod in Util.list_mod_folders(self.cfg["mods_folder"]):
            info    = Util.read_mod_info(os.path.join(self.cfg["mods_folder"], mod))
            name    = info.get("name", mod)
            version = info.get("version", "1.0")
            author  = info.get("author", "Unknown")
            enabled = self.cfg["enabled_mods"].get(mod, False)
            check   = "☑" if enabled else "☐"
            self.tree.insert(
                "", tk.END,
                values=(check, name, version, author)
            )
        print("Refreshed")

    def on_tree_click(self, event):
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row or col != "#1":
            return
        vals = self.tree.item(row, "values")
        display_name = vals[1]
        for mod in Util.list_mod_folders(self.cfg["mods_folder"]):
            info = Util.read_mod_info(os.path.join(self.cfg["mods_folder"], mod))
            if info.get("name", mod) == display_name:
                if self.cfg["enabled_mods"].get(mod, False):
                    Util.disable_mod(mod, self.cfg)
                else:
                    Util.enable_mod(mod, self.cfg)
                break
        self.refresh()

    def on_right_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def open_selected_mod_folder(self):
        print("Opening mod folder")
        selected = self.tree.selection()
        if not selected:
            return
        display_name = self.tree.item(selected[0], "values")[1]
        for mod in Util.list_mod_folders(self.cfg["mods_folder"]):
            info = Util.read_mod_info(os.path.join(self.cfg["mods_folder"], mod))
            name = info.get("name", mod)
            if name == display_name:
                folder = os.path.join(self.cfg["mods_folder"], mod)
                try:
                    os.startfile(folder)
                except Exception as e:
                    messagebox.showerror(f"{e}")
                break

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
        display_name = self.tree.item(tree_id, "values")[1]

        folder_name = None
        for m in Util.list_mod_folders(self.cfg["mods_folder"]):
            info = Util.read_mod_info(os.path.join(self.cfg["mods_folder"], m))
            if info.get("name", m) == display_name:
                folder_name = m
                break
        if folder_name is None:
            return

        mod_folder = os.path.join(self.cfg["mods_folder"], folder_name)
        info_path  = os.path.join(mod_folder, "info.json")
        data = Util.read_mod_info(mod_folder)

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
        Config.save_config(self.cfg)
        global GAME_ROOT, GAME_EXE
        GAME_ROOT  = new_root
        GAME_EXE   = os.path.join(GAME_ROOT, "SonicRacingCrossWorlds.exe")
        print("Updated root folder")