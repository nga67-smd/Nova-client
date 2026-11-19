"""Find the Roblox that is already on this PC, tune it (FastFlags, skies, mods) and start it.

Nova does not download or install Roblox. It looks for Roblox (or a Bloxstrap-style launcher's copy) on the device,
puts your FastFlags, custom sky and mods into that copy, and starts it. Roblox keeps updating itself: when a newer
version is out, Nova hands the game to Roblox's own launcher first. Sign-in stays in your browser.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

from . import paths
from .util import NovaError, http_get_json, read_json, safe_extract_zip, write_json

VERSION_URL = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
PLAYER_EXE = "RobloxPlayerBeta.exe"
VERSION_RX = re.compile(r"^version-[0-9a-f]{8,32}$")
LAUNCHERS = (("Roblox", "Roblox"), ("Bloxstrap", "Bloxstrap"), ("Voidstrap", "Voidstrap"), ("Fishstrap", "Fishstrap"))


def supported() -> bool:
    return sys.platform.startswith("win")


def root() -> Path:
    return paths.sub("Roblox")


def mods_dir() -> Path:
    d = root() / "Mods"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_file() -> Path:
    return root() / "state.json"


def _state() -> dict:
    return read_json(_state_file(), {}) or {}


# ------------------------------------------------------------------ finding Roblox on this PC

def existing_installs() -> list[dict]:
    """Every Roblox found on this PC, newest first."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return []
    found = []
    for label, sub in LAUNCHERS:
        vroot = Path(base) / sub / "Versions"
        if not vroot.is_dir():
            continue
        for d in vroot.iterdir():
            if VERSION_RX.match(d.name) and (d / PLAYER_EXE).exists():
                found.append({"version": d.name, "from": label, "path": str(d), "_t": (d / PLAYER_EXE).stat().st_mtime})
    found.sort(key=lambda x: x["_t"], reverse=True)
    for f in found:
        f.pop("_t")
    return found


def detect() -> str:
    """Look for Roblox on the device and remember the newest copy. Returns its version, or '' when there is none."""
    options = existing_installs()
    if not options:
        st = _state()
        if st.get("dir") and not (Path(st["dir"]) / PLAYER_EXE).exists():
            _state_file().unlink(missing_ok=True)           # the copy we knew about is gone
        return ""
    pick = options[0]
    st = _state()
    if st.get("dir") != pick["path"]:
        write_json(_state_file(), {**st, "version": pick["version"], "dir": pick["path"], "from": pick["from"], "found": time.time()})
    return pick["version"]


def installed_version() -> str:
    st = _state()
    return st["version"] if st.get("dir") and VERSION_RX.match(st.get("version", "")) and (Path(st["dir"]) / PLAYER_EXE).exists() else ""


def version_dir() -> Path:
    st = _state()
    if not installed_version():
        raise NovaError("Nova couldn't find Roblox on this PC. Install it from roblox.com first.")
    return Path(st["dir"])


def latest_version() -> str:
    data = http_get_json(VERSION_URL)
    v = (data or {}).get("clientVersionUpload", "")
    if not VERSION_RX.match(v):
        raise NovaError("Roblox didn't say which version is current. Try again in a moment.")
    return v


# ------------------------------------------------------------------ FastFlags

FLAG_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,120}$")

PRESETS = {
    "max_perf": {"name": "Maximum performance", "desc": "Lowest quality everywhere: no shadows, post effects or grass, lowest textures and no anti-aliasing. Fewer effects means less lag.",
                 "flags": {"DFIntDebugFRMQualityLevelOverride": 1, "FIntRenderShadowIntensity": 0, "FFlagDisablePostFx": True,
                           "FIntFRMMinGrassDistance": 0, "FIntFRMMaxGrassDistance": 0, "DFFlagTextureQualityOverrideEnabled": True,
                           "DFIntTextureQualityOverride": 0, "FIntDebugForceMSAASamples": 1}},
    "fps_144": {"name": "Unlock FPS to 144", "desc": "Raises Roblox's 60 FPS limit.", "flags": {"DFIntTaskSchedulerTargetFps": 144}},
    "fps_240": {"name": "Unlock FPS to 240", "desc": "For high refresh rate screens.", "flags": {"DFIntTaskSchedulerTargetFps": 240}},
    "fps_off": {"name": "No FPS limit", "desc": "Runs as fast as your PC allows.", "flags": {"DFIntTaskSchedulerTargetFps": 9999}},
    "dx11": {"name": "Use DirectX 11", "desc": "The most compatible graphics API.", "flags": {"FFlagDebugGraphicsPreferD3D11": True}},
    "vulkan": {"name": "Use Vulkan", "desc": "Can be faster on newer graphics cards.", "flags": {"FFlagDebugGraphicsPreferVulkan": True}},
    "no_grass": {"name": "No grass", "desc": "Fewer details to draw, more FPS.", "flags": {"FIntFRMMinGrassDistance": 0, "FIntFRMMaxGrassDistance": 0}},
    "no_post": {"name": "Turn off post effects", "desc": "Disables bloom and similar effects.", "flags": {"FFlagDisablePostFx": True}},
    "low_textures": {"name": "Low textures", "desc": "Uses less video memory.", "flags": {"DFFlagTextureQualityOverrideEnabled": True, "DFIntTextureQualityOverride": 0}},
}


