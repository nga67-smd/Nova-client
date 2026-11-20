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


def overlay_dir() -> Path | None:
    """The Modifications folder of a Bloxstrap-style launcher, when that is where the found Roblox comes from. Those launchers
    check Roblox's files every time they start it and put back anything that isn't in their Modifications folder."""
    src = _state().get("from", "")
    base = os.environ.get("LOCALAPPDATA")
    if base and src in ("Bloxstrap", "Voidstrap", "Fishstrap"):
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
    """The one folder to open for sky textures: the launcher's own Modifications sky folder (Fishstrap etc. keep what is put
    there), otherwise Roblox's sky folder."""
    ov = overlay_dir()
    if ov:
        d = ov / SKY_DEFAULT_DIRS[0]
        d.mkdir(parents=True, exist_ok=True)
        return d
    return sky_folder(version_dir())


def import_sky_pack(tmp: Path) -> dict:
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
                m = re.fullmatch(r"sky(\d*)_(bk|dn|ft|lf|rt|up)\.(tex|dds)", Path(info.filename).name, re.I)
                if not m or info.is_dir() or info.file_size > 16 * 1024 * 1024:
                    continue
                code = m.group(2).lower()
                if code in found and m.group(1) != "512":
                    continue
                data = z.read(info)
                if data[:4] == b"DDS ":
                    found[code] = data
    finally:
        tmp.unlink(missing_ok=True)
    if not found:
        raise NovaError("No sky textures (sky512_ft.tex and so on) were found in that .zip.")
    clear_sky()
    for face, code in SKY_FACES.items():
        if code in found:
            (_sky_dir() / f"{face}.dds").write_bytes(found[code])
    return sky_info()


def build_sky_mod(vdir: Path) -> None:
    """Turn the chosen sky pictures into a mod that replaces Roblox's own sky files, so every default sky changes."""
    target = mods_dir() / SKY_MOD
    shutil.rmtree(target, ignore_errors=True)
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
            "sky": sky_info(), "sky_presets": {k: v[0] for k, v in SKY_PRESETS.items()}, "mods": mods_info(), "path": str(root()), "sky_folder": str(sky_folder(Path(st["dir"]))) if v else ""}


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
