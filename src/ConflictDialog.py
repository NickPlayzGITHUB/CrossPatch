import tkinter as tk
from tkinter import ttk
import Util

class ConflictDialog(tk.Toplevel):
    def __init__(self, parent, conflicts):
        """
        A dialog window to display mod file conflicts in a clear, sortable table.

        Args:
            parent: The parent tkinter window.
            conflicts (dict): A dictionary where keys are conflicting file paths
                              and values are lists of mod folder names.
        """
        super().__init__(parent)
        self.transient(parent)
        self.title("Mod Conflicts Detected")
        self.parent = parent
        self.conflicts = conflicts
        self.geometry("1100x600")

        # --- Widgets ---
        info_frame = ttk.Frame(self, padding=(10, 10, 10, 0))
        info_frame.pack(fill=tk.X)
        ttk.Label(info_frame, text="The following files are present in multiple enabled mods.", font="-weight bold").pack(anchor="w")
        ttk.Label(info_frame, text="The mod with the highest priority (top of the list) will take precedence.").pack(anchor="w", pady=(0, 5))

        # Use a PanedWindow to allow column resizing
        paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned_window.pack(expand=True, fill=tk.BOTH, padx=10, pady=(5, 10))

        # --- Treeview Setup ---
        tree_container = ttk.Frame(paned_window) # A container for the tree and scrollbar
        self.tree = ttk.Treeview(tree_container, columns=("file", "mods"), show="headings")
        self.tree.heading("file", text="Conflicting File")
        self.tree.heading("mods", text="Provided by Mods")

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        # Add the tree container to the paned window. The 'weight' makes it take up space.
        paned_window.add(tree_container, weight=1)


        # --- Populate Data ---
        for file, mods in sorted(conflicts.items()):
            self.tree.insert("", tk.END, values=(file, ", ".join(mods)))

        # --- Finalize Window ---
        # Force the window to draw and bring it to the front before making it modal.
        self.update_idletasks()
        self.lift()
        self.grab_set()
        Util.center_window(self)

        # Schedule a resize after 1 second to ensure the window size is enforced.
        self.after(1000, self._force_resize)

    def _force_resize(self):
        """Forces the window to the desired size and re-centers it after a delay."""
        try:
            if self.winfo_exists(): # Check if window hasn't been closed
                self.geometry("900x400")
                Util.center_window(self) # Re-center after resizing
        except tk.TclError:
            pass # Window was likely destroyed before this ran.