def clean_flag(name, value):
    if not isinstance(name, str) or not FLAG_NAME.match(name):
        raise NovaError(f"'{name}' isn't a valid flag name (letters, numbers and underscores only).")
    if isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, str) and len(value) <= 200:
        v = value.strip()
        if v.lower() in ("true", "false"):
            return v.lower() == "true"
        if re.fullmatch(r"-?\d{1,12}", v):
            return int(v)
        return v
    raise NovaError(f"'{name}' needs a true/false, a whole number or short text.")


def load_flags() -> dict:
    raw = read_json(root() / "flags.json", {}) or {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and FLAG_NAME.match(k) and isinstance(v, (bool, int, str))}


def save_flags(flags: dict) -> dict:
    if not isinstance(flags, dict) or len(flags) > 300:
        raise NovaError("Flags must be a list of names and values (up to 300).")
    clean = {k: clean_flag(k, v) for k, v in flags.items()}
    write_json(root() / "flags.json", clean)
    return clean


def apply_preset(pid: str, on: bool) -> dict:
    if pid not in PRESETS:
        raise NovaError("Unknown preset.")
    flags = load_flags()
    for k, v in PRESETS[pid]["flags"].items():
        if on:
            flags[k] = v
        else:
            flags.pop(k, None)
    return save_flags(flags)


def preset_states(flags: dict) -> dict:
    return {pid: all(flags.get(k) == v for k, v in p["flags"].items()) for pid, p in PRESETS.items()}


def write_flags(vdir: Path) -> None:
    flags = load_flags()
    f = vdir / "ClientSettings" / "ClientAppSettings.json"
    if flags:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(flags, indent=2), encoding="utf-8")
    else:
        f.unlink(missing_ok=True)


# ------------------------------------------------------------------ mods (files laid over the game folder)

def mod_names(managed: bool = False) -> list[str]:
    """Folders in Mods. The custom sky Nova builds itself is only included on request."""
    return sorted(p.name for p in mods_dir().iterdir() if p.is_dir() and (managed or p.name != SKY_MOD))


def mods_info() -> list[dict]:
    disabled = set((read_json(root() / "mods_off.json", []) or []))
    out = []
    for name in mod_names():
        files = [f for f in (mods_dir() / name).rglob("*") if f.is_file()]
        out.append({"name": name, "files": len(files), "enabled": name not in disabled})
    return out


def set_mod_enabled(name: str, enabled: bool) -> None:
    if name not in mod_names():
        raise NovaError("That mod isn't in your Mods folder.")
    off = set((read_json(root() / "mods_off.json", []) or []))
    (off.discard if enabled else off.add)(name)
    write_json(root() / "mods_off.json", sorted(off))


def delete_mod(name: str) -> None:
    if name not in mod_names():
        raise NovaError("That mod isn't in your Mods folder.")
    shutil.rmtree(mods_dir() / name, ignore_errors=True)


def import_mod_zip(tmp: Path, filename: str) -> str:
    if not zipfile.is_zipfile(tmp):
        tmp.unlink(missing_ok=True)
        raise NovaError("Mods are imported as .zip files. The folders inside should match Roblox's (content, ExtraContent, ...).")
    base = re.sub(r"[^A-Za-z0-9 _.-]+", "", Path(filename or "mod").stem).strip(" .") or "mod"
    name, n = base, 2
    while (mods_dir() / name).exists() or name == SKY_MOD:
        name, n = f"{base} {n}", n + 1
    dest = mods_dir() / name
    try:
        dest.mkdir()
        safe_extract_zip(tmp, dest)
        kids = [p for p in dest.iterdir()]                       # a zip with one wrapping folder: unwrap it
        if len(kids) == 1 and kids[0].is_dir() and kids[0].name.lower() not in ("content", "extracontent", "platformcontent", "shaders", "ssl", "clientsettings"):
            inner = kids[0]
            for item in list(inner.iterdir()):
                shutil.move(str(item), str(dest / item.name))
            inner.rmdir()
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    finally:
        tmp.unlink(missing_ok=True)
    return name


