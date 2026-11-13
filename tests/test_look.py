"""Theme validation, built-in and saved themes, imported backgrounds (image / GIF / video)."""
import base64
import json
import struct
import urllib.error
import urllib.request
import zlib

import pytest

from nova import look, settings
from nova.util import NovaError


def test_sanitize_drops_unknown_and_bad_values_and_keeps_text_readable():
    out = look.sanitize({"accent": "#ffffff", "base": "#ffffff", "gradient": ["#ffffff", "#00ff00", "nope"], "pattern": "<script>",
                         "radius": 999, "font": "comic", "evil": "x", "glow": 1, "look_name": "A<b>B</b>!", "motion": "spin", "bg_mode": "image"})
    assert look.luminance(out["accent"]) <= 0.42 and look.luminance(out["base"]) <= 0.16
    assert not {"pattern", "font", "evil", "motion", "bg_mode"} & set(out)
    assert out["radius"] == 28 and out["glow"] is True and "<" not in out["look_name"]
    assert all(look.luminance(c) <= 0.3 for c in out["gradient"].split(","))
    assert look.sanitize({"accent": "url(javascript:alert(1))"}) == {} and look.sanitize("nope") == {}
    assert look.sanitize({"bg_mode": "media", "motion": "aurora"}) == {"bg_mode": "media", "motion": "aurora"}


def test_very_dark_accent_is_lifted_so_it_shows_on_dark_background():
    assert look.luminance(look.sanitize({"accent": "#000000"})["accent"]) >= 0.05


def test_every_builtin_theme_is_valid_readable_and_self_contained():
    assert len(look.THEMES) >= 25
    for tid, t in look.THEMES.items():
        p = look.theme_patch(t)
        assert p["accent"] and p["accent2"] and p["look_name"] == t["name"], tid
        assert look.luminance(p["accent"]) <= 0.42 and (not p["base"] or look.luminance(p["base"]) <= 0.16), tid
        assert p["bg_mode"] in ("surface", "gradient"), tid          # themes never depend on an imported file
        assert "font_scale" not in p and "density" not in p, tid     # accessibility choices are the user's
    assert {"nova", "nebula", "ultra", "midnight", "orchid", "amethyst"} <= set(look.THEMES)   # ids people may already have saved


