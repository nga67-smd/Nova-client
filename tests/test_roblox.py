"""Roblox detection, FastFlags, sky, mods and launch-link safety (no Roblox needed: installs are faked in a temp folder)."""
import io
import json
import struct
import time
import urllib.error
import urllib.request
import zipfile
import zlib

import pytest

from nova import roblox as rbx
from nova.util import NovaError

VER = "version-0123456789abcdef"
NEWER = "version-fedcba9876543210"


def _zip(files: dict) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return b.getvalue()


def _png(w=2, h=2):
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    raw = b"".join(b"\x00" + b"\x10\x20\x30" * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path / "nova"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return tmp_path


def _install(home, version=VER, who="Roblox"):
    d = home / "local" / who / "Versions" / version
    (d / "content" / "sounds").mkdir(parents=True)
    (d / "content" / "sky").mkdir(parents=True)
    (d / "RobloxPlayerBeta.exe").write_text("exe")
    (d / "content" / "sounds" / "ouch.ogg").write_text("orig")
    for code in ("bk", "dn", "ft", "lf", "rt", "up"):
        (d / "content" / "sky" / f"sky512_{code}.tex").write_text("orig-" + code)
    return d


class _Proc:
    def __init__(self):
        self.n = 0

    def poll(self):
        self.n += 1
        return None if self.n < 2 else 0


# ------------------------------------------------------------------ finding Roblox

def test_roblox_is_found_on_the_device_and_the_newest_copy_wins(home):
    assert rbx.detect() == "" and rbx.installed_version() == "" and rbx.status()["version"] == ""
    with pytest.raises(NovaError, match="couldn't find Roblox"):
        rbx.version_dir()
    old = _install(home, VER)
    (home / "local" / "Roblox" / "Versions" / "version-aaaaaaaaaaaaaaaa").mkdir()      # an empty leftover folder is ignored
    assert rbx.detect() == VER and rbx.version_dir() == old and rbx.status()["from"] == "Roblox"
    time.sleep(0.02)
    new = _install(home, NEWER, "Bloxstrap")
    assert rbx.detect() == NEWER and rbx.version_dir() == new and rbx.status()["from"] == "Bloxstrap"
    import shutil
    shutil.rmtree(new)
    shutil.rmtree(old)
    assert rbx.detect() == "" and rbx.installed_version() == ""                          # uninstalled elsewhere: forgotten


# ------------------------------------------------------------------ FastFlags

def test_flags_validate_save_and_write_into_the_game(home):
    d = _install(home)
    rbx.detect()
    assert rbx.save_flags({"DFIntTaskSchedulerTargetFps": "144", "FFlagX": "True", "FStringY": "hello"}) == \
        {"DFIntTaskSchedulerTargetFps": 144, "FFlagX": True, "FStringY": "hello"}
    for bad in ({"bad name": 1}, {"../x": 1}, {"FFlagOk": [1]}):
        with pytest.raises(NovaError):
            rbx.save_flags(bad)
    rbx.write_flags(d)
    f = d / "ClientSettings" / "ClientAppSettings.json"
    assert json.loads(f.read_text())["DFIntTaskSchedulerTargetFps"] == 144
    rbx.apply_preset("fps_240", True)
    assert rbx.load_flags()["DFIntTaskSchedulerTargetFps"] == 240 and rbx.status()["preset_on"]["fps_240"] is True
    rbx.apply_preset("fps_240", False)
    assert "DFIntTaskSchedulerTargetFps" not in rbx.load_flags()
    rbx.save_flags({})
    rbx.write_flags(d)
    assert not f.exists()
    with pytest.raises(NovaError):
        rbx.apply_preset("nope", True)


def test_high_optimization_turns_everything_to_lowest_and_back(home):
    rbx.apply_preset("max_perf", True)
    flags = rbx.load_flags()
    assert flags["DFIntDebugFRMQualityLevelOverride"] == 1 and flags["FIntRenderShadowIntensity"] == 0 and flags["FFlagDisablePostFx"] is True
    assert flags["DFIntTextureQualityOverride"] == 0 and rbx.status()["preset_on"]["max_perf"] is True
    rbx.apply_preset("max_perf", False)
    assert rbx.load_flags() == {} and rbx.status()["preset_on"]["max_perf"] is False


# ------------------------------------------------------------------ sky

def test_sky_color_and_pictures_become_roblox_sky_files_and_are_restored(home):
    d = _install(home)
    rbx.detect()
    assert rbx.sky_info()["set"] is False
    rbx.set_sky_color("#336699")
    assert rbx.sky_info()["set"] and all(rbx.sky_info()["faces"].values())
    rbx.build_sky_mod(d)
    rbx.apply_mods(d)
    sky = d / "content" / "sky"
    assert (sky / "sky512_ft.tex").read_bytes().startswith(b"\x89PNG") and (sky / "sky512_up.tex").read_bytes().startswith(b"\x89PNG")
    up = home / "up.png"
    up.write_bytes(_png(4, 4))
    rbx.set_sky_image("up", up)
    assert not up.exists() and rbx.sky_info()["faces"]["up"]
    rbx.clear_sky()
    assert rbx.sky_info()["set"] is False
    rbx.build_sky_mod(d)
    rbx.apply_mods(d)
    assert (sky / "sky512_ft.tex").read_text() == "orig-ft" and (sky / "sky512_up.tex").read_text() == "orig-up"
    assert rbx.mods_info() == []                                                  # the sky isn't shown as a normal mod


def test_sky_input_is_checked(home):
    f = home / "x.bin"
    for bad in (b"MZ not a picture", b"GIF89a....", b""):
        f.write_bytes(bad)
        with pytest.raises(NovaError):
            rbx.set_sky_image("all", f)
    f.write_bytes(_png())
    with pytest.raises(NovaError):
        rbx.set_sky_image("ceiling", f)
    for color in ("red", "#12345", "url(x)", ""):
        with pytest.raises(NovaError):
            rbx.set_sky_color(color)
    f.write_bytes(_png())
    assert all(rbx.set_sky_image("all", f)["faces"].values())


def test_sky_uses_the_file_names_roblox_has_and_falls_back(home):
    d = _install(home)
    for code in ("bk", "dn", "ft", "lf", "rt", "up"):                              # a Roblox that names its sky files differently
        (d / "content" / "sky" / f"sky512_{code}.tex").rename(d / "content" / "sky" / f"sky512_{code}.dds")
    rbx.detect()
    rbx.set_sky_color("#ff0000")
    rbx.build_sky_mod(d)
    assert sorted(p.name for p in (rbx.mods_dir() / "Nova Sky" / "content" / "sky").iterdir()) == sorted(f"sky512_{c}.dds" for c in ("bk", "dn", "ft", "lf", "rt", "up"))
    import shutil
    shutil.rmtree(d / "content" / "sky")                                           # no sky folder at all: default names
    rbx.build_sky_mod(d)
    assert (rbx.mods_dir() / "Nova Sky" / "content" / "sky" / "sky512_ft.tex").exists()


# ------------------------------------------------------------------ mods

def test_mods_overlay_and_restore_originals(home):
    d = _install(home)
    rbx.detect()
    tmp = home / "m.zip"
    tmp.write_bytes(_zip({"content/sounds/ouch.ogg": "MOD", "content/sky/new.png": "sky"}))
    name = rbx.import_mod_zip(tmp, "Quiet Pack.zip")
    assert name == "Quiet Pack" and rbx.mods_info() == [{"name": "Quiet Pack", "files": 2, "enabled": True}]
    rbx.apply_mods(d)
    assert (d / "content/sounds/ouch.ogg").read_text() == "MOD" and (d / "content/sky/new.png").exists()
    rbx.set_mod_enabled("Quiet Pack", False)
    rbx.apply_mods(d)
    assert (d / "content/sounds/ouch.ogg").read_text() == "orig" and not (d / "content/sky/new.png").exists()
    rbx.set_mod_enabled("Quiet Pack", True)
    rbx.apply_mods(d)
    rbx.delete_mod("Quiet Pack")
    rbx.apply_mods(d)
    assert (d / "content/sounds/ouch.ogg").read_text() == "orig" and rbx.mods_info() == []


def test_mod_import_rejects_non_zip_and_path_tricks(home):
    f = home / "x.zip"
    f.write_bytes(b"not a zip")
    with pytest.raises(NovaError, match="zip"):
        rbx.import_mod_zip(f, "x.zip")
    f.write_bytes(_zip({"../../escape.txt": "x"}))
    with pytest.raises(Exception):
        rbx.import_mod_zip(f, "evil.zip")
    assert not (home / "escape.txt").exists() and rbx.mods_info() == []
    f.write_bytes(_zip({"a.txt": "x"}))
    assert rbx.import_mod_zip(f, "Nova Sky.zip") != "Nova Sky"                      # the name Nova uses for the sky is reserved


# ------------------------------------------------------------------ launching

@pytest.mark.parametrize("uri", ["roblox-player:1+launchmode:play+gameinfo:abc+placelauncherurl:https%3A%2F%2Fx", "roblox://experiences/start?placeId=1"])
def test_launch_links_are_accepted(uri):
    assert rbx.clean_launch_uri(uri) == uri


@pytest.mark.parametrize("uri", ["", "https://evil.example", "calc.exe", "roblox://x --flag", 'roblox://x"&calc', "roblox://x\ny", "file:///c:/a"])
def test_other_launch_arguments_are_refused(uri):
    with pytest.raises(NovaError):
        rbx.clean_launch_uri(uri)


def test_start_runs_the_found_roblox_with_flags_sky_and_mods(home, monkeypatch):
    d = _install(home)
    rbx.detect()
    rbx.save_flags({"DFIntTaskSchedulerTargetFps": 144})
    rbx.set_sky_color("#00ff00")
    calls = []
    monkeypatch.setattr(rbx.subprocess, "Popen", lambda args, cwd=None: calls.append(args) or _Proc())
    rbx.start(None, app=True)
    rbx.start("roblox://experiences/start?placeId=3")
    rbx.start()
    exe = str(d / "RobloxPlayerBeta.exe")
    assert calls == [[exe, "--app"], [exe, "roblox://experiences/start?placeId=3"], [exe]]
    assert (d / "ClientSettings" / "ClientAppSettings.json").exists() and (d / "content/sky/sky512_ft.tex").read_bytes().startswith(b"\x89PNG")


def _main(monkeypatch, *args):
    import nova.app as appmod
    monkeypatch.setattr(appmod, "IS_ROBLOX", True)
    monkeypatch.setattr(appmod, "hide_child_consoles", lambda: None)
    monkeypatch.setattr(appmod, "open_window", lambda *a, **k: pytest.fail("no window expected"))
    shown = []
    monkeypatch.setattr(appmod, "_error_box", shown.append)          # a real message box would wait for a click
    return appmod.main(list(args)), shown


def test_launch_link_plays_straight_away_when_roblox_is_current(home, monkeypatch):
    _install(home)
    monkeypatch.setattr(rbx, "latest_version", lambda: VER)
    started = []
    monkeypatch.setattr(rbx, "start", lambda uri=None, app=False: started.append(uri) or _Proc())
    assert _main(monkeypatch, "--launch", "roblox-player:1+launchmode:play")[0] == 0
    assert started == ["roblox-player:1+launchmode:play"]


def test_launch_link_goes_to_roblox_launcher_when_an_update_is_out(home, monkeypatch):
    _install(home)
    monkeypatch.setattr(rbx, "latest_version", lambda: NEWER)
    handed = []
    monkeypatch.setattr(rbx, "hand_to_roblox", lambda uri: handed.append(uri) or True)
    monkeypatch.setattr(rbx, "start", lambda *a, **k: pytest.fail("an outdated Roblox must not be started directly"))
    assert _main(monkeypatch, "--launch", "roblox://experiences/start?placeId=4")[0] == 0
    assert handed == ["roblox://experiences/start?placeId=4"]


def test_launch_link_without_roblox_explains_instead_of_failing_silently(home, monkeypatch):
    monkeypatch.setattr(rbx, "hand_to_roblox", lambda uri: False)
    code, shown = _main(monkeypatch, "--launch", "roblox://experiences/start?placeId=5")
    assert code == 1 and shown and "couldn't find Roblox" in shown[0]


def test_bad_launch_link_is_refused(home, monkeypatch):
    code, shown = _main(monkeypatch, "--launch", "calc.exe --evil")
    assert code == 1 and shown and "Roblox launch link" in shown[0]


def test_roblox_launcher_handler_is_used_with_the_link(home, monkeypatch):
    rbx.write_json(rbx._state_file(), {"orig_handlers": {"roblox-player": '"C:\\Roblox\\RobloxPlayerLauncher.exe" %1'}})
    calls = []
    monkeypatch.setattr(rbx.subprocess, "Popen", lambda cmd: calls.append(cmd))
    assert rbx.hand_to_roblox("roblox-player:1+launchmode:play") is True
    assert calls == ['"C:\\Roblox\\RobloxPlayerLauncher.exe" roblox-player:1+launchmode:play']
    rbx.write_json(rbx._state_file(), {})
    assert rbx.hand_to_roblox("roblox://x") is False


# ------------------------------------------------------------------ HTTP

def test_http_routes(home, monkeypatch):
    d = _install(home)
    monkeypatch.setattr(rbx, "latest_version", lambda: NEWER)
    from nova.server import App, start_server
    start_server(App(token="tk"), 8796)

    def call(method, path, body=None, raw=None, hdr=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request("http://127.0.0.1:8796" + path, data=data, method=method, headers={"X-Nova-Token": "tk", **(hdr or {})})
        try:
            with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")

    st = call("GET", "/api/state")[1]["roblox"]
    assert st["version"] == VER and st["sky_folder"] == str(d / "content" / "sky")
    assert call("POST", "/api/roblox/check")[1] == {"latest": NEWER, "installed": VER, "update": True}
    assert call("POST", "/api/roblox/install")[0] == 404                              # Nova no longer installs Roblox
    assert call("POST", "/api/roblox/preset", {"id": "max_perf", "on": True})[1]["preset_on"]["max_perf"] is True
    assert call("POST", "/api/roblox/flags", {"flags": {"bad name": 1}})[0] == 400
    assert call("POST", "/api/roblox/sky/color", {"color": "#336699"})[1]["sky"]["set"] is True
    assert call("POST", "/api/roblox/sky-upload", raw=b"nope", hdr={"X-Face": "up"})[0] == 400
    assert call("POST", "/api/roblox/sky-upload", raw=_png(), hdr={"X-Face": "up"})[0] == 200
    assert call("POST", "/api/roblox/sky/clear")[1]["sky"]["set"] is False
    code, st = call("POST", "/api/roblox/mods-upload", raw=_zip({"content/sky/s.png": "s"}), hdr={"X-Filename": "Sky.zip"})
    assert code == 200 and st["mods"][0]["name"] == "Sky"
    assert call("POST", "/api/roblox/mods-upload", raw=b"nope", hdr={"X-Filename": "a.zip"})[0] == 400
    assert call("POST", "/api/roblox/mods/toggle", {"name": "Sky", "enabled": False})[1]["mods"][0]["enabled"] is False
    assert call("POST", "/api/roblox/mods/delete", {"name": "Sky"})[1]["mods"] == []
    assert call("POST", "/api/roblox/mods/delete", {"name": "../x"})[0] == 400
