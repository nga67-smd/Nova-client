"""Find the Roblox that is already on this PC, tune it (FastFlags, skies, mods) and start it.

Nova does not download or install Roblox. It looks for Roblox (or a Bloxstrap-style launcher's copy) on the device,
puts your FastFlags, custom sky and mods into that copy, and starts it. Roblox keeps updating itself: when a newer
version is out, Nova hands the game to Roblox's own launcher first. Sign-in stays in your browser.
"""
from __future__ import annotations

import json
import os
import random
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
LAUNCHERS = (("Roblox", "Roblox"), ("Bloxstrap", "Bloxstrap"), ("Voidstrap", "Voidstrap"))


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
    found, seen = [], set()
    places = [(label, Path(base) / sub) for label, sub in LAUNCHERS]
    try:                                                    # any other launcher that keeps Roblox in its own Versions folder
        places += [(c.name, c) for c in Path(base).iterdir() if c.is_dir() and (c / "Versions").is_dir()]
    except OSError:
        pass
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(env):
            places.append(("Roblox", Path(os.environ[env]) / "Roblox"))
    for label, folder in places:
        vroot = folder / "Versions"
        if not vroot.is_dir() or str(vroot).lower() in seen:
            continue
        seen.add(str(vroot).lower())
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
    return sorted(p.name for p in mods_dir().iterdir() if p.is_dir() and (managed or p.name not in (SKY_MOD, CROSS_MOD, SOUND_MOD)))


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
    while (mods_dir() / name).exists() or name in (SKY_MOD, CROSS_MOD, SOUND_MOD):
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


def overlay_dir() -> Path | None:
    """The Modifications folder of a Bloxstrap-style launcher, when that is where the found Roblox comes from. Those launchers
    check Roblox's files every time they start it and put back anything that isn't in their Modifications folder."""
    src = _state().get("from", "")
    base = os.environ.get("LOCALAPPDATA")
    if base and src and src != "Roblox" and (src in ("Bloxstrap", "Voidstrap") or (Path(base) / src / "Modifications").is_dir()):
        return Path(base) / src / "Modifications"
    return None


def _lay_over(target: Path, key: str, want: dict[str, Path]) -> None:
    """Copy mod files over a folder, remembering what was there, and undo it for files that are no longer wanted."""
    log_file, backup = root() / "mods_applied.json", root() / "ModBackup" / key
    log: dict = read_json(log_file, {}) or {}
    if "_version" in log:                                         # written by an earlier Nova: keep what it remembered
        old = root() / "ModBackup"
        if old.is_dir():
            (old / "game").mkdir(exist_ok=True)
            for item in list(old.iterdir()):
                if item.name not in ("game", "overlay"):
                    shutil.move(str(item), str(old / "game" / item.name))
        st_dir = _state().get("dir", "")
        log = {"game": {"_target": st_dir if Path(st_dir).name == log["_version"] else "", "files": log.get("files", {})}}
    applied = log.get(key) or {}
    if applied.get("_target") != str(target):                     # a new game folder (an update) has nothing of ours in it
        applied = {"_target": str(target)}
        shutil.rmtree(backup, ignore_errors=True)
    files = applied.setdefault("files", {})
    for rel in list(files):
        if rel not in want:
            dest = target / rel
            if files[rel]:
                b = backup / rel
                if b.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(b, dest)
            else:
                dest.unlink(missing_ok=True)
            del files[rel]
    for rel, src in want.items():
        dest = (target / rel).resolve()
        if target.resolve() not in dest.parents:
            continue
        if rel not in files:
            had = dest.exists()
            if had:
                (backup / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, backup / rel)
            files[rel] = had
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    log[key] = applied
    write_json(log_file, log)


def apply_mods(vdir: Path) -> int:
    """Lay enabled mods over the game folder (and a Bloxstrap-style launcher's Modifications folder, so it keeps them)."""
    want = _wanted_mod_files()
    ov = overlay_dir()
    if ov:
        try:
            _lay_over(ov, "overlay", want)
        except OSError:
            pass
    elif (read_json(root() / "mods_applied.json", {}) or {}).get("overlay"):
        _lay_over(Path(read_json(root() / "mods_applied.json", {})["overlay"]["_target"]), "overlay", {})   # left that launcher: clean up
    _lay_over(vdir, "game", want)
    return len(want)


# ------------------------------------------------------------------ sky
#
# Roblox's default sky is six 512x512 textures named sky512_<side>.tex. A .tex file is a DDS image (BC1/DXT1) with a new
# name, so Nova turns your pictures into exactly that and lays them over Roblox's own files (like any other mod).

