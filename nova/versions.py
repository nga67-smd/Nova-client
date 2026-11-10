"""Minecraft version manifest, version-JSON resolution, libraries, natives, assets."""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

from . import config, paths
from .util import (NovaError, Task, download_file, download_many, http_get_json, read_json,
                   write_json, safe_extract_zip)

# --------------------------------------------------------------- manifest

def get_manifest(force: bool = False) -> dict:
    cache = paths.cache_dir() / "version_manifest.json"
    if not force and cache.exists() and time.time() - cache.stat().st_mtime < 3600:
        data = read_json(cache)
        if data:
            return data
    try:
        data = http_get_json(config.mojang_manifest(), retries=2, timeout=15)
        write_json(cache, data)
        return data
    except NovaError:
        data = read_json(cache)
        if data:
            return data
        raise NovaError("Could not reach Mojang's servers and no cached version list exists. "
                        "Check your internet connection.")


def list_versions(kinds: set[str] | None = None) -> list[dict]:
    m = get_manifest()
    out = []
    for v in m.get("versions", []):
        if kinds and v.get("type") not in kinds:
            continue
        out.append({"id": v["id"], "type": v["type"], "releaseTime": v.get("releaseTime", "")})
    return out


def latest() -> dict:
    return get_manifest().get("latest", {})


# ----------------------------------------------------------- version JSON

def version_json_path(vid: str) -> Path:
    return paths.versions_dir() / vid / f"{vid}.json"


def load_raw_version(vid: str) -> dict:
    p = version_json_path(vid)
    data = read_json(p)
    if data:
        return data
    # not local: look it up in the Mojang manifest
    for v in get_manifest().get("versions", []):
        if v["id"] == vid:
            data = http_get_json(v["url"])
            write_json(p, data)
            return data
    raise NovaError(f"Minecraft version '{vid}' was not found.")


def resolve_version(vid: str, _depth: int = 0) -> dict:
    """Return the fully merged version JSON (follows inheritsFrom)."""
    if _depth > 8:
        raise NovaError("Version inheritance loop detected.")
    child = load_raw_version(vid)
    parent_id = child.get("inheritsFrom")
    if not parent_id:
        merged = dict(child)
        merged["_root_id"] = child.get("jar") or child["id"]
        merged["_chain"] = [vid]
        return merged
    parent = resolve_version(parent_id, _depth + 1)
    merged = dict(parent)
    for k, v in child.items():
        if k in ("libraries", "arguments", "inheritsFrom"):
            continue
        merged[k] = v
    # libraries: child first (so it wins on duplicates), then parent
    libs, seen = [], set()
    for lib in list(child.get("libraries", [])) + list(parent.get("libraries", [])):
        key = _lib_key(lib)
        if key in seen:
            continue
        seen.add(key)
        libs.append(lib)
    merged["libraries"] = libs
    # arguments: parent then child
    pa, ca = parent.get("arguments"), child.get("arguments")
    if pa or ca:
        pa, ca = pa or {}, ca or {}
        merged["arguments"] = {
            "game": list(pa.get("game", [])) + list(ca.get("game", [])),
            "jvm": list(pa.get("jvm", [])) + list(ca.get("jvm", [])),
        }
    if "minecraftArguments" in child:
        merged["minecraftArguments"] = child["minecraftArguments"]
    merged["id"] = child["id"]
    merged["_root_id"] = parent["_root_id"] if "jar" not in child else child["jar"]
    merged["_chain"] = [vid] + parent["_chain"]
    return merged


def _lib_key(lib: dict) -> str:
    parts = lib["name"].split(":")
    g, a = parts[0], parts[1]
    classifier = parts[3] if len(parts) > 3 else ""
    # Distinguish natives-* variants that differ by rules.
    return f"{g}:{a}:{classifier}"


# --------------------------------------------------------------- rules

def _os_matches(osrule: dict) -> bool:
    name = osrule.get("name")
    if name and name != paths.os_name():
        return False
    arch = osrule.get("arch")
    if arch:
        a = paths.arch_name()
        if arch == "x86" and a != "x86":
            return False
        if arch in ("x64", "x86_64") and a != "x64":
            return False
        if arch in ("arm64", "aarch64") and a != "arm64":
            return False
    return True


