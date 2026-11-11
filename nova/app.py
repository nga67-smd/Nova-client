"""Entry point: start the local server and open the launcher window."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from . import __version__, paths
from .server import App, start_server


def find_app_browser() -> str | None:
    """Locate a Chromium-based browser, which can open a chromeless 'app' window."""
    s = paths.os_name()
    names = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge",
             "microsoft-edge-stable", "brave-browser", "vivaldi"]
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    cands: list[str] = []
    if s == "windows":
        roots = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        rels = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
                r"BraveSoftware\Brave-Browser\Application\brave.exe", r"Chromium\Application\chrome.exe",
                r"Vivaldi\Application\vivaldi.exe"]
        cands = [str(Path(r) / rel) for r in roots if r for rel in rels]
    elif s == "osx":
        cands = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                 "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                 "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    for c in cands:
        if Path(c).exists():
            return c
    return None


def open_window(url: str) -> subprocess.Popen | None:
    browser = os.environ.get("NOVA_BROWSER") or find_app_browser()
    if browser:
        profile = paths.sub("webview")
        args = [browser, f"--app={url}", f"--user-data-dir={profile}", "--window-size=1320,860",
                "--no-first-run", "--no-default-browser-check", "--disable-features=Translate"]
        try:
            return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
    webbrowser.open(url)
    return None


def hide_child_consoles() -> None:
    """On Windows, stop helper programs (Java, installers) from flashing a console window."""
    if paths.os_name() != "windows":
        return
    orig = subprocess.Popen.__init__

    def init(self, *a, **kw):
        kw["creationflags"] = kw.get("creationflags", 0) | 0x08000000  # CREATE_NO_WINDOW
        orig(self, *a, **kw)

    subprocess.Popen.__init__ = init


def setup_logging() -> Path | None:
    """With no console (the windowed Nova.exe), send messages and crashes to nova.log instead."""
    if sys.stdout is not None and sys.stderr is not None:
        return None
    log = paths.data_dir() / "nova.log"
    try:
        if log.exists() and log.stat().st_size > 1_000_000:
            log.unlink()
        f = open(log, "a", encoding="utf-8", buffering=1)
    except OSError:
        return None
    if sys.stdout is None:
        sys.stdout = f
    if sys.stderr is None:
        sys.stderr = f
    previous = sys.excepthook

    def hook(kind, value, tb):
        previous(kind, value, tb)
        if paths.os_name() == "windows":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, f"Nova hit an error and has to close.\n\n{value}\n\nDetails: {log}",
                                                 "Nova Launcher", 0x10)
            except Exception:
                pass

    sys.excepthook = hook
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nova", description="Nova Launcher - optimized, customizable Minecraft launcher")
    ap.add_argument("--no-window", action="store_true", help="don't open a window; just print the URL")
    ap.add_argument("--keep-alive", action="store_true", help="keep running after the window closes")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--home", help="data folder (default: your user data directory)")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args(argv)
    if args.version:
        print(f"Nova Launcher {__version__}")
        return 0
    if args.home:
        os.environ["NOVA_HOME"] = args.home
    paths.data_dir().mkdir(parents=True, exist_ok=True)
    setup_logging()
    hide_child_consoles()

    app = App()
    start_server(app, args.port)
    url = f"http://127.0.0.1:{app.port}/?t={app.token}"
    print(f"Nova Launcher {__version__} running at {url}")
    print(f"Data folder: {paths.data_dir()}")
    if not args.no_window:
        open_window(url)
    keep = args.keep_alive or args.no_window
    try:
        while True:
            time.sleep(1.0)
            if keep:
                continue
            idle = time.time() - app.last_ping
            if app.seen_ping and idle > 25 and not any(app.games.running(g) for g in list(app.games.games)):
                print("Window closed - shutting down.")
                break
            if not app.seen_ping and idle > 120:
                print("No window connected - shutting down.")
                break
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
