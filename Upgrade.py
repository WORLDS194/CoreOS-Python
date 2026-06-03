# Upgrade.py
# CoreOS Bulletproof GUI Upgrade + Auto-Update Versioning

import os
import time

# ---------------------------------------------------------
# VERSION OF THIS UPDATE
# ---------------------------------------------------------
VERSION = "1.0.0"   # <--- bump this when you release a new update

print(f"[Upgrade] Starting CoreOS GUI upgrade v{VERSION}...")

# ---------------------------------------------------------
# VERSION CHECK
# ---------------------------------------------------------
version_file = "CoreOS/System/Upgrade/version.txt"
os.makedirs("CoreOS/System/Upgrade", exist_ok=True)

installed_version = None
if os.path.exists(version_file):
    with open(version_file, "r", encoding="utf-8") as f:
        installed_version = f.read().strip()

if installed_version == VERSION:
    print(f"[Upgrade] Version {VERSION} already installed. Skipping update.")
    raise SystemExit

print(f"[Upgrade] Installing update v{VERSION} (previous: {installed_version})")

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def safe_write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def file_read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def file_write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)

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

safe_write("CoreOS/System/GUI/CoreGUI.py", coregui_code)
print("[Upgrade] Installed CoreGUI.py")

# ---------------------------------------------------------
# 2. Install GUIRunner.py
# ---------------------------------------------------------
guirunner_code = r'''
class GUIRunner:
    def __init__(self, coregui):
        self.gui = coregui

    def run(self, appfile):
        print("[GUIRunner] GUI app launching not implemented yet.")
'''

safe_write("CoreOS/System/GUI/GUIRunner.py", guirunner_code)
print("[Upgrade] Installed GUIRunner.py")

# ---------------------------------------------------------
# 3. Patch CoreOS.py to add start_gui()
# ---------------------------------------------------------
coreos_path = "CoreOS/System/CoreOS.py"

if os.path.exists(coreos_path):
    code = file_read(coreos_path)

    if "def start_gui(" not in code:
        print("[Upgrade] Adding start_gui() to CoreOS.py...")

        idx = code.find("class CoreOS")
        if idx != -1:
            line_end = code.find("\n", idx)
            insert_pos = line_end + 1

            method = r'''
    def start_gui(self):
        from System.GUI.CoreGUI import CoreGUI
        self.gui = CoreGUI(self)
        self.gui.start()
'''

            code = code[:insert_pos] + method + code[insert_pos:]
            file_write(coreos_path, code)
            print("[Upgrade] start_gui() added.")
        else:
            print("[Upgrade] ERROR: class CoreOS not found.")
    else:
        print("[Upgrade] CoreOS.py already has start_gui()")
else:
    print("[Upgrade] ERROR: CoreOS.py missing")

# ---------------------------------------------------------
# 4. Patch boot.py to launch GUI
# ---------------------------------------------------------
boot_path = "boot.py"

if os.path.exists(boot_path):
    bcode = file_read(boot_path)

    if "osys.start_gui()" not in bcode:
        print("[Upgrade] Patching boot.py to launch GUI...")

        marker = "if osys.login():"
        idx = bcode.find(marker)

        if idx != -1:
            line_end = bcode.find("\n", idx)
            insert_pos = line_end + 1

            gui_line = "        osys.start_gui()\n"
            bcode = bcode[:insert_pos] + gui_line + bcode[insert_pos:]
            file_write(boot_path, bcode)
            print("[Upgrade] boot.py patched.")
        else:
            print("[Upgrade] WARNING: Could not find login block in boot.py")
    else:
        print("[Upgrade] boot.py already launches GUI")
else:
    print("[Upgrade] ERROR: boot.py missing")

# ---------------------------------------------------------
# 5. Write installed version
# ---------------------------------------------------------
with open(version_file, "w", encoding="utf-8") as f:
    f.write(VERSION)

print(f"[Upgrade] Installed version set to {VERSION}")
print("[Upgrade] CoreOS GUI upgrade complete.")
