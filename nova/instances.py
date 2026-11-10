"""Instance (profile) storage: each instance has its own game folder."""
from __future__ import annotations

import json
import re
import shutil
import time
import uuid
import zipfile
from pathlib import Path

from . import loaders, optimize, paths
from .util import NovaError, read_json, safe_extract_zip, slugify, write_json

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")

DEFAULTS = {
    "name": "New instance", "icon": "✦", "color": "#8b5cf6", "group": "", "notes": "",
    "mc_version": "", "loader": "vanilla", "loader_version": "", "version_id": "",
    "optifine_jar": "",
    "java_path": "", "memory_min": 1024, "memory_max": 4096,
    "jvm_preset": "balanced", "jvm_args": "", "game_args": "", "env": {},
    "width": 1280, "height": 720, "fullscreen": False,
    "pre_launch": "", "post_exit": "",
    "created": 0, "last_played": 0, "playtime_s": 0, "options_profile": "",
}


def check_id(iid: str) -> str:
    if not isinstance(iid, str) or not ID_RE.match(iid):
        raise NovaError("Invalid instance id.")
    return iid


def instance_dir(iid: str) -> Path:
    return paths.instances_dir() / check_id(iid)


def game_dir(iid: str) -> Path:
    return instance_dir(iid) / "minecraft"


def _file(iid: str) -> Path:
    return instance_dir(iid) / "instance.json"


def get(iid: str) -> dict:
    data = read_json(_file(iid))
    if not data:
        raise NovaError("Instance not found.")
    out = dict(DEFAULTS)
    out.update(data)
    out["id"] = iid
    return out


def list_all() -> list[dict]:
    out = []
    for d in sorted(paths.instances_dir().iterdir()):
        if d.is_dir() and (d / "instance.json").exists():
            try:
                out.append(get(d.name))
            except NovaError:
                continue
    out.sort(key=lambda i: (i.get("last_played", 0), i.get("created", 0)), reverse=True)
    return out


def _clean_fields(data: dict) -> dict:
    clean: dict = {}
    for k, default in DEFAULTS.items():
        if k not in data:
            continue
        v = data[k]
        if isinstance(default, bool):
            v = bool(v)
        elif isinstance(default, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise NovaError(f"'{k}' must be a number.")
        elif isinstance(default, dict):
            if not isinstance(v, dict):
                raise NovaError(f"'{k}' must be an object.")
            v = {str(a)[:100]: str(b)[:500] for a, b in v.items() if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(a))}
        else:
            v = str(v)
        clean[k] = v
    if "loader" in clean and clean["loader"] not in loaders.LOADERS:
        raise NovaError("Unknown mod loader.")
    if "jvm_preset" in clean and clean["jvm_preset"] not in optimize.PRESETS:
        raise NovaError("Unknown JVM preset.")
    if "color" in clean and not re.fullmatch(r"#[0-9a-fA-F]{6}", clean["color"]):
        clean["color"] = DEFAULTS["color"]
    for k in ("memory_min", "memory_max"):
        if k in clean:
            clean[k] = max(256, min(clean[k], 262144))
    if "name" in clean:
        clean["name"] = clean["name"].strip()[:60] or "Unnamed instance"
    for k in ("width", "height"):
        if k in clean:
            clean[k] = max(200, min(clean[k], 10000))
    return clean


def create(data: dict) -> dict:
    fields = _clean_fields(data)
    inst = dict(DEFAULTS)
    inst.update(fields)
    if not inst["mc_version"] and inst["loader"] != "custom":
        raise NovaError("Pick a Minecraft version.")
    base = slugify(inst["name"])
    iid, n = base, 2
    while instance_dir(iid).exists():
        iid = f"{base}-{n}"
        n += 1
    inst["created"] = int(time.time())
    inst["id"] = iid
    game_dir(iid).mkdir(parents=True, exist_ok=True)
    save(inst)
    return get(iid)


def save(inst: dict) -> None:
    iid = check_id(inst["id"])
    data = {k: inst.get(k, DEFAULTS[k]) for k in DEFAULTS}
    write_json(_file(iid), data)


def update(iid: str, patch: dict) -> dict:
    inst = get(iid)
    fields = _clean_fields(patch)
    # changing the game/loader invalidates the installed version id
    if "version_id" not in fields:
        for k in ("mc_version", "loader", "loader_version", "optifine_jar"):
            if k in fields and fields[k] != inst.get(k):
                fields["version_id"] = ""
                break
    inst.update(fields)
    save(inst)
    return get(iid)


def delete(iid: str) -> None:
    d = instance_dir(iid)
    if not d.exists():
        raise NovaError("Instance not found.")
    shutil.rmtree(d)


