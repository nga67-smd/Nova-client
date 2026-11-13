"""Custom looks: validation of every theme change, ready-made themes, and user-saved themes.

Every change to the look goes through `sanitize()`. It only lets known keys through, checks every
value, and keeps colors readable (Nova's text is light, so backgrounds stay dark and accents stay
visible). Nothing is ever used as raw CSS.
"""
from __future__ import annotations

import colorsys
import re

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

LOOK_DEFAULTS = {
    "accent": "#8b5cf6", "accent2": "#c026d3", "theme_preset": "nova",
    "surface": "void", "base": "", "bg_mode": "surface", "motion": "none",
    "gradient": "", "angle": 160, "pattern": "none", "pattern_opacity": 12, "overlay": 35,
    "font": "system", "radius": 14, "font_scale": 100, "density": "comfortable",
    "glow": True, "starfield": True, "look_name": "",
}
LOOK_KEYS = tuple(LOOK_DEFAULTS)
ENUMS = {
    "bg_mode": ("surface", "gradient", "media"),     # media = an imported image / GIF / video
    "motion": ("none", "flow", "aurora"),
    "pattern": ("none", "grid", "dots", "lines"),
    "font": ("system", "rounded", "mono", "serif"),
    "density": ("comfortable", "compact"),
    "surface": ("oled", "void", "nebula"),
}
INT_RANGES = {"angle": (0, 360), "pattern_opacity": (0, 60), "overlay": (0, 85), "radius": (0, 28), "font_scale": (85, 125)}
BOOLS = ("glow", "starfield")


# ------------------------------------------------------------------ color helpers

def _rgb(h: str) -> tuple[float, float, float]:
    return int(h[1:3], 16) / 255, int(h[3:5], 16) / 255, int(h[5:7], 16) / 255


def _hex(r: float, g: float, b: float) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c * 255))) for c in (r, g, b))


def luminance(h: str) -> float:
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _scale(h: str, f: float) -> str:
    r, g, b = _rgb(h)
    return _hex(r * f, g * f, b * f)


def _toward_white(h: str, t: float) -> str:
    r, g, b = _rgb(h)
    return _hex(r + (1 - r) * t, g + (1 - g) * t, b + (1 - b) * t)


def clamp_accent(h: str) -> str:
    """Accents carry white text and must show up on a dark background."""
    for _ in range(40):
        if luminance(h) <= 0.42:
            break
        h = _scale(h, 0.92)
    for _ in range(40):
        if luminance(h) >= 0.05:
            break
        h = _toward_white(h, 0.1)
    return h


def clamp_dark(h: str, max_lum: float = 0.16) -> str:
    """Backgrounds stay dark so Nova's light text stays readable."""
    for _ in range(60):
        if luminance(h) <= max_lum:
            break
        h = _scale(h, 0.92)
    return h


def hsl(h: str) -> tuple[float, float, float]:
    hh, ll, ss = colorsys.rgb_to_hls(*_rgb(h))
    return hh, ss, ll


def from_hsl(h: float, s: float, l: float) -> str:
    return _hex(*colorsys.hls_to_rgb(h % 1.0, max(0, min(1, l)), max(0, min(1, s))))


def palette_from(accent: str) -> dict:
    """A full coordinated look from one accent color."""
    accent = clamp_accent(accent)
    h, s, _ = hsl(accent)
    s = max(s, 0.45)
    return {"accent": accent, "accent2": clamp_accent(from_hsl(h + 0.08, s, 0.5)),
            "base": from_hsl(h, 0.38, 0.045), "bg_mode": "surface", "theme_preset": "custom"}


# ------------------------------------------------------------------ validation

def _clean_gradient(v) -> str:
    items = v if isinstance(v, (list, tuple)) else str(v).split(",")
    cols = [str(c).strip() for c in items if HEX.match(str(c).strip())]
    if len(cols) < 2:
        return ""
    return ",".join(clamp_dark(c, 0.3) for c in cols[:3])


