import os
import sys
import json
import shutil
import subprocess
import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

CONFIG_FILE = "mod_manager_config.json"
APP_TITLE   = "CrossPatch - A Crossworlds Mod Manager"
APP_VERSION = "1.0.3"

def show_console():
    try:
        if ctypes.windll.kernel32.AllocConsole():
            sys.stdout = open("CONOUT$", "w")
            sys.stderr = open("CONOUT$", "w")
    except Exception:
        pass

def hide_console():
    try:
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass

def create_appid_file():
    try:
        os.makedirs(GAME_ROOT, exist_ok=True)
        with open(APPID_FILE, "w") as f:
            f.write("480")
        messagebox.showinfo(
            "Success",
            "Game successfully patched! Enjoy the demo for another month"
        )
    except Exception as e:
        messagebox.showerror("Error", f"Could not patch game:\n{e}")

def launch_game():
    if not os.path.exists(GAME_EXE):
        messagebox.showerror(
            "Error",
            "You don't have Crossworlds installed... Did you accidentally delete it?"
        )
        return
    subprocess.Popen([GAME_EXE], cwd=GAME_ROOT)

def default_mods_folder():
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    path = os.path.join(app_dir, "Mods")
    os.makedirs(path, exist_ok=True)
    return path

def load_config():
    default_root = r"C:\Program Files (x86)\Steam\steamapps\common\SonicRacingCrossWorldsONT"
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

cfg        = load_config()
GAME_ROOT  = cfg["game_root"]
APPID_FILE = os.path.join(GAME_ROOT, "steam_appid.txt")
GAME_EXE   = os.path.join(GAME_ROOT, "SonicRacingCrossWorldsONT.exe")

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

def enable_mod(mod_name, cfg):
    src = os.path.join(cfg["mods_folder"], mod_name)
    dst = cfg["game_mods_folder"]
    os.makedirs(dst, exist_ok=True)
    for root, _, files in os.walk(src):
        for f in files:
            if f.lower() == "info.json":
                continue
            shutil.copy2(os.path.join(root, f), os.path.join(dst, f))
    cfg["enabled_mods"][mod_name] = True
    save_config(cfg)

def disable_mod(mod_name, cfg):
    dst = cfg["game_mods_folder"]
    if not os.path.isdir(dst):
        return
    src = os.path.join(cfg["mods_folder"], mod_name)
    to_remove = {
        f for _, _, files in os.walk(src)
        for f in files if f.lower() != "info.json"
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

# Crosspatch shit starts here
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

        self.refresh()

        btn_frame = ttk.Frame(root, padding=8)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Refresh Mods",
                   command=self.refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Open Game",
                   command=launch_game).pack(side=tk.LEFT, padx=5)

        settings_btn = ttk.Button(
            btn_frame, text="\u2699", width=3,
            command=self.open_settings
        )
        settings_btn.pack(side=tk.RIGHT, padx=5)

        ttk.Label(root, text=f"CrossPatch {APP_VERSION}",
                  font=("Segoe UI", 8)).pack(pady=(0,8))

    def refresh(self):
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

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("500x120")
        win.resizable(False, False)

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
        
        global GAME_ROOT, APPID_FILE, GAME_EXE
        GAME_ROOT  = new_root
        APPID_FILE = os.path.join(GAME_ROOT, "steam_appid.txt")
        GAME_EXE   = os.path.join(GAME_ROOT, "SonicRacingCrossWorldsONT.exe")

def main():
    root = tk.Tk()
    root.geometry("580x700")
    root.resizable(False, False)

    if cfg.get("show_cmd_logs"):
        show_console()
    else:
        hide_console()

    CrossPatchMain(root)
    root.mainloop()

if __name__ == "__main__":
    main()
