"""Nova cosmetics: a saved skin (hats, face gear, chest emblems, boots) and cape designed in the Cosmetics tab.

The pictures are drawn in the browser (canvas) and arrive here as PNG data. Nova validates and stores them, can upload the
skin to the signed-in Minecraft account (so everyone sees it), and copies skin + cape into each game folder for the Nova
in-game mod, which shows the cape (Mojang has no way to upload custom capes) and the skin on your own player.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import struct
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from . import accounts, msauth, paths, settings
from .util import NovaError, USER_AGENT, read_json, write_json

PNG_SIG = b"\x89PNG\r\n\x1a\n"
MAX_PNG = 64 * 1024
TEXTURE_HOSTS = (".minecraft.net",)          # skins are only fetched from Mojang's texture servers
SKIN_SIZES = {(64, 64), (64, 32)}
CAPE_SIZES = {(64, 32)}
ID = re.compile(r"^[a-z0-9_]{1,32}$")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
SELECT_KEYS = ("hat", "face", "chest", "feet", "cape")


def _dir() -> Path:
    d = paths.data_dir() / "cosmetics"
    d.mkdir(parents=True, exist_ok=True)
    return d


def png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != PNG_SIG or data[12:16] != b"IHDR":
        raise NovaError("That isn't a PNG image.")
    return struct.unpack(">II", data[16:24])


def decode_png_data(value: str, sizes: set, what: str) -> bytes:
    """Accept a base64 string or data: URL holding a PNG of one of the allowed sizes."""
    if not isinstance(value, str) or not value:
        raise NovaError(f"Missing {what}.")
    if value.startswith("data:"):
        value = value.split(",", 1)[-1]
    try:
        raw = base64.b64decode(value, validate=False)
    except ValueError:
        raise NovaError(f"The {what} image is corrupt.")
    if len(raw) > MAX_PNG:
        raise NovaError(f"The {what} image is too large.")
    if png_size(raw) not in sizes:
        raise NovaError(f"The {what} image has the wrong size.")
    return raw


def clean_state(raw: dict) -> dict:
    sel = raw.get("selected") if isinstance(raw.get("selected"), dict) else {}
    out_sel = {k: (sel.get(k) if isinstance(sel.get(k), str) and ID.match(sel.get(k, "")) else "") for k in SELECT_KEYS}
    colors = raw.get("colors") if isinstance(raw.get("colors"), dict) else {}
    return {"selected": out_sel,
            "colors": {"main": colors.get("main") if HEX.match(str(colors.get("main", ""))) else "#8b5cf6",
                       "trim": colors.get("trim") if HEX.match(str(colors.get("trim", ""))) else "#f0abfc"},
            "variant": "slim" if raw.get("variant") == "slim" else "classic"}


def load() -> dict:
    state = clean_state(read_json(_dir() / "state.json", {}) or {})
    state["has_skin"] = (_dir() / "skin.png").exists()
    state["has_cape"] = (_dir() / "cape.png").exists()
    state["has_base"] = (_dir() / "base.png").exists()
    return state


def read_file(kind: str) -> bytes | None:
    if kind not in ("skin", "cape", "base"):
        raise NovaError("Unknown file.")
    f = _dir() / f"{kind}.png"
    return f.read_bytes() if f.exists() else None


def save(body: dict) -> dict:
    skin = decode_png_data(body.get("skin"), SKIN_SIZES, "skin")
    cape = decode_png_data(body.get("cape"), CAPE_SIZES, "cape") if body.get("cape") else None
    if "cape" in body and not body.get("cape"):
        (_dir() / "cape.png").unlink(missing_ok=True)        # the cape was switched off
    base = decode_png_data(body.get("base"), SKIN_SIZES, "base skin") if body.get("base") else None
    d = _dir()
    for name, data in (("skin", skin), ("cape", cape), ("base", base)):
        if data is not None:
            tmp = d / (name + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, d / f"{name}.png")
    state = clean_state(body.get("state") or {})
    write_json(d / "state.json", state)
    return load()


def reset() -> dict:
    shutil.rmtree(_dir(), ignore_errors=True)
    return load()


def sync_to_game(game_dir: Path) -> None:
    """Put the saved skin/cape where the Nova in-game mod looks for them (nothing is written without a saved design)."""
    src = _dir()
    dst = Path(game_dir) / "nova-cosmetics"
    have = [n for n in ("skin.png", "cape.png") if (src / n).exists()]
    if not have:
        shutil.rmtree(dst, ignore_errors=True)
        return
    dst.mkdir(parents=True, exist_ok=True)
    for n in ("skin.png", "cape.png"):
        if (src / n).exists():
            shutil.copyfile(src / n, dst / n)
        else:
            (dst / n).unlink(missing_ok=True)
    state = load()
    (dst / "model.txt").write_text(state["variant"], encoding="utf-8")


# ----------------------------------------------------------- Mojang account

def _account() -> dict:
    acc = accounts.selected()
    if not acc or acc.get("type") != "microsoft":
        raise NovaError("Sign in with Microsoft in Profiles first. Offline profiles can't change their Minecraft skin online.")
    return msauth.ensure_fresh(acc, settings.load().get("ms_client_id", ""))


def _request(url: str, *, bearer: str, data: bytes | None = None, ctype: str | None = None) -> tuple[int, bytes]:
    headers = {"User-Agent": USER_AGENT, "Authorization": "Bearer " + bearer, "Accept": "application/json"}
    if ctype:
        headers["Content-Type"] = ctype
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise NovaError(f"Couldn't reach Minecraft's servers ({e}). Check your internet connection.") from e


def current_skin() -> dict:
    """The signed-in account's active skin as base64 PNG, or {} when there's no Microsoft account."""
    acc = accounts.selected()
    if not acc or acc.get("type") != "microsoft":
        return {}
    acc = _account()
    st, raw = _request(msauth.URLS["profile"], bearer=acc["mc_token"])
    if st != 200:
        raise NovaError("Couldn't read your Minecraft profile right now.")
    skins = json.loads(raw.decode("utf-8") or "{}").get("skins", [])
    active = next((s for s in skins if s.get("state") == "ACTIVE"), skins[0] if skins else None)
    if not active or not active.get("url"):
        return {}
    url = active["url"]
    host = urllib.parse.urlparse(url).hostname or ""
    if not urllib.parse.urlparse(url).scheme in ("http", "https") or not host.endswith(TEXTURE_HOSTS):
        raise NovaError("Unexpected skin location.")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=30) as r:
        png = r.read(MAX_PNG + 1)
    if len(png) > MAX_PNG or png_size(png) not in SKIN_SIZES:
        raise NovaError("Your current skin isn't in a format Nova can edit.")
    return {"png": base64.b64encode(png).decode(), "variant": "slim" if str(active.get("variant", "")).upper() == "SLIM" else "classic"}


def upload_skin() -> dict:
    skin = read_file("skin")
    if not skin:
        raise NovaError("Save your design first.")
    if png_size(skin) != (64, 64):
        raise NovaError("Only 64x64 skins can be uploaded.")
    acc = _account()
    variant = load()["variant"]
    boundary = "----nova" + uuid.uuid4().hex
    parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"variant\"\r\n\r\n{variant}\r\n".encode(),
             f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"nova-skin.png\"\r\n"
             f"Content-Type: image/png\r\n\r\n".encode(), skin, f"\r\n--{boundary}--\r\n".encode()]
    st, raw = _request(msauth.URLS["profile_skins"], bearer=acc["mc_token"], data=b"".join(parts),
                       ctype=f"multipart/form-data; boundary={boundary}")
    if st == 200:
        return {"ok": True}
    if st == 429:
        raise NovaError("Minecraft is rate-limiting skin changes. Wait a minute and try again.")
    if st in (401, 403):
        raise NovaError("Minecraft refused the skin change. Sign in again in Profiles, then retry.")
    raise NovaError(f"Minecraft rejected the skin (HTTP {st}).")
