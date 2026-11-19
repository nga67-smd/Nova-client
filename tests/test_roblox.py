"""Roblox install/update, FastFlags, mods and launch-link safety (no network: Roblox's servers are faked)."""
import hashlib
import io
import json
import urllib.error
import urllib.request
import zipfile

import pytest

from nova import roblox as rbx
from nova.util import NovaError

VER = "version-0123456789abcdef"


def _zip(files: dict) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return b.getvalue()


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    return tmp_path


def _fake_roblox(monkeypatch, version=VER, corrupt=False):
    pkgs = {"RobloxApp.zip": _zip({"RobloxPlayerBeta.exe": "exe", "content/sounds/ouch.ogg": "orig"}),
            "shaders.zip": _zip({"shaders.txt": "s"}), "unknown-thing.zip": _zip({"x": "y"})}
    manifest = "v0\n" + "".join(f"{n}\n{hashlib.md5(d).hexdigest()}\n{len(d)}\n{len(d)}\n" for n, d in pkgs.items())
    monkeypatch.setattr(rbx, "supported", lambda: True)
    monkeypatch.setattr(rbx, "http_get_json", lambda url, **k: {"clientVersionUpload": version})
    monkeypatch.setattr(rbx, "http_get_text", lambda url, **k: manifest)

    def dl(url, dest, **k):
        name = url.rsplit(f"{version}-", 1)[1]
        dest.write_bytes(b"corrupt" if corrupt else pkgs[name])
        return dest
    monkeypatch.setattr(rbx, "download_file", dl)


def test_manifest_parsing_and_bad_input():
    m = rbx.parse_manifest("v0\nRobloxApp.zip\n" + "a" * 32 + "\n10\n20\n")
    assert m == [{"name": "RobloxApp.zip", "md5": "a" * 32, "size": 10}]
    with pytest.raises(NovaError):
        rbx.parse_manifest("v9\nx")
    with pytest.raises(NovaError):
        rbx.parse_manifest("v0\n../evil.zip\n" + "a" * 32 + "\n1\n1\n")


def test_install_unpacks_official_packages_and_replaces_old_versions(home, monkeypatch):
    _fake_roblox(monkeypatch)
    old = rbx.versions_root() / "version-ffffffffffffffff"
    old.mkdir(parents=True)
    assert rbx.installed_version() == ""
    assert rbx.install() == VER and rbx.installed_version() == VER
    d = rbx.version_dir()
    assert (d / "RobloxPlayerBeta.exe").read_text() == "exe" and (d / "shaders" / "shaders.txt").exists()
    assert (d / "AppSettings.xml").exists() and not old.exists() and not (d / "x").exists()    # unknown packages are skipped
    assert rbx.install() == VER                                                                 # already current: nothing to do
    rbx.uninstall()
    assert rbx.installed_version() == ""


def test_corrupt_download_is_rejected_and_not_installed(home, monkeypatch):
    _fake_roblox(monkeypatch, corrupt=True)
    with pytest.raises(NovaError, match="didn't download correctly"):
        rbx.install()
    assert rbx.installed_version() == "" and not (rbx.versions_root() / VER).exists()


def test_install_needs_windows(home, monkeypatch):
    monkeypatch.setattr(rbx, "supported", lambda: False)
    with pytest.raises(NovaError, match="Windows"):
        rbx.install()


def test_flags_validate_save_and_write_into_the_game(home, monkeypatch):
    _fake_roblox(monkeypatch)
    rbx.install()
    saved = rbx.save_flags({"DFIntTaskSchedulerTargetFps": "144", "FFlagX": "True", "FStringY": "hello"})
    assert saved == {"DFIntTaskSchedulerTargetFps": 144, "FFlagX": True, "FStringY": "hello"}
    for bad in ({"bad name": 1}, {"../x": 1}, {"FFlagOk": [1]}):
        with pytest.raises(NovaError):
            rbx.save_flags(bad)
    rbx.write_flags(rbx.version_dir())
    f = rbx.version_dir() / "ClientSettings" / "ClientAppSettings.json"
    assert json.loads(f.read_text())["DFIntTaskSchedulerTargetFps"] == 144
    rbx.apply_preset("fps_240", True)
    assert rbx.load_flags()["DFIntTaskSchedulerTargetFps"] == 240 and rbx.status()["preset_on"]["fps_240"] is True
    rbx.apply_preset("fps_240", False)
    assert "DFIntTaskSchedulerTargetFps" not in rbx.load_flags()
    rbx.save_flags({})
    rbx.write_flags(rbx.version_dir())
    assert not f.exists()
    with pytest.raises(NovaError):
        rbx.apply_preset("nope", True)