SKY_FACES = {"front": "ft", "back": "bk", "left": "lf", "right": "rt", "up": "up", "down": "dn"}
CROSS_MOD = "Nova Crosshair"                         # same idea for the custom crosshair
SOUND_MOD = "Nova Sounds"
SKY_MOD = "Nova Sky"                                  # the folder Nova keeps in Mods for the custom sky
SKY_SIZE = 512
SKY_FILE = re.compile(r"^sky\d*_(bk|dn|ft|lf|rt|up)\.tex$", re.I)
SKY_DEFAULT_DIRS = ("PlatformContent/pc/textures/sky", "content/textures/sky")


def _sky_dir() -> Path:
    d = root() / "Sky"
    d.mkdir(parents=True, exist_ok=True)
    return d


def decode_png(data: bytes) -> tuple[int, int, bytes]:
    """Read an 8-bit PNG (what a browser canvas produces) into width, height and RGB bytes."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise NovaError("Sky pictures must be PNG.")
    pos, idat, plte, hdr = 8, [], b"", None
    while pos + 8 <= len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            plte = body
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    if not hdr or not idat:
        raise NovaError("That picture is damaged.")
    w, h, depth, ctype, _, _, interlace = hdr
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if depth != 8 or interlace or not chans or w * h > 4096 * 4096:
        raise NovaError("Nova can't read that kind of PNG. Use the Import button so Nova converts it first.")
    raw = zlib.decompress(b"".join(idat))
    stride = w * chans
    if len(raw) < (stride + 1) * h:
        raise NovaError("That picture is damaged.")
    rows, prev = [], bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        cur = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for i in range(chans, stride):
                cur[i] = (cur[i] + cur[i - chans]) & 255
        elif f == 2:
            for i in range(stride):
                cur[i] = (cur[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                cur[i] = (cur[i] + (((cur[i - chans] if i >= chans else 0) + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = cur[i - chans] if i >= chans else 0
                b = prev[i]
                c = prev[i - chans] if i >= chans else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                cur[i] = (cur[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        elif f != 0:
            raise NovaError("That picture is damaged.")
        rows.append(cur)
        prev = cur
    out = bytearray()
    for r in rows:
        if ctype == 2:
            out += r
        elif ctype == 6:
            for i in range(0, stride, 4):
                out += r[i:i + 3]
        elif ctype == 0:
            for v in r:
                out += bytes((v, v, v))
        elif ctype == 4:
            for i in range(0, stride, 2):
                out += bytes((r[i],)) * 3
        else:
            for v in r:
                out += plte[v * 3:v * 3 + 3] or b"\0\0\0"
    return w, h, bytes(out)


def encode_dxt1(w: int, h: int, rgb: bytes) -> bytes:
    """A DDS file with the picture compressed as BC1/DXT1 (the format of Roblox's sky textures)."""
    def to565(r, g, b):
        return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

    def from565(c):
        r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
        return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2)
    blocks, cache = bytearray(), {}
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            px = bytearray()
            for y in range(4):
                o = ((by + y) * w + bx) * 3
                px += rgb[o:o + 12]
            key = bytes(px)
            hit = cache.get(key)
            if hit is None:
                rs, gs, bs = key[0::3], key[1::3], key[2::3]
                lo, hi = (min(rs), min(gs), min(bs)), (max(rs), max(gs), max(bs))
                c0, c1 = to565(*hi), to565(*lo)
                if c0 == c1:
                    hit = struct.pack("<HHI", c0, c1, 0)
                else:
                    if c0 < c1:
                        c0, c1 = c1, c0
                    p0, p1 = from565(c0), from565(c1)
                    d = (p0[0] - p1[0], p0[1] - p1[1], p0[2] - p1[2])
                    den = d[0] * d[0] + d[1] * d[1] + d[2] * d[2] or 1
                    idx = 0
                    for i in range(16):
                        u = 1 - ((key[i * 3] - p1[0]) * d[0] + (key[i * 3 + 1] - p1[1]) * d[1] + (key[i * 3 + 2] - p1[2]) * d[2]) / den
                        code = 0 if u < 1 / 6 else 2 if u < 0.5 else 3 if u < 5 / 6 else 1
                        idx |= code << (2 * i)
                    hit = struct.pack("<HHI", c0, c1, idx)
                cache[key] = hit
            blocks += hit
    header = b"DDS " + struct.pack("<7I", 124, 0x81007, h, w, len(blocks), 0, 0) + bytes(44) \
        + struct.pack("<II4s5I", 32, 4, b"DXT1", 0, 0, 0, 0, 0) + struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    return header + bytes(blocks)


def _face_file(face: str) -> Path | None:
    p = _sky_dir() / f"{face}.dds"
    return p if p.exists() else None


def sky_info() -> dict:
    return {"faces": {f: bool(_face_file(f)) for f in SKY_FACES}, "set": any(_face_file(f) for f in SKY_FACES)}


def _check_square(w: int, h: int) -> None:
    if (w, h) != (SKY_SIZE, SKY_SIZE):
        raise NovaError(f"Sky pictures must be {SKY_SIZE}x{SKY_SIZE}. Use the Import button, which resizes them for you.")


