# Upgrade.py
# CoreOS Bulletproof GUI Upgrade
# - Installs /System/GUI/CoreGUI.py and GUIRunner.py
# - Ensures CoreOS has start_gui()
# - Ensures boot.py launches GUI after login
# - Never overwrites boot/CoreOS logic, only patches

import os
import time

print("[Upgrade] Starting CoreOS GUI upgrade (bulletproof)...")

# ---------- Helpers ----------

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

# ---------- 1. Install CoreGUI.py ----------

gui_base = "CoreOS/System/GUI"
os.makedirs(gui_base, exist_ok=True)

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

safe_write(os.path.join(gui_base, "CoreGUI.py"), coregui_code)
print("[Upgrade] Installed CoreGUI.py")

# ---------- 2. Install GUIRunner.py (placeholder) ----------

guirunner_code = r'''
class GUIRunner:
    def __init__(self, coregui):
        self.gui = coregui

    def run(self, appfile):
        print("[GUIRunner] GUI app launching not implemented yet.")
'''

safe_write(os.path.join(gui_base, "GUIRunner.py"), guirunner_code)
print("[Upgrade] Installed GUIRunner.py")

# ---------- 3. Ensure CoreOS has start_gui() ----------

coreos_path = "CoreOS/System/CoreOS.py"
if os.path.exists(coreos_path):
    code = file_read(coreos_path)

    if "def start_gui(" not in code:
        print("[Upgrade] Adding start_gui() to CoreOS class...")

        marker = "class CoreOS"
        idx = code.find(marker)
        if idx == -1:
            print("[Upgrade] ERROR: class CoreOS not found in CoreOS.py")
        else:
            line_end = code.find("\n", idx)
            if line_end == -1:
                line_end = len(code)

            insert_pos = line_end + 1

            start_gui_method = r'''
    def start_gui(self):
        from System.GUI.CoreGUI import CoreGUI
        self.gui = CoreGUI(self)
        self.gui.start()
'''

            new_code = code[:insert_pos] + start_gui_method + code[insert_pos:]
            file_write(coreos_path, new_code)
            print("[Upgrade] start_gui() added to CoreOS.py")
    else:
        print("[Upgrade] CoreOS.py already has start_gui()")
else:
    print("[Upgrade] WARNING: CoreOS.py not found, cannot patch start_gui()")

# ---------- 4. Ensure boot.py launches GUI after login ----------

boot_path = "boot.py"
if os.path.exists(boot_path):
    bcode = file_read(boot_path)

    if "osys.start_gui()" in bcode:
        print("[Upgrade] boot.py already launches GUI")
    else:
        print("[Upgrade] Patching boot.py to launch GUI after login...")

        marker = "if osys.login():"
        idx = bcode.find(marker)
        if idx == -1:
            print("[Upgrade] WARNING: could not find 'if osys.login():' in boot.py")
        else:
            line_end = bcode.find("\n", idx)
            if line_end == -1:
                line_end = len(bcode)
            insert_pos = line_end + 1

            indent = ""
            # detect indentation of the marker line
            line_start = bcode.rfind("\n", 0, idx)
            if line_start == -1:
                line_start = 0
            else:
                line_start += 1
            while line_start < idx and bcode[line_start] in (" ", "\t"):
                indent += bcode[line_start]
                line_start += 1

            gui_line = f"{indent}    osys.start_gui()\n"
            new_bcode = bcode[:insert_pos] + gui_line + bcode[insert_pos:]
            file_write(boot_path, new_bcode)
            print("[Upgrade] boot.py patched to call osys.start_gui()")
else:
    print("[Upgrade] WARNING: boot.py not found, cannot patch GUI launch")

# ---------- 5. Done ----------

with open("CoreOS/System/Logs/update.log", "a", encoding="utf-8") as log:
    log.write(f"[{time.ctime()}] Bulletproof GUI upgrade applied\n")

print("[Upgrade] CoreOS bulletproof GUI upgrade complete.")
