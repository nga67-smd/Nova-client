"""Imported pictures for Kawaii / Emo mode: content sniffing, limits and the HTTP flow."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from nova import modeart, settings
from nova.util import NovaError

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 40
GIF = b"GIF89a" + b"\x00" * 40
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 20


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    return tmp_path


def put(home, data, name="u.bin"):
    f = home / name
    f.write_bytes(data)
    return f


@pytest.mark.parametrize("data,ext", [(PNG, "png"), (JPG, "jpg"), (GIF, "gif"), (WEBP, "webp")])
def test_accepts_real_pictures_by_content(home, data, ext):
    items = modeart.add("kawaii", put(home, data, "whatever.txt"))
    assert items[-1]["ext"] == ext and modeart.file_for(items[-1]["id"])[1].startswith("image/")


@pytest.mark.parametrize("data", [b"<svg onload=alert(1)></svg>", b"MZ\x90\x00exe", b"just text", b""])
def test_rejects_non_pictures(home, data):
    with pytest.raises(NovaError, match="isn't a PNG"):
        modeart.add("emo", put(home, data))
    assert modeart.load() == []


def test_limits_and_modes(home):
    with pytest.raises(NovaError, match="Kawaii or Emo"):
        modeart.add("normal", put(home, PNG))
    with pytest.raises(NovaError, match="under 4 MB"):
        modeart.add("emo", put(home, PNG + b"0" * (modeart.MAX_BYTES + 1)))
    for _ in range(modeart.MAX_PER_MODE):
        modeart.add("emo", put(home, PNG))
    with pytest.raises(NovaError, match="up to 8"):
        modeart.add("emo", put(home, PNG))
    modeart.add("kawaii", put(home, PNG))                 # the other mode has its own allowance


def test_remove_and_id_safety(home):
    pid = modeart.add("emo", put(home, PNG))[0]["id"]
    assert modeart.file_for("../../etc/passwd") is None and modeart.file_for("a" * 20) is None
    modeart.remove(pid)
    assert modeart.load() == [] and not list((home / "mode_art").glob("a*.png"))


def test_http_flow(home):
    from nova.server import App, start_server
    start_server(App(token="tok9"), 8772)

    def call(method, path, data=None, hdr=None, token="tok9"):
        req = urllib.request.Request("http://127.0.0.1:8772" + path, data=data, method=method, headers={"X-Nova-Token": token, **(hdr or {})})
        try:
            with urllib.request.urlopen(req) as r: return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e: return e.code, e.read(), dict(e.headers)

    assert call("POST", "/api/mode-art-upload", PNG)[0] == 400                     # Normal mode: not allowed
    settings.update({"ui_mode": "emo"})
    assert call("POST", "/api/mode-art-upload", b"MZ exe")[0] == 400
    assert call("POST", "/api/mode-art-upload", PNG, token="bad")[0] in (401, 403)
    code, body, _ = call("POST", "/api/mode-art-upload", PNG)
    item = json.loads(body)["mode_art"][0]
    assert code == 200 and item["mode"] == "emo"
    code, body, hdr = call("GET", f"/modeart/{item['id']}?t=tok9")
    assert code == 200 and body == PNG and hdr["Content-Type"] == "image/png"
    assert call("GET", f"/modeart/{item['id']}?t=wrong")[0] == 404 and call("GET", "/modeart/aaaaaaaaa?t=tok9")[0] == 404
    assert json.loads(call("GET", "/api/state")[1])["mode_art"][0]["id"] == item["id"]
    code, body, _ = call("DELETE", f"/api/mode-art/{item['id']}")
    assert code == 200 and json.loads(body)["mode_art"] == [] and call("GET", f"/modeart/{item['id']}?t=tok9")[0] == 404