def set_sky_color(color: str) -> dict:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color or ""):
        raise NovaError("Pick a color.")
    px = bytes(int(color[i:i + 2], 16) for i in (1, 3, 5)) * (SKY_SIZE * SKY_SIZE)
    data = encode_dxt1(SKY_SIZE, SKY_SIZE, px)
    clear_sky()
    for face in SKY_FACES:
        (_sky_dir() / f"{face}.dds").write_bytes(data)
    return sky_info()


SKY_PRESETS = {
    "sunset": ("Sunset", (38, 28, 92), (255, 120, 70), (60, 24, 40), False),
    "night": ("Starry night", (4, 6, 24), (22, 30, 70), (6, 8, 20), True),
    "pastel": ("Pastel", (170, 200, 255), (255, 210, 235), (255, 235, 245), False),
    "space": ("Deep space", (0, 0, 8), (24, 8, 44), (0, 0, 6), True),
    "ocean": ("Ocean", (20, 90, 160), (150, 225, 235), (10, 60, 90), False),
}


def _mix(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def preset_pixels(name: str, face: str) -> bytes:
    _, top, horizon, bottom, stars = SKY_PRESETS[name]
    n = SKY_SIZE
    rows = []
    for y in range(n):
        t = y / (n - 1)
        c = top if face == "up" else bottom if face == "down" else _mix(top, horizon, t ** 1.5)
        rows.append(bytearray(bytes(c) * n))
    if stars and face != "down":
        rnd = random.Random(f"{name}{face}")
        for _ in range(60 if face == "up" else 35):
            x, y = rnd.randrange(n - 1), rnd.randrange(n - 1 if face == "up" else n // 2)
            v = rnd.choice((150, 200, 255))
            for dx, dy in (((0, 0), (1, 0), (0, 1), (1, 1)) if v > 220 else ((0, 0),)):
                rows[y + dy][(x + dx) * 3:(x + dx) * 3 + 3] = bytes((v, v, v))
    return b"".join(bytes(r) for r in rows)


def set_sky_preset(name: str) -> dict:
    if name not in SKY_PRESETS:
        raise NovaError("Unknown sky style.")
    clear_sky()
    for face in SKY_FACES:
        (_sky_dir() / f"{face}.dds").write_bytes(encode_dxt1(SKY_SIZE, SKY_SIZE, preset_pixels(name, face)))
    return sky_info()


def set_sky_image(face: str, tmp: Path) -> dict:
    """Use a 512x512 PNG for one side of the sky, or ('all') for every side."""
    try:
        if face != "all" and face not in SKY_FACES:
            raise NovaError("Unknown side of the sky.")
        if tmp.stat().st_size > 16 * 1024 * 1024:
            raise NovaError("That picture is too big.")
        w, h, rgb = decode_png(tmp.read_bytes())
        _check_square(w, h)
        data = encode_dxt1(w, h, rgb)
    finally:
        tmp.unlink(missing_ok=True)
    for f in (list(SKY_FACES) if face == "all" else [face]):
        (_sky_dir() / f"{f}.dds").write_bytes(data)
    return sky_info()


def clear_sky() -> dict:
    for f in SKY_FACES:
        (_sky_dir() / f"{f}.dds").unlink(missing_ok=True)
    shutil.rmtree(mods_dir() / SKY_MOD, ignore_errors=True)
    return sky_info()


def sky_files(vdir: Path) -> dict[str, list[Path]]:
    """Where Roblox keeps its sky textures, as paths relative to the game folder, per side ('ft', 'bk', ...)."""
    found: dict[str, list[Path]] = {}
    for top in ("PlatformContent", "content", "ExtraContent"):
        base = vdir / top
        if base.is_dir():
            for f in base.rglob("*.tex"):
                m = SKY_FILE.match(f.name)
                if m:
                    found.setdefault(m.group(1).lower(), []).append(f.relative_to(vdir))
    return found


def sky_folder(vdir: Path) -> Path:
    """The folder that holds Roblox's sky textures (so a person can look at the originals)."""
    for rels in sky_files(vdir).values():
        return vdir / rels[0].parent
    for d in SKY_DEFAULT_DIRS:
        if (vdir / d).is_dir():
            return vdir / d
    return vdir / SKY_DEFAULT_DIRS[0]


def sky_pack_folder() -> Path:
    """The one folder to open for sky textures: the launcher's own Modifications sky folder (Bloxstrap etc. keep what is put
    there), otherwise Roblox's sky folder."""
    ov = overlay_dir()
    if ov:
        d = ov / SKY_DEFAULT_DIRS[0]
        d.mkdir(parents=True, exist_ok=True)
        return d
    return sky_folder(version_dir())


_SIDE_WORDS = {"bk": "bk", "back": "bk", "dn": "dn", "down": "dn", "bottom": "dn", "ft": "ft", "front": "ft", "lf": "lf", "left": "lf",
               "rt": "rt", "right": "rt", "up": "up", "top": "up"}


class _SkyName:
    """A sky texture file name like sky512_ft.tex, front.dds or Sky_Left.tex: which side, and which size."""

    @staticmethod
    def fullmatch(name: str):
        stem, dot, ext = name.lower().rpartition(".")
        if not dot or ext not in ("tex", "dds"):
            return None
        words = re.findall(r"[a-z]+|\d+", stem)
        side = next((_SIDE_WORDS[w] for w in reversed(words) if w in _SIDE_WORDS), None)
        if not side:
            return None
        size = next((w for w in words if w.isdigit()), "")
        return _SkyMatch(size, side)


class _SkyMatch:
    def __init__(self, size, side):
        self._g = (size, side)

    def group(self, i):
        return self._g[i - 1]


_SKY_NAME = _SkyName


def _lib_dir() -> Path:
    return root() / "SkyLibrary"


def _lib_name(name: str) -> str:
    name = re.sub(r"[^\w .()+-]", "", name or "", flags=re.U).strip(" .")[:40]
    if not name:
        raise NovaError("Give this sky a name.")
    return name


def library_list() -> list[str]:
    d = _lib_dir()
    return sorted((x.name for x in d.iterdir() if x.is_dir() and any(x.glob("*.dds"))), key=str.lower) if d.is_dir() else []


def _lib_store(name: str, found: dict[str, bytes]) -> None:
    d = _lib_dir() / _lib_name(name)
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    for face, code in SKY_FACES.items():
        if code in found:
            (d / f"{face}.dds").write_bytes(found[code])


def _use_sky_textures(found: dict[str, bytes], name: str = "", apply: bool = True) -> dict:
    if not found:
        raise NovaError("No sky textures (sky512_ft.tex and so on) were found there.")
    if name:
        _lib_store(name, found)                       # every imported sky is kept in "Your skies"
    if apply:
        clear_sky()
        for face, code in SKY_FACES.items():
            if code in found:
                (_sky_dir() / f"{face}.dds").write_bytes(found[code])
    return sky_info()


def use_library_sky(name: str) -> dict:
    d = _lib_dir() / _lib_name(name)
    found = {code: (d / f"{face}.dds").read_bytes() for face, code in SKY_FACES.items() if (d / f"{face}.dds").is_file()}
    if not found:
        raise NovaError("That sky isn't in your list any more.")
    return _use_sky_textures(found)


def delete_library_sky(name: str) -> None:
    shutil.rmtree(_lib_dir() / _lib_name(name), ignore_errors=True)


def save_current_sky(name: str) -> None:
    found = {code: f.read_bytes() for face, code in SKY_FACES.items() if (f := _face_file(face))}
    if not found:
        raise NovaError("There's no custom sky to save yet.")
    _lib_store(name, found)


def import_sky_pack(tmp: Path, name: str = "", apply: bool = True) -> dict:
    """Use a downloaded sky pack (.zip with sky512_*.tex or .dds files, like a skybox fix) as the sky."""
    found: dict[str, bytes] = {}
    try:
        if tmp.stat().st_size > 256 * 1024 * 1024:
            raise NovaError("That sky pack is too big.")
        try:
            z = zipfile.ZipFile(tmp)
        except zipfile.BadZipFile:
            raise NovaError("That isn't a .zip file.") from None
        with z:
            for info in z.infolist():
                m = _SKY_NAME.fullmatch(Path(info.filename).name)
                if not m or info.is_dir() or info.file_size > 16 * 1024 * 1024:
                    continue
                code = m.group(2).lower()
                if code in found and m.group(1) != "512":
                    continue
                found[code] = z.read(info)
    finally:
        tmp.unlink(missing_ok=True)
    return _use_sky_textures(found, name, apply)


def _sky_stage() -> Path:
    return paths.data_dir() / "skypack_stage"


def stage_sky_file(name: str, first: bool, save) -> None:
    """One loose sky file (picked from a folder) waits here until the rest have arrived."""
    stage = _sky_stage()
    if first:
        shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True, exist_ok=True)
    name = Path(name or "").name
    if _SKY_NAME.fullmatch(name):
        save(stage / name)


def finish_sky_files(name: str = "", apply: bool = True) -> dict:
    stage, found = _sky_stage(), {}
    try:
        for f in sorted(stage.glob("*")) if stage.is_dir() else []:
            m = _SKY_NAME.fullmatch(f.name)
            if not m or f.stat().st_size > 16 * 1024 * 1024:
                continue
            code, data = m.group(2).lower(), f.read_bytes()
            if code not in found or m.group(1) == "512":
                found[code] = data
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return _use_sky_textures(found, name, apply)


def build_sky_mod(vdir: Path) -> None:
    """Turn the chosen sky pictures into a mod that replaces Roblox's own sky files, so every default sky changes."""
    target = mods_dir() / SKY_MOD
    shutil.rmtree(target, ignore_errors=True)
    try:
        sync_skyfix()
    except NovaError:
        pass                                          # Roblox was using the cache; the sky files below still get written
    build_crosshair_mod(vdir)
    build_sound_mod(vdir)
    if not sky_info()["set"]:
        return
    where = sky_files(vdir)
    for face, code in SKY_FACES.items():
        src = _face_file(face)
        if not src:
            continue
        for rel in where.get(code) or [Path(SKY_DEFAULT_DIRS[0]) / f"sky512_{code}.tex"]:
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target / rel)


