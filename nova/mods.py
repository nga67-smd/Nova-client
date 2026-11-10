"""Mod / shader / resource-pack management backed by the Modrinth API."""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from . import config, instances
from .util import NovaError, Task, USER_AGENT, download_file, file_hash, http_get_json, read_json, write_json

KINDS = {"mod": "mods", "shader": "shaderpacks", "resourcepack": "resourcepacks"}


def loader_categories(loader: str) -> list[str]:
    return {"fabric": ["fabric"], "quilt": ["quilt", "fabric"], "forge": ["forge"],
            "neoforge": ["neoforge"], "optifine": ["forge"]}.get(loader, [])


def _api(path: str, params: dict | None = None):
    url = config.modrinth_api() + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return http_get_json(url)


def _post_json(path: str, body: dict):
    req = urllib.request.Request(config.modrinth_api() + path, data=json.dumps(body).encode(),
                                 headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        raise NovaError(f"Modrinth request failed: {e}")


# ----------------------------------------------------------------- search

def search(query: str, mc: str = "", loader: str = "", ptype: str = "mod", sort: str = "relevance",
           offset: int = 0, limit: int = 20) -> dict:
    if ptype not in KINDS:
        raise NovaError("Unknown project type.")
    facets = [[f"project_type:{ptype}"]]
    if mc:
        facets.append([f"versions:{mc}"])
    cats = loader_categories(loader) if ptype == "mod" else []
    if cats:
        facets.append([f"categories:{c}" for c in cats])
    if sort not in ("relevance", "downloads", "follows", "newest", "updated"):
        sort = "relevance"
    data = _api("/search", {"query": query, "facets": json.dumps(facets), "index": sort,
                            "offset": max(0, offset), "limit": max(1, min(limit, 50))})
    hits = [{"project_id": h["project_id"], "slug": h["slug"], "title": h["title"],
             "description": h.get("description", ""), "icon_url": h.get("icon_url") or "",
             "downloads": h.get("downloads", 0), "follows": h.get("follows", 0), "author": h.get("author", ""),
             "categories": h.get("display_categories") or h.get("categories", [])[:4],
             "client_side": h.get("client_side"), "server_side": h.get("server_side")}
            for h in data.get("hits", [])]
    return {"hits": hits, "total": data.get("total_hits", len(hits))}


# --------------------------------------------------------------- versions

def pick_version(project: str, mc: str, loader: str, ptype: str = "mod") -> dict | None:
    params: dict = {}
    if mc:
        params["game_versions"] = json.dumps([mc])
    cats = loader_categories(loader) if ptype == "mod" else []
    if cats:
        params["loaders"] = json.dumps(cats)
    vs = _api(f"/project/{urllib.parse.quote(project)}/version", params)
    if not vs:
        return None
    order = {"release": 0, "beta": 1, "alpha": 2}
    vs.sort(key=lambda v: v.get("date_published", ""), reverse=True)
    vs.sort(key=lambda v: order.get(v.get("version_type", "release"), 3))
    # when several loaders are acceptable (quilt accepts fabric) prefer native loader files
    if cats and len(cats) > 1:
        native = [v for v in vs if cats[0] in v.get("loaders", [])]
        if native and order.get(native[0].get("version_type"), 3) <= order.get(vs[0].get("version_type"), 3):
            return native[0]
    return vs[0]


def _meta_path(inst_id: str) -> Path:
    return instances.game_dir(inst_id) / "nova_mods.json"


def _load_meta(inst_id: str) -> dict:
    return read_json(_meta_path(inst_id), {}) or {}


def _kind_dir(inst_id: str, ptype: str) -> Path:
    if ptype not in KINDS:
        raise NovaError("Unknown content type.")
    return instances.game_dir(inst_id) / KINDS[ptype]


def safe_name(name: str) -> str:
    n = Path(str(name)).name
    if not n or n.startswith("."):
        raise NovaError("Invalid file name.")
    return n


def install_project(inst: dict, project: str, ptype: str = "mod", task: Task | None = None,
                    _seen: set | None = None, _depth: int = 0) -> list[dict]:
    """Install a project plus its required dependencies. Returns list of installed entries."""
    seen = _seen if _seen is not None else set()
    if _depth > 6:
        return []
    ver = pick_version(project, inst["mc_version"], inst["loader"], ptype)
    if not ver:
        raise NovaError(f"'{project}' has no version for Minecraft {inst['mc_version']}"
                        + (f" on {inst['loader'].title()}" if ptype == "mod" and inst["loader"] != "vanilla" else "") + ".")
    pid = ver["project_id"]
    if pid in seen:
        return []
    seen.add(pid)
    proj = _api(f"/project/{pid}")
    files = ver.get("files", [])
    primary = next((f for f in files if f.get("primary")), files[0] if files else None)
    if not primary:
        raise NovaError(f"{proj.get('title', project)} has no downloadable file.")
    fname = safe_name(primary["filename"])
    folder = _kind_dir(inst["id"], ptype)
    folder.mkdir(parents=True, exist_ok=True)
    meta = _load_meta(inst["id"])
    # drop older copies of the same project
    for old, m in list(meta.items()):
        if m.get("project_id") == pid and old != fname:
            for suffix in ("", ".disabled"):
                try:
                    (_kind_dir(inst["id"], m.get("type", "mod")) / (old + suffix)).unlink()
                except OSError:
                    pass
            meta.pop(old, None)
    if task:
        task.update(f"Installing {proj.get('title', fname)}…")
    download_file(primary["url"], folder / fname, sha1=primary.get("hashes", {}).get("sha1"),
                  sha512=primary.get("hashes", {}).get("sha512"))
    meta[fname] = {"project_id": pid, "slug": proj.get("slug", project), "title": proj.get("title", fname),
                   "icon_url": proj.get("icon_url") or "", "version": ver.get("version_number", ""),
                   "version_id": ver["id"], "type": ptype}
    write_json(_meta_path(inst["id"]), meta)
    installed = [{"title": proj.get("title", fname), "file": fname, "version": ver.get("version_number", "")}]
    if ptype == "mod":
        for dep in ver.get("dependencies", []):
            if dep.get("dependency_type") != "required" or not dep.get("project_id"):
                continue
            if dep["project_id"] in seen:
                continue
            already = any(m.get("project_id") == dep["project_id"] for m in _load_meta(inst["id"]).values())
            if already:
                seen.add(dep["project_id"])
                continue
            try:
                installed += install_project(inst, dep["project_id"], "mod", task, seen, _depth + 1)
            except NovaError:
                pass  # optional-ish dependency with no matching build; the game will report it
    return installed


# ---------------------------------------------------------------- listing

def list_installed(inst: dict, ptype: str = "mod") -> list[dict]:
    folder = _kind_dir(inst["id"], ptype)
    meta = _load_meta(inst["id"])
    out = []
    if not folder.exists():
        return out
    for f in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if f.name.startswith("."):
            continue
        name = f.name
        enabled = True
        if name.endswith(".disabled"):
            enabled, name = False, name[:-9]
        if ptype == "mod" and not name.lower().endswith(".jar"):
            continue
        m = meta.get(name, {})
        out.append({"file": name, "enabled": enabled,
                    "size": f.stat().st_size if f.is_file() else 0,
                    "title": m.get("title") or re.sub(r"\.(jar|zip)$", "", name, flags=re.I),
                    "version": m.get("version", ""), "icon_url": m.get("icon_url", ""),
                    "slug": m.get("slug", ""), "managed": bool(m)})
    return out


def toggle(inst: dict, ptype: str, filename: str) -> bool:
    folder = _kind_dir(inst["id"], ptype)
    fn = safe_name(filename)
    on, off = folder / fn, folder / (fn + ".disabled")
    if on.exists():
        on.rename(off)
        return False
    if off.exists():
        off.rename(on)
        return True
    raise NovaError("File not found.")


def remove(inst: dict, ptype: str, filename: str) -> None:
    folder = _kind_dir(inst["id"], ptype)
    fn = safe_name(filename)
    removed = False
    for suffix in ("", ".disabled"):
        p = folder / (fn + suffix)
        if p.is_file():
            p.unlink()
            removed = True
    if not removed:
        raise NovaError("File not found.")
    meta = _load_meta(inst["id"])
    if meta.pop(fn, None) is not None:
        write_json(_meta_path(inst["id"]), meta)


# ---------------------------------------------------------------- updates

def check_updates(inst: dict) -> list[dict]:
    """Ask Modrinth whether newer builds exist for installed mods (matched by file hash)."""
    folder = _kind_dir(inst["id"], "mod")
    hashes: dict[str, str] = {}
    if folder.exists():
        for f in folder.glob("*.jar"):
            hashes[file_hash(f, "sha1")] = f.name
    if not hashes:
        return []
    body = {"hashes": list(hashes), "algorithm": "sha1", "game_versions": [inst["mc_version"]]}
    cats = loader_categories(inst["loader"])
    if cats:
        body["loaders"] = cats
    res = _post_json("/version_files/update", body)
    out = []
    for h, ver in res.items():
        files = ver.get("files", [])
        primary = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not primary:
            continue
        if primary.get("hashes", {}).get("sha1", "").lower() != h.lower() and ver.get("version_type") != "alpha":
            out.append({"file": hashes[h], "project_id": ver["project_id"], "new_version": ver.get("version_number", "")})
    return out


def update_all(inst: dict, task: Task | None = None) -> int:
    ups = check_updates(inst)
    n = 0
    for i, u in enumerate(ups):
        if task:
            task.update(f"Updating {u['file']}… ({i + 1}/{len(ups)})", (i) / max(1, len(ups)))
        try:
            install_project(inst, u["project_id"], "mod")
            n += 1
        except NovaError:
            continue
    return n


# ---------------------------------------------------- optimization packs

OPT_PACKS = {
    "fabric": [
        {"slug": "sodium", "name": "Sodium", "why": "Rewrites the renderer. The single biggest FPS boost.", "default": True},
        {"slug": "lithium", "name": "Lithium", "why": "Faster game logic, physics and AI.", "default": True},
        {"slug": "ferrite-core", "name": "FerriteCore", "why": "Cuts memory use.", "default": True},
        {"slug": "modernfix", "name": "ModernFix", "why": "Faster startup and lower RAM.", "default": True},
        {"slug": "immediatelyfast", "name": "ImmediatelyFast", "why": "Speeds up immediate-mode rendering and the UI.", "default": True},
        {"slug": "entityculling", "name": "Entity Culling", "why": "Skips drawing entities you cannot see.", "default": True},
        {"slug": "moreculling", "name": "More Culling", "why": "Culls hidden block faces and more.", "default": False},
        {"slug": "dynamic-fps", "name": "Dynamic FPS", "why": "Drops frame rate when the window is unfocused.", "default": True},
        {"slug": "sodium-extra", "name": "Sodium Extra", "why": "Extra video options for Sodium.", "default": False},
        {"slug": "c2me-fabric", "name": "C2ME", "why": "Multithreaded chunk loading. Great on many-core CPUs.", "default": False},
        {"slug": "ksyxis", "name": "Ksyxis", "why": "Much faster world loading.", "default": False},
        {"slug": "memoryleakfix", "name": "MemoryLeakFix", "why": "Plugs known vanilla memory leaks.", "default": False},
        {"slug": "iris", "name": "Iris Shaders", "why": "Shader pack support that works with Sodium.", "default": False},
    ],
    "forge": [
        {"slug": "embeddium", "name": "Embeddium", "why": "Sodium for Forge. Big renderer speedup.", "default": True},
        {"slug": "ferrite-core", "name": "FerriteCore", "why": "Cuts memory use.", "default": True},
        {"slug": "modernfix", "name": "ModernFix", "why": "Faster startup and lower RAM.", "default": True},
        {"slug": "immediatelyfast", "name": "ImmediatelyFast", "why": "Speeds up immediate-mode rendering.", "default": True},
        {"slug": "entityculling", "name": "Entity Culling", "why": "Skips drawing entities you cannot see.", "default": True},
        {"slug": "memoryleakfix", "name": "MemoryLeakFix", "why": "Plugs known vanilla memory leaks.", "default": False},
        {"slug": "oculus", "name": "Oculus", "why": "Shader pack support (Iris for Forge).", "default": False},
    ],
}
OPT_PACKS["quilt"] = OPT_PACKS["fabric"]
OPT_PACKS["neoforge"] = OPT_PACKS["forge"]


def optimization_pack(loader: str) -> list[dict]:
    return OPT_PACKS.get(loader, [])


def install_optimization_pack(inst: dict, slugs: list[str], task: Task | None = None) -> dict:
    allowed = {p["slug"] for p in optimization_pack(inst["loader"])}
    done, skipped = [], []
    seen: set = set()
    slugs = [s for s in slugs if s in allowed]
    for i, slug in enumerate(slugs):
        if task:
            task.update(f"Installing {slug}… ({i + 1}/{len(slugs)})", i / max(1, len(slugs)))
        try:
            res = install_project(inst, slug, "mod", task, seen)
            done += [r["title"] for r in res]
        except NovaError as e:
            skipped.append({"slug": slug, "reason": str(e)})
    return {"installed": done, "skipped": skipped}
