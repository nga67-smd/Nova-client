"""Filesystem layout and platform helpers."""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def os_name() -> str:
    """Mojang-style OS name: windows / osx / linux."""
    s = platform.system()
    if s == "Windows":
        return "windows"
    if s == "Darwin":
        return "osx"
    return "linux"


def arch_name() -> str:
    """Mojang-style arch: x86 / x64 / arm64."""
    m = platform.machine().lower()
    if m in ("arm64", "aarch64"):
        return "arm64"
    if m in ("x86_64", "amd64"):
        return "x64"
    if m in ("i386", "i686", "x86"):
        return "x86"
    return "x64"


def data_dir() -> Path:
    env = os.environ.get("NOVA_HOME")
    if env:
        return Path(env).expanduser()
    s = os_name()
    if s == "windows":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif s == "osx":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "NovaLauncher"


def sub(name: str) -> Path:
    p = data_dir() / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def libraries_dir() -> Path:
    return sub("libraries")


def assets_dir() -> Path:
    return sub("assets")


def versions_dir() -> Path:
    return sub("versions")


def runtimes_dir() -> Path:
    return sub("runtimes")


def cache_dir() -> Path:
    return sub("cache")


def downloads_dir() -> Path:
    return sub("downloads")


def instances_dir() -> Path:
    return sub("instances")


def ui_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)  # PyInstaller
    if base:
        return Path(base) / "nova" / "ui"
    return Path(__file__).parent / "ui"


def open_in_file_manager(path: Path) -> None:
    import subprocess

    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    s = os_name()
    if s == "windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif s == "osx":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