def rules_allow(rules: list | None, features: dict | None = None) -> bool:
    if not rules:
        return True
    features = features or {}
    allowed = False
    for r in rules:
        ok = True
        if "os" in r and not _os_matches(r["os"]):
            ok = False
        if ok and "features" in r:
            for k, want in r["features"].items():
                if bool(features.get(k, False)) != bool(want):
                    ok = False
                    break
        if ok:
            allowed = (r.get("action", "allow") == "allow")
    return allowed


# ------------------------------------------------------------- libraries

def maven_path(name: str) -> str:
    ext = "jar"
    if "@" in name:
        name, ext = name.split("@", 1)
    parts = name.split(":")
    g, a, v = parts[0], parts[1], parts[2]
    classifier = parts[3] if len(parts) > 3 else None
    fn = f"{a}-{v}" + (f"-{classifier}" if classifier else "") + f".{ext}"
    return f"{g.replace('.', '/')}/{a}/{v}/{fn}"


def _native_classifier(lib: dict) -> str | None:
    nat = lib.get("natives")
    if not nat:
        return None
    c = nat.get(paths.os_name())
    if not c:
        return None
    return c.replace("${arch}", "64" if paths.arch_name() in ("x64", "arm64") else "32")


def library_files(version: dict) -> tuple[list[dict], list[dict]]:
    """Return (classpath_libs, native_libs). Each: {path,url,sha1,size,name,exclude}."""
    cp: list[dict] = []
    natives: list[dict] = []
    for lib in version.get("libraries", []):
        if not rules_allow(lib.get("rules")):
            continue
        dl = lib.get("downloads", {})
        art = dl.get("artifact")
        classifier = _native_classifier(lib)
        if classifier:
            c = dl.get("classifiers", {}).get(classifier)
            if c:
                natives.append({"name": lib["name"], "path": c.get("path") or maven_path(lib["name"] + ":" + classifier),
                                "url": c["url"], "sha1": c.get("sha1"), "size": c.get("size"),
                                "exclude": lib.get("extract", {}).get("exclude", ["META-INF/"])})
            elif not dl:
                # old-style maven lib with natives but no downloads block
                rel = maven_path(lib["name"] + ":" + classifier)
                base = lib.get("url", config.libraries_base() + "/").rstrip("/") + "/"
                natives.append({"name": lib["name"], "path": rel, "url": base + rel, "sha1": None,
                                "size": None, "exclude": lib.get("extract", {}).get("exclude", ["META-INF/"])})
            # a lib that has `natives` may also have a plain artifact
        if art:
            cp.append({"name": lib["name"], "path": art.get("path") or maven_path(lib["name"]),
                       "url": art["url"], "sha1": art.get("sha1"), "size": art.get("size")})
        elif not classifier or (classifier and not dl):
            if classifier:
                continue
            rel = maven_path(lib["name"])
            base = lib.get("url", config.libraries_base() + "/").rstrip("/") + "/"
            cp.append({"name": lib["name"], "path": rel, "url": base + rel,
                       "sha1": lib.get("sha1"), "size": lib.get("size")})
    return cp, natives


def classpath_entries(version: dict) -> list[Path]:
    cp, _ = library_files(version)
    base = paths.libraries_dir()
    out = [base / c["path"] for c in cp]
    out.append(client_jar_path(version))
    return out


def client_jar_path(version: dict) -> Path:
    root = version["_root_id"]
    return paths.versions_dir() / root / f"{root}.jar"


# ------------------------------------------------------------- preparing

