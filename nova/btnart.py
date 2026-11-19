"""Your own picture as the background of a kind of button (main, other, delete buttons).

Files stay in the data folder, are checked by content (PNG/JPEG/WebP/GIF only) and are only shown inside Nova.
"""
from __future__ import annotations

from pathlib import Path

from . import paths
from .util import NovaError

SLOTS = ("primary", "normal", "danger")
MAX_BYTES = 64 * 1024 * 1024
TYPES = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}


def _dir() -> Path:
    d = paths.data_dir() / "button_art"
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


def _find(slot: str) -> Path | None:
    for ext in TYPES:
        p = _dir() / f"{slot}.{ext}"
        if p.exists():
            return p
    return None


def load() -> dict:
    """{slot: version} for every slot that has a picture; the version changes when the picture does."""
    out = {}
    for s in SLOTS:
        p = _find(s)
        if p:
            out[s] = int(p.stat().st_mtime)
    return out


def set_picture(slot: str, tmp: Path) -> dict:
    if slot not in SLOTS:
        tmp.unlink(missing_ok=True)
        raise NovaError("Unknown button.")
    ext = sniff(tmp)
    if not ext:
        tmp.unlink(missing_ok=True)
        raise NovaError("That isn't a PNG, JPEG, WebP or GIF picture.")
    if tmp.stat().st_size > MAX_BYTES:
        tmp.unlink(missing_ok=True)
        raise NovaError("Pictures must be under 64 MB.")
    remove(slot)
    tmp.replace(_dir() / f"{slot}.{ext}")
    return load()


def remove(slot: str) -> dict:
    if slot in SLOTS:
        for ext in TYPES:
            (_dir() / f"{slot}.{ext}").unlink(missing_ok=True)
    return load()


def file_for(slot: str) -> tuple[Path, str] | None:
    if slot not in SLOTS:
        return None
    p = _find(slot)
    return (p, TYPES[p.suffix[1:]]) if p else None
