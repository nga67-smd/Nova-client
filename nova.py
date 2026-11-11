#!/usr/bin/env python3
"""Run Nova Launcher:  python nova.py   (Windows: double-click Nova.bat, or use Nova.exe)"""
import sys


def fail(message: str) -> None:
    """Show a startup problem instead of letting a double-clicked window vanish."""
    print("\n" + message + "\n")
    try:
        if sys.stdin is not None and sys.stdin.isatty():
            input("Press Enter to close this window...")
        elif sys.platform.startswith("win"):
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "Nova Launcher", 0x10)
    except Exception:
        pass
    sys.exit(1)


if sys.version_info < (3, 10):
    fail(f"Nova needs Python 3.10 or newer, but this is Python {sys.version_info[0]}.{sys.version_info[1]}.\n"
         "Install a newer Python from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'),\n"
         "or skip Python and use Nova.exe from the Releases page.")

if __name__ == "__main__":
    try:
        from nova.app import main
    except ImportError as e:
        fail(f"Nova's files are incomplete ({e}).\n"
             "Extract the whole zip to a folder first (don't run it from inside the zip), then try again.")
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        import traceback
        fail("Nova hit an error and has to close:\n\n" + traceback.format_exc())
