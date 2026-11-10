"""Player profiles: Microsoft (online) accounts and offline local profiles."""
from __future__ import annotations

import hashlib
import os
import re
import uuid

from . import paths
from .util import NovaError, read_json, write_json


def offline_uuid(name: str) -> str:
    """Same algorithm as Java's UUID.nameUUIDFromBytes("OfflinePlayer:<name>")."""
    d = bytearray(hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest())
    d[6] = (d[6] & 0x0F) | 0x30
    d[8] = (d[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(d)))


def _file():
    return paths.data_dir() / "accounts.json"


def load() -> dict:
    data = read_json(_file(), None)
    if not isinstance(data, dict) or "accounts" not in data:
        data = {"accounts": [], "selected": None}
    return data


SECRET_KEYS = ("refresh_token", "mc_token", "mc_expires")


def save(data: dict) -> None:
    write_json(_file(), data)
    try:
        os.chmod(_file(), 0o600)  # holds login tokens
    except OSError:
        pass


def public(acc: dict) -> dict:
    """The account minus its secrets; safe to send to the UI."""
    out = {k: v for k, v in acc.items() if k not in SECRET_KEYS}
    out["type"] = acc.get("type", "offline")
    return out


def upsert_microsoft(result: dict, refresh_token: str) -> dict:
    """Add or update a Microsoft account (matched by UUID) with fresh tokens."""
    data = load()
    acc = next((a for a in data["accounts"] if a.get("type") == "microsoft" and a["uuid"] == result["uuid"]), None)
    if acc is None:
        acc = {"id": uuid.uuid4().hex[:8], "type": "microsoft"}
        data["accounts"].append(acc)
    acc.update({"username": result["username"], "uuid": result["uuid"], "mc_token": result["mc_token"],
                "mc_expires": result["mc_expires"], "xuid": result.get("xuid", ""), "refresh_token": refresh_token})
    if not data.get("selected"):
        data["selected"] = acc["id"]
    save(data)
    return dict(acc)


def add_offline(name: str) -> dict:
    name = name.strip()
    if not re.fullmatch(r"[A-Za-z0-9_]{3,16}", name):
        raise NovaError("Usernames must be 3-16 characters: letters, numbers and underscores.")
    data = load()
    if any(a["username"].lower() == name.lower() for a in data["accounts"]):
        raise NovaError("You already have a profile with that name.")
    acc = {"id": uuid.uuid4().hex[:8], "type": "offline", "username": name, "uuid": offline_uuid(name)}
    data["accounts"].append(acc)
    if not data.get("selected"):
        data["selected"] = acc["id"]
    save(data)
    return acc


def remove(acc_id: str) -> None:
    data = load()
    data["accounts"] = [a for a in data["accounts"] if a["id"] != acc_id]
    if data.get("selected") == acc_id:
        data["selected"] = data["accounts"][0]["id"] if data["accounts"] else None
    save(data)


def select(acc_id: str) -> None:
    data = load()
    if not any(a["id"] == acc_id for a in data["accounts"]):
        raise NovaError("Unknown profile.")
    data["selected"] = acc_id
    save(data)


def selected() -> dict | None:
    data = load()
    for a in data["accounts"]:
        if a["id"] == data.get("selected"):
            return a
    return data["accounts"][0] if data["accounts"] else None
