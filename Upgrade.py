# boot.py

import os
import sys
import time

ROOT = "CoreOS"

# ---------------------------------------------------------
# 1. Create directory structure
# ---------------------------------------------------------
def initialize_directories():
    system = os.path.join(ROOT, "System")
    users = os.path.join(ROOT, "Users")
    apps = os.path.join(ROOT, "Apps")

    kernel = os.path.join(system, "Kernel")
    memory = os.path.join(system, "Memory")
    fs = os.path.join(system, "FS")
    runner = os.path.join(system, "Runner")
    logs = os.path.join(system, "Logs")
    upgrade = os.path.join(system, "Upgrade")

    print("[boot] Initializing CoreOS directory structure...")

    for path in [ROOT, system, users, apps, kernel, memory, fs, runner, logs, upgrade]:
        os.makedirs(path, exist_ok=True)

    # Make Python packages
    for path in [ROOT, system, kernel, memory, fs, runner]:
        init_path = os.path.join(path, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w") as f:
                f.write("")

    # Create user folders
    for user in ["admin", "guest"]:
        os.makedirs(os.path.join(users, user), exist_ok=True)

    # Boot log
    boot_log = os.path.join(system, "Logs", "boot.log")
    with open(boot_log, "a", encoding="utf-8") as f:
        f.write(f"[{time.ctime()}] CoreOS booted\n")

    print("[boot] Directory structure ready.")


# ---------------------------------------------------------
# 2. MemoryManager.py (only if missing)
# ---------------------------------------------------------
def write_memory_manager():
    path = os.path.join(ROOT, "System", "Memory", "MemoryManager.py")
    if os.path.exists(path):
        print("[boot] MemoryManager.py exists, not overwriting.")
        return
    code = r'''
class MemoryManager:
    def __init__(self, limit_mb=16):
        self.limit = limit_mb * 1024 * 1024
        self.used = 0

    def allocate(self, amount):
        if amount < 0:
            return False
        if self.used + amount > self.limit:
            return False
        self.used += amount
        return True

    def free(self, amount):
        if amount < 0:
            return
        self.used = max(0, self.used - amount)

    def status(self):
        return self.used, self.limit
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print("[boot] Generated MemoryManager.py")


# ---------------------------------------------------------
# 3. ACFS.py (virtual file system, only if missing)
# ---------------------------------------------------------
def write_acfs():
    path = os.path.join(ROOT, "System", "FS", "ACFS.py")
    if os.path.exists(path):
        print("[boot] ACFS.py exists, not overwriting.")
        return
    code = r'''
from System.Memory.MemoryManager import MemoryManager

class ACFS:
    def __init__(self):
        # node: {type, children, content, size, owner, mode}
        self.fs = {
            "/": {"type": "dir", "children": {}, "size": 0, "owner": "root", "mode": "rwx"}
        }
        self.cwd = "/"
        self.mem = MemoryManager()

    def _join(self, base, name):
        if name.startswith("/"):
            return name
        if base.endswith("/"):
            return base + name
        return base + "/" + name

    def _get(self, path):
        return self.fs.get(path)

    # ---------------- Directories ----------------
    def list_dir(self, path=None, all_flag=False):
        path = path or self.cwd
        node = self._get(path)
        if not node or node["type"] != "dir":
            return []
        names = sorted(node["children"].keys())
        if all_flag:
            return [".", ".."] + names
        return names

    def mkdir(self, name, owner="root"):
        new_path = self._join(self.cwd, name)
        if new_path in self.fs:
            return False

        if not self.mem.allocate(512):
            print("[MemoryError] Out of RAM")
            return False

        self.fs[new_path] = {
            "type": "dir",
            "children": {},
            "size": 512,
            "owner": owner,
            "mode": "rwx"
        }
        self.fs[self.cwd]["children"][name] = new_path
        return True

    def rmdir(self, name):
        path = self._join(self.cwd, name)
        node = self._get(path)
        if not node or node["type"] != "dir":
            return False
        if node["children"]:
            return False

        self.mem.free(node["size"])
        del self.fs[path]
        del self.fs[self.cwd]["children"][name]
        return True

    def cd(self, name):
        if name == "/":
            self.cwd = "/"
            return True
        if name == "..":
            if self.cwd == "/":
                return True
            parent = self.cwd.rsplit("/", 1)[0]
            self.cwd = parent if parent else "/"
            return True

        path = self._join(self.cwd, name)
        node = self._get(path)
        if node and node["type"] == "dir":
            self.cwd = path
            return True
        return False

    def pwd(self):
        return self.cwd

    # ---------------- Files ----------------
    def create_file(self, name, owner="root"):
        path = self._join(self.cwd, name)
        if path in self.fs:
            return True

        if not self.mem.allocate(64):
            print("[MemoryError] Out of RAM")
            return False

        self.fs[path] = {
            "type": "file",
            "content": "",
            "size": 64,
            "owner": owner,
            "mode": "rw"
        }
        self.fs[self.cwd]["children"][name] = path
        return True

    def write_file(self, name, content):
        path = self._join(self.cwd, name)
        node = self._get(path)

        if not node:
            if not self.create_file(name):
                return
            node = self._get(path)

        old = node["size"]
        new = 64 + len(content)
        delta = new - old

        if delta > 0:
            if not self.mem.allocate(delta):
                print("[MemoryError] Out of RAM")
                return
        else:
            self.mem.free(-delta)

        node["content"] = content
        node["size"] = new

    def read_file(self, name):
        path = self._join(self.cwd, name)
        node = self._get(path)
        if not node or node["type"] != "file":
            return None
        return node["content"]

    def delete_file(self, name):
        path = self._join(self.cwd, name)
        node = self._get(path)
        if not node or node["type"] != "file":
            return False

        self.mem.free(node["size"])
        del self.fs[path]
        del self.fs[self.cwd]["children"][name]
        return True

    # ---------------- Permissions ----------------
    def chmod(self, name, mode):
        path = self._join(self.cwd, name)
        node = self._get(path)
        if not node:
            return False
        node["mode"] = mode
        return True

    def chown(self, name, owner):
        path = self._join(self.cwd, name)
        node = self._get(path)
        if not node:
            return False
        node["owner"] = owner
        return True

    # ---------------- Memory ----------------
    def memory_status(self):
        return self.mem.status()
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print("[boot] Generated ACFS.py")


# ---------------------------------------------------------
# 4. CoreKernel.py (only if missing)
# ---------------------------------------------------------
def write_corekernel():
    path = os.path.join(ROOT, "System", "Kernel", "CoreKernel.py")
    if os.path.exists(path):
        print("[boot] CoreKernel.py exists, not overwriting.")
        return
    code = r'''
from System.FS.ACFS import ACFS

class CoreKernel:
    def __init__(self):
        self.fs = ACFS()

    def sys_ls(self, all_flag=False): return self.fs.list_dir(all_flag=all_flag)
    def sys_cd(self, name): return self.fs.cd(name)
    def sys_pwd(self): return self.fs.pwd()
    def sys_mkdir(self, name, owner): return self.fs.mkdir(name, owner=owner)
    def sys_rmdir(self, name): return self.fs.rmdir(name)

    def sys_touch(self, name, owner): return self.fs.create_file(name, owner=owner)
    def sys_write(self, name, content): self.fs.write_file(name, content)
    def sys_read(self, name): return self.fs.read_file(name)
    def sys_rm(self, name): return self.fs.delete_file(name)

    def sys_chmod(self, name, mode): return self.fs.chmod(name, mode)
    def sys_chown(self, name, owner): return self.fs.chown(name, owner)

    def sys_memstat(self): return self.fs.memory_status()
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print("[boot] Generated CoreKernel.py")


# ---------------------------------------------------------
# 5. Runner.py (CoreApps runtime, only if missing)
# ---------------------------------------------------------
def write_runner():
    path = os.path.join(ROOT, "System", "Runner", "Runner.py")
    if os.path.exists(path):
        print("[boot] Runner.py exists, not overwriting.")
        return
    code = r'''
from System.Kernel.CoreKernel import CoreKernel

class Runner:
    def __init__(self):
        self.kernel = CoreKernel()
        self.max_depth = 10
        self.vars = {}

    def run_app(self, path, depth=0):
        if depth > self.max_depth:
            print("[Runner] Max recursion depth reached")
            return

        content = self.kernel.sys_read(path)
        if content is None:
            print(f"[Runner] App not found: {path}")
            return

        lines = content.split("\n")
        pc = 0
        labels = {}

        # first pass: labels
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("LABEL "):
                label = line.split(maxsplit=1)[1]
                labels[label] = i

        while pc < len(lines):
            raw = lines[pc]
            line = raw.strip()
            pc += 1
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            cmd = parts[0].upper()
            args = parts[1:]

            if cmd == "PRINT":
                print(" ".join(args))

            elif cmd == "MEMSTAT":
                used, limit = self.kernel.sys_memstat()
                print(f"Memory: {used}/{limit} bytes")

            elif cmd == "MKDIR":
                self.kernel.sys_mkdir(args[0], owner="app")

            elif cmd == "TOUCH":
                self.kernel.sys_touch(args[0], owner="app")

            elif cmd == "WRITE":
                filename = args[0]
                text = " ".join(args[1:])
                self.kernel.sys_write(filename, text)

            elif cmd == "RUN":
                self.run_app(args[0], depth + 1)

            elif cmd == "SET":
                if len(args) >= 2:
                    name = args[0]
                    value = " ".join(args[1:])
                    self.vars[name] = value

            elif cmd == "IF":
                # IF var == value GOTO label
                if len(args) >= 5 and args[1] == "==" and args[3].upper() == "GOTO":
                    var = args[0]
                    value = args[2]
                    label = args[4]
                    if self.vars.get(var) == value and label in labels:
                        pc = labels[label]

            elif cmd == "GOTO":
                label = args[0]
                if label in labels:
                    pc = labels[label]

            elif cmd == "EXIT":
                return

            else:
                print(f"[Runner] Unknown instruction: {cmd}")
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print("[boot] Generated Runner.py")


# ---------------------------------------------------------
# 6. CoreOS.py (shell + update mode, only if missing)
# ---------------------------------------------------------
def write_coreos():
    path = os.path.join(ROOT, "System", "CoreOS.py")
    if os.path.exists(path):
        print("[boot] CoreOS.py exists, not overwriting.")
        return
    code = r'''
import getpass
import urllib.request
import traceback
import time
import os

from System.Kernel.CoreKernel import CoreKernel
from System.Runner.Runner import Runner

class CoreOS:
    CDN_URL = "https://raw.githubusercontent.com/WORLDS194/CoreOS-Python/refs/heads/main/Upgrade.py"

    def __init__(self):
        self.kernel = CoreKernel()
        self.runner = Runner()
        self.users = {"admin": "admin", "guest": "guest"}
        self.current_user = None
        self.running = True
        self.history = []
        self.env = {}
        self.aliases = {}
        self.next_pid = 1
        self.processes = {}  # pid -> {"cmd": str, "status": str}

    # ------------- Login -------------
    def login(self):
        print("=== CoreOS Login ===")
        for _ in range(3):
            user = input("Username: ").strip()
            pw = getpass.getpass("Password: ")
            if self.users.get(user) == pw:
                self.current_user = user
                print(f"Welcome, {user}!")
                return True
            print("Invalid login.\n")
        return False

    # ------------- Shell loop -------------
    def run_shell(self):
        print("Type 'help' for commands.\n")
        while self.running:
            cmdline = input(f"{self.current_user}@CoreOS {self.kernel.sys_pwd()}> ").strip()
            if not cmdline:
                continue

            # history recall: !n
            if cmdline.startswith("!"):
                try:
                    idx = int(cmdline[1:])
                    cmdline = self.history[idx]
                    print(cmdline)
                except:
                    print("Invalid history index")
                    continue

            self.history.append(cmdline)

            parts = cmdline.split()
            cmd = parts[0]
            args = parts[1:]

            # aliases
            if cmd in self.aliases:
                aliased = self.aliases[cmd] + " " + " ".join(args)
                parts = aliased.split()
                cmd = parts[0]
                args = parts[1:]

            self.handle(cmd, args)

    # ------------- Process management -------------
    def spawn_process(self, cmdline):
        pid = self.next_pid
        self.next_pid += 1
        self.processes[pid] = {"cmd": cmdline, "status": "running"}
        # no real concurrency; mark as exited immediately
        self.processes[pid]["status"] = "exited"
        return pid

    # ------------- Update mode -------------
    def enter_update_mode(self):
        print("\n" * 50)
        print("========================================")
        print("      Updating CoreOS Python...")
        print("      Please wait. Do not turn off.")
        print("========================================")
        self.perform_update()

    def perform_update(self):
        url = self.CDN_URL
        upgrade_path = "CoreOS/System/Upgrade/Upgrade.py"

        # Do not overwrite existing Upgrade.py
        if not os.path.exists(upgrade_path):
            try:
                data = urllib.request.urlopen(url).read().decode("utf-8")
                with open(upgrade_path, "w", encoding="utf-8") as f:
                    f.write(data)
                print("[update] Upgrade.py downloaded from CDN.")
            except Exception as e:
                print("[update] Failed to download Upgrade.py")
                print(e)
                return
        else:
            print("[update] Using existing Upgrade.py (not overwriting).")

        print("[update] Running Upgrade.py...")

        try:
            with open(upgrade_path, "r", encoding="utf-8") as f:
                code = f.read()
            exec(code, {"__name__": "__coreos_upgrade__"})
            print("[update] Update applied successfully.")
        except Exception:
            print("[update] Error applying update:")
            print(traceback.format_exc())

        with open("CoreOS/System/Logs/update.log", "a", encoding="utf-8") as log:
            log.write(f"[{time.ctime()}] Update applied\n")

        print("========================================")
        print("      Update Complete. Rebooting...")
        print("========================================")
        time.sleep(2)
        self.reboot_system()

    def reboot_system(self):
        print("Rebooting CoreOS...")
        self.history = []
        self.kernel = CoreKernel()
        self.processes = {}
        self.next_pid = 1
        # after reboot, go back to shell
        self.run_shell()

    # ------------- Command handler -------------
    def handle(self, cmd, args):
        if cmd == "help":
            self.cmd_help()

        elif cmd == "ls":
            all_flag = "-a" in args
            for f in self.kernel.sys_ls(all_flag=all_flag):
                print(f)

        elif cmd == "cd":
            if args:
                if not self.kernel.sys_cd(args[0]):
                    print("Directory not found")

        elif cmd == "pwd":
            print(self.kernel.sys_pwd())

        elif cmd == "mkdir":
            if args:
                self.kernel.sys_mkdir(args[0], owner=self.current_user)

        elif cmd == "rmdir":
            if args:
                if not self.kernel.sys_rmdir(args[0]):
                    print("Directory not empty or missing")

        elif cmd == "touch":
            if args:
                self.kernel.sys_touch(args[0], owner=self.current_user)

        elif cmd == "cat":
            if args:
                content = self.kernel.sys_read(args[0])
                print(content if content else "(empty or missing)")

        elif cmd == "echo":
            if ">" in args:
                idx = args.index(">")
                text = " ".join(args[:idx])
                if idx + 1 >= len(args):
                    print("usage: echo TEXT > file")
                    return
                filename = args[idx + 1]
                self.kernel.sys_write(filename, text)
            else:
                print(" ".join(args))

        elif cmd == "rm":
            recursive = "-r" in args
            targets = [a for a in args if not a.startswith("-")]
            if not targets:
                print("usage: rm [-r] <name>")
                return
            name = targets[0]
            if recursive:
                if not self.kernel.sys_rm(name):
                    if not self.kernel.sys_rmdir(name):
                        print("rm -r failed")
            else:
                if not self.kernel.sys_rm(name):
                    print("rm failed")

        elif cmd == "chmod":
            if len(args) == 2:
                if not self.kernel.sys_chmod(args[1], args[0]):
                    print("chmod failed")

        elif cmd == "chown":
            if len(args) == 2:
                if not self.kernel.sys_chown(args[1], args[0]):
                    print("chown failed")

        elif cmd == "run":
            if args:
                background = False
                if args[-1] == "&":
                    background = True
                    args = args[:-1]
                app_path = "/Apps/" + args[0]
                if background:
                    pid = self.spawn_process("run " + args[0] + " &")
                    print(f"[started background job pid={pid}]")
                else:
                    self.runner.run_app(app_path)

        elif cmd == "ps":
            for pid, info in self.processes.items():
                print(pid, info["status"], info["cmd"])

        elif cmd == "kill":
            if args:
                try:
                    pid = int(args[0])
                    if pid in self.processes:
                        self.processes[pid]["status"] = "killed"
                        print(f"killed {pid}")
                    else:
                        print("no such pid")
                except:
                    print("invalid pid")

        elif cmd == "history":
            for i, h in enumerate(self.history):
                print(i, h)

        elif cmd == "whoami":
            print(self.current_user)

        elif cmd == "clear":
            print("\\n" * 50)

        elif cmd == "mem":
            used, limit = self.kernel.sys_memstat()
            print(f"Memory: {used}/{limit} bytes")

        elif cmd == "set":
            if len(args) >= 1:
                if "=" in args[0]:
                    name, value = args[0].split("=", 1)
                    self.env[name] = value
                elif len(args) >= 2:
                    name = args[0]
                    value = " ".join(args[1:])
                    self.env[name] = value

        elif cmd == "unset":
            if args and args[0] in self.env:
                del self.env[args[0]]

        elif cmd == "env":
            for k, v in self.env.items():
                print(f"{k}={v}")

        elif cmd == "alias":
            if not args:
                for k, v in self.aliases.items():
                    print(f"alias {k}='{v}'")
            else:
                if "=" in args[0]:
                    name, rest = args[0].split("=", 1)
                    self.aliases[name] = rest
                elif len(args) >= 2:
                    name = args[0]
                    self.aliases[name] = " ".join(args[1:])

        elif cmd == "unalias":
            if args and args[0] in self.aliases:
                del self.aliases[args[0]]

        elif cmd == "update":
            # leave shell and enter dedicated update mode
            self.running = False
            self.enter_update_mode()

        elif cmd == "shutdown":
            print("System shutting down.")
            self.running = False

        elif cmd == "reboot":
            print("Rebooting...")
            self.running = False
            self.reboot_system()

        else:
            print("Unknown command.")

    def cmd_help(self):
        print("Commands:")
        print("  ls [-a]")
        print("  cd <dir>")
        print("  pwd")
        print("  mkdir <dir>")
        print("  rmdir <dir>")
        print("  touch <file>")
        print("  cat <file>")
        print("  echo TEXT > file")
        print("  rm [-r] <name>")
        print("  chmod <mode> <name>")
        print("  chown <owner> <name>")
        print("  run <app>.alc [&]")
        print("  ps")
        print("  kill <pid>")
        print("  history  /  !n")
        print("  whoami")
        print("  clear")
        print("  mem")
        print("  set NAME=VALUE | set NAME VALUE")
        print("  unset NAME")
        print("  env")
        print("  alias [name=cmd]")
        print("  unalias <name>")
        print("  update")
        print("  shutdown")
        print("  reboot")
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print("[boot] Generated CoreOS.py")


# ---------------------------------------------------------
# 7. Boot sequence
# ---------------------------------------------------------
def main():
    initialize_directories()
    write_memory_manager()
    write_acfs()
    write_corekernel()
    write_runner()
    write_coreos()

    print("[boot] CoreOS source generated.")
    print("[boot] Launching OS...")

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from System.CoreOS import CoreOS
    osys = CoreOS()
    if osys.login():
        osys.run_shell()


if __name__ == "__main__":
    main()
