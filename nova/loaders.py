"""Mod loader support: Fabric, Quilt, Forge, NeoForge, OptiFine, custom imports."""
from __future__ import annotations

import base64
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from . import config, java as javamod, paths, versions
from .util import NovaError, Task, download_file, http_get_json, http_get_text, read_json, write_json

LOADERS = ["vanilla", "fabric", "quilt", "forge", "neoforge", "optifine", "custom"]

# Tiny Java 8 class that calls optifine.Installer.doInstall(File) by reflection,
# so OptiFine can be installed without opening its GUI.
_SHIM_B64 = "yv66vgAAADQAQgoAAgADBwAEDAAFAAYBABBqYXZhL2xhbmcvT2JqZWN0AQAGPGluaXQ+AQADKClWCQAIAAkHAAoMAAsADAEAEGphdmEvbGFuZy9TeXN0ZW0BAANlcnIBABVMamF2YS9pby9QcmludFN0cmVhbTsIAA4BACp1c2FnZTogTm92YU9wdGlGaW5lSW5zdGFsbCA8bWluZWNyYWZ0LWRpcj4KABAAEQcAEgwAEwAUAQATamF2YS9pby9QcmludFN0cmVhbQEAB3ByaW50bG4BABUoTGphdmEvbGFuZy9TdHJpbmc7KVYKAAgAFgwAFwAYAQAEZXhpdAEABChJKVYHABoBAAxqYXZhL2lvL0ZpbGUKABkAHAwABQAUCAAeAQASb3B0aWZpbmUuSW5zdGFsbGVyCgAgACEHACIMACMAJAEAD2phdmEvbGFuZy9DbGFzcwEAB2Zvck5hbWUBACUoTGphdmEvbGFuZy9TdHJpbmc7KUxqYXZhL2xhbmcvQ2xhc3M7CAAmAQAJZG9JbnN0YWxsCgAgACgMACkAKgEACWdldE1ldGhvZAEAQChMamF2YS9sYW5nL1N0cmluZztbTGphdmEvbGFuZy9DbGFzczspTGphdmEvbGFuZy9yZWZsZWN0L01ldGhvZDsKACwALQcALgwALwAwAQAYamF2YS9sYW5nL3JlZmxlY3QvTWV0aG9kAQAGaW52b2tlAQA5KExqYXZhL2xhbmcvT2JqZWN0O1tMamF2YS9sYW5nL09iamVjdDspTGphdmEvbGFuZy9PYmplY3Q7CQAIADIMADMADAEAA291dAgANQEAEE5PVkFfT1BUSUZJTkVfT0sHADcBABNOb3ZhT3B0aUZpbmVJbnN0YWxsAQAEQ29kZQEAD0xpbmVOdW1iZXJUYWJsZQEABG1haW4BABYoW0xqYXZhL2xhbmcvU3RyaW5nOylWAQANU3RhY2tNYXBUYWJsZQEACkV4Y2VwdGlvbnMHAD8BABNqYXZhL2xhbmcvRXhjZXB0aW9uAQAKU291cmNlRmlsZQEAGE5vdmFPcHRpRmluZUluc3RhbGwuamF2YQAhADYAAgAAAAAAAgABAAUABgABADgAAAAdAAEAAQAAAAUqtwABsQAAAAEAOQAAAAYAAQAAAAUACQA6ADsAAgA4AAAAiwAGAAQAAABKKr4EogAPsgAHEg22AA8FuAAVuwAZWSoDMrcAG0wSHbgAH00sEiUEvQAgWQMSGVO2ACdOLQEEvQACWQMrU7YAK1eyADESNLYAD7EAAAACADkAAAAmAAkAAAAHAAYACAAOAAkAEgALAB0ADAAjAA0AMwAOAEEADwBJABAAPAAAAAMAARIAPQAAAAQAAQA+AAEAQAAAAAIAQQ=="
_SHIM_NAME = "NovaOptiFineInstall"


# ------------------------------------------------------------ fabric/quilt

def _meta(loader: str) -> str:
    return config.fabric_meta() if loader == "fabric" else config.quilt_meta()


def fabric_like_versions(loader: str, mc: str) -> list[dict]:
    data = http_get_json(f"{_meta(loader)}/versions/loader/{mc}")
    out = []
    for e in data:
        l = e.get("loader", {})
        out.append({"version": l.get("version"), "stable": bool(l.get("stable", True)) and "beta" not in str(l.get("version", ""))})
    return [o for o in out if o["version"]]


