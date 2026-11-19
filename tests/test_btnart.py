"""Pictures imported as button backgrounds."""
import json
import struct
import urllib.error
import urllib.request
import zlib

import pytest

from nova import btnart
from nova.util import NovaError


def _png():
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00\x01\x02\x03")) + chunk(b"IEND", b"")


def test_set_replace_remove_and_validate(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    f = tmp_path / "up.bin"
    f.write_bytes(_png())
    assert list(btnart.set_picture("primary", f)) == ["primary"] and not f.exists()
    f.write_bytes(b"GIF89a" + bytes(40))
    btnart.set_picture("primary", f)                                  # replaces the old file, whatever its type
    assert btnart.file_for("primary")[1] == "image/gif" and len(list((tmp_path / "button_art").iterdir())) == 1
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(6 * 1024 * 1024))             # a large, high-resolution picture is kept as is
    btnart.set_picture("primary", f)
    assert btnart.file_for("primary")[0].stat().st_size == 8 + 6 * 1024 * 1024
    f.write_bytes(b"MZ not a picture")
    with pytest.raises(NovaError):
        btnart.set_picture("normal", f)
    f.write_bytes(_png())
    with pytest.raises(NovaError):
        btnart.set_picture("../evil", f)
    assert btnart.file_for("../x") is None and btnart.file_for("danger") is None
    assert btnart.remove("primary") == {} and btnart.file_for("primary") is None


def test_http_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    from nova.server import App, start_server
    start_server(App(token="tk"), 8793)

    def call(method, path, data=None, hdr=None, token="tk"):
        req = urllib.request.Request("http://127.0.0.1:8793" + path, data=data, method=method, headers={"X-Nova-Token": token, **(hdr or {})})
        try:
            with urllib.request.urlopen(req) as r: return r.status, r.read()
        except urllib.error.HTTPError as e: return e.code, e.read()

    assert call("POST", "/api/button-art-upload", _png(), {"X-Slot": "primary"}, token="bad")[0] in (401, 403)
    assert call("POST", "/api/button-art-upload", b"MZ nope", {"X-Slot": "primary"})[0] == 400
    assert call("POST", "/api/button-art-upload", _png(), {"X-Slot": "nope"})[0] == 400
    code, body = call("POST", "/api/button-art-upload", _png(), {"X-Slot": "danger"})
    assert code == 200 and list(json.loads(body)["btn_art"]) == ["danger"]
    assert call("GET", "/btnart/danger?t=tk") == (200, _png())
    assert call("GET", "/btnart/danger?t=wrong")[0] == 404 and call("GET", "/btnart/normal?t=tk")[0] == 404
    assert "danger" in json.loads(call("GET", "/api/state")[1])["btn_art"]
    assert json.loads(call("DELETE", "/api/button-art/danger")[1])["btn_art"] == {}
