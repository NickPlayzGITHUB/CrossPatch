import tkinter as tk
from tkinter import ttk, filedialog
import os
import platform

import Util
from Credits import CreditsWindow
import Config

class SettingsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent
        self.config = Config.config

        self.withdraw()
        
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        self.show_logs_var = tk.BooleanVar(
            value=self.config.get("show_cmd_logs", False)
        )
        chk = ttk.Checkbutton(
            frame,
            text="Show console logs",
            variable=self.show_logs_var,
            command=self.on_toggle_logs
        )
        if platform.system() == "Windows":
            chk.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,8))

        ttk.Label(frame, text="Game Directory:").grid(row=1, column=0, sticky="w")
        self.game_root_var = tk.StringVar(value=self.config["game_root"])
        entry = ttk.Entry(frame, textvariable=self.game_root_var, width=50, state="readonly")
        entry.grid(row=1, column=1, sticky="we", padx=(5,0))
        pick_btn = ttk.Button(frame, text="...", width=3, command=self.on_change_game_root)
        pick_btn.grid(row=1, column=2, sticky="e", padx=(5,0))

        ttk.Label(frame, text="Mods Folder:").grid(row=2, column=0, sticky="w", pady=(8,0))
        self.mods_folder_var = tk.StringVar(value=self.config["mods_folder"])
        mods_entry = ttk.Entry(frame, textvariable=self.mods_folder_var, width=50, state="readonly")
        mods_entry.grid(row=2, column=1, sticky="we", padx=(5,0), pady=(8,0))
        mods_pick_btn = ttk.Button(frame, text="...", width=3, command=self.on_change_mods_folder)
        mods_pick_btn.grid(row=2, column=2, sticky="e", padx=(5,0), pady=(8,0))
        frame.columnconfigure(1, weight=1)

        # Button frame at the bottom
        btn_frame = ttk.Frame(frame)
        # Align the frame to the left of its grid cell
        btn_frame.grid(row=3, column=0, columnspan=3, pady=(12,0), sticky="w")
        
        # Pack buttons vertically (default side=TOP) and align them left (anchor=w)
        ttk.Button(btn_frame, text="Check for Mod Updates", command=self.on_check_mod_updates).pack(anchor="w")
        ttk.Button(btn_frame, text="Credits", command=lambda: self.open_credits()).pack(anchor="w", pady=(5, 0))

        self.title("Settings")
        if platform.system() == "Windows":
            self.geometry("500x210")
        else:
            self.geometry("500x250")
        self.resizable(False, False)
        self.update_idletasks()
        Util.center_window(self)
        self.deiconify()
        self.transient(parent)
        self.grab_set()


    def on_check_mod_updates(self):
        self.parent.check_all_mod_updates()

    def open_credits(self):
        CreditsWindow(self)

    # Something is going wrong here
    def on_toggle_logs(self):
        enabled = self.show_logs_var.get()
        self.config["show_cmd_logs"] = enabled
        Config.save_config(self.config)
        if enabled:
            Config.show_console()
        else:
            Config.hide_console() 
    
    def on_change_mods_folder(self):
        new_folder = filedialog.askdirectory(
            title="Select a folder to store your mods",
            initialdir=self.config["mods_folder"]
        )
        if not new_folder:
            return
        self.mods_folder_var.set(new_folder)
        self.config["mods_folder"] = new_folder
        Config.save_config(self.config)
        # Trigger a refresh on the main window to reflect the change
        self.parent.refresh()

    def on_change_game_root(self):
        new_root = filedialog.askdirectory(
            title="Select Crossworlds Install Folder",
            initialdir=self.config["game_root"]
        )
        if not new_root:
            return
        self.game_root_var.set(new_root)
        self.config["game_root"] = new_root
        self.config["game_mods_folder"] = os.path.join(new_root, "UNION", "Content", "Paks", "~mods")
        Config.save_config(self.config)
        global GAME_ROOT, GAME_EXE
        GAME_ROOT  = new_root
        GAME_EXE   = os.path.join(GAME_ROOT, "SonicRacingCrossWorlds.exe")
        print("Updated root folder")