def sky_check() -> dict:
    """Is Nova's sky really in the game files right now, and what else could be undoing it?"""
    vdir = version_dir()
    where = sky_files(vdir)
    files = {}
    for face, code in SKY_FACES.items():
        mine = _face_file(face)
        paths_ = where.get(code) or []
        if not mine:
            files[face] = "default"
        elif not paths_:
            files[face] = "missing"
        else:
            try:
                files[face] = "yours" if all((vdir / p).read_bytes() == mine.read_bytes() for p in paths_) else "original"
            except OSError:
                files[face] = "missing"
    ov = overlay_dir()
    return {"folder": str(sky_folder(vdir)), "version": vdir.name, "from": _state().get("from", ""), "launcher_folder": str(ov) if ov else "",
            "files": files, "found_files": sum(len(v) for v in where.values()), "registered": protocol_registered()}


def apply_sky_now() -> bool:
    """Put the sky into the Roblox on this PC right away (it can't be changed while Roblox is open)."""
    try:
        vdir = version_dir()
        build_sky_mod(vdir)
        apply_mods(vdir)
        return True
    except (NovaError, OSError):
        return False


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
            "sky": sky_info(), "crosshair": crosshair_info(), "extras": extras_info(), "weather": _weather_info(), "sky_library": library_list(), "skyfix": {"on": skyfix_on(), "enabled": st.get("skyfix", True)}, "sky_presets": {k: v[0] for k, v in SKY_PRESETS.items()}, "path": str(root()), "sky_folder": str(sky_folder(Path(st["dir"]))) if v else ""}


