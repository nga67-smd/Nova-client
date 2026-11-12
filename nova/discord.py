"""Discord Rich Presence through Discord's local IPC (standard library only).

Shows "Playing Nova Launcher" with the instance, Minecraft version and loader while a game runs,
and "In the launcher" otherwise. Needs a Discord application (its name is what Discord shows after
"Playing"); put its Application ID in config.BUILTIN_DISCORD_CLIENT_ID. Without one, this stays idle.
"""
from __future__ import annotations

import json
import os
import socket
import struct
import sys
import threading
import time
import uuid

from . import config, instances

OP_HANDSHAKE, OP_FRAME, OP_CLOSE, OP_PING, OP_PONG = 0, 1, 2, 3, 4
REPO_URL = "https://github.com/nga67-smd/Nova-client"
MIN_INTERVAL = 15          # Discord allows one presence update per 15 seconds
RECONNECT_EVERY = 30       # how often to look for Discord again if it wasn't running


def build_activity(playing: dict | None, show_details: bool, launcher_started: float) -> dict:
    """The activity payload. `playing` is {"name", "mc_version", "loader", "started"} or None."""
    buttons = [{"label": "Get Nova Launcher", "url": REPO_URL}]
    assets = {"large_image": "nova", "large_text": "Nova Launcher"}
    if playing:
        if show_details:
            loader = playing.get("loader") or "vanilla"
            mc = playing.get("mc_version") or ""
            details = f"Playing {playing.get('name') or 'Minecraft'}"
            state = f"Minecraft {mc}".strip() + ("" if loader == "vanilla" else f" · {loader.title()}")
        else:
            details, state = "Playing Minecraft", "with Nova Launcher"
        return {"details": details[:128], "state": state[:128], "assets": assets, "buttons": buttons,
                "timestamps": {"start": int(playing.get("started") or time.time())}}
    return {"details": "In the launcher", "state": "Tuning Minecraft with Nova", "assets": assets,
            "buttons": buttons, "timestamps": {"start": int(launcher_started)}}


class _Pipe:
    """A byte stream to Discord: a named pipe on Windows, a unix socket elsewhere."""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.f = None
        self.sock: socket.socket | None = None

    def connect(self) -> bool:
        for n in range(10):
            try:
                if sys.platform.startswith("win"):
                    self.f = open(rf"\\?\pipe\discord-ipc-{n}", "r+b", buffering=0)
                else:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(5)
                    s.connect(self._unix_path(n))
                    self.sock = s
                return True
            except OSError:
                self.close()
        return False

    @staticmethod
    def _unix_path(n: int) -> str:
        base = next((os.environ[k] for k in ("XDG_RUNTIME_DIR", "TMPDIR", "TMP", "TEMP") if os.environ.get(k)), "/tmp")
        candidates = [f"{base}/discord-ipc-{n}", f"{base}/snap.discord/discord-ipc-{n}",
                      f"{base}/app/com.discordapp.Discord/discord-ipc-{n}"]
        return next((c for c in candidates if os.path.exists(c)), candidates[0])

    def _write(self, data: bytes) -> None:
        if self.f:
            self.f.write(data)
        else:
            self.sock.sendall(data)

    def _read(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.f.read(n - len(buf)) if self.f else self.sock.recv(n - len(buf))
            if not chunk:
                raise OSError("Discord closed the connection")
            buf += chunk
        return buf

    def send(self, op: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self._write(struct.pack("<II", op, len(data)) + data)

    def recv(self) -> tuple[int, dict]:
        op, length = struct.unpack("<II", self._read(8))
        return op, json.loads(self._read(length).decode() or "{}")

    def handshake(self) -> None:
        self.send(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id})
        op, data = self.recv()
        if data.get("evt") != "READY":
            raise OSError(f"Discord refused the connection: {data}")

    def set_activity(self, activity: dict | None) -> None:
        self.send(OP_FRAME, {"cmd": "SET_ACTIVITY", "nonce": str(uuid.uuid4()),
                             "args": {"pid": os.getpid(), "activity": activity}})
        op, _ = self.recv()
        while op == OP_PING:              # answer pings, then read the real reply
            op, _ = self.recv()

    def close(self) -> None:
        for c in (self.f, self.sock):
            try:
                if c:
                    c.close()
            except OSError:
                pass
        self.f = self.sock = None


class Presence:
    def __init__(self, app):
        self.app = app
        self.started = time.time()
        self.stop = threading.Event()
        self.pipe: _Pipe | None = None
        self.last_sent = ""
        self.last_time = 0.0

    def client_id(self) -> str:
        from . import settings
        return (settings.load().get("discord_client_id", "").strip() or config.default_discord_client_id())

    def current_playing(self) -> dict | None:
        for info in self.app.games.all_info():
            if info.get("status") in ("starting", "running"):
                inst = instances.get(info["instance"])
                if inst:
                    return {"name": inst["name"], "mc_version": inst.get("mc_version", ""),
                            "loader": inst.get("loader", "vanilla"), "started": info.get("started")}
        return None

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True, name="discord-presence").start()

    def shutdown(self) -> None:
        self.stop.set()
        if self.pipe:
            try:
                self.pipe.set_activity(None)
            except Exception:
                pass
            self.pipe.close()

    def tick(self) -> None:
        """One step: connect if needed, send the presence if it changed. Never raises."""
        from . import settings
        s = settings.load()
        cid = self.client_id()
        if not (s.get("discord_presence") and cid):
            if self.pipe:
                self.shutdown_pipe()
            return
        try:
            if not self.pipe:
                p = _Pipe(cid)
                if not p.connect():
                    self.last_time = time.time() + RECONNECT_EVERY - MIN_INTERVAL
                    return
                p.handshake()
                self.pipe, self.last_sent = p, ""
            act = build_activity(self.current_playing(), bool(s.get("discord_show_details", True)), self.started)
            key = json.dumps(act, sort_keys=True)
            if key != self.last_sent and time.time() - self.last_time >= MIN_INTERVAL:
                self.pipe.set_activity(act)
                self.last_sent, self.last_time = key, time.time()
        except Exception:
            self.shutdown_pipe()

    def shutdown_pipe(self) -> None:
        if self.pipe:
            self.pipe.close()
        self.pipe = None

    def _run(self) -> None:
        while not self.stop.wait(3):
            self.tick()
