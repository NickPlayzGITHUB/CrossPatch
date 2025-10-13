import tkinter as tk

class Tooltip:
    """
    Creates a tooltip for a given widget that appears on hover.
    """
    def __init__(self, widget, text, style):
        self.widget = widget
        self.text = text
        self.style = style
        self.tooltip_window = None
        self.id = None
        self.x = self.y = 0
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip) # 500ms delay

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        # Create the tooltip window but keep it off-screen initially to calculate its size
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+9999+9999") # Position it off-screen

        # Create the label with the tooltip text
        label = tk.Label(tw, text=self.text, justify='left', relief='solid', borderwidth=1, background="#222222", foreground="white", padx=5, pady=3)
        label.pack(ipadx=1)

        # Force the window to update and calculate its size
        tw.update_idletasks()

        # Get the required size of the tooltip
        tip_width = tw.winfo_reqwidth()
        tip_height = tw.winfo_reqheight()

        # Calculate the position to be centered above the widget
        widget_x = self.widget.winfo_rootx()
        widget_y = self.widget.winfo_rooty()
        widget_width = self.widget.winfo_width()
        x = widget_x + (widget_width // 2) - (tip_width // 2)
        y = widget_y - tip_height - 5 # Position it above the widget with a 5px margin

        tw.wm_geometry(f"+{x}+{y}")

    def hidetip(self):
        tw = self.tooltip_window
        self.tooltip_window = None
        if tw:
            tw.destroy()