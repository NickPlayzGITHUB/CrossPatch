import os
import sys
import json
import shutil
import subprocess
import ctypes
import urllib.request
import webbrowser
import threading
import tkinter as tk
import platform
import requests
from bs4 import BeautifulSoup
from tkinter import filedialog, messagebox, ttk

CONFIG_FILE = "mod_manager_config.json"
APP_TITLE   = "CrossPatch - A Crossworlds Mod Manager"
APP_VERSION = "1.0.8"
UPDATE_URL = "https://raw.githubusercontent.com/NickPlayzGITHUB/CrossPatch/refs/heads/main/version.txt"
GITHUB_REDIRECT = "https://github.com/NickPlayzGITHUB/CrossPatch/releases/"
DWMWA_USE_IMMERSIVE_DARK_MODE = 20 

_original_stdout = sys.stdout
_original_stderr = sys.stderr
_console_streams = None

def show_console():
    global _console_streams
    try:
        if ctypes.windll.kernel32.AllocConsole():
            _console_streams = (
                open("CONOUT$", "w", buffering=1),
                open("CONOUT$", "w", buffering=1)
            )
            sys.stdout = _console_streams[0]
            sys.stderr = _console_streams[1]
            print("Welcome to CrossPatch's Console logs! If you're a regular user there's really no point in having this enabled\nYou should only use this for debugging purposes, serves no other purpose really")
    except Exception as e:
        print(f"Failed to show console: {e}")
        sys.stdout = _original_stdout
        sys.stderr = _original_stderr

def hide_console():
    global _console_streams
    try:
        sys.stdout = _original_stdout
        sys.stderr = _original_stderr
        
        if _console_streams:
            try:
                _console_streams[0].close()
                _console_streams[1].close()
            except:
                pass
            _console_streams = None
            
        ctypes.windll.kernel32.FreeConsole()
    except Exception as e:
        print(f"Failed to hide console: {e}")

def fetch_remote_version():
    print("Fetching version.txt")
    try:
        with urllib.request.urlopen(UPDATE_URL, timeout=5) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception:
        return None

def is_newer_version(local, remote):
    def to_nums(v):
        return [int(x) for x in v.split(".")]
    lv, rv = to_nums(local), to_nums(remote)
    length = max(len(lv), len(rv))
    lv += [0] * (length - len(lv))
    rv += [0] * (length - len(rv))
    return rv > lv

def show_update_prompt(root, remote_version):
    prompt = tk.Toplevel(root)
    set_dark_mode(prompt)
    prompt.title("Update Available")
    prompt.resizable(False, False)
    print("Update available")

    ttk.Label(
        prompt,
        text=f"CrossPatch {remote_version} is available."
    ).pack(padx=12, pady=(12, 6))

    btn_frame = ttk.Frame(prompt)
    btn_frame.pack(padx=12, pady=(0, 12))

    def on_update():
        prompt.destroy()
        webbrowser.open(GITHUB_REDIRECT)
        print(f"Opening {GITHUB_REDIRECT}")

    def on_ignore():
        prompt.destroy()
        print("Update declined... why")

    ttk.Button(btn_frame, text="Update", command=on_update)\
        .pack(side=tk.LEFT, padx=(0, 6))
    ttk.Button(btn_frame, text="Ignore", command=on_ignore)\
        .pack(side=tk.LEFT)

    prompt.attributes("-topmost", True)

    prompt.update_idletasks() 
    root_x = root.winfo_rootx()
    root_y = root.winfo_rooty()
    root_w = root.winfo_width()
    root_h = root.winfo_height()

    win_w = prompt.winfo_width()
    win_h = prompt.winfo_height()

    pos_x = root_x + (root_w - win_w) // 2
    pos_y = root_y + (root_h - win_h) // 2

    prompt.geometry(f"+{pos_x}+{pos_y}")
    



def check_for_updates(root):
    print("Checking for updates...")
    remote = fetch_remote_version()
    if remote and is_newer_version(APP_VERSION, remote):
        print(f"CrossPatch {APP_VERSION} is outdated, Latest Version is {remote}")
        root.after(0, lambda: show_update_prompt(root, remote))


