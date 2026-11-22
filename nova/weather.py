"""Weather over your screen while you play: rain, snow or a thunderstorm in three strengths.

Nova can't draw inside Roblox, so this is a see-through window laid over the screen. It ignores the mouse, never takes focus and
(by default) only shows while you are in a game, not on the Roblox app's home page. It runs as its own small process, so closing Nova ends it.
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
        z = r.random() ** 0.8                                    # 0 = far away, 1 = right in front of you
        y = r.uniform(0, self.h) if start else r.uniform(-60, 0)
        if self.snow:
            return {"x": r.uniform(0, self.w), "y": y, "z": z, "r": 1.1 + z * 5.2, "a": r.uniform(0, math.pi / 3),
                    "vy": 35 + z * 120, "vx": 0.0, "ph": r.uniform(0, 6.3), "sw": 10 + z * 34}
        heavy = {"low": 0.85, "mild": 1.0, "heavy": 1.2}[self.level]
        vy = (650 + z * 950) * heavy
        return {"x": r.uniform(-120, self.w + 120), "y": y, "z": z, "len": (12 + z * 46) * heavy, "vy": vy, "vx": -(110 + z * 110) * heavy,
                "wide": 2 if z > 0.62 else 1}

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


def shade(z: float, far: tuple[int, int, int], near: tuple[int, int, int]) -> str:
    """Far things are dim and bluish, near things bright: a color between the two by depth."""
    z = max(0.0, min(1.0, z))
    return "#%02x%02x%02x" % tuple(round(a + (b - a) * z) for a, b in zip(far, near))


def snowflake_lines(x: float, y: float, r: float, a: float) -> list[tuple[float, float, float, float]]:
    """Three lines crossing in the middle: a six-armed snowflake."""
    out = []
    for k in range(3):
        t = a + k * math.pi / 3
        dx, dy = math.cos(t) * r, math.sin(t) * r
        out.append((x - dx, y - dy, x + dx, y + dy))
    return out


# ---- is the person in a game, or only on the Roblox app's home page? (the home page is started with --app)
JOIN_MARK = "Joining game"
LEAVE_MARKS = ("Client:Disconnect", "Time to disconnect replication data", "Game ended", "Leaving game")


def is_ingame(cmdline: str, log_tail: str) -> bool:
    """cmdline: how the front Roblox window's program was started ('' if unknown). log_tail: the end of Roblox's newest log."""
    cmd = (cmdline or "").lower()
    if cmd and "--app" not in cmd:
        return True                                              # started by a game link: it is a game
    joined, left = log_tail.rfind(JOIN_MARK), max(log_tail.rfind(m) for m in LEAVE_MARKS)
    if not cmd and joined < 0:
        return True                                              # can't tell: better to show than to hide
    return joined > left


# ------------------------------------------------------------------ the see-through window (Windows)

def available() -> bool:
    try:
        import tkinter  # noqa: F401
        return True
    except Exception:
        return False


def _foreground_roblox_pid() -> int:
    """The process id of the front window when it is a Roblox window, else 0."""
    if os.name != "nt":
        return 0
    import ctypes
    u = ctypes.windll.user32
    h = u.GetForegroundWindow()
    buf = ctypes.create_unicode_buffer(256)
    u.GetWindowTextW(h, buf, 256)
    if buf.value != "Roblox":
        return 0
    pid = ctypes.c_ulong(0)
    u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    return pid.value


_CMD_CACHE: dict[int, str] = {}


def _cmdline(pid: int) -> str:
    if pid not in _CMD_CACHE:
        out = ""
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                  f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                                 capture_output=True, text=True, timeout=8, creationflags=0x08000000).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        _CMD_CACHE[pid] = out
    return _CMD_CACHE[pid]


def _log_tail() -> str:
    base = os.environ.get("LOCALAPPDATA")
    try:
        logs = sorted((Path(base) / "Roblox" / "logs").glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True) if base else []
        if not logs:
            return ""
        with open(logs[0], "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 300_000))
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


def _in_game_now() -> bool:
    pid = _foreground_roblox_pid()
    if not pid:
        return False
    cmd = _cmdline(pid)
    return is_ingame(cmd, _log_tail() if (not cmd or "--app" in cmd.lower()) else "")


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
    items = []                                                   # per particle: a function that moves its drawing
    for p in sky.parts:
        if sky.snow:
            col = shade(p["z"], (150, 168, 200), (255, 255, 255))
            if p["r"] < 2.3:                                         # far away: a tiny dim speck
                it = cv.create_rectangle(0, 0, 1, 1, fill=col, outline="")
                items.append(lambda p, it=it: cv.coords(it, p["x"], p["y"], p["x"] + max(1, p["r"]), p["y"] + max(1, p["r"])))
                continue
            halo = cv.create_oval(0, 0, 1, 1, fill="#cfe2ff", outline="", stipple="gray25") if p["r"] > 4.6 else None   # a soft glow: out of focus
            arms = [cv.create_line(0, 0, 1, 1, fill=col, width=2 if p["r"] > 4.6 else 1) for _ in range(3)]

            def move_flake(p, halo=halo, arms=arms):
                if halo:
                    cv.coords(halo, p["x"] - p["r"] * 1.5, p["y"] - p["r"] * 1.5, p["x"] + p["r"] * 1.5, p["y"] + p["r"] * 1.5)
                for ln, c in zip(arms, snowflake_lines(p["x"], p["y"], p["r"], p["a"] + sky.t * 0.4 * (1 if p["ph"] > 3.1 else -1))):
                    cv.coords(ln, *c)
            items.append(move_flake)
        else:
            col = shade(p["z"], (84, 104, 150), (214, 228, 255))
            it = cv.create_line(0, 0, 1, 1, fill=col, width=p["wide"])
            items.append(lambda p, it=it: cv.coords(it, p["x"], p["y"], p["x"] + p["vx"] / p["vy"] * p["len"], p["y"] + p["len"]))
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
            want = (not only_roblox) or _in_game_now()
            if want != state["shown"]:
                state["shown"] = want
                root.deiconify() if want else root.withdraw()
                if want:
                    root.attributes("-topmost", True)
                    click_through()
        if state["shown"]:
            sky.step(dt)
            for move, p in zip(items, sky.parts):
                move(p)
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
