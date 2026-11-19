"""Nova Launcher - an optimization-focused, customizable Minecraft launcher (and, as NovaRoblox, a Roblox one)."""
import os

__version__ = "1.0.0"
IS_ROBLOX = os.environ.get("NOVA_APP") == "roblox"        # set by novarbx.py; the same code serves both apps
APP_NAME = "Nova Roblox" if IS_ROBLOX else "Nova Launcher"
