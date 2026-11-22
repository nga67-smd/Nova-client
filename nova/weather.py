"""Weather over your screen while you play: rain, snow or a thunderstorm in three strengths.

Nova can't draw inside Roblox, so this is a see-through window laid over the screen. It ignores the mouse, never takes focus and
(by default) only shows while the Roblox window is the one in front. It runs as its own small process, so closing Nova ends it.
"""
from __future__ import annotations

import math
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

from .util import NovaError, read_json, write_json

KINDS = {"off": "Off", "rain": "Rain", "snow": "Snow", "thunder": "Thunderstorm"}
LEVELS = {"low": "Low", "mild": "Mild", "heavy": "Heavy"}
DEFAULTS = {"kind": "off", "level": "mild", "only_roblox": True}

# how many drops / flakes for a 1920x1080 screen (scaled to other sizes)
COUNTS = {"rain": {"low": 90, "mild": 260, "heavy": 650}, "snow": {"low": 45, "mild": 130, "heavy": 320},
          "thunder": {"low": 140, "mild": 330, "heavy": 700}}
# seconds between lightning strikes (min, max)
STRIKES = {"low": (15.0, 30.0), "mild": (8.0, 16.0), "heavy": (3.5, 9.0)}


def _file() -> Path:
    from . import roblox
    return roblox.root() / "weather.json"


def settings() -> dict:
    raw = read_json(_file(), {}) or {}
    out = dict(DEFAULTS)
    if raw.get("kind") in KINDS:
        out["kind"] = raw["kind"]
    if raw.get("level") in LEVELS:
        out["level"] = raw["level"]
    out["only_roblox"] = bool(raw.get("only_roblox", True))
    return out


def save(kind: str, level: str, only_roblox: bool) -> dict:
    if kind not in KINDS:
        raise NovaError("Pick rain, snow or a thunderstorm.")
    if level not in LEVELS:
        raise NovaError("Pick low, mild or heavy.")
    write_json(_file(), {"kind": kind, "level": level, "only_roblox": bool(only_roblox)})
    return settings()


# ------------------------------------------------------------------ the weather itself (no window needed)

class Sky:
    """Falling drops or flakes and the lightning timer. Positions are in pixels; call step(seconds) every frame."""

    def __init__(self, kind: str, level: str, width: int, height: int, rng: random.Random | None = None):
        if kind not in COUNTS or level not in LEVELS:
            raise NovaError("Unknown weather.")
        self.kind, self.level, self.w, self.h = kind, level, max(200, width), max(200, height)
        self.rng = rng or random.Random()
        n = max(10, round(COUNTS[kind][level] * (self.w * self.h) / (1920 * 1080)))
        self.parts = [self._new(start=True) for _ in range(n)]
        self.t = 0.0
        self.flash = 0.0                                        # 0..1, how bright the lightning is right now
        self.next_strike = self._gap() if kind == "thunder" else math.inf
        self.strikes = 0

    @property
    def snow(self) -> bool:
        return self.kind == "snow"

    def _gap(self) -> float:
        lo, hi = STRIKES[self.level]
        return self.t + self.rng.uniform(lo, hi)

    def _new(self, start: bool = False) -> dict:
        r = self.rng
        if self.snow:
            p = {"x": r.uniform(0, self.w), "y": r.uniform(0, self.h) if start else r.uniform(-30, 0), "r": r.uniform(1.5, 4.2),
                 "vy": r.uniform(55, 150), "ph": r.uniform(0, 6.3), "sw": r.uniform(12, 40)}
            p["vx"] = 0.0
        else:
            heavy = {"low": 0.8, "mild": 1.0, "heavy": 1.25}[self.level]
            p = {"x": r.uniform(-100, self.w + 100), "y": r.uniform(0, self.h) if start else r.uniform(-60, 0),
                 "len": r.uniform(12, 24) * heavy, "vy": r.uniform(900, 1400) * heavy, "vx": -r.uniform(120, 220) * heavy}
        return p

    def step(self, dt: float) -> None:
        dt = min(max(dt, 0.0), 0.1)
        self.t += dt
        for p in self.parts:
            p["y"] += p["vy"] * dt
            if self.snow:
                p["x"] += math.sin(self.t * 1.3 + p["ph"]) * p["sw"] * dt
            else:
                p["x"] += p["vx"] * dt
            if p["y"] > self.h + 30 or p["x"] < -140 or p["x"] > self.w + 140:
                p.update(self._new())
        if self.kind == "thunder":
            if self.t >= self.next_strike:
                self.flash, self.strikes, self.next_strike = 1.0, self.strikes + 1, self._gap()
            elif self.flash > 0:
                # a quick double flicker, then it fades
                self.flash = max(0.0, self.flash - dt * 2.6)

    def flash_alpha(self) -> float:
        """How bright to flash the screen: 0 for none up to about 0.45."""
        if self.flash <= 0:
            return 0.0
        f = self.flash
        flick = 0.55 + 0.45 * math.sin(f * 22)                  # the flicker
        return round(max(0.0, min(0.45, 0.45 * f * flick)), 3)


