"""Launcher-wide settings, including the theme/customization options."""
from __future__ import annotations

import re

from . import config, look, paths
from .util import NovaError, read_json, write_json

THEME_PRESETS = {k: {"name": v["name"], "accent": v["accent"], "accent2": v["accent2"]} for k, v in look.THEMES.items()}

SURFACES = {
    "oled":   {"name": "OLED Black"},
    "void":   {"name": "Void (default)"},
    "nebula": {"name": "Deep Nebula"},
}

DEFAULTS = {
    "theme_preset": "nova",
    "accent": "#8b5cf6",
    "accent2": "#c026d3",
    "surface": "void",
    "radius": 14,
    "font_scale": 100,
    "density": "comfortable",   # comfortable | compact
    "animations": True,
    "glow": True,
    "starfield": True,
    "library_view": "grid",     # grid | list
    "java_path": "",
    "global_jvm_args": "",
    "auto_download_java": True,
    "keep_launcher_open": True,
    "show_console_on_launch": True,
    "default_memory_mode": "auto",   # auto | manual
    # custom look (validated by look.sanitize)
    "base": "", "bg_mode": "surface", "gradient": "", "angle": 160, "pattern": "none", "pattern_opacity": 12,
    "overlay": 35, "font": "system", "look_name": "", "motion": "none",
    "bg_media": "",                  # "", "image" or "video": what the imported background file is
    "bg_pause_in_game": True,        # pause animated backgrounds while Minecraft is running
    "ms_client_id": "",              # Azure app (client) ID for Microsoft sign-in
    "discord_presence": True,        # Discord Rich Presence (needs Discord running)
    "discord_show_details": True,    # show instance name / version, not just "Playing Minecraft"
    "discord_client_id": "",         # optional override of the built-in Discord application ID
}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def load() -> dict:
    data = read_json(paths.data_dir() / "settings.json", {}) or {}
    out = dict(DEFAULTS)
    out.update({k: v for k, v in data.items() if k in DEFAULTS})
    if out["bg_mode"] == "image":      # older versions called an imported background "image"
        out["bg_mode"] = "media"
        out["bg_media"] = out["bg_media"] or ("image" if (paths.data_dir() / "background.img").exists() else "")
    if "ai_api_key" in data:           # the AI chat was removed: don't keep its API key on disk
        data.pop("ai_api_key", None)
        write_json(paths.data_dir() / "settings.json", {k: v for k, v in data.items() if k in DEFAULTS})
    if not str(out.get("ms_client_id", "")).strip():
        out["ms_client_id"] = config.default_ms_client_id()
    return out


def update(patch: dict) -> dict:
    cur = load()
    for k, v in patch.items():
        if k not in DEFAULTS:
            continue
        d = DEFAULTS[k]
        if isinstance(d, bool):
            v = bool(v)
        elif isinstance(d, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise NovaError(f"'{k}' must be a number.")
        else:
            v = str(v)
        if k in ("accent", "accent2") and not _HEX.match(v):
            raise NovaError("Colors must look like #8b5cf6.")
        if k == "theme_preset" and v not in THEME_PRESETS and v != "custom" and not v.startswith("my-"):
            raise NovaError("Unknown theme.")
        if k == "surface" and v not in SURFACES:
            raise NovaError("Unknown surface style.")
        if k == "radius":
            v = max(0, min(v, 28))
        if k == "font_scale":
            v = max(80, min(v, 140))
        if k == "density" and v not in ("comfortable", "compact"):
            raise NovaError("Unknown density.")
        if k == "library_view" and v not in ("grid", "list"):
            raise NovaError("Unknown view.")
        if k == "bg_media" and v not in ("", "image", "video"):
            raise NovaError("Unknown background type.")
        if k in look.LOOK_DEFAULTS and k not in ("accent", "accent2", "theme_preset", "surface", "radius", "font_scale", "density"):
            clean = look.sanitize({k: v})
            if k not in clean:
                raise NovaError(f"'{k}' has an invalid value.")
            v = clean[k]
        if k == "discord_client_id":
            v = v.strip()
            if v and not re.fullmatch(r"\d{15,25}", v):
                raise NovaError("A Discord application ID is a long number, like 1234567890123456789.")
        if k == "ms_client_id":
            v = v.strip()
            if v and not re.fullmatch(r"[0-9a-fA-F-]{36}", v):
                raise NovaError("An app ID looks like 12345678-abcd-1234-abcd-1234567890ab.")
        cur[k] = v
    write_json(paths.data_dir() / "settings.json", cur)
    return cur

