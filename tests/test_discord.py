"""Discord Rich Presence against a fake Discord listening on a unix socket."""
import json
import os
import socket
import struct
import sys
import threading
import time

import pytest

from nova import discord, instances

pytestmark = pytest.mark.skipif(sys.platform.startswith("win"), reason="fake Discord uses a unix socket")


class FakeDiscord:
    def __init__(self, path):
        self.frames = []
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(str(path)); self.srv.listen(1)
        threading.Thread(target=self._serve, daemon=True).start()

    def _read(self, c, n):
        b = b""
        while len(b) < n:
            chunk = c.recv(n - len(b))
            if not chunk:
                raise OSError
            b += chunk
        return b

    def _send(self, c, op, obj):
        d = json.dumps(obj).encode(); c.sendall(struct.pack("<II", op, len(d)) + d)

    def _serve(self):
        c, _ = self.srv.accept()
        try:
            while True:
                op, ln = struct.unpack("<II", self._read(c, 8))
                msg = json.loads(self._read(c, ln))
                self.frames.append((op, msg))
                if op == 0:
                    self._send(c, 1, {"cmd": "DISPATCH", "evt": "READY", "data": {}})
                else:
                    self._send(c, 1, {"cmd": "SET_ACTIVITY", "evt": None, "nonce": msg.get("nonce")})
        except OSError:
            pass


class FakeApp:
    def __init__(self, infos): self.games = type("G", (), {"all_info": staticmethod(lambda: infos)})()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path / "home"))
    run = tmp_path / "run"; run.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(run))
    monkeypatch.setenv("NOVA_DISCORD_CLIENT_ID", "1234567890123456789")
    return run


def test_activity_text_mentions_nova_and_instance():
    a = discord.build_activity({"name": "SMP", "mc_version": "1.21.8", "loader": "fabric", "started": 1000}, True, 0)
    assert a["details"] == "Playing SMP" and a["state"] == "Minecraft 1.21.8 · Fabric"
    assert a["assets"]["large_text"] == "Nova Launcher" and a["timestamps"]["start"] == 1000
    assert a["buttons"][0]["url"].startswith("https://github.com/")
    hidden = discord.build_activity({"name": "Secret Server", "mc_version": "1.21.8", "loader": "fabric"}, False, 0)
    assert "Secret" not in json.dumps(hidden) and "Nova Launcher" in hidden["state"]
    assert discord.build_activity(None, True, 5)["details"] == "In the launcher"


def test_connects_sends_presence_and_updates(env, monkeypatch):
    fake = FakeDiscord(env / "discord-ipc-0")
    monkeypatch.setattr(discord, "MIN_INTERVAL", 0)
    infos = []
    p = discord.Presence(FakeApp(infos))
    p.tick()
    time.sleep(0.2)
    assert fake.frames[0][0] == 0 and fake.frames[0][1]["client_id"] == "1234567890123456789"
    act = fake.frames[1][1]["args"]["activity"]
    assert act["details"] == "In the launcher" and fake.frames[1][1]["cmd"] == "SET_ACTIVITY"
    inst = instances.create({"name": "My Pack", "mc_version": "1.21.8", "loader": "vanilla"})
    infos.append({"instance": inst["id"], "status": "running", "started": 1234})
    p.tick(); time.sleep(0.2)
    assert fake.frames[-1][1]["args"]["activity"]["details"] == "Playing My Pack"
    n = len(fake.frames); p.tick(); time.sleep(0.1)
    assert len(fake.frames) == n                       # unchanged presence isn't resent
    p.shutdown(); time.sleep(0.2)
    assert fake.frames[-1][1]["args"]["activity"] is None  # cleared on exit


def test_no_discord_running_is_harmless(env):
    p = discord.Presence(FakeApp([]))
    p.tick(); p.tick()                                 # nothing listening: no error, no crash
    assert p.pipe is None


def test_off_by_default_without_an_application_id(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path / "h"))
    monkeypatch.delenv("NOVA_DISCORD_CLIENT_ID", raising=False)
    p = discord.Presence(FakeApp([]))
    p.tick()
    assert p.pipe is None and p.client_id() == ""
