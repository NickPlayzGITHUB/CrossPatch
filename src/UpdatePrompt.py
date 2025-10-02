import tkinter as tk
from tkinter import ttk
import webbrowser

import Util

from Constants import GITHUB_REDIRECT

class UpdatePromptWindow(tk.Toplevel):
    def __init__(self, parent, remote_version):
        super().__init__(parent)

        self.title("Update Available")
        self.resizable(False, False)
        print("Update available")

        ttk.Label(
            self,
            text=f"CrossPatch {remote_version} is available."
        ).pack(padx=12, pady=(12, 6))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(padx=12, pady=(0, 12))

        def on_update():
            self.destroy()
            webbrowser.open(GITHUB_REDIRECT)
            print(f"Opening {GITHUB_REDIRECT}")

        def on_ignore():
            self.destroy()
            print("Update declined... why")

        ttk.Button(btn_frame, text="Update", command=on_update) \
            .pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_frame, text="Ignore", command=on_ignore) \
            .pack(side=tk.LEFT)

        self.attributes("-topmost", True)

        Util.center_window(self)