def fabric_like_supported_games(loader: str) -> set[str]:
    data = http_get_json(f"{_meta(loader)}/versions/game")
    return {g["version"] for g in data}


def install_fabric_like(loader: str, mc: str, loader_version: str, task: Task | None = None) -> str:
    if task:
        task.update(f"Fetching {loader.title()} profile…")
    profile = http_get_json(f"{_meta(loader)}/versions/loader/{mc}/{loader_version}/profile/json")
    vid = profile["id"]
    write_json(versions.version_json_path(vid), profile)
    return vid


# ------------------------------------------------------------------ forge

def forge_versions(mc: str) -> list[dict]:
    xml = http_get_text(f"{config.forge_maven()}/net/minecraftforge/forge/maven-metadata.xml")
    root = ET.fromstring(xml)
    out = []
    for v in root.iter("version"):
        txt = (v.text or "").strip()
        if txt.startswith(mc + "-"):
            out.append(txt[len(mc) + 1:])

    def key(s):
        return [int(p) if p.isdigit() else 0 for p in re.split(r"[.\-]", s)]
    out.sort(key=key, reverse=True)
    return [{"version": v, "stable": True} for v in out]


def forge_supported_games() -> set[str]:
    xml = http_get_text(f"{config.forge_maven()}/net/minecraftforge/forge/maven-metadata.xml")
    root = ET.fromstring(xml)
    games = set()
    for v in root.iter("version"):
        t = (v.text or "").strip()
        if "-" in t:
            games.add(t.split("-", 1)[0])
    return games


def install_forge(mc: str, forge_version: str, java_path: str, task: Task | None = None) -> str:
    full = f"{mc}-{forge_version}"
    url = f"{config.forge_maven()}/net/minecraftforge/forge/{full}/forge-{full}-installer.jar"
    return _run_installer(url, f"forge-{full}-installer.jar", mc, java_path, task, "Forge")


# --------------------------------------------------------------- neoforge

def neoforge_to_mc(v: str) -> str:
    """Map a NeoForge version to its Minecraft version.
    20.4.x -> 1.20.4, 21.0.x -> 1.21, 21.1.x -> 1.21.1, 26.1.x.y -> 26.1"""
    base = re.split(r"[-+]", v)[0]
    parts = [p for p in base.split(".") if p.isdigit()]
    if len(parts) < 2:
        return ""
    major, minor = int(parts[0]), int(parts[1])
    if major >= 26:  # year-based Minecraft versions
        if len(parts) >= 4 and int(parts[2]) != 0:
            return f"{major}.{minor}.{parts[2]}"
        return f"{major}.{minor}"
    return f"1.{major}" if minor == 0 else f"1.{major}.{minor}"


def _neoforge_all() -> list[str]:
    data = http_get_json(config.neoforge_api())
    return list(data.get("versions", []))


def neoforge_versions(mc: str) -> list[dict]:
    out = [v for v in _neoforge_all() if neoforge_to_mc(v) == mc]

    def key(s):
        return [int(p) if p.isdigit() else 0 for p in re.split(r"[.\-]", s)]
    out.sort(key=key, reverse=True)
    return [{"version": v, "stable": "beta" not in v and "alpha" not in v} for v in out]


def neoforge_supported_games() -> set[str]:
    return {neoforge_to_mc(v) for v in _neoforge_all()} - {""}


def install_neoforge(neo_version: str, java_path: str, task: Task | None = None) -> str:
    mc = neoforge_to_mc(neo_version)
    url = f"{config.neoforge_maven()}/net/neoforged/neoforge/{neo_version}/neoforge-{neo_version}-installer.jar"
    return _run_installer(url, f"neoforge-{neo_version}-installer.jar", mc, java_path, task, "NeoForge")


def _version_ids() -> set[str]:
    return {p.name for p in paths.versions_dir().iterdir() if p.is_dir()}


def _ensure_profiles_stub() -> None:
    """Forge/NeoForge installers insist on a launcher_profiles.json."""
    p = paths.data_dir() / "launcher_profiles.json"
    if not p.exists():
        write_json(p, {"profiles": {}, "settings": {}, "version": 3})


