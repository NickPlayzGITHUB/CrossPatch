import tkinter as tk
from tkinter import ttk

import Util

class ModUpdatePromptWindow(tk.Toplevel):
    def __init__(self, parent, mod_page, mod_name, current_version, new_version, mod_folder_name):
        super().__init__(parent)
        self.parent = parent
        self.mod_folder_name = mod_folder_name

        self.title("Update Available")
        self.resizable(False, False)
        
        ttk.Label(
            self,
            text=f"A new version of {mod_name} is available!\n\n"
                 f"Current version: v{current_version}\n"
                 f"New version: v{new_version}"
        ).pack(padx=12, pady=(12, 6))
        
        btn_frame = ttk.Frame(self)
        btn_frame.pack(padx=12, pady=(0, 12))
        
        def on_update():
            self.destroy()
            self.parent.update_mod_from_url(mod_page, self.mod_folder_name)
            
        def on_ignore():
            self.destroy()
            
        ttk.Button(btn_frame, text="Update", command=on_update)\
            .pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Ignore", command=on_ignore)\
            .pack(side=tk.LEFT)
            
        self.attributes("-topmost", True)
        
        Util.center_window(self)