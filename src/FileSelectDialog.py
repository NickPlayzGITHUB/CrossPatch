import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import threading
import requests
from io import BytesIO
from html.parser import HTMLParser

import Util

# --- Optional Pillow dependency for image handling ---
try:
    from PIL import Image, ImageTk
    PILLOW_SUPPORT = True
except ImportError:
    PILLOW_SUPPORT = False

class HTMLTextParser(HTMLParser):
    """A simple HTML parser to apply formatting to a tkinter Text widget."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.active_tags = []
        # Configure tags for formatting
        self.text_widget.tag_configure("bold", font=("Segoe UI", 9, "bold"))
        self.text_widget.tag_configure("italic", font=("Segoe UI", 9, "italic"))
        self.text_widget.tag_configure("GreenColor", foreground="#2dc82d")
        self.text_widget.tag_configure("RedColor", foreground="#ff4141")
        self.text_widget.tag_configure("BlueColor", foreground="#4189ff")

    def handle_starttag(self, tag, attrs):
        if tag in ('b', 'strong'):
            self.active_tags.append("bold")
        elif tag in ('i', 'em'):
            self.active_tags.append("italic")
        elif tag == 'span':
            attrs_dict = dict(attrs)
            if 'class' in attrs_dict and attrs_dict['class'] in ('GreenColor', 'RedColor', 'BlueColor'):
                self.active_tags.append(attrs_dict['class'])
        elif tag == 'br':
            self.text_widget.insert(tk.END, '\n')

    def handle_endtag(self, tag):
        self.active_tags.pop() if self.active_tags else None

    def handle_data(self, data):
        self.text_widget.insert(tk.END, data, tuple(self.active_tags))

class FileSelectDialog(tk.Toplevel):
    def __init__(self, parent, item_data):
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()

        self.item_data = item_data
        self.mod_name = self.item_data.get('_sName', 'Unknown Mod')
        # Sort files by date added, newest first
        self.files_data = sorted(
            self.item_data.get('_aFiles', []),
            key=lambda f: f.get('_tsDateAdded', 0),
            reverse=True
        )

        self.title(f"Download Options for '{self.mod_name}'")
        self.geometry("1100x600")
        self.result = None

        # --- Main Paned Window Layout ---
        paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Left Pane (Info) ---
        left_pane = ttk.Frame(paned_window, width=350)
        left_pane.pack(fill=tk.BOTH, expand=True)
        paned_window.add(left_pane, weight=1)

        # Image
        self.image_label = ttk.Label(left_pane, text="Loading image..." if PILLOW_SUPPORT else "Pillow not installed.")
        self.image_label.pack(pady=(0, 10))
        if PILLOW_SUPPORT:
            threading.Thread(target=self._load_image, daemon=True).start()

        # Description
        desc_label = ttk.Label(left_pane, text="Description", font=("Segoe UI", 10, "bold"))
        desc_label.pack(anchor=tk.W, pady=(5, 2))
        description = self.item_data.get('_sDescription', 'No description available.')
        desc_text = ttk.Label(left_pane, text=description, wraplength=330, justify=tk.LEFT)
        desc_text.pack(fill=tk.X, anchor=tk.W)

        # Body/Readme
        body_label = ttk.Label(left_pane, text="Readme", font=("Segoe UI", 10, "bold"))
        body_label.pack(anchor=tk.W, pady=(10, 2))
        
        body_frame = ttk.Frame(left_pane)
        body_frame.pack(fill=tk.BOTH, expand=True)
        
        body_text_widget = tk.Text(body_frame, wrap=tk.WORD, height=10, relief="flat", borderwidth=0, highlightthickness=0)
        body_scrollbar = ttk.Scrollbar(body_frame, orient=tk.VERTICAL, command=body_text_widget.yview)
        body_text_widget.configure(yscrollcommand=body_scrollbar.set)
        
        body_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        body_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Use the HTML parser to insert content
        body_content = self.item_data.get('_sText', 'No readme content available.')
        body_text_widget.config(state=tk.NORMAL) # Must be normal to insert
        parser = HTMLTextParser(body_text_widget)
        parser.feed(body_content)
        body_text_widget.config(state=tk.DISABLED) # Make it read-only

        # --- Right Pane (Downloads) ---
        right_pane = ttk.Frame(paned_window, width=550)
        right_pane.pack(fill=tk.BOTH, expand=True)
        paned_window.add(right_pane, weight=2)

        # File List Treeview
        cols = ("file", "version", "size", "date", "desc")
        self.tree = ttk.Treeview(right_pane, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("file", text="File Name")
        self.tree.heading("version", text="Version")
        self.tree.heading("size", text="Size")
        self.tree.heading("date", text="Date Added")
        self.tree.heading("desc", text="Description")

        self.tree.column("file", width=220, anchor=tk.W)
        self.tree.column("version", width=80, anchor=tk.CENTER)
        self.tree.column("size", width=80, anchor=tk.E)
        self.tree.column("date", width=120, anchor=tk.CENTER)
        self.tree.column("desc", width=250, anchor=tk.W)

        for i, file_info in enumerate(self.files_data):
            file_name = file_info.get('_sFile', 'N/A')
            file_version = file_info.get('_sVersion', '') # GameBanana API includes this field
            file_size_bytes = file_info.get('_nFilesize', 0)
            file_size_mb = f"{file_size_bytes / (1024*1024):.2f} MB" if file_size_bytes > 0 else "N/A"
            timestamp = file_info.get('_tsDateAdded', 0)
            date_added = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M') if timestamp > 0 else "N/A"
            description = file_info.get('_sDescription', '')
            self.tree.insert("", tk.END, iid=i, values=(file_name, file_version, file_size_mb, date_added, description))

        tree_scrollbar = ttk.Scrollbar(right_pane, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)
        
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_download)

        # Select the first (usually latest/main) file by default
        if self.files_data:
            self.tree.selection_set(self.tree.get_children()[0])

        # --- Bottom Buttons ---
        btn_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=(5,0))
        ttk.Button(btn_frame, text="Download Selected", command=self.on_download).pack(side=tk.RIGHT)

        # --- Finalize Window ---
        Util.center_window(self)
        self.wait_window(self)

    def _load_image(self):
        """Downloads and displays the mod's preview image in a separate thread."""
        try:
            preview_media = self.item_data.get('_aPreviewMedia', {})
            images = preview_media.get('_aImages', [])
            if not images:
                self.image_label.config(text="No preview image.")
                return

            # Construct the image URL
            base_url = images[0].get('_sBaseUrl')
            file_url = images[0].get('_sFile')
            if not base_url or not file_url:
                self.image_label.config(text="Invalid image URL.")
                return

            image_url = f"{base_url}/{file_url}"
            
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            img_data = response.content
            img = Image.open(BytesIO(img_data))
            
            # Resize image to fit within a 340x200 box while maintaining aspect ratio
            img.thumbnail((340, 200), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            # Update the UI from the main thread
            self.after(0, self._update_image_label, photo)

        except Exception as e:
            print(f"Failed to load image: {e}")
            self.after(0, lambda: self.image_label.config(text="Failed to load image."))

    def _update_image_label(self, photo):
        """Updates the image label and stores a reference to the photo."""
        self.image_label.image = photo # Keep a reference!
        self.image_label.config(image=photo, text="")

    def on_download(self, event=None):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a file to download.", parent=self)
            return

        # The IID of the tree item is its index in the sorted self.files_data list
        selected_index = int(selected_item[0])
        self.result = self.files_data[selected_index]
        self.destroy()

    def get_selection(self):
        return self.result