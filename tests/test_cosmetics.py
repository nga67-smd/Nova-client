"""Cosmetics storage, validation, game-folder sync and Mojang skin upload (against a fake service)."""
import base64
import json
import struct
import threading
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nova import accounts, cosmetics, msauth
from nova.util import NovaError


def png(w, h):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x00\x00\x00\x00" * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def b64(b):
    return "data:image/png;base64," + base64.b64encode(b).decode()


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    return tmp_path


def body(**kw):
    d = {"skin": b64(png(64, 64)), "cape": b64(png(64, 32)), "base": b64(png(64, 64)),
         "state": {"selected": {"hat": "beanie", "face": "", "chest": "emblem", "feet": "", "cape": "classic"},
                   "colors": {"main": "#112233", "trim": "#abcdef"}, "variant": "slim"}}
    d.update(kw)
    return d


def test_save_load_roundtrip_and_files(home):
    st = cosmetics.save(body())
    assert st["has_skin"] and st["has_cape"] and st["has_base"]
    assert st["selected"]["hat"] == "beanie" and st["colors"]["main"] == "#112233" and st["variant"] == "slim"
    assert cosmetics.png_size(cosmetics.read_file("skin")) == (64, 64)
    assert cosmetics.png_size(cosmetics.read_file("cape")) == (64, 32)


@pytest.mark.parametrize("bad,match", [
    ({"skin": b64(b"not a png at all, just text bytes")}, "PNG"),
    ({"skin": b64(png(100, 100))}, "wrong size"),
    ({"skin": b64(png(64, 64) + b"0" * 70000)}, "too large"),
    ({"cape": b64(png(64, 64))}, "wrong size"),
    ({"skin": ""}, "Missing"),
])
def test_invalid_images_rejected(home, bad, match):
    with pytest.raises(NovaError, match=match):
        cosmetics.save(body(**bad))
    assert not cosmetics.load()["has_skin"]


def test_state_is_sanitised(home):
    st = cosmetics.save(body(state={"selected": {"hat": "../../evil", "cape": "ok_1"}, "colors": {"main": "red", "trim": "#00ff00"}, "variant": "x"}))
    assert st["selected"]["hat"] == "" and st["selected"]["cape"] == "ok_1"
    assert st["colors"] == {"main": "#8b5cf6", "trim": "#00ff00"} and st["variant"] == "classic"


def test_sync_to_game_copies_and_cleans_up(home, tmp_path):
    game = tmp_path / "game"
    cosmetics.sync_to_game(game)
    assert not (game / "nova-cosmetics").exists()           # nothing saved: nothing written
    cosmetics.save(body())
    cosmetics.sync_to_game(game)
    d = game / "nova-cosmetics"
    assert (d / "skin.png").exists() and (d / "cape.png").exists() and (d / "model.txt").read_text() == "slim"
    cosmetics.reset()
    cosmetics.sync_to_game(game)
    assert not d.exists()


class Fake:
    def __init__(self):
        self.uploads = []
        self.status = 200


@pytest.fixture
def mojang(home, monkeypatch):
    fake = Fake()
    skin_png = png(64, 64)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_GET(self):
            if self.path == "/profile":
                b = json.dumps({"skins": [{"state": "ACTIVE", "variant": "SLIM", "url": f"http://127.0.0.1:{self.server.server_port}/tex"}]}).encode()
            elif self.path == "/tex":
                b = skin_png
            else:
                b = b"{}"
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            fake.uploads.append((self.headers.get("Authorization"), self.headers.get("Content-Type"), self.rfile.read(n)))
            self.send_response(fake.status); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"{}")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    monkeypatch.setitem(msauth.URLS, "profile", base + "/profile")
    monkeypatch.setitem(msauth.URLS, "profile_skins", base + "/skins")
    monkeypatch.setattr(cosmetics, "TEXTURE_HOSTS", ("127.0.0.1",))
    import time
    accounts.upsert_microsoft({"username": "Steve", "uuid": "069a79f4-44e9-4726-a5be-fca90e38aaf5", "mc_token": "TOK",
                               "mc_expires": int(time.time()) + 9999, "xuid": "1"}, "R")
    yield fake
    srv.shutdown()


def test_upload_skin_sends_multipart_with_variant_and_token(mojang):
    cosmetics.save(body())
    assert cosmetics.upload_skin() == {"ok": True}
    auth, ctype, data = mojang.uploads[0]
    assert auth == "Bearer TOK" and ctype.startswith("multipart/form-data; boundary=")
    assert b'name="variant"\r\n\r\nslim' in data and b"\x89PNG" in data and b'filename="nova-skin.png"' in data


@pytest.mark.parametrize("status,match", [(429, "rate-limiting"), (401, "Sign in again"), (400, "HTTP 400")])
def test_upload_errors(mojang, status, match):
    cosmetics.save(body()); mojang.status = status
    with pytest.raises(NovaError, match=match):
        cosmetics.upload_skin()


def test_upload_needs_saved_design_and_microsoft(home):
    with pytest.raises(NovaError, match="Save your design"):
        cosmetics.upload_skin()
    cosmetics.save(body())
    accounts.add_offline("Alex")
    with pytest.raises(NovaError, match="Microsoft"):
        cosmetics.upload_skin()


def test_current_skin_fetch_and_host_allowlist(mojang, monkeypatch):
    r = cosmetics.current_skin()
    assert r["variant"] == "slim" and cosmetics.png_size(base64.b64decode(r["png"])) == (64, 64)
    monkeypatch.setattr(cosmetics, "TEXTURE_HOSTS", (".minecraft.net",))
    with pytest.raises(NovaError, match="Unexpected skin location"):
        cosmetics.current_skin()


def test_current_skin_empty_for_offline(home):
    accounts.add_offline("Alex")
    assert cosmetics.current_skin() == {}


def test_switching_cape_off_removes_it(home):
    cosmetics.save(body())
    assert cosmetics.load()["has_cape"]
    cosmetics.save(body(cape=None))
    assert not cosmetics.load()["has_cape"]
