"""Performance tooling: JVM flag presets, memory recommendations, options.txt
profiles and disk clean-up."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import paths
from .util import dir_size

# ---------------------------------------------------------------- system

def system_ram_mb() -> int:
    try:
        s = paths.os_name()
        if s == "linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) // 1024
        elif s == "windows":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = MS()
            ms.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))  # type: ignore[attr-defined]
            return int(ms.ullTotalPhys // (1024 * 1024))
        elif s == "osx":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            return int(out.stdout.strip()) // (1024 * 1024)
    except Exception:
        pass
    return 8192


def system_info() -> dict:
    return {"ram_mb": system_ram_mb(), "cpus": os.cpu_count() or 4, "os": paths.os_name(),
            "arch": paths.arch_name()}


def recommend_memory(loader: str, mod_count: int, ram_mb: int | None = None) -> dict:
    """Suggest -Xms/-Xmx in MB. Never recommends more than ~55% of physical RAM."""
    ram = ram_mb or system_ram_mb()
    if loader == "vanilla" or mod_count == 0:
        want = 2048
    elif mod_count < 40:
        want = 4096
    elif mod_count < 120:
        want = 6144
    elif mod_count < 250:
        want = 8192
    else:
        want = 10240
    cap = int(ram * 0.55) // 256 * 256
    mx = max(1024, min(want, cap))
    mn = max(512, min(mx, (mx // 2) // 256 * 256))
    return {"min": mn, "max": mx, "ram_mb": ram}


# ------------------------------------------------------------ JVM presets

def _aikar(max_mb: int) -> list[str]:
    big = max_mb >= 12 * 1024
    return [
        "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=200",
        "-XX:+UnlockExperimentalVMOptions", "-XX:+DisableExplicitGC", "-XX:+AlwaysPreTouch",
        f"-XX:G1NewSizePercent={40 if big else 30}", f"-XX:G1MaxNewSizePercent={50 if big else 40}",
        f"-XX:G1HeapRegionSize={16 if big else 8}M", f"-XX:G1ReservePercent={15 if big else 20}",
        "-XX:G1HeapWastePercent=5", "-XX:G1MixedGCCountTarget=4",
        f"-XX:InitiatingHeapOccupancyPercent={20 if big else 15}",
        "-XX:G1MixedGCLiveThresholdPercent=90", "-XX:G1RSetUpdatingPauseTimePercent=5",
        "-XX:SurvivorRatio=32", "-XX:+PerfDisableSharedMem", "-XX:MaxTenuringThreshold=1",
    ]


def _balanced(max_mb: int) -> list[str]:
    return [
        "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=50",
        "-XX:+UnlockExperimentalVMOptions", "-XX:+DisableExplicitGC",
        "-XX:G1NewSizePercent=30", "-XX:G1MaxNewSizePercent=40", "-XX:G1HeapRegionSize=8M",
        "-XX:G1ReservePercent=20", "-XX:InitiatingHeapOccupancyPercent=15",
        "-XX:+PerfDisableSharedMem",
    ]


def _zgc(max_mb: int, java_major: int) -> list[str]:
    if java_major < 21:
        return _balanced(max_mb)
    flags = ["-XX:+UseZGC", "-XX:+DisableExplicitGC", "-XX:+PerfDisableSharedMem"]
    if java_major < 23:
        flags.insert(1, "-XX:+ZGenerational")  # generational is default from 23
    return flags


def _lowend(max_mb: int) -> list[str]:
    return ["-XX:+UseSerialGC", "-XX:+DisableExplicitGC", "-Xshare:auto", "-XX:+PerfDisableSharedMem"]


PRESETS = {
    "balanced": {"name": "Nova Balanced", "icon": "◈",
                 "desc": "Low-pause G1 tuning that works well for almost everyone. Recommended."},
    "aikar": {"name": "Aikar's Flags", "icon": "⚙",
              "desc": "The community-standard G1 flag set. Best with 6 GB+ and big modpacks. Slightly slower start (pre-touches memory)."},
    "zgc": {"name": "Generational ZGC", "icon": "⚡",
            "desc": "Near-zero GC pauses. Needs Java 21+ and a CPU with spare cores; falls back to Balanced on older Java."},
    "lowend": {"name": "Low-end PC", "icon": "▽",
               "desc": "Serial GC with a small footprint for dual-core or low-RAM machines."},
    "none": {"name": "None (vanilla JVM defaults)", "icon": "○", "desc": "Pass no extra tuning flags."},
    "custom": {"name": "Custom only", "icon": "✎", "desc": "Use only the arguments you type yourself."},
}


def preset_flags(preset: str, max_mb: int, java_major: int) -> list[str]:
    if preset == "aikar":
        return _aikar(max_mb)
    if preset == "zgc":
        return _zgc(max_mb, java_major)
    if preset == "lowend":
        return _lowend(max_mb)
    if preset == "balanced":
        return _balanced(max_mb)
    return []


def build_jvm_args(inst: dict, java_major: int, global_args: str = "") -> list[str]:
    from .util import split_args
    mx = int(inst.get("memory_max") or 2048)
    mn = int(inst.get("memory_min") or min(mx, 1024))
    mn = min(mn, mx)
    args = [f"-Xms{mn}M", f"-Xmx{mx}M"]
    args += preset_flags(inst.get("jvm_preset", "balanced"), mx, java_major)
    for extra in (global_args, inst.get("jvm_args", "")):
        if extra and extra.strip():
            args += split_args(extra)
    # de-duplicate exact repeats while preserving order
    seen, out = set(), []
    for a in args:
        if a in seen and a.startswith("-XX:"):
            continue
        seen.add(a)
        out.append(a)
    return out


# ------------------------------------------------------- options.txt tuning

OPTIONS_PROFILES = {
    "performance": {
        "name": "Max FPS", "desc": "Aggressive settings for the highest frame rate.",
        "values": {"renderDistance": "8", "simulationDistance": "6", "maxFps": "260", "enableVsync": "false",
                   "fancyGraphics": "false", "graphicsMode": "0", "particles": "2",
                   "entityDistanceScaling": "0.5", "biomeBlendRadius": "0", "mipmapLevels": "0",
                   "entityShadows": "false", "renderClouds": "false", "fboEnable": "true"},
    },
    "balanced": {
        "name": "Balanced", "desc": "Good looks with solid performance.",
        "values": {"renderDistance": "12", "simulationDistance": "10", "maxFps": "144", "enableVsync": "false",
                   "fancyGraphics": "true", "graphicsMode": "1", "particles": "1",
                   "entityDistanceScaling": "1.0", "biomeBlendRadius": "2", "mipmapLevels": "2",
                   "entityShadows": "true", "renderClouds": "fast"},
    },
    "quality": {
        "name": "Quality", "desc": "Prettier visuals for strong hardware.",
        "values": {"renderDistance": "20", "simulationDistance": "12", "maxFps": "260", "enableVsync": "false",
                   "fancyGraphics": "true", "graphicsMode": "2", "particles": "0",
                   "entityDistanceScaling": "1.5", "biomeBlendRadius": "5", "mipmapLevels": "4",
                   "entityShadows": "true", "renderClouds": "true"},
    },
}


def read_options(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k] = v
    return out


def apply_options_profile(game_dir: Path, profile: str) -> list[str]:
    """Merge a profile into options.txt, keeping every other setting. Returns changed keys."""
    prof = OPTIONS_PROFILES.get(profile)
    if not prof:
        raise ValueError("Unknown profile")
    path = game_dir / "options.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    values = dict(prof["values"])
    # Only touch keys the game already uses, plus the universal ones on a fresh file.
    universal = {"renderDistance", "maxFps", "enableVsync", "particles", "renderClouds", "entityShadows"}
    seen_keys = {l.split(":", 1)[0] for l in existing if ":" in l}
    if seen_keys:
        values = {k: v for k, v in values.items() if k in seen_keys or k in universal}
    else:
        values = {k: v for k, v in values.items() if k in universal}
    changed, out_lines, done = [], [], set()
    for line in existing:
        if ":" in line:
            k = line.split(":", 1)[0]
            if k in values:
                out_lines.append(f"{k}:{values[k]}")
                done.add(k)
                changed.append(k)
                continue
        out_lines.append(line)
    for k, v in values.items():
        if k not in done:
            out_lines.append(f"{k}:{v}")
            changed.append(k)
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return changed


# ---------------------------------------------------------------- cleanup

CLEAN_TARGETS = {
    "logs": ("Logs", "logs"),
    "crash-reports": ("Crash reports", "crash-reports"),
    "screenshots-cache": ("Shader cache", "shadercache"),
    "debug": ("Debug dumps", "debug"),
}


def cleanup_report(game_dir: Path) -> list[dict]:
    out = []
    for key, (label, folder) in CLEAN_TARGETS.items():
        p = game_dir / folder
        out.append({"key": key, "label": label, "folder": folder,
                    "bytes": dir_size(p) if p.exists() else 0})
    return out


def cleanup(game_dir: Path, keys: list[str]) -> int:
    freed = 0
    for key in keys:
        t = CLEAN_TARGETS.get(key)
        if not t:
            continue
        p = game_dir / t[1]
        if p.exists():
            freed += dir_size(p)
            shutil.rmtree(p, ignore_errors=True)
    return freed
