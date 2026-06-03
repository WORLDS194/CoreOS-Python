# Upgrade.py
# CoreOS GUI Desktop Upgrade
# Installs CoreGUI, GUIRunner, and patches boot + CoreOS to enable GUI default mode

import os
import time

print("[Upgrade] Starting CoreOS GUI upgrade...")

BASE = "CoreOS/System/GUI"
os.makedirs(BASE, exist_ok=True)

# ---------------------------------------------------------
# 1. Install CoreGUI.py
# ---------------------------------------------------------
coregui_code = r'''
import tkinter as tk

class CoreGUI:
    def __init__(self, coreos):
        self.coreos = coreos
        self.root = tk.Tk()
        self.root.title("CoreOS Desktop")
        self.root.geometry("900x600")
        self.root.configure(bg="#202020")
        self.root.config(cursor="none")

        self.canvas = tk.Canvas(self.root, bg="#202020", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.cursor_radius = 6
        self.cursor = self.canvas.create_oval(
            0, 0, self.cursor_radius*2, self.cursor_radius*2,
            outline="black", width=2, fill="white"
        )

        self.root.bind("<Motion>", self._on_mouse_move)
        self._build_desktop()

    def _on_mouse_move(self, event):
        x, y = event.x, event.y
        r = self.cursor_radius
        self.canvas.coords(self.cursor, x-r, y-r, x+r, y+r)

    def _build_desktop(self):
        self.canvas.create_text(
            20, 20,
            anchor="nw",
            text="CoreOS Python Desktop",
            fill="white",
            font=("Consolas", 20, "bold")
        )

        self._button(20, 80, 160, 50, "Open Terminal", self._open_cli)
        self._button(20, 150, 160, 50, "Update System", self._update_os)
        self._button(20, 220, 160, 50, "Shutdown", self._shutdown)

    def _button(self, x, y, w, h, label, callback):
        rect = self.canvas.create_rectangle(
            x, y, x+w, y+h,
            outline="#ffffff", width=1, fill="#303030"
        )
        text = self.canvas.create_text(
            x+w/2, y+h/2,
            text=label,
            fill="white",
            font=("Consolas", 12)
        )

        def click(event, cb=callback):
            cb()

        self.canvas.tag_bind(rect, "<Button-1>", click)
        self.canvas.tag_bind(text, "<Button-1>", click)

    def _open_cli(self):
        self.root.withdraw()
        self.coreos.run_shell()
        self.root.deiconify()

    def _update_os(self):
        self.root.withdraw()
        self.coreos.enter_update_mode()
        if self.coreos.running:
            self.root.deiconify()
        else:
            self.root.destroy()

    def _shutdown(self):
        self.coreos.running = False
        self.root.destroy()

    def start(self):
        self.root.mainloop()
'''

with open(f"{BASE}/CoreGUI.py", "w", encoding="utf-8") as f:
    f.write(coregui_code)

print("[Upgrade] Installed CoreGUI.py")

# ---------------------------------------------------------
# 2. Install GUIRunner.py (future GUI apps)
# ---------------------------------------------------------
guirunner_code = r'''
class GUIRunner:
    def __init__(self, coregui):
        self.gui = coregui

    def run(self, appfile):
        print("[GUIRunner] GUI app launching not implemented yet.")
'''

with open(f"{BASE}/GUIRunner.py", "w", encoding="utf-8") as f:
    f.write(guirunner_code)

print("[Upgrade] Installed GUIRunner.py")

# ---------------------------------------------------------
# 3. Patch CoreOS.py to enable GUI default mode
# ---------------------------------------------------------
coreos_path = "CoreOS/System/CoreOS.py"

if os.path.exists(coreos_path):
    with open(coreos_path, "r", encoding="utf-8") as f:
        coreos_code = f.read()

    if "start_gui" not in coreos_code:
        coreos_code = coreos_code.replace(
            "if osys.login():",
            "if osys.login():\n        osys.start_gui()"
        )

        with open(coreos_path, "w", encoding="utf-8") as f:
            f.write(coreos_code)

        print("[Upgrade] Patched CoreOS.py to enable GUI default mode")
    else:
        print("[Upgrade] CoreOS.py already GUI-enabled")
else:
    print("[Upgrade] CoreOS.py missing, cannot patch")

# ---------------------------------------------------------
# 4. Patch boot.py to call GUI automatically
# ---------------------------------------------------------
boot_path = "boot.py"

if os.path.exists(boot_path):
    with open(boot_path, "r", encoding="utf-8") as f:
        boot_code = f.read()

    if "start_gui" not in boot_code:
        boot_code = boot_code.replace(
            "if osys.login():",
            "if osys.login():\n        osys.start_gui()"
        )

        with open(boot_path, "w", encoding="utf-8") as f:
            f.write(boot_code)

        print("[Upgrade] Patched boot.py to launch GUI")
    else:
        print("[Upgrade] boot.py already GUI-enabled")
else:
    print("[Upgrade] boot.py missing, cannot patch")

print("[Upgrade] CoreOS GUI upgrade complete.")
