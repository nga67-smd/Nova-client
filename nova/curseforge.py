"""CurseForge backend for mods / shaders / resource packs.

CurseForge's API needs a (free) API key from https://console.curseforge.com. Nova keeps the key in the
data folder (owner-only file) and never sends it anywhere except api.curseforge.com.
Project ids are written "cf:<number>" everywhere in Nova so they can't clash with Modrinth ids.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from . import config, paths
from .util import NovaError, USER_AGENT

GAME_ID = 432
CLASS_IDS = {"mod": 6, "resourcepack": 12, "shader": 6552}
LOADER_TYPES = {"forge": 1, "fabric": 4, "quilt": 5, "neoforge": 6}
SORT_FIELDS = {"relevance": 2, "downloads": 6, "follows": 2, "newest": 11, "updated": 3}
PREFIX = "cf:"


# --------------------------------------------------------------------- key

def _key_file():
    return paths.data_dir() / "curseforge.key"


def get_key() -> str:
    k = os.environ.get("NOVA_CURSEFORGE_KEY", "").strip()
    if k:
        return k
    try:
        k = _key_file().read_text(encoding="utf-8").strip()
    except OSError:
        k = ""
    return k or config.BUILTIN_CURSEFORGE_KEY.strip()


def has_key() -> bool:
    return bool(get_key())


def set_key(key: str) -> None:
    key = (key or "").strip().strip("\"'")
    f = _key_file()
    if not key:
        try:
            f.unlink()
        except OSError:
            pass
        return
    if len(key) < 20 or len(key) > 200 or any(c.isspace() for c in key):
        raise NovaError("That doesn't look like a CurseForge API key. Copy the whole key from console.curseforge.com.")
    f.parent.mkdir(parents=True, exist_ok=True)
    old = f.read_text(encoding="utf-8") if f.exists() else None
    f.write_text(key, encoding="utf-8")
    try:
        os.chmod(f, 0o600)
    except OSError:
        pass
    if os.environ.get("NOVA_CURSEFORGE_KEY"):
        return
    try:
        _api(f"/games/{GAME_ID}")          # prove the key works before keeping it
    except NovaError as e:
        if "rejected" in str(e):
            if old is None:
                f.unlink(missing_ok=True)
            else:
                f.write_text(old, encoding="utf-8")
            raise


def is_id(project: str) -> bool:
    return str(project).startswith(PREFIX)


def _num(project: str) -> int:
    try:
        return int(str(project)[len(PREFIX):])
    except ValueError:
        raise NovaError("Invalid CurseForge project.")


# --------------------------------------------------------------------- http

def _api(path: str, params: dict | None = None):
    key = get_key()
    if not key:
        raise NovaError("Add your CurseForge API key in Settings to use CurseForge.")
    url = config.curseforge_api() + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"x-api-key": key, "Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            try:
                detail = e.read().decode("utf-8", "replace").strip().replace("\n", " ")[:120]
            except OSError:
                detail = ""
            raise NovaError(f"CurseForge rejected the API key (HTTP {e.code}{': ' + detail if detail else ''}). "
                            "Paste the whole key from console.curseforge.com → API keys (it usually starts with $2a$10$).") from e
        if e.code == 404:
            raise NovaError("CurseForge doesn't have that project.") from e
        if e.code == 429:
            raise NovaError("CurseForge is rate-limiting requests. Wait a moment and try again.") from e
        raise NovaError(f"CurseForge request failed (HTTP {e.code}).") from e
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise NovaError(f"Couldn't reach CurseForge ({e}). Check your internet connection.") from e


def loader_types(loader: str) -> list[int]:
    """CurseForge loader ids to accept, native loader first."""
    return {"quilt": [5, 4], "optifine": [1]}.get(loader) or ([LOADER_TYPES[loader]] if loader in LOADER_TYPES else [])


# ------------------------------------------------------------------- search

def search(query: str, mc: str, loader: str, ptype: str, sort: str, offset: int, limit: int = 20) -> dict:
    if ptype not in CLASS_IDS:
        raise NovaError("Unknown project type.")
    params = {"gameId": GAME_ID, "classId": CLASS_IDS[ptype], "searchFilter": query,
              "sortField": SORT_FIELDS.get(sort, 2), "sortOrder": "desc",
              "index": max(0, offset), "pageSize": max(1, min(limit, 50))}
    if mc:
        params["gameVersion"] = mc
    lt = loader_types(loader) if ptype == "mod" else []
    if lt:
        params["modLoaderType"] = lt[0]   # the API takes one loader; Quilt searches also show Quilt-tagged mods first
        if len(lt) > 1:
            del params["modLoaderType"]   # Quilt: fabric mods work too, so don't filter the search
    data = _api("/mods/search", params)
    hits = []
    for h in data.get("data", []):
        hits.append({"project_id": f"{PREFIX}{h['id']}", "slug": h.get("slug", ""), "title": h.get("name", ""),
                     "description": h.get("summary", ""), "icon_url": (h.get("logo") or {}).get("thumbnailUrl", ""),
                     "downloads": int(h.get("downloadCount", 0)), "follows": int(h.get("thumbsUpCount", 0)),
                     "author": ", ".join(a.get("name", "") for a in h.get("authors", [])[:2]),
                     "categories": [c.get("name", "") for c in h.get("categories", [])[:4]],
                     "source": "curseforge", "url": (h.get("links") or {}).get("websiteUrl", "")})
    pag = data.get("pagination", {})
    return {"hits": hits, "total": int(pag.get("totalCount", len(hits)))}


# ----------------------------------------------------------------- versions

def _rank(f: dict):
    return (f.get("releaseType", 1), -_ts(f.get("fileDate", "")))


def _ts(s: str) -> int:
    return int("".join(c for c in s[:19] if c.isdigit()) or 0)


def pick_file(project: str, mc: str, loader: str, ptype: str = "mod") -> dict | None:
    """Best file (release > beta > alpha, then newest) for this Minecraft version and loader."""
    mid = _num(project)
    lts = loader_types(loader) if ptype == "mod" else []
    tries = lts or [0]
    for lt in tries:
        params = {"pageSize": 50}
        if mc:
            params["gameVersion"] = mc
        if lt:
            params["modLoaderType"] = lt
        files = [f for f in _api(f"/mods/{mid}/files", params).get("data", []) if f.get("isAvailable", True)]
        if files:
            files.sort(key=_rank)
            return files[0]
    return None


def mod_info(project: str) -> dict:
    return _api(f"/mods/{_num(project)}").get("data", {})


def download_info(f: dict) -> tuple[str, str | None]:
    """(url, sha1) for a file entry. Authors can disable third-party downloads: then there is no URL."""
    url = f.get("downloadUrl")
    if not url:
        raise NovaError(f"The author of '{f.get('displayName') or f.get('fileName')}' doesn't allow downloads outside "
                        "CurseForge. Download it from curseforge.com and drop it into the mods folder.")
    sha1 = next((h.get("value") for h in f.get("hashes", []) if h.get("algo") == 1), None)
    return url, sha1


def required_deps(f: dict) -> list[str]:
    return [f"{PREFIX}{d['modId']}" for d in f.get("dependencies", []) if d.get("relationType") == 3 and d.get("modId")]
