import tkinter as tk
from tkinter import ttk

import Util

class CreditsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)

        self.withdraw()

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="NockCS", font=("Segoe UI", 20, "bold"))\
            .pack(anchor="center", pady=(0,4))
        ttk.Label(frame, text="Lead Developer/Programmer", font=("Segoe UI", 10))\
            .pack(anchor="center", pady=(0,12))
        
        ttk.Label(frame, text="RED1", font=("Segoe UI", 16, "bold"))\
            .pack(anchor="center", pady=(0,4))
        ttk.Label(frame, text="Secondary Main Programmer", font=("Segoe UI", 10))\
            .pack(anchor="center", pady=(0,12))

        ttk.Label(frame, text="AntiApple4life", font=("Segoe UI", 16, "bold"))\
            .pack(anchor="center", pady=(0,4))
        ttk.Label(frame, text="Linux Support Programmer", font=("Segoe UI", 10))\
            .pack(anchor="center", pady=(0,12))
        
        ttk.Label(frame, text="Ben Thalmann", font=("Segoe UI", 16, "bold"))\
            .pack(anchor="center", pady=(0,4))
        ttk.Label(frame, text="Cleaned Up Codebase", font=("Segoe UI", 10))\
            .pack(anchor="center", pady=(0,12))
        

        ttk.Button(frame, text="Close", command=self.destroy)\
            .pack(pady=(20,0))
        
        self.title("Credits")
        self.resizable(False, False)
        self.update_idletasks()
        Util.center_window(self)
        self.deiconify()
        self.transient(parent)
        self.grab_set()
        