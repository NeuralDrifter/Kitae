# Copyright (c) 2026 Michael Burgus (https://github.com/NeuralDrifter)
# Licensed under the MIT License. See LICENSE file for details.

"""Splash screen — shows the Kitae artwork for 1.5s, then launches the main app."""

import os
import tkinter as tk
from PIL import Image, ImageTk


SPLASH_DURATION_MS = 1500
SPLASH_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "splash.png")


def show_splash():
    """Display splash window, then launch the main app after it closes."""
    root = tk.Tk()
    root.overrideredirect(True)  # No title bar / window decorations
    root.configure(bg="#000000")

    # Load and display the splash image
    img = Image.open(SPLASH_FILE)

    # Scale to fit screen nicely (max 900px wide, keep aspect)
    max_w = 900
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)

    tk_img = ImageTk.PhotoImage(img)

    label = tk.Label(root, image=tk_img, bg="#000000", borderwidth=0)
    label.pack()

    # Center on screen
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - img.width) // 2
    y = (sh - img.height) // 2
    root.geometry(f"{img.width}x{img.height}+{x}+{y}")

    # After 1.5s, destroy splash and launch main app
    def _launch():
        root.destroy()
        from gui.app import AgentLoopApp
        app = AgentLoopApp()
        app.mainloop()

    root.after(SPLASH_DURATION_MS, _launch)
    root.mainloop()