def duplicate(iid: str, new_name: str | None = None) -> dict:
    src = get(iid)
    name = (new_name or f"{src['name']} copy").strip()[:60]
    base = slugify(name)
    nid, n = base, 2
    while instance_dir(nid).exists():
        nid = f"{base}-{n}"
        n += 1
    shutil.copytree(instance_dir(iid), instance_dir(nid), ignore=shutil.ignore_patterns("natives"))
    inst = get(nid)
    inst.update({"name": name, "created": int(time.time()), "last_played": 0, "playtime_s": 0})
    save(inst)
    return get(nid)


def record_play(iid: str, seconds: int) -> None:
    try:
        inst = get(iid)
    except NovaError:
        return
    inst["last_played"] = int(time.time())
    inst["playtime_s"] = int(inst.get("playtime_s", 0)) + max(0, int(seconds))
    save(inst)


# ---------------------------------------------------- export / import packs

# Fields that can run code or change how Java starts. Never carried by packs.
UNSAFE_PACK_FIELDS = ("pre_launch", "post_exit", "env", "jvm_args", "game_args")

EXPORT_INCLUDE = ["mods", "config", "resourcepacks", "shaderpacks", "options.txt", "servers.dat",
                  "optionsshaders.txt", "nova_mods.json", "defaultconfigs", "kubejs"]


def export_pack(iid: str, dest: Path, include_saves: bool = False) -> Path:
    inst = get(iid)
    gd = game_dir(iid)
    dest = Path(dest)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        meta = {k: inst[k] for k in DEFAULTS if k not in ("created", "last_played", "playtime_s", "version_id",
                                                           "optifine_jar", "java_path") + UNSAFE_PACK_FIELDS}
        z.writestr("nova-pack.json", json.dumps({"format": 1, "instance": meta}, indent=2))
        items = list(EXPORT_INCLUDE) + (["saves"] if include_saves else [])
        for name in items:
            p = gd / name
            if p.is_file():
                z.write(p, f"minecraft/{name}")
            elif p.is_dir():
                for f in p.rglob("*"):
                    if f.is_file():
                        z.write(f, f"minecraft/{f.relative_to(gd).as_posix()}")
    return dest


def import_pack(zpath: Path) -> dict:
    zpath = Path(zpath)
    try:
        with zipfile.ZipFile(zpath) as z:
            names = z.namelist()
            if "nova-pack.json" in names:
                meta = json.loads(z.read("nova-pack.json")).get("instance", {})
                meta = {k: v for k, v in meta.items() if k not in UNSAFE_PACK_FIELDS + ("java_path", "optifine_jar", "version_id")}
                inst = create(meta)
                safe_extract_zip(zpath, instance_dir(inst["id"]), skip=lambda n: n == "nova-pack.json")
                return get(inst["id"])
            if "modrinth.index.json" in names:
                return import_mrpack(zpath)
    except zipfile.BadZipFile:
        raise NovaError("That file isn't a valid pack archive.")
    raise NovaError("Unrecognized pack. Supported: Nova packs (.novapack) and Modrinth packs (.mrpack).")


def import_mrpack(zpath: Path) -> dict:
    from .util import download_file
    with zipfile.ZipFile(zpath) as z:
        index = json.loads(z.read("modrinth.index.json"))
    deps = index.get("dependencies", {})
    mc = deps.get("minecraft")
    if not mc:
        raise NovaError("This .mrpack doesn't specify a Minecraft version.")
    loader, lver = "vanilla", ""
    for key, ld in (("fabric-loader", "fabric"), ("quilt-loader", "quilt"), ("forge", "forge"),
                    ("neoforge", "neoforge")):
        if key in deps:
            loader, lver = ld, deps[key]
            break
    inst = create({"name": index.get("name", "Modrinth pack"), "mc_version": mc, "loader": loader,
                   "loader_version": lver, "memory_max": 4096, "icon": "◆"})
    gd = game_dir(inst["id"]).resolve()
    try:
        for f in index.get("files", []):
            if f.get("env", {}).get("client") == "unsupported":
                continue
            rel = f["path"]
            target = (gd / rel).resolve()
            if gd not in target.parents:
                raise NovaError(f"Unsafe path in pack: {rel}")
            url = (f.get("downloads") or [None])[0]
            if not url:
                continue
            download_file(url, target, sha1=f.get("hashes", {}).get("sha1"))
        with zipfile.ZipFile(zpath) as z:
            for prefix in ("overrides/", "client-overrides/"):
                for m in z.infolist():
                    if m.filename.startswith(prefix) and not m.is_dir():
                        rel = m.filename[len(prefix):]
                        target = (gd / rel).resolve()
                        if gd not in target.parents:
                            continue
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with z.open(m) as s, open(target, "wb") as o:
                            shutil.copyfileobj(s, o)
    except Exception:
        shutil.rmtree(instance_dir(inst["id"]), ignore_errors=True)
        raise
    return get(inst["id"])
