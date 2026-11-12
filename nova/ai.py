"""The theme chat: a built-in offline assistant, or Claude when the user adds an API key.

The key is stored in settings.json, never sent to the UI, and only ever sent to api.anthropic.com.
Whatever the model returns is treated as untrusted: it is parsed as JSON and passed through
look.sanitize(), so it can only change the known theme settings.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from . import look, settings
from .util import NovaError, USER_AGENT

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"

SYSTEM = """You are the theme designer inside Nova Launcher, a Minecraft launcher with a dark UI.
The user describes how they want the launcher to look. Reply with ONLY a JSON object:
{"reply": "<one or two friendly sentences>", "changes": { ... }}

"changes" may contain any of these keys (omit the ones you don't change):
- accent, accent2: hex colors like "#8b5cf6" (buttons, highlights, glow). Vivid, mid-brightness.
- base: hex page background color. MUST be very dark (the UI text is light). "" = default.
- bg_mode: "surface" | "gradient" | "image";  gradient: 2-3 dark hex colors joined by commas, e.g. "#06120a,#0f2a17"; angle: 0-360
- pattern: "none" | "grid" | "dots" | "lines";  pattern_opacity: 0-60
- overlay: 0-85 (how much a background image is dimmed)
- font: "system" | "rounded" | "mono" | "serif"
- radius: 0-28 (corner roundness); font_scale: 85-125; density: "comfortable" | "compact"
- glow: true/false; starfield: true/false; look_name: short name for the look

Keep text readable: backgrounds dark, accents bright enough to see. Be creative and make coordinated palettes
(accent + accent2 + a tinted dark base or a dark gradient). If the request isn't about the launcher's look,
say so briefly and return empty changes. Never include anything except the JSON object."""


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in reply")
    data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data


def ask_claude(message: str, history: list, current: dict, api_key: str, model: str) -> tuple[str, dict]:
    msgs = []
    for h in (history or [])[-8:]:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant") and isinstance(h.get("text"), str):
            msgs.append({"role": h["role"], "content": h["text"][:1500]})
    msgs.append({"role": "user", "content": message[:1500]})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    shown = {k: current.get(k) for k in look.LOOK_KEYS}
    body = {"model": model or DEFAULT_MODEL, "max_tokens": 900,
            "system": SYSTEM + "\n\nCurrent look: " + json.dumps(shown), "messages": msgs}
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), method="POST", headers={
        "x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            pass
        if e.code in (401, 403):
            raise NovaError("Claude didn't accept that API key. Check it in the AI page.") from e
        if e.code == 429:
            raise NovaError("Claude is rate-limiting this key right now. Try again in a minute.") from e
        raise NovaError(f"Claude returned an error ({e.code}). {detail}".strip()) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise NovaError(f"Couldn't reach Claude ({e}).") from e
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    try:
        parsed = _extract_json(text)
    except ValueError:
        return text.strip()[:400] or "I couldn't turn that into a look.", {}
    return str(parsed.get("reply", "Done."))[:400], look.sanitize(parsed.get("changes") or {})


def chat(message: str, history: list) -> dict:
    """Run one chat turn and return {reply, changes, engine, error?}. Does not apply anything."""
    message = (message or "").strip()
    if not message:
        raise NovaError("Type what you want Nova to look like.")
    s = settings.load()
    if re.fullmatch(r"\s*undo\s*", message, re.I):
        return {"reply": "", "changes": {}, "engine": "undo"}
    key = s.get("ai_api_key", "").strip()
    use_claude = bool(key) and s.get("ai_engine", "auto") != "offline"
    if use_claude:
        try:
            reply, changes = ask_claude(message, history, s, key, s.get("ai_model") or DEFAULT_MODEL)
            return {"reply": reply, "changes": changes, "engine": "claude"}
        except NovaError as e:
            reply, changes = look.offline_respond(message, s)
            return {"reply": reply, "changes": changes, "engine": "offline", "error": str(e) + " Used the built-in assistant instead."}
    reply, changes = look.offline_respond(message, s)
    return {"reply": reply, "changes": changes, "engine": "offline"}
