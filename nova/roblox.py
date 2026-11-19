"""Install, update, tune and launch Roblox (Windows), the way Bloxstrap-style bootstrappers do.

Roblox's own downloads are used as they are: Nova asks Roblox which version is current, downloads its official
packages, unpacks them into its own folder, then starts RobloxPlayerBeta.exe. Nova adds FastFlags (client settings)
and user mods on top. Roblox sign-in stays in your browser: you press Play on roblox.com and Roblox hands the
game to Nova, which opens it with your settings.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from . import paths
from .util import NovaError, Task, download_file, http_get_json, http_get_text, read_json, safe_extract_zip, write_json

VERSION_URL = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
CDN = "https://setup.rbxcdn.com"
PLAYER_EXE = "RobloxPlayerBeta.exe"
VERSION_RX = re.compile(r"^version-[0-9a-f]{8,32}$")

# which folder each official package unpacks into ("" is the game folder itself)
PACKAGE_DIRS = {
    "RobloxApp.zip": "", "shaders.zip": "shaders/", "ssl.zip": "ssl/",
    "content-avatar.zip": "content/avatar/", "content-configs.zip": "content/configs/", "content-fonts.zip": "content/fonts/",
    "content-sky.zip": "content/sky/", "content-sounds.zip": "content/sounds/", "content-textures2.zip": "content/textures/",
    "content-models.zip": "content/models/", "content-textures3.zip": "PlatformContent/pc/textures/",
    "content-terrain.zip": "PlatformContent/pc/terrain/", "content-platform-fonts.zip": "PlatformContent/pc/fonts/",
    "extracontent-luapackages.zip": "ExtraContent/LuaPackages/", "extracontent-translations.zip": "ExtraContent/translations/",
    "extracontent-models.zip": "ExtraContent/models/", "extracontent-textures.zip": "ExtraContent/textures/",
    "content-studio_svg_textures.zip": "content/studio_svg_textures/",
}
APP_SETTINGS = '<?xml version="1.0" encoding="UTF-8"?>\n<Settings>\n\t<ContentFolder>content</ContentFolder>\n\t<BaseUrl>http://www.roblox.com</BaseUrl>\n</Settings>\n'


def supported() -> bool:
    return sys.platform.startswith("win")


def root() -> Path:
    return paths.sub("Roblox")


def versions_root() -> Path:
    return root() / "Versions"


def mods_dir() -> Path:
    d = root() / "Mods"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_file() -> Path:
    return root() / "state.json"


def installed_version() -> str:
    v = (read_json(_state_file(), {}) or {}).get("version", "")
    return v if VERSION_RX.match(v or "") and (versions_root() / v / PLAYER_EXE).exists() else ""


def version_dir(v: str | None = None) -> Path:
    v = v or installed_version()
    if not VERSION_RX.match(v or ""):
        raise NovaError("Roblox isn't installed yet.")
    return versions_root() / v


# ------------------------------------------------------------------ install / update

def latest_version() -> str:
    data = http_get_json(VERSION_URL)
    v = (data or {}).get("clientVersionUpload", "")
    if not VERSION_RX.match(v):
        raise NovaError("Roblox didn't say which version is current. Try again in a moment.")
    return v


def parse_manifest(text: str) -> list[dict]:
    """rbxPkgManifest.txt: the line 'v0', then four lines per package: name, md5, compressed size, size."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines or lines[0] != "v0":
        raise NovaError("Roblox's file list is in a format Nova doesn't know yet.")
    out = []
    body = lines[1:]
    for i in range(0, len(body) - 3, 4):
        name, md5, comp, size = body[i:i + 4]
        if not re.match(r"^[A-Za-z0-9_.-]+$", name) or not re.match(r"^[0-9a-f]{32}$", md5):
            raise NovaError("Roblox's file list looks damaged.")
        out.append({"name": name, "md5": md5, "size": int(comp) if comp.isdigit() else 0})
    return out


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def install(task: Task | None = None, version: str | None = None) -> str:
    """Download and unpack the current Roblox. Returns the installed version."""
    if not supported():
        raise NovaError("Roblox only runs on Windows, so Nova can only install it there.")
    task = task or Task("Install Roblox")
    task.update("Checking the current Roblox version…", 0)
    version = version or latest_version()
    target = versions_root() / version
    if (target / PLAYER_EXE).exists():
        _set_installed(version)
        return version
    manifest = parse_manifest(http_get_text(f"{CDN}/{version}-rbxPkgManifest.txt"))
    pkgs = [m for m in manifest if m["name"] in PACKAGE_DIRS]
    if not any(m["name"] == "RobloxApp.zip" for m in pkgs):
        raise NovaError("Roblox's file list has no game package. Roblox may have changed its downloads.")
    tmp = root() / "Downloads" / version
    tmp.mkdir(parents=True, exist_ok=True)
    work = versions_root() / (version + ".part")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    total = max(1, len(pkgs))
    for n, m in enumerate(pkgs):
        task.update(f"Downloading {m['name']} ({n + 1}/{total})…", n / total)
        dest = tmp / m["name"]
        for attempt in range(3):
            download_file(f"{CDN}/{version}-{m['name']}", dest)
            if _md5(dest) == m["md5"]:
                break
            dest.unlink(missing_ok=True)
        else:
            raise NovaError(f"{m['name']} didn't download correctly. Check your connection and try again.")
        task.update(f"Unpacking {m['name']}…", (n + 0.7) / total)
        sub = PACKAGE_DIRS[m["name"]]
        out = work / sub if sub else work
        out.mkdir(parents=True, exist_ok=True)
        safe_extract_zip(dest, out)
    (work / "AppSettings.xml").write_text(APP_SETTINGS, encoding="utf-8")
    shutil.rmtree(target, ignore_errors=True)
    work.rename(target)
    shutil.rmtree(tmp, ignore_errors=True)
    _set_installed(version)
    for old in versions_root().iterdir():                       # keep only the current version
        if old.is_dir() and old.name != version:
            shutil.rmtree(old, ignore_errors=True)
    task.update("Done", 1)
    return version