def test_applying_a_theme_resets_leftovers_from_the_previous_one(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    settings.update(look.theme_patch(look.THEMES["cyberpunk"]))
    assert settings.load()["pattern"] == "grid" and settings.load()["font"] == "mono"
    settings.update(look.theme_patch(look.THEMES["nova"]))
    s = settings.load()
    assert s["pattern"] == "none" and s["font"] == "system" and s["radius"] == 14 and s["starfield"] is True


def test_saved_themes_roundtrip_replace_and_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    settings.update({"accent": "#ff0000", "gradient": "#101010,#202040", "bg_mode": "gradient", "pattern": "dots", "motion": "flow"})
    t = look.save_user_theme("My <b>Red</b> Look", settings.load())
    assert t["id"].startswith("my-") and "<" not in t["name"] and ">" not in t["name"]
    assert look.find_theme(t["id"])["pattern"] == "dots" and look.find_theme(t["id"])["motion"] == "flow"
    settings.update({"pattern": "grid"})
    again = look.save_user_theme(t["name"].upper(), settings.load())      # same name (case-insensitive) replaces it
    assert again["id"] == t["id"] and len(look.load_user_themes()) == 1 and look.find_theme(t["id"])["pattern"] == "grid"
    settings.update({"theme_preset": t["id"]})                              # saved ids are valid presets
    look.delete_user_theme(t["id"])
    assert look.load_user_themes() == [] and look.find_theme(t["id"]) is None
    with pytest.raises(NovaError):
        look.save_user_theme("   ", settings.load())


def test_saved_theme_never_depends_on_an_imported_file(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    settings.update({"bg_mode": "media", "bg_media": "video"})
    t = look.save_user_theme("Clip", settings.load())
    assert look.find_theme(t["id"])["bg_mode"] == "surface"


def test_settings_validation_and_old_settings_migrate(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    for bad in ({"pattern": "<script>"}, {"bg_media": "exe"}, {"motion": "spin"}):
        with pytest.raises(NovaError):
            settings.update(bad)
    # settings.json written by the earlier build: "image" mode and a stored AI key
    (tmp_path / "settings.json").write_text(json.dumps({"bg_mode": "image", "bg_image": True, "ai_api_key": "sk-ant-secret"}))
    (tmp_path / "background.img").write_bytes(b"\x89PNG\r\n\x1a\n")
    s = settings.load()
    assert s["bg_mode"] == "media" and s["bg_media"] == "image"
    assert "sk-ant-secret" not in (tmp_path / "settings.json").read_text() and "ai_api_key" not in s


# ---------------------------------------------------------------- imported backgrounds

def _png():
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00\x01\x02\x03")) + chunk(b"IEND", b"")


GIF = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
WEBM = b"\x1a\x45\xdf\xa3" + bytes(range(256)) * 40          # EBML magic + filler: enough for type sniffing and range tests
MP4 = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 40


@pytest.mark.parametrize("data,mime,kind", [(_png(), "image/png", "image"), (GIF, "image/gif", "image"),
                                            (WEBM, "video/webm", "video"), (MP4, "video/mp4", "video"),
                                            (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp", "image"), (b"\xff\xd8\xff\xe0JFIF", "image/jpeg", "image")])
def test_media_type_is_judged_by_content_not_name(tmp_path, data, mime, kind):
    from nova.server import _media_type
    f = tmp_path / "anything.txt"; f.write_bytes(data)
    assert _media_type(f) == (mime, kind)


@pytest.mark.parametrize("data", [b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", b"MZ\x90\x00 an exe", b"plain text", b""])
def test_svg_scripts_executables_and_text_are_not_media(tmp_path, data):
    from nova.server import _media_type
    f = tmp_path / "x.png"; f.write_bytes(data)
    assert _media_type(f) == ("", "")


def test_import_background_flow_over_http(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    from nova.server import App, start_server
    start_server(App(token="tok123"), 8771)

    def call(method, path, data=None, hdr=None, token="tok123"):
        req = urllib.request.Request("http://127.0.0.1:8771" + path, data=data, method=method, headers={"X-Nova-Token": token, **(hdr or {})})
        try:
            with urllib.request.urlopen(req) as r: return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e: return e.code, e.read(), dict(e.headers)

    code, body, _ = call("POST", "/api/look/media-upload", b"MZ not media", {"X-Filename": "a.mp4"})
    assert code == 400 and b"PNG, JPEG, WebP, GIF, MP4 or WebM" in body and not (tmp_path / "background.img").exists()
    assert call("POST", "/api/look/media-upload", GIF, {"X-Filename": "a.gif"}, token="wrong")[0] in (401, 403)

    code, body, _ = call("POST", "/api/look/media-upload", GIF, {"X-Filename": "a.gif"})
    s = json.loads(body)
    assert code == 200 and s["bg_media"] == "image" and s["bg_mode"] == "media"
    code, body, hdr = call("GET", "/background?t=tok123")
    assert code == 200 and body == GIF and hdr["Content-Type"] == "image/gif"
    assert call("GET", "/background?t=wrong")[0] == 404

    code, body, _ = call("POST", "/api/look/media-upload", WEBM, {"X-Filename": "clip.webm"})
    assert json.loads(body)["bg_media"] == "video"                                    # replaces the previous file
    code, body, hdr = call("GET", "/background?t=tok123", hdr={"Range": "bytes=10-19"})
    assert code == 206 and body == WEBM[10:20] and hdr["Content-Range"] == f"bytes 10-19/{len(WEBM)}" and hdr["Accept-Ranges"] == "bytes"
    code, body, hdr = call("GET", "/background?t=tok123", hdr={"Range": "bytes=-5"})
    assert code == 206 and body == WEBM[-5:]
    assert call("GET", "/background?t=tok123", hdr={"Range": f"bytes={len(WEBM) + 5}-"})[0] == 416
    assert call("GET", "/background?t=tok123")[2]["Content-Type"] == "video/webm"

    code, body, _ = call("POST", "/api/themes/apply", json.dumps({"id": "synthwave"}).encode(), {"Content-Type": "application/json"})
    s = json.loads(body)
    assert code == 200 and s["theme_preset"] == "synthwave" and s["motion"] == "flow" and s["bg_media"] == "video"
    code, body, _ = call("POST", "/api/themes/apply", json.dumps({"id": "nope"}).encode(), {"Content-Type": "application/json"})
    assert code == 400

    assert json.loads(call("DELETE", "/api/look/media")[1])["bg_media"] == ""
    assert call("GET", "/background?t=tok123")[0] == 404
