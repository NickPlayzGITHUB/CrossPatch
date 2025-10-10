import tkinter as tk
from tkinter import ttk
import threading
import platform
import ctypes
import requests
from io import BytesIO

import Util

# --- Optional Pillow dependency for image handling ---
try:
    from PIL import Image, ImageTk
    PILLOW_SUPPORT = True
except ImportError:
    PILLOW_SUPPORT = False

# --- Windows-specific structures for flashing the window ---
if platform.system() == "Windows":
    class FLASHWINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("hwnd", ctypes.c_void_p),
            ("dwFlags", ctypes.c_uint),
            ("uCount", ctypes.c_uint),
            ("dwTimeout", ctypes.c_uint)
        ]

class OneClickInstallDialog(tk.Toplevel):
    def __init__(self, parent, item_data):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()

        self.item_data = item_data
        mod_name = self.item_data.get('_sName', 'Unknown Mod')

        self.title("Confirm Download")
        # self.geometry("400x320") # Removed fixed size to allow auto-sizing
        self.resizable(False, False)
        self.confirmed = False

        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Image ---
        # Create a frame to reserve space for the image, preventing the window from being too small initially.
        image_placeholder = ttk.Frame(main_frame, width=360, height=180)
        image_placeholder.pack(pady=(0, 15))
        image_placeholder.pack_propagate(False) # Prevent frame from shrinking
        self.image_label = ttk.Label(image_placeholder, text="Loading image..." if PILLOW_SUPPORT else "Pillow not installed.")
        self.image_label.pack(fill=tk.BOTH, expand=True)
        if PILLOW_SUPPORT:
            threading.Thread(target=self._load_image, daemon=True).start()

        # --- Mod Name ---
        name_label = ttk.Label(main_frame, text=mod_name, font=("Segoe UI", 12, "bold"), wraplength=370, justify=tk.CENTER)
        name_label.pack(pady=(0, 5))

        # --- Confirmation Text ---
        confirm_text = ttk.Label(main_frame, text="Do you want to download this mod?", justify=tk.CENTER)
        confirm_text.pack()

        # --- Bottom Buttons ---
        btn_frame = ttk.Frame(self, padding=(15, 10))
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        yes_btn = ttk.Button(btn_frame, text="Yes", command=self.on_confirm, style="Accent.TButton")
        yes_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        no_btn = ttk.Button(btn_frame, text="No", command=self.on_cancel)
        no_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        # --- Finalize Window ---
        Util.center_window(self)
        self.focus_force() # Force focus on the dialog

        # On Windows, flash the taskbar icon to alert the user
        if platform.system() == "Windows":
            try:
                hwnd = self.winfo_id()
                info = FLASHWINFO()
                info.cbSize = ctypes.sizeof(info)
                info.hwnd = hwnd
                info.dwFlags = 3 | 12  # FLASHW_ALL | FLASHW_TIMERNOFG
                info.uCount = 0 # Flash indefinitely
                info.dwTimeout = 0
                ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
            except Exception as e:
                print(f"Could not flash window: {e}")

        self.wait_window(self)

    def _load_image(self):
        """Downloads and displays the mod's preview image in a separate thread."""
        try:
            preview_media = self.item_data.get('_aPreviewMedia', {})
            images = preview_media.get('_aImages', [])
            if not images:
                self.after(0, lambda: self.image_label.config(text="No preview image."))
                return

            base_url = images[0].get('_sBaseUrl')
            file_url = images[0].get('_sFile')
            if not base_url or not file_url:
                self.after(0, lambda: self.image_label.config(text="Invalid image URL."))
                return

            image_url = f"{base_url}/{file_url}"
            
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            img = Image.open(BytesIO(response.content))
            
            # Resize image to fit a max height/width (e.g., 180px)
            img.thumbnail((360, 180), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            self.after(0, self._update_image_label, photo)

        except Exception as e:
            print(f"Failed to load image for dialog: {e}")
            self.after(0, lambda: self.image_label.config(text="Failed to load image."))

    def _update_image_label(self, photo):
        """Updates the image label and stores a reference to the photo."""
        self.image_label.image = photo # Keep a reference!
        self.image_label.config(image=photo, text="")
        # After setting the image, re-center the window to correct any minor position shifts.
        self.update_idletasks()
        Util.center_window(self)

    def on_confirm(self):
        self.confirmed = True
        self.destroy()

    def on_cancel(self):
        self.confirmed = False
        self.destroy()

    def was_confirmed(self):
        return self.confirmed