def _set_installed(version: str) -> None:
    write_json(_state_file(), {"version": version, "installed": time.time()})


def uninstall() -> None:
    shutil.rmtree(versions_root(), ignore_errors=True)
    _state_file().unlink(missing_ok=True)
    (root() / "mods_applied.json").unlink(missing_ok=True)


# ------------------------------------------------------------------ FastFlags

FLAG_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,120}$")

PRESETS = {
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

def mod_names() -> list[str]:
    return sorted(p.name for p in mods_dir().iterdir() if p.is_dir())


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
    while (mods_dir() / name).exists():
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
    for name in mod_names():
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


# ------------------------------------------------------------------ protocol handler and launching

PROTOCOLS = ("roblox-player", "roblox")


def _handler_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --launch "%1"'
    return f'"{sys.executable}" "{Path(sys.argv[0]).resolve()}" --launch "%1"'


def protocol_registered() -> bool:
    """True when 'Play' on roblox.com currently opens Roblox through this app."""
    if not supported():
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\roblox-player\shell\open\command") as k:
            cmd = winreg.QueryValueEx(k, "")[0]
    except (OSError, ImportError):
        return False
    return "--launch" in cmd and Path(sys.executable).name.lower() in cmd.lower()


def register_protocol() -> None:
    """Make 'Play' on roblox.com open Roblox through Nova (for this Windows user only)."""
    if not supported():
        raise NovaError("This only works on Windows.")
    import winreg
    for proto in PROTOCOLS:
        base = rf"Software\Classes\{proto}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f"URL: {proto} Protocol")
            winreg.SetValueEx(k, "URL Protocol", 0, winreg.REG_SZ, "")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _handler_command())


def unregister_protocol() -> None:
    """Remove Nova's handler. Roblox's own installer registers itself again the next time it runs."""
    if not supported():
        return
    import winreg
    for proto in PROTOCOLS:
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


def start(uri: str | None = None) -> subprocess.Popen:
    """Apply flags and mods, then run Roblox (with a launch link from roblox.com, if there is one)."""
    vdir = version_dir()
    write_flags(vdir)
    apply_mods(vdir)
    args = [str(vdir / PLAYER_EXE)]
    if uri:
        args.append(clean_launch_uri(uri))
    return subprocess.Popen(args, cwd=str(vdir))


def status() -> dict:
    v = installed_version()
    flags = load_flags()
    return {"supported": supported(), "version": v, "registered": protocol_registered(), "flags": flags,
            "presets": {k: {"name": p["name"], "desc": p["desc"]} for k, p in PRESETS.items()}, "preset_on": preset_states(flags),
            "mods": mods_info(), "path": str(root())}
