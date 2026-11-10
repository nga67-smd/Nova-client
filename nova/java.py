"""Find or download the right Java runtime."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from . import config, paths
from .util import (NovaError, Task, download_file, http_get_json, safe_extract_tar, safe_extract_zip)

_major_cache: dict[str, int | None] = {}


def exe_name() -> str:
    return "java.exe" if paths.os_name() == "windows" else "java"


def java_major(java_path: str | Path) -> int | None:
    key = str(java_path)
    if key in _major_cache:
        return _major_cache[key]
    major = None
    try:
        flags = 0x08000000 if paths.os_name() == "windows" else 0  # CREATE_NO_WINDOW
        out = subprocess.run([key, "-version"], capture_output=True, text=True, timeout=15,
                             creationflags=flags)
        text = (out.stderr or "") + (out.stdout or "")
        m = re.search(r'version "(\d+)(?:\.(\d+))?', text)
        if m:
            major = int(m.group(1))
            if major == 1 and m.group(2):
                major = int(m.group(2))  # 1.8 -> 8
    except Exception:
        major = None
    _major_cache[key] = major
    return major


def _candidates() -> list[Path]:
    found: list[Path] = []

    def add(p):
        p = Path(p)
        if p.exists() and p not in found:
            found.append(p)

    for var in ("NOVA_JAVA", "JAVA_HOME"):
        v = os.environ.get(var)
        if v:
            pv = Path(v)
            add(pv if pv.is_file() else pv / "bin" / exe_name())
    w = shutil.which("java")
    if w:
        add(w)
    # managed runtimes
    rt = paths.runtimes_dir()
    for d in sorted(rt.glob("*")):
        for exe in (d / "bin" / exe_name(), d / "Contents" / "Home" / "bin" / exe_name()):
            add(exe)
    s = paths.os_name()
    roots: list[Path] = []
    if s == "windows":
        for pf in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
            if pf:
                for vendor in ("Java", "Eclipse Adoptium", "Microsoft", "Zulu", "BellSoft", "Amazon Corretto"):
                    roots.append(Path(pf) / vendor)
    elif s == "osx":
        roots += [Path("/Library/Java/JavaVirtualMachines"), Path.home() / "Library/Java/JavaVirtualMachines"]
    else:
        roots += [Path("/usr/lib/jvm"), Path("/usr/java"), Path.home() / ".sdkman/candidates/java"]
    for r in roots:
        if r.is_dir():
            for d in sorted(r.iterdir()):
                add(d / "bin" / exe_name())
                add(d / "Contents" / "Home" / "bin" / exe_name())
    return found


def detect() -> list[dict]:
    out = []
    for p in _candidates():
        m = java_major(p)
        if m:
            out.append({"path": str(p), "major": m})
    return sorted(out, key=lambda j: j["major"])


def required_major(version: dict) -> int:
    jv = version.get("javaVersion") or {}
    if jv.get("majorVersion"):
        return int(jv["majorVersion"])
    return 8


def find_suitable(major: int) -> str | None:
    javas = detect()
    for j in javas:
        if j["major"] == major:
            return j["path"]
    if major >= 17:
        higher = [j for j in javas if j["major"] >= major]
        if higher:
            return higher[0]["path"]
    return None


def _adoptium_os() -> str:
    return {"windows": "windows", "osx": "mac", "linux": "linux"}[paths.os_name()]


def _adoptium_arch() -> str:
    return {"x64": "x64", "arm64": "aarch64", "x86": "x32"}[paths.arch_name()]


def install_managed(major: int, task: Task | None = None) -> str:
    """Download a Temurin JRE from Adoptium into the runtimes folder."""
    dest_root = paths.runtimes_dir() / f"temurin-{major}"
    exe = _find_exe(dest_root)
    if exe:
        return str(exe)
    url = (f"{config.adoptium_api()}/binary/latest/{major}/ga/{_adoptium_os()}/{_adoptium_arch()}"
           f"/jre/hotspot/normal/eclipse")
    if task:
        task.update(f"Downloading Java {major}…")
    archive = paths.downloads_dir() / f"temurin-{major}.{'zip' if paths.os_name() == 'windows' else 'tar.gz'}"
    download_file(url, archive)
    tmp = paths.runtimes_dir() / f".tmp-temurin-{major}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        if archive.suffix == ".zip":
            safe_extract_zip(archive, tmp)
        else:
            safe_extract_tar(archive, tmp)
        # flatten single top-level dir
        entries = [e for e in tmp.iterdir()]
        src = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmp
        shutil.rmtree(dest_root, ignore_errors=True)
        shutil.move(str(src), str(dest_root))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            archive.unlink()
        except OSError:
            pass
    exe = _find_exe(dest_root)
    if not exe:
        raise NovaError(f"Downloaded Java {major} but could not find the java executable.")
    if paths.os_name() != "windows":
        os.chmod(exe, 0o755)
    _major_cache.pop(str(exe), None)
    return str(exe)


def _find_exe(root: Path) -> Path | None:
    for cand in (root / "bin" / exe_name(), root / "Contents" / "Home" / "bin" / exe_name()):
        if cand.exists():
            return cand
    return None


def ensure_java(version: dict, override: str | None, settings_java: str | None,
                task: Task | None = None, auto_download: bool = True) -> tuple[str, int]:
    """Return (java_path, major). Honors per-instance then global overrides."""
    need = required_major(version)
    for custom in (override, settings_java):
        if custom:
            if not Path(custom).exists():
                raise NovaError(f"Java path does not exist: {custom}")
            m = java_major(custom)
            if not m:
                raise NovaError(f"Could not run Java at: {custom}")
            return custom, m
    found = find_suitable(need)
    if found:
        return found, java_major(found) or need
    if not auto_download:
        raise NovaError(f"Java {need} is required but was not found.")
    path = install_managed(need, task)
    return path, need
