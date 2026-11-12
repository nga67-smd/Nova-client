"""Custom looks: validation of theme changes, ready-made moods, and an offline theme assistant.

Every change to the theme, whether typed in Settings or proposed by the AI chat, goes through
`sanitize()`. It only lets known keys through, checks every value, and keeps colors readable
(Nova's text is light, so backgrounds stay dark and accents stay visible). Nothing the AI returns
is ever used as raw CSS.
"""
from __future__ import annotations

import colorsys
import re

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

LOOK_DEFAULTS = {
    "accent": "#8b5cf6", "accent2": "#c026d3", "theme_preset": "nova",
    "surface": "void", "base": "", "bg_mode": "surface",
    "gradient": "", "angle": 160, "pattern": "none", "pattern_opacity": 12, "overlay": 35,
    "font": "system", "radius": 14, "font_scale": 100, "density": "comfortable",
    "glow": True, "starfield": True, "look_name": "",
}
LOOK_KEYS = tuple(LOOK_DEFAULTS)
ENUMS = {
    "bg_mode": ("surface", "gradient", "image"),
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


# ------------------------------------------------------------------ moods

MOODS = {
    "ocean":    {"look_name": "Ocean", "accent": "#0ea5e9", "accent2": "#14b8a6", "base": "#04121c", "bg_mode": "gradient", "gradient": "#03111c,#06304a,#04121c", "angle": 170, "pattern": "none"},
    "forest":   {"look_name": "Forest", "accent": "#22c55e", "accent2": "#84cc16", "base": "#06120a", "bg_mode": "gradient", "gradient": "#06120a,#0f2a17,#06120a", "angle": 160},
    "sunset":   {"look_name": "Sunset", "accent": "#f97316", "accent2": "#ec4899", "base": "#150811", "bg_mode": "gradient", "gradient": "#1a0b14,#3b1230,#2b1208", "angle": 200},
    "cyberpunk": {"look_name": "Cyberpunk", "accent": "#e11d9b", "accent2": "#06b6d4", "base": "#09060f", "bg_mode": "surface", "pattern": "grid", "pattern_opacity": 10, "radius": 4, "font": "mono", "starfield": False},
    "neon":     {"look_name": "Neon", "accent": "#22d3ee", "accent2": "#a3e635", "base": "#040a10", "pattern": "dots", "pattern_opacity": 14, "glow": True},
    "sakura":   {"look_name": "Sakura", "accent": "#f472b6", "accent2": "#fb7185", "base": "#160a12", "bg_mode": "gradient", "gradient": "#1a0b14,#2f1224", "angle": 150, "font": "rounded", "radius": 20},
    "lava":     {"look_name": "Lava", "accent": "#ef4444", "accent2": "#f59e0b", "base": "#120706", "bg_mode": "gradient", "gradient": "#120706,#2e0d08,#120706", "angle": 190},
    "ice":      {"look_name": "Ice", "accent": "#38bdf8", "accent2": "#a5b4fc", "base": "#07111c", "bg_mode": "gradient", "gradient": "#07111c,#0e2236", "angle": 160, "pattern": "lines", "pattern_opacity": 6},
    "mono":     {"look_name": "Monochrome", "accent": "#a1a1aa", "accent2": "#71717a", "base": "#09090b", "bg_mode": "surface", "starfield": False, "glow": False},
    "galaxy":   {"look_name": "Galaxy", "accent": "#8b5cf6", "accent2": "#3b82f6", "base": "#070514", "bg_mode": "gradient", "gradient": "#070514,#1a0f3a,#0a1230", "angle": 135, "starfield": True},
    "aurora":   {"look_name": "Aurora", "accent": "#2dd4bf", "accent2": "#a78bfa", "base": "#050f14", "bg_mode": "gradient", "gradient": "#050f14,#0b2a2a,#1a1040", "angle": 170, "starfield": True},
    "mint":     {"look_name": "Mint", "accent": "#34d399", "accent2": "#2dd4bf", "base": "#05120f", "bg_mode": "surface", "font": "rounded"},
    "desert":   {"look_name": "Desert", "accent": "#d97706", "accent2": "#e11d48", "base": "#150e08", "bg_mode": "gradient", "gradient": "#150e08,#2b1b0c", "angle": 175, "font": "serif"},
    "candy":    {"look_name": "Candy", "accent": "#ec4899", "accent2": "#8b5cf6", "base": "#14081a", "pattern": "dots", "pattern_opacity": 10, "radius": 24, "font": "rounded"},
    "oled":     {"look_name": "OLED Black", "base": "#000000", "bg_mode": "surface", "surface": "oled", "starfield": False},
}
MOOD_ALIASES = {"sea": "ocean", "water": "ocean", "blue lagoon": "ocean", "nature": "forest", "jungle": "forest", "woods": "forest",
                "sunrise": "sunset", "dusk": "sunset", "synthwave": "cyberpunk", "retro": "cyberpunk", "vaporwave": "cyberpunk",
                "cherry": "sakura", "blossom": "sakura", "fire": "lava", "volcano": "lava", "snow": "ice", "winter": "ice",
                "frost": "ice", "gray": "mono", "grey": "mono", "greyscale": "mono", "black and white": "mono", "space": "galaxy",
                "cosmic": "galaxy", "northern lights": "aurora", "sand": "desert", "sweet": "candy", "pitch black": "oled", "amoled": "oled"}

COLORS = {
    "red": "#ef4444", "crimson": "#dc2626", "orange": "#f97316", "amber": "#f59e0b", "yellow": "#eab308", "gold": "#d4a017",
    "lime": "#84cc16", "green": "#22c55e", "emerald": "#10b981", "teal": "#14b8a6", "cyan": "#06b6d4", "turquoise": "#2dd4bf",
    "sky": "#38bdf8", "blue": "#3b82f6", "navy": "#1e3a8a", "indigo": "#6366f1", "violet": "#8b5cf6", "purple": "#a855f7",
    "magenta": "#d946ef", "fuchsia": "#d946ef", "pink": "#ec4899", "rose": "#f43f5e", "coral": "#fb7185", "brown": "#a16207",
    "white": "#e5e7eb", "silver": "#a1a1aa", "slate": "#64748b", "lavender": "#a78bfa", "mint": "#34d399", "peach": "#fb923c",
}


def _find_colors(text: str) -> list[tuple[str, str]]:
    found = []
    for m in re.finditer(r"#[0-9a-fA-F]{6}\b|\b[a-z]+\b", text):
        w = m.group(0)
        if w.startswith("#"):
            found.append((w.lower(), w.lower()))
        elif w in COLORS:
            found.append((w, COLORS[w]))
    return found


HELP = ("I can restyle Nova from plain words. Try: “ocean theme”, “dark red with a grid”, "
        "“purple to blue gradient”, “sharper corners”, “no stars”, “bigger text”, "
        "“monospace font”, or “reset”. For free-form requests, add a Claude API key below and I'll understand anything.")


def offline_respond(text: str, current: dict) -> tuple[str, dict]:
    """A keyword-based theme assistant that needs no internet and no key."""
    t = " " + re.sub(r"[^\w#\s'-]", " ", text.lower()) + " "
    patch: dict = {}
    notes: list[str] = []

    if re.search(r"\b(reset|default|original|start over)\b", t):
        return "Back to Nova's original look.", dict(LOOK_DEFAULTS)

    mood = next((m for m in MOODS if f" {m} " in t), None) or next((v for k, v in MOOD_ALIASES.items() if f" {k} " in t), None)
    if mood:
        patch.update(MOODS[mood])
        notes.append(f"{MOODS[mood]['look_name']} look")

    colors = _find_colors(t)
    wants_gradient = bool(re.search(r"\b(gradient|fade|blend|to)\b", t)) and len(colors) >= 2
    bg_words = re.search(r"\b(background|backdrop|wallpaper)\b", t)
    if wants_gradient:
        a, b = colors[0][1], colors[1][1]
        patch.update({"bg_mode": "gradient", "gradient": f"{clamp_dark(a, 0.25)},{clamp_dark(b, 0.25)}", "accent": a, "accent2": b,
                      "theme_preset": "custom"})
        notes.append(f"{colors[0][0]} → {colors[1][0]} gradient")
    elif colors:
        name, hexv = colors[0]
        if mood:   # "ocean blue": keep the mood's background, just retint the accents
            pal = palette_from(hexv)
            patch.update({"accent": pal["accent"], "accent2": pal["accent2"], "theme_preset": "custom"})
            notes.append(f"{name} accent")
        elif bg_words and not re.search(r"\baccent\b", t):
            patch.update({"base": hexv, "bg_mode": "surface"})
            notes.append(f"{name} background")
        else:
            patch.update(palette_from(hexv))
            if len(colors) > 1:
                patch["accent2"] = clamp_accent(colors[1][1])
            notes.append(f"{name} accent")

    for pat in ("grid", "dots", "lines"):
        if f" {pat} " in t and not re.search(rf"\bno {pat}\b", t):
            patch.update({"pattern": pat, "pattern_opacity": 12})
            notes.append(f"{pat} pattern")
    if re.search(r"\b(no|remove|without|hide) (pattern|grid|dots|lines)\b", t):
        patch["pattern"] = "none"
        notes.append("pattern removed")

    if re.search(r"\b(no|remove|without|hide|turn off|disable) (the )?(stars|starfield)\b", t):
        patch["starfield"] = False; notes.append("stars off")
    elif re.search(r"\b(stars|starfield)\b", t):
        patch["starfield"] = True; notes.append("stars on")
    if re.search(r"\b(no|remove|without|turn off|disable) (the )?glow\b", t):
        patch["glow"] = False; notes.append("glow off")
    elif re.search(r"\b(more|extra|stronger|add|turn on) glow\b|\bglowy\b", t):
        patch["glow"] = True; notes.append("glow on")

    if re.search(r"\b(sharper|sharp|square|squarer|angular|boxy|less round)\b", t):
        patch["radius"] = 3 if re.search(r"\b(square|boxy)\b", t) else max(0, int(current.get("radius", 14)) - 8); notes.append("sharper corners")
    elif re.search(r"\b(rounder|round|rounded|softer|bubbly|pill)\b", t) and "font" not in t:
        patch["radius"] = 26 if re.search(r"\b(bubbly|pill)\b", t) else min(28, int(current.get("radius", 14)) + 8); notes.append("rounder corners")

    if re.search(r"\b(bigger|larger|increase|big)\b.*\b(text|font|ui)\b|\b(text|font)\b.*\b(bigger|larger)\b", t):
        patch["font_scale"] = min(125, int(current.get("font_scale", 100)) + 10); notes.append("bigger text")
    elif re.search(r"\b(smaller|tiny|reduce|small)\b.*\b(text|font|ui)\b|\b(text|font)\b.*\b(smaller)\b", t):
        patch["font_scale"] = max(85, int(current.get("font_scale", 100)) - 10); notes.append("smaller text")
    if re.search(r"\bcompact\b", t):
        patch["density"] = "compact"; notes.append("compact layout")
    elif re.search(r"\b(comfortable|roomy|spacious|airy)\b", t):
        patch["density"] = "comfortable"; notes.append("roomy layout")

    for f, words in (("mono", r"mono|monospace|code|terminal|hacker"), ("serif", r"serif|elegant|classic"),
                     ("rounded", r"rounded font|friendly font|soft font"), ("system", r"normal font|default font|system font")):
        if re.search(rf"\b({words})\b", t) and not (f == "mono" and mood == "mono" and "font" not in t):
            patch["font"] = f; notes.append(f"{f} font")
            break

    if re.search(r"\bdarker\b", t) and not patch.get("base"):
        patch["base"] = clamp_dark(_scale(current.get("base") or "#0b0816", 0.6), 0.16); notes.append("darker")
    elif re.search(r"\b(lighter|brighter)\b", t) and not patch.get("base"):
        patch["base"] = clamp_dark(_toward_white(current.get("base") or "#0b0816", 0.12)); notes.append("a bit lighter")
    if re.search(r"\b(black|amoled)\b", t) and re.search(r"\b(background|oled|screen)\b", t) and not patch.get("base"):
        patch.update({"base": "#000000", "surface": "oled"}); notes.append("pure black")
    if re.search(r"\b(overlay|dim)\b", t):
        patch["overlay"] = min(85, int(current.get("overlay", 35)) + 15); notes.append("dimmer background")

    clean = sanitize(patch)
    if not clean:
        return HELP, {}
    return "Done: " + ", ".join(notes) + ". Say “undo” to go back.", clean