def _wanted_mod_files() -> dict[str, Path]:
    off = set((read_json(root() / "mods_off.json", []) or []))
    want: dict[str, Path] = {}
    for name in mod_names(managed=True):
        if name in off:
            continue
        base = mods_dir() / name
        for f in sorted(base.rglob("*")):
            if f.is_file():
                rel = f.relative_to(base).as_posix()
                if rel.lower() != "readme.txt" and not rel.startswith(".."):
                    want[rel] = f
    return want


def apply_mods(vdir: Path) -> int:
    """Lay enabled mods over the game folder; put the original file back when a mod is switched off or removed."""
    log_file, backup = root() / "mods_applied.json", root() / "ModBackup"
    applied: dict = read_json(log_file, {}) or {}
    if applied.get("_version") != vdir.name:                      # a fresh install has nothing of ours in it
        applied = {"_version": vdir.name}
        shutil.rmtree(backup, ignore_errors=True)
    files = applied.setdefault("files", {})
    want = _wanted_mod_files()
    for rel in list(files):
        if rel not in want:
            target = vdir / rel
            if files[rel]:
                b = backup / rel
                if b.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(b, target)
            else:
                target.unlink(missing_ok=True)
            del files[rel]
    for rel, src in want.items():
        target = (vdir / rel).resolve()
        if vdir.resolve() not in target.parents:
            continue
        if rel not in files:
            had = target.exists()
            if had:
                (backup / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup / rel)
            files[rel] = had
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    write_json(log_file, applied)
    return len(want)


# ------------------------------------------------------------------ sky

SKY_FACES = {"front": "ft", "back": "bk", "left": "lf", "right": "rt", "up": "up", "down": "dn"}
SKY_MOD = "Nova Sky"                                  # the folder Nova keeps in Mods for the custom sky
SKY_FILE = re.compile(r"^(sky\d*_)(bk|dn|ft|lf|rt|up)\.(\w+)$", re.I)


def _sky_dir() -> Path:
    d = root() / "Sky"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sniff_image(path: Path) -> str:
    try:
        with open(path, "rb") as f:
            h = f.read(8)
    except OSError:
        return ""
    return "png" if h.startswith(b"\x89PNG\r\n\x1a\n") else "jpg" if h.startswith(b"\xff\xd8\xff") else ""


def solid_png(color: str, size: int = 512) -> bytes:
    """A plain one-color picture, made without any image library."""
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color or ""):
        raise NovaError("Pick a color.")
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    row = b"\x00" + bytes((r, g, b)) * size

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(row * size, 9)) + chunk(b"IEND", b""))


def _face_file(face: str) -> Path | None:
    for ext in ("png", "jpg"):
        p = _sky_dir() / f"{face}.{ext}"
        if p.exists():
            return p
    return None


def sky_info() -> dict:
    return {"faces": {f: bool(_face_file(f)) for f in SKY_FACES}, "set": any(_face_file(f) for f in SKY_FACES)}


def set_sky_color(color: str) -> dict:
    data = solid_png(color)
    clear_sky()
    for face in SKY_FACES:
        (_sky_dir() / f"{face}.png").write_bytes(data)
    return sky_info()


def set_sky_image(face: str, tmp: Path) -> dict:
    """Use a picture for one side of the sky, or ('all') for every side."""
    if face != "all" and face not in SKY_FACES:
        tmp.unlink(missing_ok=True)
        raise NovaError("Unknown side of the sky.")
    ext = sniff_image(tmp)
    if not ext:
        tmp.unlink(missing_ok=True)
        raise NovaError("Sky pictures must be PNG or JPEG.")
    if tmp.stat().st_size > 32 * 1024 * 1024:
        tmp.unlink(missing_ok=True)
        raise NovaError("Pictures must be under 32 MB.")
    faces = list(SKY_FACES) if face == "all" else [face]
    for f in faces:
        for e in ("png", "jpg"):
            (_sky_dir() / f"{f}.{e}").unlink(missing_ok=True)
        shutil.copyfile(tmp, _sky_dir() / f"{f}.{ext}")
    tmp.unlink(missing_ok=True)
    return sky_info()


def clear_sky() -> dict:
    for f in SKY_FACES:
        for e in ("png", "jpg"):
            (_sky_dir() / f"{f}.{e}").unlink(missing_ok=True)
    shutil.rmtree(mods_dir() / SKY_MOD, ignore_errors=True)
    return sky_info()


def sky_folder(vdir: Path) -> Path:
    return vdir / "content" / "sky"


