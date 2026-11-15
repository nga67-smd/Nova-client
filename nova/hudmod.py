"""Installs the Nova in-game mod (HUD + Cosmetics cape/skin) into Fabric instances that need it."""
from __future__ import annotations

import re

from . import config, instances, mods
from .util import NovaError, Task, download_file, http_get_json

SUPPORTED = ("1.21.1", "1.21.8")
JAR = re.compile(r"^nova-hud-.*\+mc(?P<mc>[0-9.]+)\.jar$")


def supported(inst: dict) -> bool:
    return inst.get("loader") == "fabric" and inst.get("mc_version") in SUPPORTED


def _mods_dir(inst: dict):
    return instances.game_dir(inst["id"]) / "mods"


def installed(inst: dict) -> bool:
    d = _mods_dir(inst)
    return d.exists() and any(JAR.match(f.name) for f in d.glob("nova-hud-*.jar"))


def _asset(mc: str) -> dict:
    rel = http_get_json(config.hud_release_api(), headers={"Accept": "application/vnd.github+json"})
    for a in rel.get("assets", []):
        m = JAR.match(a.get("name", ""))
        if m and m.group("mc") == mc and a.get("browser_download_url"):
            return a
    raise NovaError(f"The Nova mod isn't published for Minecraft {mc} yet.")


def ensure(inst: dict, task: Task | None = None) -> str:
    """Make sure this Fabric instance has Fabric API and the newest Nova mod. Returns a short status word."""
    if not supported(inst):
        return "unsupported"
    asset = _asset(inst["mc_version"])
    d = _mods_dir(inst)
    d.mkdir(parents=True, exist_ok=True)
    target = d / asset["name"]
    status = "current"
    if not target.exists() or (asset.get("size") and target.stat().st_size != asset["size"]):
        if task:
            task.update("Installing the Nova in-game mod…")
        for old in d.glob("nova-hud-*.jar"):
            old.unlink(missing_ok=True)
        download_file(asset["browser_download_url"], target, size=asset.get("size"))
        status = "installed"
    have_api = any(f.name.lower().startswith("fabric-api") for f in d.glob("*.jar"))
    if not have_api:
        if task:
            task.update("Installing Fabric API (needed by the Nova mod)…")
        mods.install_project(inst, "fabric-api", "mod", task)
        status = "installed"
    return status