def _junk_dirs() -> list[Path]:
    """Roblox's logs and temporary files. Safe to delete; Roblox recreates them."""
    out = []
    la, tmp = os.environ.get("LOCALAPPDATA"), os.environ.get("TEMP") or os.environ.get("TMP")
    if la:
        out.append(Path(la) / "Roblox" / "logs")
    if tmp:
        out.append(Path(tmp) / "Roblox")
    return [d for d in out if d.is_dir()]


def _tree_size(d: Path) -> int:
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file())


def cleanup_info() -> dict:
    return {"bytes": sum(_tree_size(d) for d in _junk_dirs())}


def cleanup() -> dict:
    freed = 0
    for d in _junk_dirs():
        for f in d.iterdir():
            try:
                freed += _tree_size(f) if f.is_dir() else f.stat().st_size
                shutil.rmtree(f) if f.is_dir() else f.unlink()
            except OSError:
                pass                                       # in use by a running Roblox
    return {"freed": freed}


# ------------------------------------------------------------------ skybox fix
# The community "skybox fix": Roblox keeps the sky mesh in its download cache (rbx-storage). These six cache entries hold a
# corrected mesh, so a custom sky shows properly in every game. They are made read-only so Roblox doesn't overwrite them.
SKYFIX_NAMES = ("6c94b9385e52d221f0538aadaceead2d", "7328622d2d509b95dd4dd2c721d1ca8b", "78cb2e93aee0cdbd79b15a866bc93a54",
                "9244e00ff9fd6cee0bb40a262bb35d31", "a50f6563c50ca4d5dcb255ee5cfab097", "a564ec8aeef3614e788d02f0090089d8")
