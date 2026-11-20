"""Roblox detection, FastFlags, sky, mods and launch-link safety (no Roblox needed: installs are faked in a temp folder)."""
import os
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


def _png(w=512, h=512, color=(0x10, 0x20, 0x30), filt=0, ctype=2):
    """A PNG of one color or (when color is a function) a gradient, written with the given PNG row filter."""
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    chans = {2: 3, 6: 4}[ctype]
    rows = [bytes(v for x in range(w) for v in ((color(x, y) if callable(color) else color) + ((255,) if ctype == 6 else ()))) for y in range(h)]
    out, prev = b"", bytes(w * chans)
    for r in rows:
        if filt == 0:
            enc = r
        elif filt == 1:
            enc = bytes((r[i] - (r[i - chans] if i >= chans else 0)) & 255 for i in range(len(r)))
        elif filt == 2:
            enc = bytes((r[i] - prev[i]) & 255 for i in range(len(r)))
        elif filt == 3:
            enc = bytes((r[i] - (((r[i - chans] if i >= chans else 0) + prev[i]) >> 1)) & 255 for i in range(len(r)))
        else:
            def paeth(i):
                a_, b_, c_ = (r[i - chans] if i >= chans else 0), prev[i], (prev[i - chans] if i >= chans else 0)
                pa, pb, pc = abs(b_ - c_), abs(a_ - c_), abs(a_ + b_ - 2 * c_)
                return a_ if pa <= pb and pa <= pc else b_ if pb <= pc else c_
            enc = bytes((r[i] - paeth(i)) & 255 for i in range(len(r)))
        out += bytes([filt]) + enc
        prev = r
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(out)) + chunk(b"IEND", b"")