# ------------------------------------------------------------------ the see-through window (Windows)

def available() -> bool:
    try:
        import tkinter  # noqa: F401
        return True
    except Exception:
        return False


def _foreground_title() -> str:
    if os.name != "nt":
        return ""
    import ctypes
    u = ctypes.windll.user32
    h = u.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    u.GetWindowTextW(h, buf, 256)
    return buf.value


def run_overlay(kind: str, level: str, only_roblox: bool = True) -> int:
    """Runs until the parent (Nova) goes away. Draws the weather in a click-through, always-on-top window."""
    import tkinter as tk
    sky_cls = Sky
    root = tk.Tk()
    root.title("Nova weather")
    key = "#010203"                                              # this color is see-through
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    root.overrideredirect(True)
    root.geometry(f"{w}x{h}+0+0")
    root.configure(bg=key)
    root.attributes("-topmost", True)
    if os.name == "nt":
        root.attributes("-transparentcolor", key)
    cv = tk.Canvas(root, width=w, height=h, bg=key, highlightthickness=0, bd=0)
    cv.pack(fill="both", expand=True)

    def click_through() -> None:
        if os.name != "nt":
            return
        import ctypes
        u = ctypes.windll.user32
        hwnd = u.GetParent(root.winfo_id()) or root.winfo_id()
        style = u.GetWindowLongW(hwnd, -20)
        u.SetWindowLongW(hwnd, -20, style | 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000)   # layered, click-through, no taskbar button, no focus

    root.update_idletasks()
    click_through()
    sky = sky_cls(kind, level, w, h)
    color = "#ffffff" if sky.snow else "#9db9e8"
    items = []
    for p in sky.parts:
        items.append(cv.create_oval(0, 0, 1, 1, fill=color, outline="") if sky.snow else cv.create_line(0, 0, 1, 1, fill=color, width=1))
    flash_rect = cv.create_rectangle(0, 0, w, h, fill="#ffffff", outline="", stipple="gray12", state="hidden") if kind == "thunder" else None
    state = {"last": time.time(), "shown": True, "check": 0.0, "alive": True}

    def watch_parent() -> None:                                  # Nova keeps our stdin open; when it ends, so do we
        try:
            sys.stdin.read()
        except Exception:
            pass
        state["alive"] = False

    threading.Thread(target=watch_parent, daemon=True).start()

    def tick() -> None:
        if not state["alive"]:
            root.destroy()
            return
        now = time.time()
        dt, state["last"] = now - state["last"], now
        if now - state["check"] > 1.0:
            state["check"] = now
            want = (not only_roblox) or _foreground_title() == "Roblox"
            if want != state["shown"]:
                state["shown"] = want
                root.deiconify() if want else root.withdraw()
                if want:
                    root.attributes("-topmost", True)
                    click_through()
        if state["shown"]:
            sky.step(dt)
            for it, p in zip(items, sky.parts):
                if sky.snow:
                    r = p["r"]
                    cv.coords(it, p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r)
                else:
                    cv.coords(it, p["x"], p["y"], p["x"] + p["vx"] / p["vy"] * p["len"], p["y"] + p["len"])
            if flash_rect:
                a = sky.flash_alpha()
                cv.itemconfigure(flash_rect, state="normal" if a > 0 else "hidden", stipple="gray50" if a > 0.3 else "gray25" if a > 0.12 else "gray12")
        root.after(33, tick)

    root.after(33, tick)
    root.mainloop()
    return 0


def selftest() -> int:
    """For the build: can this program open a window of the kind the weather needs?"""
    try:
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        tk.Canvas(r).create_line(0, 0, 1, 1)
        r.destroy()
        return 0
    except Exception as e:
        print(f"weather window unavailable: {e}")
        return 1


# ------------------------------------------------------------------ started and stopped by the app

class Runner:
    def __init__(self):
        self.proc: subprocess.Popen | None = None

    def command(self, s: dict) -> list[str]:
        base = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(Path(sys.argv[0]).resolve())]
        return base + ["--weather", f"{s['kind']}:{s['level']}:{'1' if s['only_roblox'] else '0'}"]

    def stop(self) -> None:
        p, self.proc = self.proc, None
        if p and p.poll() is None:
            try:
                p.stdin.close()                                  # the overlay exits when this ends (also covers the real program under a launcher stub)
            except (OSError, AttributeError, ValueError):
                pass
            try:
                p.terminate()
                p.wait(3)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def apply(self, s: dict | None = None) -> None:
        """Make the running weather match the settings."""
        s = s or settings()
        self.stop()
        if s["kind"] == "off":
            return
        if not available():
            raise NovaError("This build of Nova can't draw weather.")
        kw = {"creationflags": 0x08000000} if os.name == "nt" else {}
        self.proc = subprocess.Popen(self.command(s), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)

    def running(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)
