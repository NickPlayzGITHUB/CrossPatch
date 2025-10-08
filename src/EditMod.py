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

        original_mod_type = data.get("mod_type", "pak")
        name_var    = tk.StringVar(value=data.get("name", display_name))
        version_var = tk.StringVar(value=data.get("version", "1.0"))
        author_var  = tk.StringVar(value=data.get("author", "Unknown"))
        mod_type_var = tk.StringVar(value=data.get("mod_type", "pak"))
        mod_page_var = tk.StringVar(value=data.get("mod_page", ""))

        ttk.Label(frm, text="Name: ").grid(row=0, column=0, sticky="e", pady=4)
        ttk.Entry(frm, textvariable=name_var, width=40)\
           .grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Version: ").grid(row=1, column=0, sticky="e", pady=4)
        ttk.Entry(frm, textvariable=version_var, width=40)\
           .grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Author: ").grid(row=2, column=0, sticky="e", pady=4)
        ttk.Entry(frm, textvariable=author_var, width=40)\
           .grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Mod Type: ").grid(row=3, column=0, sticky="e", pady=4)
        mod_type_combo = ttk.Combobox(frm, textvariable=mod_type_var, values=["pak", "ue4ss-script", "ue4ss-logic"], state="readonly", width=38)
        mod_type_combo.grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(frm, text="Mod Page: ").grid(row=4, column=0, sticky="e", pady=4)
        ttk.Entry(frm, textvariable=mod_page_var, width=40)\
            .grid(row=4, column=1, sticky="w", pady=4)

        btnf = ttk.Frame(frm)
        btnf.grid(row=5, column=0, columnspan=2, pady=(12,0))

        def on_save(folder=folder_name, item_id=tree_id):
            new_data = {
                "name":    name_var.get().strip(),
                "version": version_var.get().strip(),
                "author":  author_var.get().strip(),
                "mod_type": mod_type_var.get(),
                "mod_page": mod_page_var.get().strip()
            }
            # Clean up empty fields
            if not new_data["mod_page"]:
                del new_data["mod_page"]

            try:
                with open(os.path.join(Config.config["mods_folder"], folder, "info.json"), "w", encoding="utf-8") as f:
                    json.dump(new_data, f, indent=2)
            except Exception as e:
                messagebox.showerror(f"{e}")
                return
            
            is_enabled = Config.config["enabled_mods"].get(folder, False)
            new_mod_type = new_data["mod_type"]

            # If the mod type changed for an enabled mod, a full refresh is needed
            # to move it to the correct directory.
            if is_enabled and new_mod_type != original_mod_type:
                # Explicitly remove the mod from its old location before refreshing
                Util.remove_mod_from_game_folders(folder, Config.config)
                parent.refresh()
            else: # Otherwise, just update the row in the UI
                check = "☑" if is_enabled else "☐"
                parent.tree.item(item_id, values=(
                    check, new_data["name"], new_data["version"], new_data["author"], new_mod_type.upper()))
            self.destroy()

        def on_cancel():
            self.destroy()

        ttk.Button(btnf, text="Save",   command=on_save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btnf, text="Cancel", command=on_cancel).pack(side=tk.LEFT)

        Util.center_window(self)
        self.deiconify()
        self.transient(parent)
        self.grab_set()