def _run_installer(url: str, filename: str, mc: str, java_path: str, task: Task | None, label: str) -> str:
    if task:
        task.update(f"Downloading {label} installer…")
    installer = paths.downloads_dir() / filename
    download_file(url, installer)
    # the installers need the vanilla client jar + json to already exist
    if mc:
        versions.prepare_version_client_only(mc)
    _ensure_profiles_stub()
    before = _version_ids()
    if task:
        task.update(f"Running {label} installer (this can take a few minutes)…")
    flags = 0x08000000 if paths.os_name() == "windows" else 0
    proc = subprocess.run([java_path, "-jar", str(installer), "--installClient", str(paths.data_dir())],
                          capture_output=True, text=True, cwd=str(paths.data_dir()), timeout=1800,
                          creationflags=flags)
    after = _version_ids()
    new = sorted(after - before)
    if proc.returncode != 0 and not new:
        tail = "\n".join((proc.stdout + "\n" + proc.stderr).strip().splitlines()[-8:])
        raise NovaError(f"{label} installer failed:\n{tail}")
    if not new:
        # already installed earlier: find a matching id
        guess = [v for v in after if label.lower() in v.lower() and (not mc or mc in v or label == "NeoForge")]
        new = sorted(guess)
        if not new:
            raise NovaError(f"{label} installer finished but no new version was created.")
    # prefer the id that contains the loader name
    for v in new:
        if label.lower() in v.lower():
            return v
    return new[-1]


# --------------------------------------------------------------- optifine

def install_optifine(optifine_jar: str, mc: str, java_path: str, task: Task | None = None) -> str:
    """Install a user-supplied OptiFine installer jar into the shared version store."""
    jar = Path(optifine_jar)
    if not jar.is_file():
        raise NovaError("OptiFine jar not found. Download it from optifine.net first (it can't be fetched automatically).")
    try:
        with zipfile.ZipFile(jar) as z:
            if "optifine/Installer.class" not in z.namelist():
                raise NovaError("That file isn't an OptiFine installer. Download the regular 'Preview/Release' jar from optifine.net.")
    except zipfile.BadZipFile:
        raise NovaError("That file isn't a valid jar.")
    versions.prepare_version_client_only(mc)
    _ensure_profiles_stub()
    work = paths.cache_dir() / "optifine-shim"
    work.mkdir(parents=True, exist_ok=True)
    (work / f"{_SHIM_NAME}.class").write_bytes(base64.b64decode(_SHIM_B64))
    before = _version_ids()
    if task:
        task.update("Installing OptiFine…")
    sep = ";" if paths.os_name() == "windows" else ":"
    flags = 0x08000000 if paths.os_name() == "windows" else 0
    proc = subprocess.run([java_path, "-cp", f"{jar}{sep}{work}", _SHIM_NAME, str(paths.data_dir())],
                          capture_output=True, text=True, timeout=600, creationflags=flags,
                          cwd=str(paths.data_dir()))
    after = _version_ids()
    new = sorted(after - before)
    if "NOVA_OPTIFINE_OK" not in proc.stdout and not new:
        tail = "\n".join((proc.stdout + "\n" + proc.stderr).strip().splitlines()[-6:])
        raise NovaError("OptiFine's installer didn't complete.\n" + tail)
    if not new:
        new = [v for v in after if "optifine" in v.lower() and mc in v]
        if not new:
            raise NovaError("OptiFine installed but no version was created. Is this jar for Minecraft " + mc + "?")
    return sorted(new)[-1]


# ----------------------------------------------------------------- custom

def import_custom_version(src_dir: str) -> str:
    """Import a version folder (e.g. made by another launcher) into the shared store."""
    src = Path(src_dir)
    if not src.is_dir():
        raise NovaError("Folder not found.")
    jsons = list(src.glob("*.json"))
    if not jsons:
        raise NovaError("No version .json found in that folder.")
    data = read_json(jsons[0])
    vid = (data or {}).get("id")
    if not vid:
        raise NovaError("That version JSON has no id.")
    dest = paths.versions_dir() / vid
    dest.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file():
            shutil.copyfile(f, dest / (f"{vid}.json" if f.suffix == ".json" and f == jsons[0] else f.name))
    return vid


def list_installed_versions() -> list[str]:
    return sorted(p.name for p in paths.versions_dir().iterdir()
                  if p.is_dir() and (p / f"{p.name}.json").exists())


# ---------------------------------------------------------------- dispatch

def available_loader_versions(loader: str, mc: str) -> list[dict]:
    if loader in ("fabric", "quilt"):
        return fabric_like_versions(loader, mc)
    if loader == "forge":
        return forge_versions(mc)
    if loader == "neoforge":
        return neoforge_versions(mc)
    return []


def supported_games(loader: str) -> set[str] | None:
    try:
        if loader in ("fabric", "quilt"):
            return fabric_like_supported_games(loader)
        if loader == "forge":
            return forge_supported_games()
        if loader == "neoforge":
            return neoforge_supported_games()
    except NovaError:
        return None
    return None