SKYFIX_DATA = (
    "UkJYSAIAAAA2AAAAaHR0cHM6Ly9jMC5yYnhjZG4uY29tLzRkYTJmZmMyZTZkNzBiMGJhMTk1NmYxNGMzZDZmNTNmAMgAAAADAwAA"
    "r3LVTeUAAABaZumlAwAAAHgtYW16LWlkLTI6IDNzVnkyTjloTkFMV2FjNG1Bc0xpUTc1UnM2WjZGMFBRMnN2WWl4djdRamFBWEcw"
    "dkZBTGtva0M4N2NvZktYZFcyMzlhKy9tRXVyRT0NCngtYW16LXJlcXVlc3QtaWQ6IDU4SkgxR0VNSkNCNVRNNUINCngtYW16LXJl"
    "cGxpY2F0aW9uLXN0YXR1czogQ09NUExFVEVEDQpMYXN0LU1vZGlmaWVkOiBUaHUsIDI1IEp1bCAyMDI0IDIxOjU3OjUyIEdNVA0K"
    "RVRhZzogIjRkYTJmZmMyZTZkNzBiMGJhMTk1NmYxNGMzZDZmNTNmIg0KeC1hbXotc2VydmVyLXNpZGUtZW5jcnlwdGlvbjogQUVT"
    "MjU2DQpDb250ZW50LUVuY29kaW5nOiBnemlwDQp4LWFtei12ZXJzaW9uLWlkOiB0U2VseEVzbTd2VklaamxsOTk1Ty5Db2NMUDZD"
    "S3ppQg0KQWNjZXB0LVJhbmdlczogYnl0ZXMNCkNvbnRlbnQtVHlwZTogYXBwbGljYXRpb24vb2N0ZXQtc3RyZWFtDQpTZXJ2ZXI6"
    "IEFtYXpvblMzDQpDb250ZW50LUxlbmd0aDogMTQwDQpDYWNoZS1Db250cm9sOiBwdWJsaWMsIG1heC1hZ2U9MjY1MTQ3OTINCkRh"
    "dGU6IEZyaSwgMTMgRGVjIDIwMjQgMjM6MDM6NDggR01UDQpDb25uZWN0aW9uOiBrZWVwLWFsaXZlDQpWYXJ5OiBBY2NlcHQtRW5j"
    "b2RpbmcNClJieC1DZG4tUHJvdmlkZXI6IGFrDQpBY2Nlc3MtQ29udHJvbC1FeHBvc2UtSGVhZGVyczogUmJ4LUNkbi1Qcm92aWRl"
    "cixBa2FtYWktUmVxdWVzdC1CQw0KQWNjZXNzLUNvbnRyb2wtQWxsb3ctTWV0aG9kczogR0VUDQpBY2Nlc3MtQ29udHJvbC1BbGxv"
    "dy1PcmlnaW46ICoNClRpbWluZy1BbGxvdy1PcmlnaW46ICoNCnZlcnNpb24gNC4wMQoYAAQABAAAAAIAAAACAAAAAAAAAAAAAQAy"
    "R8O+Pk2MwRRHwz70BDW/UHgnM/IENb8AAIA/AAAAAH8Af/7/////Q0fDvjxNjEFlR8M+9AQ1v1B4JzPyBDW/AAAAAAAAAAB/AH/+"
    "/////zJHwz48TYxBFEfDvvQENb9QeCcz8gQ1vwAAAAAAAIA/fwB//v////9DR8M+Pk2MwWVHw770BDW/UHgnM/IENb8AAIA/AACA"
    "P38Af/7/////AAAAAAEAAAACAAAAAAAAAAIAAAADAAAAAAAAAAIAAAA="
)


def _skyfix_files() -> list[Path]:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return []
    return [Path(base) / "Roblox" / "rbx-storage" / n[:2] / n for n in SKYFIX_NAMES]


def skyfix_on() -> bool:
    import base64
    want = base64.b64decode(SKYFIX_DATA)
    try:
        files = _skyfix_files()
        return bool(files) and all(f.read_bytes() == want for f in files)
    except OSError:
        return False


def _writable(f: Path) -> None:
    try:
        os.chmod(f, 0o666)
    except OSError:
        pass


def install_skyfix() -> None:
    import base64
    import stat
    want = base64.b64decode(SKYFIX_DATA)
    for f in _skyfix_files():
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            if f.exists():
                _writable(f)
            f.write_bytes(want)
            os.chmod(f, stat.S_IREAD)
        except OSError as e:
            raise NovaError("Couldn't update Roblox's sky cache. Close Roblox and try again.") from e


def remove_skyfix() -> None:
    """Delete the fixed cache entries; Roblox downloads its own again the next time it needs them."""
    for f in _skyfix_files():
        if f.exists():
            _writable(f)
            f.unlink(missing_ok=True)


def sync_skyfix() -> None:
    """The fix is on while a custom sky is set (unless turned off), off otherwise."""
    want = sky_info()["set"] and _state().get("skyfix", True)
    if want and not skyfix_on():
        install_skyfix()
    elif not want and _state().get("skyfix_added") and skyfix_on():
        remove_skyfix()
    st = _state()
    if bool(want) != bool(st.get("skyfix_added")):
        write_json(_state_file(), {**st, "skyfix_added": bool(want)})


def set_skyfix(enabled: bool) -> None:
    write_json(_state_file(), {**_state(), "skyfix": bool(enabled)})
    sync_skyfix()


# ------------------------------------------------------------------ refresh when Roblox closes

_RUN_CACHE = [0.0, False]


def player_running() -> bool:
    """Is any Roblox game window process running on this PC? (looked up at most every 2 seconds)"""
    if os.name != "nt":
        return False
    if time.time() - _RUN_CACHE[0] < 2:
        return _RUN_CACHE[1]
    _RUN_CACHE[1] = _player_running_now()
    _RUN_CACHE[0] = time.time()
    return _RUN_CACHE[1]


def _player_running_now() -> bool:
    try:
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {PLAYER_EXE}", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             timeout=10, creationflags=0x08000000).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return PLAYER_EXE.lower() in out.lower()