def build_sky_mod(vdir: Path) -> None:
    """Turn the chosen sky pictures into a mod that uses Roblox's own sky file names, so every game's default sky changes."""
    target = mods_dir() / SKY_MOD
    shutil.rmtree(target, ignore_errors=True)
    if not sky_info()["set"]:
        return
    names = {}
    folder = sky_folder(vdir)
    if folder.is_dir():
        for f in folder.iterdir():
            m = SKY_FILE.match(f.name)
            if m:
                names[m.group(2).lower()] = f.name
    out = target / "content" / "sky"
    out.mkdir(parents=True, exist_ok=True)
    for face, code in SKY_FACES.items():
        src = _face_file(face)
        if src:
            shutil.copyfile(src, out / names.get(code, f"sky512_{code}.tex"))


# ------------------------------------------------------------------ protocol handler and launching

PROTOCOLS = ("roblox-player", "roblox")


def _handler_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --launch "%1"'
    return f'"{sys.executable}" "{Path(sys.argv[0]).resolve()}" --launch "%1"'


def _is_ours(cmd: str) -> bool:
    return "--launch" in cmd and Path(sys.executable).name.lower() in cmd.lower()


def _read_handler(proto: str) -> str:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{proto}\shell\open\command") as k:
            return winreg.QueryValueEx(k, "")[0]
    except (OSError, ImportError):
        return ""


def protocol_registered() -> bool:
    """True when 'Play' on roblox.com currently opens Roblox through this app."""
    return supported() and _is_ours(_read_handler("roblox-player"))


def register_protocol() -> None:
    """Make 'Play' on roblox.com open Roblox through Nova (this Windows user only). Roblox's own handler is remembered."""
    if not supported():
        raise NovaError("This only works on Windows.")
    import winreg
    st = _state()
    saved = dict(st.get("orig_handlers") or {})
    for proto in PROTOCOLS:
        cur = _read_handler(proto)
        if cur and not _is_ours(cur):
            saved[proto] = cur                                   # so Roblox can still update itself and be put back
    write_json(_state_file(), {**st, "orig_handlers": saved})
    for proto in PROTOCOLS:
        base = rf"Software\Classes\{proto}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f"URL: {proto} Protocol")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _handler_command())


def unregister_protocol() -> None:
    """Give 'Play' back to Roblox's own launcher."""
    if not supported():
        return
    import winreg
    saved = _state().get("orig_handlers") or {}
    for proto in PROTOCOLS:
        if proto in saved:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{proto}\shell\open\command") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, saved[proto])
        else:
            for sub in (r"\shell\open\command", r"\shell\open", r"\shell", ""):
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{proto}{sub}")
                except OSError:
                    pass


def clean_launch_uri(uri: str) -> str:
    """Only the two Roblox link types are handed to the game, and nothing that could carry extra arguments."""
    uri = (uri or "").strip()
    if not re.match(r"^(roblox-player|roblox):", uri, re.I) or len(uri) > 4000 or re.search(r"[\s\"<>|&^\x00-\x1f]", uri):
        raise NovaError("That isn't a Roblox launch link.")
    return uri


def hand_to_roblox(uri: str) -> bool:
    """Open a launch link with Roblox's own launcher (the handler that was there before Nova), which updates Roblox first."""
    uri = clean_launch_uri(uri)
    saved = _state().get("orig_handlers") or {}
    cmd = saved.get("roblox-player" if uri.lower().startswith("roblox-player") else "roblox") or saved.get("roblox-player") or ""
    if not cmd or "%1" not in cmd:
        return False
    subprocess.Popen(cmd.replace("%1", uri))
    return True


def start(uri: str | None = None, app: bool = False) -> subprocess.Popen:
    """Apply flags, sky and mods, then run Roblox: with a launch link from roblox.com, or (app=True) the Roblox app itself."""
    vdir = version_dir()
    write_flags(vdir)
    build_sky_mod(vdir)
    apply_mods(vdir)
    args = [str(vdir / PLAYER_EXE)]
    if uri:
        args.append(clean_launch_uri(uri))
    elif app:
        args.append("--app")                       # opens Roblox's own home screen, the same way Bloxstrap's Launch button does
    return subprocess.Popen(args, cwd=str(vdir))


def status() -> dict:
    v = detect()
    flags = load_flags()
    st = _state()
    return {"supported": supported(), "version": v, "from": st.get("from", "") if v else "", "found": existing_installs()[:3],
            "registered": protocol_registered(), "flags": flags,
            "presets": {k: {"name": p["name"], "desc": p["desc"]} for k, p in PRESETS.items()}, "preset_on": preset_states(flags),
            "sky": sky_info(), "mods": mods_info(), "path": str(root()), "sky_folder": str(sky_folder(Path(st["dir"]))) if v else ""}
