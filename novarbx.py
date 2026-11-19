#!/usr/bin/env python3
"""Run Nova Roblox:  python novarbx.py   (Windows: NovaRoblox.exe)"""
import os
import sys

os.environ["NOVA_APP"] = "roblox"          # must be set before the nova package is imported

if sys.version_info < (3, 10):
    sys.exit("Nova Roblox needs Python 3.10 or newer.")

if __name__ == "__main__":
    try:
        from nova.app import main
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        import traceback
        msg = "Nova Roblox hit an error and has to close:\n\n" + traceback.format_exc()
        print(msg)
        if sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, msg, "Nova Roblox", 0x10)
            except Exception:
                pass
        sys.exit(1)