def test_mods_overlay_and_restore_originals(home, monkeypatch):
    _fake_roblox(monkeypatch)
    rbx.install()
    tmp = home / "m.zip"
    tmp.write_bytes(_zip({"content/sounds/ouch.ogg": "MOD", "content/sky/new.png": "sky"}))
    name = rbx.import_mod_zip(tmp, "Quiet Pack.zip")
    assert name == "Quiet Pack" and rbx.mods_info() == [{"name": "Quiet Pack", "files": 2, "enabled": True}]
    d = rbx.version_dir()
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
    assert not (home.parent / "escape.txt").exists() and rbx.mods_info() == []


@pytest.mark.parametrize("uri", ["roblox-player:1+launchmode:play+gameinfo:abc+placelauncherurl:https%3A%2F%2Fx",
                                 "roblox://experiences/start?placeId=1"])
def test_launch_links_are_accepted(uri):
    assert rbx.clean_launch_uri(uri) == uri


@pytest.mark.parametrize("uri", ["", "https://evil.example", "calc.exe", "roblox://x --flag", 'roblox://x"&calc', "roblox://x\ny", "file:///c:/a"])
def test_other_launch_arguments_are_refused(uri):
    with pytest.raises(NovaError):
        rbx.clean_launch_uri(uri)


def test_http_routes(home, monkeypatch):
    _fake_roblox(monkeypatch)
    from nova.server import App, start_server
    start_server(App(token="tk"), 8796)

    def call(method, path, body=None, raw=None, hdr=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request("http://127.0.0.1:8796" + path, data=data, method=method, headers={"X-Nova-Token": "tk", **(hdr or {})})
        try:
            with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")

    assert call("GET", "/api/state")[1]["roblox"]["version"] == ""
    code, c = call("POST", "/api/roblox/check")
    assert code == 200 and c["latest"] == VER and c["update"] is False
    code, t = call("POST", "/api/roblox/install")
    assert code == 200
    import time
    for _ in range(50):
        st = call("GET", "/api/tasks")[1]["tasks"]
        if all(x["status"] != "running" for x in st):
            break
        time.sleep(0.1)
    assert call("GET", "/api/state")[1]["roblox"]["version"] == VER
    assert call("POST", "/api/roblox/preset", {"id": "no_grass", "on": True})[1]["preset_on"]["no_grass"] is True
    assert call("POST", "/api/roblox/flags", {"flags": {"bad name": 1}})[0] == 400
    z = _zip({"content/sky/s.png": "s"})
    code, st = call("POST", "/api/roblox/mods-upload", raw=z, hdr={"X-Filename": "Sky.zip"})
    assert code == 200 and st["mods"][0]["name"] == "Sky"
    assert call("POST", "/api/roblox/mods-upload", raw=b"nope", hdr={"X-Filename": "a.zip"})[0] == 400
    assert call("POST", "/api/roblox/mods/toggle", {"name": "Sky", "enabled": False})[1]["mods"][0]["enabled"] is False
    assert call("POST", "/api/roblox/mods/delete", {"name": "Sky"})[1]["mods"] == []
    assert call("POST", "/api/roblox/mods/delete", {"name": "../x"})[0] == 400


class _Proc:
    def __init__(self):
        self.n = 0

    def poll(self):
        self.n += 1
        return None if self.n < 2 else 0


def test_launch_link_fast_path_opens_roblox_without_a_window(home, monkeypatch):
    import nova.app as appmod
    _fake_roblox(monkeypatch)
    rbx.install()
    started = []
    monkeypatch.setattr(rbx, "start", lambda uri=None: started.append(uri) or _Proc())
    monkeypatch.setattr(appmod, "IS_ROBLOX", True)
    monkeypatch.setattr(appmod, "hide_child_consoles", lambda: None)      # it patches subprocess for the whole test run
    monkeypatch.setattr(appmod, "open_window", lambda *a, **k: pytest.fail("no window expected"))
    assert appmod.main(["--launch", "roblox-player:1+launchmode:play", "--port", "0"]) == 0
    assert started == ["roblox-player:1+launchmode:play"]


def test_launch_link_waits_for_install_then_plays(home, monkeypatch):
    from nova.server import App
    _fake_roblox(monkeypatch)
    started = []
    monkeypatch.setattr(rbx, "start", lambda uri=None: started.append(uri) or _Proc())
    app = App()
    app.pending_uri = "roblox://experiences/start?placeId=1"
    t = app.start_roblox_install()
    import time
    for _ in range(60):
        if t.status != "running":
            break
        time.sleep(0.1)
    assert t.status == "done" and started == ["roblox://experiences/start?placeId=1"] and app.pending_uri is None


def test_bad_launch_link_is_refused(home, monkeypatch):
    import nova.app as appmod
    shown = []
    monkeypatch.setattr(appmod, "IS_ROBLOX", True)
    monkeypatch.setattr(appmod, "hide_child_consoles", lambda: None)
    monkeypatch.setattr(appmod, "_error_box", shown.append)          # a real message box would wait for a click
    assert appmod.main(["--launch", "calc.exe --evil"]) == 1
    assert shown and "Roblox launch link" in shown[0]


def test_existing_roblox_on_the_pc_can_be_used_without_downloading(home, monkeypatch, tmp_path):
    local = tmp_path / "local"
    mine = local / "Roblox" / "Versions" / VER
    mine.mkdir(parents=True)
    (mine / "RobloxPlayerBeta.exe").write_text("exe")
    (local / "Roblox" / "Versions" / "version-aaaaaaaaaaaaaaaa").mkdir()          # an empty leftover folder: ignored
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    assert rbx.installed_version() == "" and rbx.status()["existing"][0]["version"] == VER
    assert rbx.adopt_existing("C:/not/offered") == ""                             # only folders Nova found itself are accepted
    assert rbx.adopt_existing() == VER and rbx.installed_version() == VER and rbx.is_external()
    assert rbx.version_dir() == mine
    rbx.save_flags({"DFIntTaskSchedulerTargetFps": 144})
    rbx.write_flags(rbx.version_dir())
    assert (mine / "ClientSettings" / "ClientAppSettings.json").exists()
    rbx.uninstall()                                                                # never deletes Roblox's own folder
    assert rbx.installed_version() == "" and (mine / "RobloxPlayerBeta.exe").exists()


def test_launch_link_uses_an_existing_roblox(home, monkeypatch, tmp_path):
    import nova.app as appmod
    local = tmp_path / "local"
    (local / "Roblox" / "Versions" / VER).mkdir(parents=True)
    (local / "Roblox" / "Versions" / VER / "RobloxPlayerBeta.exe").write_text("exe")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    _fake_roblox(monkeypatch)                                                       # Roblox says VER is current
    started = []
    monkeypatch.setattr(rbx, "start", lambda uri=None: started.append(uri) or _Proc())
    monkeypatch.setattr(appmod, "IS_ROBLOX", True)
    monkeypatch.setattr(appmod, "hide_child_consoles", lambda: None)
    monkeypatch.setattr(appmod, "open_window", lambda *a, **k: pytest.fail("no window expected"))
    assert appmod.main(["--launch", "roblox://experiences/start?placeId=2"]) == 0
    assert started == ["roblox://experiences/start?placeId=2"] and rbx.is_external()