def _dxt1_pixel(dds: bytes, x: int, y: int, w: int = 512):
    """Read one pixel back out of a DXT1 DDS."""
    assert dds[:4] == b"DDS " and dds[84:88] == b"DXT1"
    blk = 128 + ((y // 4) * (w // 4) + x // 4) * 8
    c0, c1, idx = struct.unpack("<HHI", dds[blk:blk + 8])
    def rgb(c): return ((c >> 11 & 31) * 255 // 31, (c >> 5 & 63) * 255 // 63, (c & 31) * 255 // 31)
    p0, p1 = rgb(c0), rgb(c1)
    pal = [p0, p1, tuple((2 * a + b) // 3 for a, b in zip(p0, p1)), tuple((a + 2 * b) // 3 for a, b in zip(p0, p1))]
    return pal[(idx >> (2 * ((y % 4) * 4 + x % 4))) & 3]


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

def test_png_reader_handles_every_row_filter_and_color_type(home):
    grad = lambda x, y: ((x * 3) & 255, (y * 5) & 255, (x + y) & 255)
    for filt in range(5):
        for ctype in (2, 6):
            w, h, rgb = rbx.decode_png(_png(32, 16, grad, filt, ctype))
            assert (w, h) == (32, 16) and rgb[:3] == bytes(grad(0, 0)) and rgb[(5 * 32 + 7) * 3:(5 * 32 + 7) * 3 + 3] == bytes(grad(7, 5))
    for bad in (b"", b"GIF89a....", b"\x89PNG\r\n\x1a\n"):
        with pytest.raises(NovaError):
            rbx.decode_png(bad)


def test_dxt1_file_has_the_layout_roblox_expects_and_keeps_the_colors(home):
    w, h, rgb = rbx.decode_png(_png(512, 512, lambda x, y: (x // 2, 255 - y // 2, 90)))
    dds = rbx.encode_dxt1(w, h, rgb)
    assert len(dds) == 128 + 512 * 512 // 2 and struct.unpack("<II", dds[4:12]) == (124, 0x81007)
    assert struct.unpack("<II", dds[12:20]) == (512, 512) and struct.unpack("<I", dds[20:24])[0] == 512 * 512 // 2
    for x, y in ((0, 0), (255, 100), (511, 511), (300, 17)):
        got, want = _dxt1_pixel(dds, x, y), (x // 2, 255 - y // 2, 90)
        assert all(abs(a - b) <= 14 for a, b in zip(got, want)), (x, y, got, want)


def test_sky_color_and_pictures_become_roblox_sky_files_and_are_restored(home):
    d = _install(home)
    rbx.detect()
    assert rbx.sky_info()["set"] is False
    rbx.set_sky_color("#336699")
    assert rbx.sky_info()["set"] and all(rbx.sky_info()["faces"].values())
    assert rbx.apply_sky_now() is True
    sky = d / "content" / "sky"
    for code in ("ft", "up", "bk"):
        data = (sky / f"sky512_{code}.tex").read_bytes()
        assert data[:4] == b"DDS " and len(data) == 128 + 512 * 512 // 2
    r, g, b = _dxt1_pixel((sky / "sky512_ft.tex").read_bytes(), 100, 100)
    assert abs(r - 0x33) <= 8 and abs(g - 0x66) <= 8 and abs(b - 0x99) <= 8
    up = home / "up.png"
    up.write_bytes(_png(512, 512, (250, 0, 0)))
    rbx.set_sky_image("up", up)
    assert not up.exists() and rbx.apply_sky_now()
    assert _dxt1_pixel((sky / "sky512_up.tex").read_bytes(), 9, 9)[0] > 230 and _dxt1_pixel((sky / "sky512_ft.tex").read_bytes(), 9, 9)[0] < 80
    rbx.clear_sky()
    assert rbx.sky_info()["set"] is False and rbx.apply_sky_now()
    assert (sky / "sky512_ft.tex").read_text() == "orig-ft" and (sky / "sky512_up.tex").read_text() == "orig-up"
    assert rbx.mods_info() == []                                                  # the sky isn't shown as a normal mod


def test_sky_input_is_checked(home):
    f = home / "x.bin"
    for bad in (b"MZ not a picture", b"GIF89a....", b""):
        f.write_bytes(bad)
        with pytest.raises(NovaError):
            rbx.set_sky_image("all", f)
        assert not f.exists()
    f.write_bytes(_png(64, 64))                                                    # not 512x512: the app resizes before sending
    with pytest.raises(NovaError, match="512x512"):
        rbx.set_sky_image("all", f)
    f.write_bytes(_png())
    with pytest.raises(NovaError):
        rbx.set_sky_image("ceiling", f)
    for color in ("red", "#12345", "url(x)", ""):
        with pytest.raises(NovaError):
            rbx.set_sky_color(color)
    f.write_bytes(_png())
    assert all(rbx.set_sky_image("all", f)["faces"].values())


def test_sky_goes_where_this_roblox_keeps_its_sky_and_falls_back(home):
    d = _install(home)
    import shutil
    shutil.rmtree(d / "content" / "sky")
    new = d / "PlatformContent" / "pc" / "textures" / "sky"                          # where current Roblox keeps them
    new.mkdir(parents=True)
    for code in ("bk", "dn", "ft", "lf", "rt", "up"):
        (new / f"sky512_{code}.tex").write_text("orig-" + code)
    rbx.detect()
    assert rbx.sky_folder(d) == new
    rbx.set_sky_color("#ff0000")
    assert rbx.apply_sky_now() and (new / "sky512_dn.tex").read_bytes()[:4] == b"DDS "
    rbx.clear_sky()
    rbx.apply_sky_now()
    assert (new / "sky512_dn.tex").read_text() == "orig-dn"
    shutil.rmtree(new)                                                                # no sky files at all: the usual place
    rbx.set_sky_color("#00ff00")
    rbx.build_sky_mod(d)
    assert (rbx.mods_dir() / "Nova Sky" / "PlatformContent/pc/textures/sky/sky512_ft.tex").exists()


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
    assert (d / "ClientSettings" / "ClientAppSettings.json").exists() and (d / "content/sky/sky512_ft.tex").read_bytes()[:4] == b"DDS "


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
    assert (d / "content" / "sky" / "sky512_up.tex").read_bytes()[:4] == b"DDS "
    assert call("POST", "/api/roblox/sky/clear")[1]["sky"]["set"] is False
    code, st = call("POST", "/api/roblox/mods-upload", raw=_zip({"content/sky/s.png": "s"}), hdr={"X-Filename": "Sky.zip"})
    assert code == 200 and st["mods"][0]["name"] == "Sky"
    assert call("POST", "/api/roblox/mods-upload", raw=b"nope", hdr={"X-Filename": "a.zip"})[0] == 400
    assert call("POST", "/api/roblox/mods/toggle", {"name": "Sky", "enabled": False})[1]["mods"][0]["enabled"] is False
    assert call("POST", "/api/roblox/mods/delete", {"name": "Sky"})[1]["mods"] == []
    assert call("POST", "/api/roblox/mods/delete", {"name": "../x"})[0] == 400


def test_sky_check_says_whether_your_sky_is_in_the_game_files(home):
    d = _install(home)
    rbx.detect()
    assert set(rbx.sky_check()["files"].values()) == {"default"}
    rbx.set_sky_color("#336699")
    rbx.apply_sky_now()
    chk = rbx.sky_check()
    assert set(chk["files"].values()) == {"yours"} and chk["found_files"] == 6 and chk["version"] == VER
    (d / "content" / "sky" / "sky512_ft.tex").write_text("put back by a launcher")        # something restored a file
    assert rbx.sky_check()["files"]["front"] == "original" and rbx.sky_check()["files"]["back"] == "yours"
    assert rbx.apply_sky_now() and rbx.sky_check()["files"]["front"] == "yours"


def test_bloxstrap_family_launchers_get_the_mods_in_their_own_modifications_folder(home):
    d = _install(home, VER, "Voidstrap")
    assert rbx.detect() == VER and rbx.status()["from"] == "Voidstrap"
    rbx.set_sky_color("#ff00ff")
    assert rbx.apply_sky_now()
    mods = home / "local" / "Voidstrap" / "Modifications"
    assert rbx.sky_check()["launcher_folder"] == str(mods)
    assert (mods / "content" / "sky" / "sky512_ft.tex").read_bytes()[:4] == b"DDS " and (d / "content/sky/sky512_ft.tex").read_bytes()[:4] == b"DDS "
    (mods / "content" / "sounds").mkdir(parents=True)
    (mods / "content" / "sounds" / "mine.ogg").write_text("the person's own mod")             # their own files are left alone
    rbx.clear_sky()
    rbx.apply_sky_now()
    assert not (mods / "content" / "sky" / "sky512_ft.tex").exists() and (mods / "content" / "sounds" / "mine.ogg").exists()
    assert (d / "content/sky/sky512_ft.tex").read_text() == "orig-ft"


def test_mods_remembered_by_the_earlier_format_are_still_undone(home):
    d = _install(home)
    rbx.detect()
    (d / "content" / "sounds" / "ouch.ogg").write_text("MOD")                                # an earlier Nova had put this here
    (rbx.root() / "ModBackup" / "content" / "sounds").mkdir(parents=True)
    (rbx.root() / "ModBackup" / "content" / "sounds" / "ouch.ogg").write_text("orig")
    rbx.write_json(rbx.root() / "mods_applied.json", {"_version": VER, "files": {"content/sounds/ouch.ogg": True}})
    rbx.apply_mods(d)
    assert (d / "content/sounds/ouch.ogg").read_text() == "orig"


def test_ready_made_skies_are_valid_textures(home):
    d = _install(home)
    rbx.detect()
    for name in rbx.SKY_PRESETS:
        rbx.set_sky_preset(name)
        assert rbx.apply_sky_now()
        for code in ("ft", "up", "dn"):
            data = (d / "content" / "sky" / f"sky512_{code}.tex").read_bytes()
            assert data[:4] == b"DDS " and len(data) == 128 + 512 * 512 // 2
    top = _dxt1_pixel((d / "content" / "sky" / "sky512_ft.tex").read_bytes(), 100, 2)
    low = _dxt1_pixel((d / "content" / "sky" / "sky512_ft.tex").read_bytes(), 100, 509)
    assert top != low                                                             # a gradient, not a flat color
    try:
        rbx.set_sky_preset("nope")
        assert False
    except rbx.NovaError:
        pass


def test_cleanup_clears_logs_and_temp_only(home, monkeypatch):
    la, tmp = home / "la", home / "tmp"
    (la / "Roblox" / "logs").mkdir(parents=True); (tmp / "Roblox" / "x").mkdir(parents=True)
    (la / "Roblox" / "logs" / "a.log").write_bytes(b"x" * 1000)
    (tmp / "Roblox" / "x" / "b.bin").write_bytes(b"y" * 500)
    (la / "Roblox" / "keep.txt").write_text("keep")
    monkeypatch.setenv("LOCALAPPDATA", str(la)); monkeypatch.setenv("TEMP", str(tmp))
    assert rbx.cleanup_info()["bytes"] == 1500
    assert rbx.cleanup()["freed"] == 1500
    assert rbx.cleanup_info()["bytes"] == 0 and (la / "Roblox" / "keep.txt").exists()


def test_sky_pack_zip_becomes_the_sky_and_one_folder_opens(home, monkeypatch):
    import io, zipfile
    d = _install(home)
    rbx.detect()
    dds = rbx.encode_dxt1(512, 512, bytes((200, 30, 30)) * 512 * 512)
    z = home / "pack.zip"
    with zipfile.ZipFile(z, "w") as f:
        for code in ("bk", "dn", "ft", "lf", "rt", "up"):
            f.writestr(f"Skybox Fix/PlatformContent/pc/textures/sky/sky512_{code}.tex", dds)
        f.writestr("readme.txt", "hi")
    rbx.import_sky_pack(z)
    assert not z.exists() and all(rbx.sky_info()["faces"].values()) and rbx.apply_sky_now()
    assert (d / "content" / "sky" / "sky512_ft.tex").read_bytes() == dds
    bad = home / "bad.zip"
    with zipfile.ZipFile(bad, "w") as f:
        f.writestr("a.txt", "x")
    try:
        rbx.import_sky_pack(bad)
        assert False
    except rbx.NovaError:
        pass
    assert rbx.sky_pack_folder().is_dir()


def test_skybox_fix_follows_the_sky(home, monkeypatch):
    import stat
    la = home / "local"
    d = _install(home)
    rbx.detect()
    assert not rbx.skyfix_on()
    rbx.set_sky_color("#112233")
    assert rbx.apply_sky_now() and rbx.skyfix_on()
    f = la / "Roblox" / "rbx-storage" / "a5" / "a564ec8aeef3614e788d02f0090089d8"
    assert f.read_bytes()[:4] == b"RBXH" and not f.stat().st_mode & stat.S_IWUSR    # read-only so Roblox leaves it
    rbx.apply_sky_now()                                                          # again over a read-only file
    assert rbx.skyfix_on()
    rbx.set_skyfix(False)
    assert not rbx.skyfix_on() and rbx.status()["skyfix"]["enabled"] is False
    rbx.set_skyfix(True)
    assert rbx.skyfix_on()
    rbx.clear_sky(); rbx.apply_sky_now()
    assert not rbx.skyfix_on() and not f.exists()


def test_refresh_happens_when_roblox_closes(home):
    d = _install(home)
    rbx.detect()
    rbx.set_sky_color("#445566")
    assert rbx.apply_sky_now()
    f = d / "content" / "sky" / "sky512_ft.tex"
    f.write_text("put back by an update")                                           # Roblox undid it while it ran
    state = {"on": True}
    w = rbx.CloseWatcher(lambda: state["on"])
    assert w.tick() is False and f.read_text() == "put back by an update"           # still open: nothing happens
    state["on"] = False
    assert w.tick() is True and f.read_bytes()[:4] == b"DDS "                       # closed: sky is back
    assert w.tick() is False                                                         # only once per close
