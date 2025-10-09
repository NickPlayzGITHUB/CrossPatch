import tkinter as tk
from tkinter import ttk
import webbrowser

class UpdateListWindow(tk.Toplevel):
    def __init__(self, parent, updates):
        super().__init__(parent)
        self.title("Available Updates")
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
        self.geometry(f"+{rx + (rw - ww) // 2}+{ry + (rh - wh) // 2}")

    def open_mod_page(self, url):
        webbrowser.open(url)