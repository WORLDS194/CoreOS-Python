print("[Upgrade] CoreOS updated successfully!")

from System.CoreOS import CoreOS

def hello(self, args):
    print("Hello from the update!")

old = CoreOS.handle

def new_handle(self, cmd, args):
    if cmd == "hello":
        return hello(self, args)
    return old(self, cmd, args)

CoreOS.handle = new_handle