def sanitize(patch: dict) -> dict:
    """Return only valid, readable theme changes from an untrusted dict."""
    out: dict = {}
    if not isinstance(patch, dict):
        return out
    for k, v in patch.items():
        if k not in LOOK_DEFAULTS:
            continue
        try:
            if k in ("accent", "accent2"):
                if isinstance(v, str) and HEX.match(v):
                    out[k] = clamp_accent(v.lower())
            elif k == "base":
                if v == "" or v is None:
                    out[k] = ""
                elif isinstance(v, str) and HEX.match(v):
                    out[k] = clamp_dark(v.lower())
            elif k == "gradient":
                out[k] = _clean_gradient(v)
            elif k in ENUMS:
                if v in ENUMS[k]:
                    out[k] = v
            elif k in INT_RANGES:
                lo, hi = INT_RANGES[k]
                out[k] = max(lo, min(hi, int(round(float(v)))))
            elif k in BOOLS:
                out[k] = bool(v)
            elif k == "look_name":
                out[k] = re.sub(r"[^\w .,'&-]", "", str(v))[:40]
            elif k == "theme_preset":
                out[k] = "custom" if v == "custom" else str(v)[:20]
        except (TypeError, ValueError):
            continue
    if "gradient" in out and out["gradient"] == "" and out.get("bg_mode") == "gradient":
        out["bg_mode"] = "surface"
    if any(k in out for k in ("accent", "accent2", "base", "gradient")) and "theme_preset" not in out:
        out["theme_preset"] = "custom"
    return out


# ------------------------------------------------------------------ themes
# Each theme is a complete look. Applying one resets every look setting to its default first, so
# themes never inherit leftovers from the previous one (text size and density are left alone).

def _t(name, accent, accent2, base="", **kw):
    return {"name": name, "accent": accent, "accent2": accent2, "base": base, **kw}


THEMES = {
    # the original accent-only themes
    "nova":     _t("Nova Violet", "#8b5cf6", "#c026d3"),
    "nebula":   _t("Nebula Magenta", "#d946ef", "#7c3aed"),
    "ultra":    _t("Ultraviolet", "#a855f7", "#6366f1"),
    "midnight": _t("Midnight Indigo", "#6366f1", "#a855f7"),
    "orchid":   _t("Orchid", "#c084fc", "#f472b6"),
    "amethyst": _t("Amethyst", "#9333ea", "#db2777"),
    # full looks
    "ocean":    _t("Ocean", "#0ea5e9", "#14b8a6", "#04121c", bg_mode="gradient", gradient="#03111c,#06304a,#04121c", angle=170),
    "deepsea":  _t("Deep Sea", "#38bdf8", "#2dd4bf", "#030c14", bg_mode="gradient", gradient="#030c14,#052a3f,#031a2a", angle=180, motion="flow", starfield=False),
    "forest":   _t("Forest", "#22c55e", "#84cc16", "#06120a", bg_mode="gradient", gradient="#06120a,#0f2a17,#06120a", angle=160),
    "matrix":   _t("Matrix", "#22c55e", "#16a34a", "#020a04", pattern="grid", pattern_opacity=9, font="mono", radius=2, starfield=False),
    "sunset":   _t("Sunset", "#f97316", "#ec4899", "#150811", bg_mode="gradient", gradient="#1a0b14,#3b1230,#2b1208", angle=200),
    "ember":    _t("Ember", "#f97316", "#ef4444", "#120706", bg_mode="gradient", gradient="#120706,#2e0d08,#120706", angle=190, motion="aurora"),
    "lava":     _t("Lava", "#ef4444", "#f59e0b", "#120706", bg_mode="gradient", gradient="#120706,#2e0d08,#120706", angle=190),
    "cyberpunk": _t("Cyberpunk", "#e11d9b", "#06b6d4", "#09060f", pattern="grid", pattern_opacity=10, radius=4, font="mono", starfield=False),
    "synthwave": _t("Synthwave", "#f472b6", "#22d3ee", "#0d0620", bg_mode="gradient", gradient="#1a0b2e,#0b1a3a,#12062a", angle=180, pattern="grid", pattern_opacity=8, motion="flow", starfield=False),
    "neon":     _t("Neon", "#22d3ee", "#a3e635", "#040a10", pattern="dots", pattern_opacity=14),
    "sakura":   _t("Sakura", "#f472b6", "#fb7185", "#160a12", bg_mode="gradient", gradient="#1a0b14,#2f1224", angle=150, font="rounded", radius=20),
    "candy":    _t("Candy", "#ec4899", "#8b5cf6", "#14081a", pattern="dots", pattern_opacity=10, radius=24, font="rounded"),
    "ice":      _t("Ice", "#38bdf8", "#a5b4fc", "#07111c", bg_mode="gradient", gradient="#07111c,#0e2236", angle=160, pattern="lines", pattern_opacity=6),
    "mono":     _t("Monochrome", "#a1a1aa", "#71717a", "#09090b", starfield=False, glow=False),
    "oled":     _t("OLED Black", "#8b5cf6", "#c026d3", "#000000", surface="oled", starfield=False),
    "galaxy":   _t("Galaxy", "#8b5cf6", "#3b82f6", "#070514", bg_mode="gradient", gradient="#070514,#1a0f3a,#0a1230", angle=135),
    "aurora":   _t("Aurora", "#2dd4bf", "#a78bfa", "#050f14", bg_mode="gradient", gradient="#050f14,#0b2a2a,#1a1040", angle=170, motion="aurora"),
    "mint":     _t("Mint", "#34d399", "#2dd4bf", "#05120f", font="rounded"),
    "desert":   _t("Desert", "#d97706", "#e11d48", "#150e08", bg_mode="gradient", gradient="#150e08,#2b1b0c", angle=175, font="serif"),
    "rosegold": _t("Rose Gold", "#fb7185", "#f59e0b", "#140a0c", bg_mode="gradient", gradient="#140a0c,#2a1418", angle=165, font="serif", radius=18),
    "terminal": _t("Terminal", "#4ade80", "#22d3ee", "#050805", font="mono", radius=0, pattern="lines", pattern_opacity=5, starfield=False, glow=False),
}
_KEEP_USER = ("font_scale", "density")      # accessibility choices a theme never overrides
MAX_USER_THEMES = 30


