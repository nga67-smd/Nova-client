"""Theme validation, the offline theme assistant, the Claude engine (fake API) and secret handling."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nova import ai, look, settings
from nova.util import NovaError


def test_sanitize_drops_unknown_and_bad_values_and_keeps_text_readable():
    out = look.sanitize({"accent": "#ffffff", "base": "#ffffff", "gradient": ["#ffffff", "#00ff00", "nope"], "pattern": "<script>",
                         "radius": 999, "font": "comic", "evil": "x", "glow": 1, "look_name": "A<b>B</b>!"})
    assert look.luminance(out["accent"]) <= 0.42 and look.luminance(out["base"]) <= 0.16
    assert "pattern" not in out and "font" not in out and "evil" not in out
    assert out["radius"] == 28 and out["glow"] is True and "<" not in out["look_name"]
    assert all(look.luminance(c) <= 0.3 for c in out["gradient"].split(","))
    assert look.sanitize({"accent": "url(javascript:alert(1))"}) == {}
    assert look.sanitize("not a dict") == {}


def test_very_dark_accent_is_lifted_so_it_shows_on_dark_background():
    assert look.luminance(look.sanitize({"accent": "#000000"})["accent"]) >= 0.05


@pytest.mark.parametrize("text,key,expect", [
    ("make it an ocean theme", "bg_mode", "gradient"),
    ("cyberpunk please", "pattern", "grid"),
    ("sharper corners", "radius", 6),
    ("turn off the stars", "starfield", False),
    ("use a monospace font", "font", "mono"),
    ("bigger text", "font_scale", 110),
    ("make it red", "theme_preset", "custom"),
    ("purple to blue gradient", "bg_mode", "gradient"),
])
def test_offline_assistant_understands_common_requests(text, key, expect):
    reply, patch = look.offline_respond(text, look.LOOK_DEFAULTS)
    assert patch.get(key) == expect, (reply, patch)


def test_ocean_blue_keeps_the_ocean_gradient_but_retints():
    _, patch = look.offline_respond("make it ocean blue", look.LOOK_DEFAULTS)
    assert patch["bg_mode"] == "gradient" and patch["theme_preset"] == "custom"


def test_unknown_request_returns_help_and_no_changes():
    reply, patch = look.offline_respond("what's the weather", look.LOOK_DEFAULTS)
    assert patch == {} and "Try:" in reply
    assert look.offline_respond("reset", {})[1]["accent"] == look.LOOK_DEFAULTS["accent"]


class FakeClaude(BaseHTTPRequestHandler):
    reply = {"reply": "Moody teal.", "changes": {"accent": "#14b8a6", "base": "#ffffff", "pattern": "grid", "hack": 1}}
    status = 200
    seen = {}

    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeClaude.seen = {"key": self.headers.get("x-api-key"), "body": body}
        data = json.dumps({"content": [{"type": "text", "text": "Sure!\n" + json.dumps(self.reply)}]} if self.status == 200
                          else {"error": {"message": "bad"}}).encode()
        self.send_response(self.status); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


@pytest.fixture
def claude(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeClaude)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(ai, "API_URL", f"http://127.0.0.1:{srv.server_port}/v1/messages")
    FakeClaude.status = 200
    yield
    srv.shutdown()


def test_claude_reply_is_sanitized_and_key_is_sent_in_header(claude):
    settings.update({"ai_api_key": "sk-ant-" + "a" * 30})
    res = ai.chat("teal grid please", [])
    assert res["engine"] == "claude" and res["reply"] == "Moody teal."
    assert res["changes"]["pattern"] == "grid" and "hack" not in res["changes"]
    assert look.luminance(res["changes"]["base"]) <= 0.16                      # white background was darkened
    assert FakeClaude.seen["key"].startswith("sk-ant-") and FakeClaude.seen["body"]["messages"][-1]["content"] == "teal grid please"


def test_claude_failure_falls_back_to_offline_with_a_message(claude):
    settings.update({"ai_api_key": "sk-ant-" + "a" * 30})
    FakeClaude.status = 401
    res = ai.chat("ocean theme", [])
    assert res["engine"] == "offline" and "API key" in res["error"] and res["changes"]["bg_mode"] == "gradient"


def test_no_key_uses_offline_and_key_never_reaches_the_ui(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    assert ai.chat("sunset", [])["engine"] == "offline"
    settings.update({"ai_api_key": "sk-ant-" + "b" * 30})
    pub = settings.public()
    assert "ai_api_key" not in pub and pub["ai_api_key_set"] is True and "sk-ant" not in json.dumps(pub)
    with pytest.raises(NovaError):
        settings.update({"ai_api_key": "not a key!"})
    with pytest.raises(NovaError):
        settings.update({"pattern": "<script>"})


def test_background_image_upload_serves_back_only_with_token_and_rejects_non_images(tmp_path, monkeypatch):
    import urllib.request, urllib.error, struct, zlib
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    from nova.server import App, start_server
    app = App(token="tok123"); start_server(app, 8771)
    def call(method, path, data=None, hdr=None):
        req = urllib.request.Request("http://127.0.0.1:8771" + path, data=data, method=method, headers={"X-Nova-Token": "tok123", **(hdr or {})})
        try:
            with urllib.request.urlopen(req) as r: return r.status, r.read()
        except urllib.error.HTTPError as e: return e.code, e.read()
    code, body = call("POST", "/api/look/image-upload", b"not an image at all", {"X-Filename": "x.png"})
    assert code == 400 and b"PNG, JPEG" in body and not (tmp_path / "background.img").exists()
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00\x01\x02\x03")) + chunk(b"IEND", b"")
    code, body = call("POST", "/api/look/image-upload", png, {"X-Filename": "x.png"})
    assert code == 200 and json.loads(body)["bg_mode"] == "image" and json.loads(body)["bg_image"] is True
    assert call("GET", "/background?t=tok123")[0] == 200 and call("GET", "/background?t=wrong")[0] == 404
    assert call("DELETE", "/api/look/image")[0] == 200 and call("GET", "/background?t=tok123")[0] == 404
