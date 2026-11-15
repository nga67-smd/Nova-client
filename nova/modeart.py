"""Your own pictures for Kawaii / Emo mode (anime art, band photos, whatever you like).

Nova can't fetch pictures from the web for you, so you import your own. Files are kept in the data folder, checked by
content (PNG/JPEG/WebP/GIF only), and only ever shown inside Nova.
"""
from __future__ import annotations

import re
import secrets
from pathlib import Path

from . import paths
from .util import NovaError, read_json, write_json

MODES = ("kawaii", "emo")
MAX_BYTES = 4 * 1024 * 1024
MAX_PER_MODE = 8
ID = re.compile(r"^a[0-9a-f]{8}$")
TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}


def _dir() -> Path:
    d = paths.data_dir() / "mode_art"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sniff(path: Path) -> str:
    """'png' / 'jpg' / 'webp' / 'gif', or '' when the file isn't one of those pictures."""
    try:
        with open(path, "rb") as f:
            h = f.read(16)
    except OSError:
        return ""
    if h.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if h.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP":
        return "webp"
    if h[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return ""


def load() -> list[dict]:
    items = read_json(_dir() / "index.json", []) or []
    return [i for i in items if isinstance(i, dict) and ID.match(str(i.get("id", ""))) and i.get("mode") in MODES and i.get("ext") in TYPES
            and (_dir() / f"{i['id']}.{i['ext']}").exists()]


def add(mode: str, tmp: Path) -> list[dict]:
    """Take ownership of an uploaded temp file for `mode` and return the new list."""
    if mode not in MODES:
        tmp.unlink(missing_ok=True)
        raise NovaError("Pictures can be added in Kawaii or Emo mode.")
    ext = sniff(tmp)
    if not ext:
        tmp.unlink(missing_ok=True)
        raise NovaError("That isn't a PNG, JPEG, WebP or GIF picture.")
    if tmp.stat().st_size > MAX_BYTES:
        tmp.unlink(missing_ok=True)
        raise NovaError("Pictures must be under 4 MB.")
    items = load()
    if sum(1 for i in items if i["mode"] == mode) >= MAX_PER_MODE:
        tmp.unlink(missing_ok=True)
        raise NovaError(f"You can keep up to {MAX_PER_MODE} pictures per mode. Remove one first.")
    pid = "a" + secrets.token_hex(4)
    tmp.replace(_dir() / f"{pid}.{ext}")
    items.append({"id": pid, "mode": mode, "ext": ext})
    write_json(_dir() / "index.json", items)
    return items


def remove(pid: str) -> list[dict]:
    items = load()
    keep = []
    for i in items:
        if i["id"] == pid:
            (_dir() / f"{i['id']}.{i['ext']}").unlink(missing_ok=True)
        else:
            keep.append(i)
    write_json(_dir() / "index.json", keep)
    return keep


def file_for(pid: str) -> tuple[Path, str] | None:
    if not ID.match(pid or ""):
        return None
    for i in load():
        if i["id"] == pid:
            return _dir() / f"{pid}.{i['ext']}", TYPES[i["ext"]]
    return None