def theme_patch(theme: dict) -> dict:
    """The full set of look settings for one theme, validated."""
    base = {k: v for k, v in LOOK_DEFAULTS.items() if k not in _KEEP_USER}
    base.update({k: v for k, v in theme.items() if k != "name"})
    base["look_name"] = theme.get("name", "")
    return sanitize(base)


def _user_file():
    from . import paths
    return paths.data_dir() / "themes.json"


def load_user_themes() -> list[dict]:
    from .util import read_json
    data = read_json(_user_file(), {}) or {}
    out = []
    for t in data.get("themes", []):
        if isinstance(t, dict) and isinstance(t.get("id"), str) and isinstance(t.get("look"), dict):
            out.append({"id": t["id"], "name": str(t.get("name", "My theme"))[:40], "look": sanitize(t["look"])})
    return out


def save_user_theme(name: str, current: dict) -> dict:
    """Save the current look under a name (replacing a theme with the same name)."""
    import re as _re
    import uuid
    from .util import NovaError, write_json
    name = _re.sub(r"[^\w .,'&-]", "", name or "").strip()[:40]
    if not name:
        raise NovaError("Give the theme a name.")
    look = {k: current[k] for k in LOOK_KEYS if k in current and k not in ("theme_preset", "look_name")}
    if look.get("bg_mode") == "media":      # imported files stay on this computer, not in the theme
        look["bg_mode"] = "gradient" if look.get("gradient") else "surface"
    themes = load_user_themes()
    existing = next((t for t in themes if t["name"].lower() == name.lower()), None)
    if existing is None and len(themes) >= MAX_USER_THEMES:
        raise NovaError(f"You can keep up to {MAX_USER_THEMES} saved themes. Delete one first.")
    entry = existing or {"id": "my-" + uuid.uuid4().hex[:8], "name": name}
    entry["name"], entry["look"] = name, sanitize(look)
    if existing is None:
        themes.append(entry)
    write_json(_user_file(), {"themes": themes})
    return entry


def delete_user_theme(tid: str) -> None:
    from .util import write_json
    write_json(_user_file(), {"themes": [t for t in load_user_themes() if t["id"] != tid]})


def find_theme(tid: str) -> dict | None:
    """A built-in or saved theme by id, as a dict ready for theme_patch(); None if unknown."""
    if tid in THEMES:
        return THEMES[tid]
    t = next((t for t in load_user_themes() if t["id"] == tid), None)
    return {**t["look"], "name": t["name"]} if t else None