def refresh_after_close() -> bool:
    """Put the sky (and the skybox fix, flags and mods) back after Roblox closed, in case it or an update undid them."""
    try:
        vdir = version_dir()
        write_flags(vdir)
    except (NovaError, OSError):
        pass
    return apply_sky_now()


class CloseWatcher:
    """Calls refresh_after_close() each time a running Roblox is closed."""

    def __init__(self, running=player_running, refresh=refresh_after_close):
        self.running, self.refresh, self.was = running, refresh, False

    def tick(self) -> bool:
        now = bool(self.running())
        closed = self.was and not now
        self.was = now
        if closed:
            self.refresh()
        return closed

    def run(self, every: float = 4.0) -> None:
        while True:
            try:
                self.tick()
            except Exception:
                pass
            time.sleep(every)


# ------------------------------------------------------------------ crosshairs
# Roblox draws its mouse cursors from small PNG files. In first person and shift-lock the game shows ArrowFarCursor /
# MouseLockedCursor in the middle of the screen, so a picture there is a crosshair. (Which file a given game shows is up to
# the game; some draw their own crosshair.)

CURSOR_DIR = "content/textures/Cursors/KeyboardMouse"
CROSS_AIM = ("ArrowFarCursor.png", "MouseLockedCursor.png")
CROSS_POINTER = ("ArrowCursor.png",)
CROSS_SHAPES = {"dot": "Dot", "plus": "Plus", "plus_gap": "Plus with a gap", "x": "X", "circle": "Circle", "circle_dot": "Circle and dot", "t": "T shape"}
CROSS_PX = 64


def _cross_dir() -> Path:
    d = root() / "Crosshair"
    d.mkdir(parents=True, exist_ok=True)
    return d


def encode_png(w: int, h: int, rgba: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def _inside(shape: str, x: float, y: float, k: float, grow: float) -> bool:
    """Is the point (x, y), measured from the middle, on this crosshair? k scales it, grow thickens it (for the outline)."""
    t, ax, ay = 1.1 * k + grow, abs(x), abs(y)
    r = (ax * ax + ay * ay) ** 0.5
    if shape == "dot":
        return r <= 3.2 * k + grow
    if shape == "plus":
        return (ax <= t and ay <= 13 * k + grow) or (ay <= t and ax <= 13 * k + grow)
    if shape == "plus_gap":
        return (ax <= t and 5 * k - grow <= ay <= 14 * k + grow) or (ay <= t and 5 * k - grow <= ax <= 14 * k + grow)
    if shape == "x":
        return abs(ax - ay) <= t * 1.3 and r <= 14 * k + grow
    if shape == "circle":
        return abs(r - 12 * k) <= t
    if shape == "circle_dot":
        return abs(r - 12 * k) <= t or r <= 2.2 * k + grow
    if shape == "t":
        return (ay <= t and ax <= 13 * k + grow) or (ax <= t and 0 <= y <= 13 * k + grow)
    return False


def render_crosshair(shape: str, color: str, size: str = "medium") -> bytes:
    if shape not in CROSS_SHAPES:
        raise NovaError("Unknown crosshair.")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color or ""):
        raise NovaError("Pick a color.")
    if size not in ("small", "medium", "large"):
        raise NovaError("Pick a size.")
    k = {"small": 0.7, "medium": 1.0, "large": 1.5}[size]
    rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    out = bytearray()
    sub = [(i + 0.5) / 3 - 0.5 for i in range(3)]
    for py in range(CROSS_PX):
        for px in range(CROSS_PX):
            fill = edge = 0
            for dy in sub:
                for dx in sub:
                    x, y = px + dx - CROSS_PX / 2 + 0.5, py + dy - CROSS_PX / 2 + 0.5
                    fill += _inside(shape, x, y, k, 0)
                    edge += _inside(shape, x, y, k, 1.1)
            f, e = fill / 9, edge / 9
            a = f + e * (1 - f) if e > f else f
            if a <= 0:
                out += bytes(4)
            else:
                out += bytes([round(c * f / a) for c in rgb]) + bytes([round(255 * a)])
    return encode_png(CROSS_PX, CROSS_PX, bytes(out))


def _cross_info() -> dict:
    return read_json(_cross_dir() / "crosshair.json", {}) or {}


def _cross_file() -> Path:
    return _cross_dir() / "crosshair.png"


def crosshair_info() -> dict:
    import base64
    f, meta = _cross_file(), _cross_info()
    prev = "data:image/png;base64," + base64.b64encode(f.read_bytes()).decode() if f.is_file() else ""
    return {"set": f.is_file(), "name": meta.get("name", ""), "pointer": bool(meta.get("pointer")), "preview": prev, "shapes": CROSS_SHAPES}


