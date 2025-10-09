import tkinter as tk
from tkinter import ttk, messagebox
import os
import json

import Util
import Config

class EditModWindow(tk.Toplevel):
    def __init__(self, parent, display_name, data, folder_name, tree_id):
        super().__init__(parent)

        self.withdraw()
        self.title(f"Edit {display_name} info.json")
    
        frm = ttk.Frame(self, padding=12)
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
                with open(os.path.join(Config.config["mods_folder"], folder, "info.json"), "w", encoding="utf-8") as f:
                    json.dump(new_data, f, indent=2)
            except Exception as e:
                messagebox.showerror(f"{e}")
                return

            enabled = Config.config["enabled_mods"].get(folder, False) # insane bandaid fix
            check = "☑" if enabled else "☐"
            parent.tree.item(item_id, values=(check,
                new_data["name"], new_data["version"], new_data["author"])
            )
            self.destroy()

        def on_cancel():
            self.destroy()

        ttk.Button(btnf, text="Save",   command=on_save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btnf, text="Cancel", command=on_cancel).pack(side=tk.LEFT)

        Util.center_window(self)
        self.deiconify()
        self.transient(parent)
        self.grab_set()