def prepare_version(version_id: str, task: Task | None = None) -> dict:
    """Download everything the version needs. Returns the resolved JSON."""
    def step(msg, lo, hi):
        if task:
            task.stage(msg, lo, hi)

    step("Reading version data", 0.0, 0.05)
    version = resolve_version(version_id)
    root = version["_root_id"]
    if root != version_id and not version_json_path(root).exists():
        load_raw_version(root)

    # client jar
    step("Downloading game client", 0.05, 0.25)
    jar = client_jar_path(version)
    client = version.get("downloads", {}).get("client")
    if client:
        download_file(client["url"], jar, sha1=client.get("sha1"), size=client.get("size"),
                      on_bytes=None)
    elif not jar.exists():
        raise NovaError(f"No client jar available for '{root}'. Re-install this version.")

    # libraries
    step("Downloading libraries", 0.25, 0.7)
    cp, natives = library_files(version)
    lib_dir = paths.libraries_dir()
    items = [(c["url"], lib_dir / c["path"], c.get("sha1"), c.get("size")) for c in cp + natives
             if c.get("url")]
    # skip libs with empty urls (Forge-installed libs are already on disk)
    missing_no_url = [c for c in cp if not c.get("url") and not (lib_dir / c["path"]).exists()]
    if missing_no_url:
        raise NovaError(f"Library missing and has no download URL: {missing_no_url[0]['name']}")
    download_many(items, task, label="Libraries")

    # assets
    step("Downloading assets", 0.7, 0.97)
    ensure_assets(version, task)
    return version


def natives_dir_for(instance_id: str) -> Path:
    return paths.instances_dir() / instance_id / "natives"


def extract_natives(version: dict, dest: Path) -> None:
    _cp, natives = library_files(version)
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    for n in natives:
        jar = paths.libraries_dir() / n["path"]
        if not jar.exists():
            continue
        excl = n.get("exclude") or []
        try:
            safe_extract_zip(jar, dest, skip=lambda fn, excl=excl: any(fn.startswith(e) for e in excl))
        except zipfile.BadZipFile:
            raise NovaError(f"Corrupt native library: {jar.name}")


def ensure_assets(version: dict, task: Task | None = None) -> None:
    ai = version.get("assetIndex")
    if not ai:
        return
    idx_path = paths.assets_dir() / "indexes" / f"{ai['id']}.json"
    download_file(ai["url"], idx_path, sha1=ai.get("sha1"), size=ai.get("size"))
    index = read_json(idx_path) or {}
    objects = index.get("objects", {})
    items = []
    for name, obj in objects.items():
        h = obj["hash"]
        dest = paths.assets_dir() / "objects" / h[:2] / h
        items.append((f"{config.asset_base()}/{h[:2]}/{h}", dest, h, obj.get("size")))
    download_many(items, task, workers=16, label="Assets")
    # legacy layouts
    if index.get("virtual") or index.get("map_to_resources"):
        target = (paths.assets_dir() / "virtual" / "legacy") if index.get("virtual") else None
        for name, obj in objects.items():
            src = paths.assets_dir() / "objects" / obj["hash"][:2] / obj["hash"]
            if target is not None:
                dst = target / name
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)


def assets_game_dir(version: dict, instance_game_dir: Path) -> Path:
    """Value for ${game_assets}/${assets_root} depending on legacy asset types."""
    ai = version.get("assetIndex", {})
    idx = read_json(paths.assets_dir() / "indexes" / f"{ai.get('id', '')}.json", {}) or {}
    if idx.get("map_to_resources"):
        return instance_game_dir / "resources"
    if idx.get("virtual"):
        return paths.assets_dir() / "virtual" / "legacy"
    return paths.assets_dir()


def mc_minor(mc_version: str) -> tuple[int, int]:
    """Parse '1.20.4' -> (20, 4); '26.1' -> (26, 1). Unknown -> (0, 0)."""
    m = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", mc_version or "")
    if not m:
        return (0, 0)
    a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if a == 1:
        return (b, c)
    return (a, b)


def prepare_version_client_only(version_id: str) -> None:
    """Make sure a vanilla version's JSON and client jar exist (needed by Forge/OptiFine installers)."""
    version = resolve_version(version_id)
    jar = client_jar_path(version)
    client = version.get("downloads", {}).get("client")
    if client:
        download_file(client["url"], jar, sha1=client.get("sha1"), size=client.get("size"))