def _save_cross(png: bytes, name: str) -> dict:
    _cross_file().write_bytes(png)
    write_json(_cross_dir() / "crosshair.json", {**_cross_info(), "name": name})
    return crosshair_info()


def set_crosshair_preset(shape: str, color: str, size: str) -> dict:
    return _save_cross(render_crosshair(shape, color, size), CROSS_SHAPES.get(shape, shape))


def set_crosshair_image(tmp: Path, name: str) -> dict:
    try:
        data = tmp.read_bytes()
        if tmp.stat().st_size > 2 * 1024 * 1024:
            raise NovaError("That picture is too big for a crosshair.")
        try:
            w, h, _ = decode_png(data)
        except NovaError:
            raise NovaError("Use the Import button, which turns your picture into a crosshair.") from None
        if not (8 <= w <= 256 and 8 <= h <= 256):
            raise NovaError("A crosshair picture should be between 8 and 256 pixels wide.")
    finally:
        tmp.unlink(missing_ok=True)
    return _save_cross(data, (name or "Your picture")[:40])


def set_crosshair_pointer(on: bool) -> None:
    write_json(_cross_dir() / "crosshair.json", {**_cross_info(), "pointer": bool(on)})


def clear_crosshair() -> dict:
    _cross_file().unlink(missing_ok=True)
    shutil.rmtree(mods_dir() / CROSS_MOD, ignore_errors=True)
    return crosshair_info()


def build_crosshair_mod(vdir: Path) -> None:
    target = mods_dir() / CROSS_MOD
    shutil.rmtree(target, ignore_errors=True)
    if not _cross_file().is_file():
        return
    names = CROSS_AIM + (CROSS_POINTER if _cross_info().get("pointer") else ())
    for n in names:
        (target / CURSOR_DIR).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_cross_file(), target / CURSOR_DIR / n)


# ------------------------------------------------------------------ extras: death sound and FPS limit

FPS_FLAG = "DFIntTaskSchedulerTargetFps"
DEATH_SOUND = "content/sounds/ouch.ogg"                 # the "oof" Roblox plays when a character dies


def _snd_dir() -> Path:
    d = root() / "Sounds"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _silent_wav() -> bytes:
    n = 8000 // 5                                        # a fifth of a second of silence
    return b"RIFF" + struct.pack("<I", 36 + n) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 8000, 8000, 1, 8) + b"data" + struct.pack("<I", n) + b"\x80" * n


def _sound_mode() -> str:
    return (read_json(_snd_dir() / "sound.json", {}) or {}).get("death", "default")


def set_death_sound(mode: str, tmp: Path | None = None, name: str = "") -> None:
    """mode: default | mute | custom (a short .ogg, .mp3 or .wav you imported)."""
    try:
        if mode not in ("default", "mute", "custom"):
            raise NovaError("Pick default, mute or your own sound.")
        if mode == "custom":
            if tmp is None or not tmp.is_file() or tmp.stat().st_size > 2 * 1024 * 1024:
                raise NovaError("Pick a sound under 2 MB.")
            head = tmp.read_bytes()[:12]
            if not (head[:4] == b"OggS" or head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2") or (head[:4] == b"RIFF" and head[8:12] == b"WAVE")):
                raise NovaError("Use an .ogg, .mp3 or .wav sound.")
            shutil.copyfile(tmp, _snd_dir() / "death.snd")
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    write_json(_snd_dir() / "sound.json", {"death": mode, "name": (name or "")[:40]})


def build_sound_mod(vdir: Path) -> None:
    target = mods_dir() / SOUND_MOD
    shutil.rmtree(target, ignore_errors=True)
    mode = _sound_mode()
    if mode == "default":
        return
    src = _snd_dir() / "death.snd"
    if mode == "custom" and not src.is_file():
        return
    (target / DEATH_SOUND).parent.mkdir(parents=True, exist_ok=True)
    if mode == "mute":
        (target / DEATH_SOUND).write_bytes(_silent_wav())
    else:
        shutil.copyfile(src, target / DEATH_SOUND)


def set_fps_cap(fps: int | None) -> None:
    """None puts Roblox's own limit back. Otherwise 30-9999."""
    flags = load_flags()
    if fps is None:
        flags.pop(FPS_FLAG, None)
    else:
        if isinstance(fps, bool) or not isinstance(fps, int) or not 30 <= fps <= 9999:
            raise NovaError("Pick an FPS limit between 30 and 9999.")
        flags[FPS_FLAG] = fps
    save_flags(flags)


def extras_info() -> dict:
    meta = read_json(_snd_dir() / "sound.json", {}) or {}
    fps = load_flags().get(FPS_FLAG)
    return {"death": meta.get("death", "default"), "death_name": meta.get("name", ""), "fps": fps if isinstance(fps, int) and not isinstance(fps, bool) else None}


def _weather_info() -> dict:
    from . import weather
    return {**weather.settings(), "kinds": weather.KINDS, "levels": weather.LEVELS, "available": weather.available()}