def launch_game():
    if platform.system() == "Windows":
        print(f"Attempting to launch {GAME_EXE}...") # Removed the EXE check since too many people were having issues, idk why that was even a thing after I made the game launch from steam instead of the exe
        webbrowser.open("steam://run/2486820")
    elif platform.system() == "Linux":
        subprocess.Popen(["steam", "steam://rungameid/2486820"])
    print("Opening Crossworlds...")
    

def default_mods_folder():
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    path = os.path.join(app_dir, "Mods")
    os.makedirs(path, exist_ok=True)
    return path

def load_config():
    default_root = ""
    if platform.system() == "Windows":
        default_root = r"C:\Program Files (x86)\Steam\steamapps\common\SonicRacingCrossWorlds"
    elif platform.system() == "Linux":
        default_root = os.path.join(os.path.expanduser("~"), ".local", "share", "Steam", "steamapps", "common", "SonicRacingCrossWorlds")
    default_mods = os.path.join(default_root, "UNION", "Content", "Paks", "~mods")
    os.makedirs(default_mods, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                root = data.get("game_root", default_root)
                return {
                    "mods_folder":      data.get("mods_folder", default_mods_folder()),
                    "game_root":        root,
                    "game_mods_folder": os.path.join(root, "UNION", "Content", "Paks", "~mods"),
                    "enabled_mods":     data.get("enabled_mods", {}),
                    "show_cmd_logs":    data.get("show_cmd_logs", False)
                }
        except Exception:
            pass
    return {
        "mods_folder":      default_mods_folder(),
        "game_root":        default_root,
        "game_mods_folder": default_mods,
        "enabled_mods":     {},
        "show_cmd_logs":    False
    }

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print("Config Saved")

cfg        = load_config()
GAME_ROOT  = cfg["game_root"]
GAME_EXE   = os.path.join(GAME_ROOT, "SonicRacingCrossWorlds.exe")

def list_mod_folders(path):
    if not os.path.isdir(path):
        return []
    try:
        return sorted(
            [d for d in os.listdir(path)
             if os.path.isdir(os.path.join(path, d))],
            key=str.lower
        )
    except Exception:
        return []

def read_mod_info(mod_path):
    info_file = os.path.join(mod_path, "info.json")
    if os.path.exists(info_file):
        try:
            return json.load(open(info_file, "r", encoding="utf-8"))
        except Exception:
            return {}
    return {}
    

def get_game_mods_folder(cfg):
    return os.path.join(
        cfg["game_root"],
        "UNION",
        "Content",
        "Paks",
        "~mods"
    )

def enable_mod(mod_name, cfg):
    print(f"enabled {mod_name}")
    src = os.path.join(cfg["mods_folder"], mod_name)
    dst = get_game_mods_folder(cfg)
    os.makedirs(dst, exist_ok=True)
    for root, _, files in os.walk(src):
        for f in files:
            if f.lower() == "info.json":
                continue
            shutil.copy2(
                os.path.join(root, f),
                os.path.join(dst, f)
            )
    cfg["enabled_mods"][mod_name] = True
    print(f"{mod_name} files copied to {dst}")
    save_config(cfg)

def clean_mods_folder(cfg): #enhanced refresh
    dst = get_game_mods_folder(cfg)
    if not os.path.isdir(dst):
        return
        
    for filename in os.listdir(dst):
        file_path = os.path.join(dst, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error removing {filename}: {e}")
    

def disable_mod(mod_name, cfg):
    print(f"disabled {mod_name}")
    dst = get_game_mods_folder(cfg)
    if not os.path.isdir(dst):
        return
    src = os.path.join(cfg["mods_folder"], mod_name)
    to_remove = {
        f for _, _, files in os.walk(src)
        for f in files
        if f.lower() != "info.json"
    }
    for f in to_remove:
        path = os.path.join(dst, f)
        if os.path.exists(path):
            os.remove(path)
    cfg["enabled_mods"][mod_name] = False
    save_config(cfg)

def set_dark_mode(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    dark_bg, mid_bg = "#1e1e1e", "#2d2d2d"
    fg, sel_bg       = "#ffffff", "#505050"
    root.configure(bg=dark_bg, bd=0, highlightthickness=0)
    style.configure(".", relief="flat", borderwidth=0, focusthickness=0)
    style.configure("TFrame", background=dark_bg)
    style.configure("TLabel", background=dark_bg, foreground=fg)
    style.configure("TButton",
        background=mid_bg,
        foreground=fg,
        relief="flat",
        borderwidth=0
    )
    style.map("TButton",
        background=[("active", sel_bg)],
        foreground=[("disabled", "#888888")]
    )
    style.configure("TEntry", fieldbackground=mid_bg, foreground=fg)
    style.configure("TCombobox", fieldbackground=mid_bg, foreground=fg)
    style.map("TCombobox",
        fieldbackground=[("readonly", mid_bg)],
        background=[("active", sel_bg)]
    )
    style.configure("TCheckbutton", background=dark_bg, foreground=fg)
    style.configure("Vertical.TScrollbar",
        troughcolor=mid_bg,
        background=sel_bg,
        arrowcolor=fg
    )
    style.configure("Treeview",
        background=mid_bg,
        fieldbackground=mid_bg,
        foreground=fg,
        rowheight=24
    )
    style.configure("Treeview.Heading",
        background=mid_bg,
        foreground=fg,
        font=("Segoe UI", 10, "bold")
    )
    style.map("Treeview",
        background=[("selected", sel_bg)],
        foreground=[("selected", fg)]
    )

class UpdateListWindow(tk.Toplevel): # Why did it make a new class....?
    def __init__(self, parent, updates):
        super().__init__(parent)
        self.title("Available Updates")
        set_dark_mode(self)
        self.resizable(False, False)
        
        main_frame = ttk.Frame(self, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        if updates:
            ttk.Label(
                main_frame,
                text="The following mods have updates available:",
                font=("Segoe UI", 10)
            ).pack(pady=(0, 10))
        else:
            ttk.Label(
                main_frame,
                text="No updates available",
                font=("Segoe UI", 10)
            ).pack(pady=(0, 10))
        
        # Create a frame for the updates list
        updates_frame = ttk.Frame(main_frame)
        updates_frame.pack(fill=tk.BOTH, expand=True)
        
        # Add each mod update
        for mod_name, mod_info in updates.items():
            mod_frame = ttk.Frame(updates_frame)
            mod_frame.pack(fill=tk.X, pady=2)
            
            info_text = f"{mod_name} (v{mod_info['current']} → v{mod_info['new']})"
            ttk.Label(mod_frame, text=info_text).pack(side=tk.LEFT)
            
            ttk.Button(
                mod_frame,
                text="Update",
                command=lambda url=mod_info['url']: self.open_mod_page(url)
            ).pack(side=tk.RIGHT)
        
        # Close button at the bottom
        ttk.Button(
            main_frame,
            text="Close",
            command=self.destroy
        ).pack(pady=(10, 0))
        
        # Center the window
        self.transient(parent)
        self.grab_set()
        
        self.update_idletasks()
        rx, ry = parent.winfo_rootx(), parent.winfo_rooty()
        rw, rh = parent.winfo_width(), parent.winfo_height()
        ww, wh = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{rx + (rw-ww)//2}+{ry + (rh-wh)//2}")
    
    def open_mod_page(self, url):
        webbrowser.open(url)

class CrossPatchMain:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.cfg  = cfg
        set_dark_mode(root)
        mid = ttk.Frame(root, padding=8)
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
        self.context_menu = tk.Menu(self.root, tearoff=0)
        dark_bg, mid_bg = "#1e1e1e", "#2d2d2d" # These AI names make no sense wtf is dark and mid bg sob emoji
        fg, sel_bg     = "#ffffff", "#505050"
        self.context_menu = tk.Menu(
            self.root,
            tearoff=0,
            background=mid_bg,
            foreground=fg,
            activebackground=sel_bg,
            activeforeground=fg,
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
        btn_frame = ttk.Frame(root, padding=8)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Refresh Mods",
                   command=self.refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Open Game",
                   command=launch_game).pack(side=tk.LEFT, padx=5)
        settings_btn = ttk.Button(
            btn_frame, text="⚙", width=3,
            command=self.open_settings
        )
        settings_btn.pack(side=tk.RIGHT, padx=5)
        
        
        ttk.Button(btn_frame, text="Check for Updates",
                  command=self.check_all_mod_updates).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(root, text=f"CrossPatch {APP_VERSION}",
                  font=("Segoe UI", 8)).pack(pady=(0,8))

    def refresh(self):
        
        clean_mods_folder(self.cfg)
        
        for mod in list_mod_folders(self.cfg["mods_folder"]):
            if self.cfg["enabled_mods"].get(mod, False):
                enable_mod(mod, self.cfg)
        
        # Refresh the display
        self.tree.delete(*self.tree.get_children())
        for mod in list_mod_folders(self.cfg["mods_folder"]):
            info    = read_mod_info(os.path.join(self.cfg["mods_folder"], mod))
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
        for mod in list_mod_folders(self.cfg["mods_folder"]):
            info = read_mod_info(os.path.join(self.cfg["mods_folder"], mod))
            if info.get("name", mod) == display_name:
                if self.cfg["enabled_mods"].get(mod, False):
                    disable_mod(mod, self.cfg)
                else:
                    enable_mod(mod, self.cfg)
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
        for mod in list_mod_folders(self.cfg["mods_folder"]):
            info = read_mod_info(os.path.join(self.cfg["mods_folder"], mod))
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
        
        for mod in list_mod_folders(self.cfg["mods_folder"]):
            mod_info = read_mod_info(os.path.join(self.cfg["mods_folder"], mod))
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
                
                if is_newer_version(mod_version, gb_version):
                    updates[mod_name] = {
                        'current': mod_version,
                        'new': gb_version,
                        'url': mod_page
                    }
                    print(f"Update found for {mod_name}: {mod_version} -> {gb_version}")
                
            except Exception as e:
                print(f"Error checking {mod_name}: {str(e)}")
                continue
        
        UpdateListWindow(self.root, updates)
    
    def check_mod_updates(self):
        print("Checking for mod updates...")
        sel = self.tree.selection()
        if not sel:
            return
        
        tree_id = sel[0]
        display_name = self.tree.item(tree_id, "values")[1]
        
        mod_folder = None
        mod_info = None
        for mod in list_mod_folders(self.cfg["mods_folder"]):
            info = read_mod_info(os.path.join(self.cfg["mods_folder"], mod))
            if info.get("name", mod) == display_name:
                mod_folder = mod
                mod_info = info
                break
                
        if not mod_folder or not mod_info:
            print(f"Could not find mod info for {display_name}")
            return
            
        mod_page = mod_info.get("mod_page")
        if not mod_page or not mod_page.startswith("https://gamebanana.com"): # no porn links please
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
            print(f"Response content: {response.text[:200]}...")  
            
            response.raise_for_status()
            
            try:
                item_data = response.json()
                print(f"Parsed JSON data: {item_data}")
    
                gb_version = item_data.get("_sVersion")
                if not gb_version:
                    messagebox.showwarning("Update Check", "No updates found")
                    return
                    
                print(f"Found version: {gb_version}")
            except ValueError as e:
                print(f"Failed to parse JSON response. Full response:\n{response.text}")
                raise Exception(f"Failed to parse Gamebanana API response: {str(e)}")
            local_version = mod_info.get("version", "1.0")
            
            if is_newer_version(local_version, gb_version):
                self.show_mod_update_prompt(mod_page, display_name, local_version, gb_version)
            else:
                messagebox.showinfo("Update Check", f"{display_name} is up to date (v{local_version})")
                
        except Exception as e:
            messagebox.showerror("Update Check Error", f"Failed to check for updates: {str(e)}")
            
    def show_mod_update_prompt(self, mod_page, mod_name, current_version, new_version):
        prompt = tk.Toplevel(self.root)
        set_dark_mode(prompt)
        prompt.title("Update Available")
        prompt.resizable(False, False)
        
        ttk.Label(
            prompt,
            text=f"A new version of {mod_name} is available!\n\n"
                 f"Current version: v{current_version}\n"
                 f"New version: v{new_version}"
        ).pack(padx=12, pady=(12, 6))
        
        btn_frame = ttk.Frame(prompt)
        btn_frame.pack(padx=12, pady=(0, 12))
        
        def on_update():
            webbrowser.open(mod_page)
            prompt.destroy()
            
        def on_ignore():
            prompt.destroy()
            
        ttk.Button(btn_frame, text="Update", command=on_update)\
            .pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Ignore", command=on_ignore)\
            .pack(side=tk.LEFT)
            
        prompt.attributes("-topmost", True)
        
        prompt.update_idletasks()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_w = self.root.winfo_width()
        root_h = self.root.winfo_height()
        
        win_w = prompt.winfo_width()
        win_h = prompt.winfo_height()
        
        pos_x = root_x + (root_w - win_w) // 2
        pos_y = root_y + (root_h - win_h) // 2
        
        prompt.geometry(f"+{pos_x}+{pos_y}")

    def edit_selected_mod_info(self):
        print("Editing mod info.json")
        sel = self.tree.selection()
        if not sel:
            return
        tree_id = sel[0]
        display_name = self.tree.item(tree_id, "values")[1]

        folder_name = None
        for m in list_mod_folders(self.cfg["mods_folder"]):
            info = read_mod_info(os.path.join(self.cfg["mods_folder"], m))
            if info.get("name", m) == display_name:
                folder_name = m
                break
        if folder_name is None:
            return

        mod_folder = os.path.join(self.cfg["mods_folder"], folder_name)
        info_path  = os.path.join(mod_folder, "info.json")
        data = read_mod_info(mod_folder)

        win = tk.Toplevel(self.root)
        set_dark_mode(win)
        win.title(f"Edit {display_name} info.json")
        win.transient(self.root)
        win.grab_set()

        win.update_idletasks()
        rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        ww, wh = win.winfo_width(), win.winfo_height()
        win.geometry(f"+{rx + (rw-ww)//2}+{ry + (rh-wh)//2}")

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        name_var    = tk.StringVar(value=data.get("name", display_name))
        version_var = tk.StringVar(value=data.get("version", "1.0"))
        author_var  = tk.StringVar(value=data.get("author", "Unknown"))

        ttk.Label(frm, text="Name: ").grid(row=0, column=0, sticky="e", pady=4)
        ttk.Entry(frm, textvariable=name_var, width=40)\
           .grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(frm, text="Version: ").grid(row=1, column=0, sticky="e", pady=4)
        ttk.Entry(frm, textvariable=version_var, width=40)\
           .grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(frm, text="Author: ").grid(row=2, column=0, sticky="e", pady=4)
        ttk.Entry(frm, textvariable=author_var, width=40)\
           .grid(row=2, column=1, sticky="w", pady=4)

        btnf = ttk.Frame(frm)
        btnf.grid(row=3, column=0, columnspan=2, pady=(12,0))

        def on_save(folder=folder_name, item_id=tree_id):
            new_data = {
                "name":    name_var.get().strip(),
                "version": version_var.get().strip(),
                "author":  author_var.get().strip()
            }
            try:
                with open(os.path.join(self.cfg["mods_folder"], folder, "info.json"), "w", encoding="utf-8") as f:
                    json.dump(new_data, f, indent=2)
            except Exception as e:
                messagebox.showerror(f"{e}")
                return

            enabled = self.cfg["enabled_mods"].get(folder, False) # insane bandaid fix
            check = "☑" if enabled else "☐"
            self.tree.item(item_id, values=(check,
                new_data["name"], new_data["version"], new_data["author"])
            )
            win.destroy()

        def on_cancel():
            win.destroy()

        ttk.Button(btnf, text="Save",   command=on_save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btnf, text="Cancel", command=on_cancel).pack(side=tk.LEFT)


    def open_settings(self):
        win = tk.Toplevel(self.root)
        set_dark_mode(win)
        win.title("Settings")
        win.geometry("500x120")
        win.resizable(False, False)

        win.transient(self.root)
        win.grab_set()

        win.update_idletasks()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_w = self.root.winfo_width()
        root_h = self.root.winfo_height()
        win_w  = win.winfo_width()
        win_h  = win.winfo_height()
        pos_x  = root_x + (root_w - win_w) // 2
        pos_y  = root_y + (root_h - win_h) // 2
        win.geometry(f"+{pos_x}+{pos_y}")

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        self.show_logs_var = tk.BooleanVar(
            value=self.cfg.get("show_cmd_logs", False)
        )
        chk = ttk.Checkbutton(
            frame,
            text="Show console logs",
            variable=self.show_logs_var,
            command=self.on_toggle_logs
        )
        chk.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,8))

        ttk.Label(frame, text="Game Directory:").grid(row=1, column=0, sticky="w")
        self.game_root_var = tk.StringVar(value=self.cfg["game_root"])
        entry = ttk.Entry(frame, textvariable=self.game_root_var, width=50, state="readonly")
        entry.grid(row=1, column=1, sticky="we", padx=(5,0))
        pick_btn = ttk.Button(frame, text="...", width=3, command=self.on_change_game_root)
        pick_btn.grid(row=1, column=2, sticky="e", padx=(5,0))
        frame.columnconfigure(1, weight=1)
        ttk.Button(frame, text="Credits", command=lambda: self.open_credits(win))\
        .grid(row=2, column=0, columnspan=3, pady=(12,0))


        print("Opened Settings")

    def open_credits(self, settings_win=None):
        if settings_win:
            settings_win.destroy()

        win = tk.Toplevel(self.root)
        set_dark_mode(win)
        win.title("Credits")
        win.geometry("400x240")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        win.update_idletasks()
        rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        ww, wh = win.winfo_width(), win.winfo_height()
        win.geometry(f"+{rx + (rw-ww)//2}+{ry + (rh-wh)//2}")

        frame = ttk.Frame(win, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="NockCS", font=("Segoe UI", 20, "bold"))\
            .pack(anchor="center", pady=(0,4))
        ttk.Label(frame, text="Lead Developer/Programmer", font=("Segoe UI", 10))\
            .pack(anchor="center", pady=(0,12))

        ttk.Label(frame, text="AntiApple4life", font=("Segoe UI", 16, "bold"))\
            .pack(anchor="center", pady=(0,4))
        ttk.Label(frame, text="Linux Support Programmer", font=("Segoe UI", 10))\
            .pack(anchor="center", pady=(0,12))

        ttk.Button(frame, text="Close", command=win.destroy)\
            .pack(pady=(20,0))

        

    # Something is going wrong here
    def on_toggle_logs(self):
        enabled = self.show_logs_var.get()
        self.cfg["show_cmd_logs"] = enabled
        save_config(self.cfg)
        if enabled:
            show_console()
        else:
            hide_console() 

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
        save_config(self.cfg)
        global GAME_ROOT, GAME_EXE
        GAME_ROOT  = new_root
        GAME_EXE   = os.path.join(GAME_ROOT, "SonicRacingCrossWorlds.exe")
        print("Updated root folder")

def main():
    root = tk.Tk()
    if platform.system() == "Windows":
        root.iconbitmap("CrossP.ico")
    root.geometry("580x700")
    root.resizable(False, False)
    if cfg.get("show_cmd_logs"):
        show_console()
    else:
        hide_console()
    CrossPatchMain(root)
    threading.Thread(target=lambda: check_for_updates(root), daemon=True).start()
    root.mainloop()

if __name__ == "__main__":
    main()
