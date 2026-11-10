"""HTTP, hashing, downloads and background task tracking."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
import zipfile
import tarfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterable

from . import __version__

USER_AGENT = f"NovaLauncher/{__version__} (+local launcher)"


class NovaError(Exception):
    """An error whose message is safe and useful to show to the user."""


# ----------------------------------------------------------------- HTTP

def _open(url: str, timeout: float = 30, headers: dict | None = None, data: bytes | None = None):
    h = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, data=data)
    return urllib.request.urlopen(req, timeout=timeout)


def http_get(url: str, timeout: float = 30, retries: int = 3, headers: dict | None = None) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with _open(url, timeout, headers) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404, 410):
                break
        except Exception as e:  # network hiccup
            last = e
        time.sleep(0.4 * (attempt + 1))
    raise NovaError(f"Could not download {url}: {last}")


def http_get_json(url: str, **kw) -> Any:
    return json.loads(http_get(url, **kw).decode("utf-8"))


def http_get_text(url: str, **kw) -> str:
    return http_get(url, **kw).decode("utf-8", "replace")


# -------------------------------------------------------------- hashing

def file_hash(path: Path, algo: str = "sha1") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, dest: Path, sha1: str | None = None, sha512: str | None = None,
                  size: int | None = None, on_bytes: Callable[[int], None] | None = None) -> Path:
    """Download atomically; verify hash when provided. Skips if dest already valid."""
    dest = Path(dest)
    if dest.exists():
        if sha1:
            if file_hash(dest, "sha1") == sha1.lower():
                return dest
        elif sha512:
            if file_hash(dest, "sha512") == sha512.lower():
                return dest
        elif size is not None and dest.stat().st_size == size:
            return dest
        elif size is None and dest.stat().st_size > 0:
            return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + f".{uuid.uuid4().hex[:6]}.part")
    last: Exception | None = None
    for attempt in range(3):
        try:
            h1 = hashlib.sha1()
            h5 = hashlib.sha512()
            with _open(url, timeout=60) as r, open(part, "wb") as f:
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
                    h1.update(chunk)
                    h5.update(chunk)
                    if on_bytes:
                        on_bytes(len(chunk))
            if sha1 and h1.hexdigest() != sha1.lower():
                raise NovaError(f"Checksum mismatch for {dest.name}")
            if sha512 and h5.hexdigest() != sha512.lower():
                raise NovaError(f"Checksum mismatch for {dest.name}")
            os.replace(part, dest)
            return dest
        except Exception as e:
            last = e
            try:
                part.unlink()
            except OSError:
                pass
            if isinstance(e, urllib.error.HTTPError) and e.code in (403, 404, 410):
                break
            time.sleep(0.5 * (attempt + 1))
    raise NovaError(f"Failed to download {url}: {last}")


def download_many(items: Iterable[tuple], task: "Task | None" = None, workers: int = 8,
                  label: str = "Downloading") -> None:
    """items: (url, dest, sha1, size). Skips files already valid."""
    items = list(items)
    total = len(items)
    if not total:
        return
    done = 0
    lock = threading.Lock()

    def one(it):
        url, dest, sha1, size = (list(it) + [None, None])[:4]
        download_file(url, Path(dest), sha1=sha1, size=size)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, it) for it in items]
        for f in as_completed(futs):
            f.result()
            with lock:
                done += 1
                if task:
                    task.update(message=f"{label} ({done}/{total})", sub=done / total)


# ------------------------------------------------------------- archives

def safe_extract_zip(zpath: Path, dest: Path, skip: Callable[[str], bool] | None = None) -> None:
    dest = Path(dest).resolve()
    with zipfile.ZipFile(zpath) as z:
        for m in z.infolist():
            if skip and skip(m.filename):
                continue
            target = (dest / m.filename).resolve()
            if dest != target and dest not in target.parents:
                raise NovaError(f"Unsafe path in archive: {m.filename}")
            if m.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as src, open(target, "wb") as out:
                while True:
                    c = src.read(1 << 16)
                    if not c:
                        break
                    out.write(c)
            # preserve exec bit (unix zips)
            mode = (m.external_attr >> 16) & 0o777
            if mode & 0o111:
                try:
                    os.chmod(target, mode)
                except OSError:
                    pass


def safe_extract_tar(tpath: Path, dest: Path) -> None:
    dest = Path(dest).resolve()
    with tarfile.open(tpath) as t:
        for m in t.getmembers():
            target = (dest / m.name).resolve()
            if dest != target and dest not in target.parents:
                raise NovaError(f"Unsafe path in archive: {m.name}")
            if m.issym() or m.islnk():
                # keep only links that stay inside dest
                link = (target.parent / m.linkname).resolve()
                if dest not in link.parents and link != dest:
                    continue
        try:
            t.extractall(dest, filter="data")  # py3.12+
        except TypeError:
            t.extractall(dest)


# --------------------------------------------------------------- misc

def slugify(s: str, fallback: str = "instance") -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip().lower()).strip("-")
    return s[:40] or fallback


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


# ----------------------------------------------------------- task tracking

class Task:
    def __init__(self, title: str, kind: str = "generic"):
        self.id = uuid.uuid4().hex[:10]
        self.title = title
        self.kind = kind
        self.status = "running"      # running | done | error
        self.message = "Starting…"
        self.progress = 0.0           # 0..1 overall
        self.error: str | None = None
        self.result: Any = None
        self.started = time.time()
        self.finished: float | None = None
        self._stage_lo = 0.0
        self._stage_hi = 1.0

    def stage(self, message: str, lo: float, hi: float) -> None:
        self._stage_lo, self._stage_hi = lo, hi
        self.message = message
        self.progress = lo

    def update(self, message: str | None = None, sub: float | None = None) -> None:
        if message is not None:
            self.message = message
        if sub is not None:
            self.progress = self._stage_lo + (self._stage_hi - self._stage_lo) * max(0.0, min(1.0, sub))

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "kind": self.kind, "status": self.status,
                "message": self.message, "progress": round(self.progress, 4), "error": self.error,
                "result": self.result if isinstance(self.result, (dict, list, str, int, float, type(None))) else None}


class TaskManager:
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def run(self, title: str, fn: Callable[[Task], Any], kind: str = "generic") -> Task:
        task = Task(title, kind)
        with self._lock:
            self._tasks[task.id] = task

        def runner():
            try:
                task.result = fn(task)
                task.progress = 1.0
                task.status = "done"
                task.message = "Done"
            except NovaError as e:
                task.status, task.error, task.message = "error", str(e), "Failed"
            except Exception as e:  # unexpected
                import traceback
                traceback.print_exc()
                task.status, task.error, task.message = "error", f"{type(e).__name__}: {e}", "Failed"
            finally:
                task.finished = time.time()

        threading.Thread(target=runner, daemon=True, name=f"task-{task.id}").start()
        return task

    def list(self) -> list[dict]:
        now = time.time()
        with self._lock:
            for tid in [t for t, k in self._tasks.items() if k.finished and now - k.finished > 600]:
                del self._tasks[tid]
            return [t.to_dict() for t in sorted(self._tasks.values(), key=lambda t: t.started)]

    def dismiss(self, tid: str) -> None:
        with self._lock:
            t = self._tasks.get(tid)
            if t and t.status != "running":
                del self._tasks[tid]

    def get(self, tid: str) -> Task | None:
        return self._tasks.get(tid)
