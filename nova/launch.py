"""Preparing and launching the game, and tracking running processes."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from . import __version__, accounts, instances, java as javamod, loaders, msauth, optimize, paths, settings as settingsmod, versions
from .util import NovaError, Task, download_file

NO_WINDOW = 0x08000000 if paths.os_name() == "windows" else 0


# ------------------------------------------------------------ preparation

def _install_loader(inst: dict, task: Task | None) -> str:
    """Install the instance's loader if needed and return the version id."""
    loader, mc = inst["loader"], inst["mc_version"]
    if loader == "vanilla":
        return mc
    if loader == "custom":
        vid = inst.get("version_id")
        if not vid or not versions.version_json_path(vid).exists():
            raise NovaError("This instance uses a custom version that isn't installed. Edit the instance and pick one.")
        return vid
    if loader in ("fabric", "quilt"):
        lv = inst.get("loader_version")
        if not lv:
            options = loaders.fabric_like_versions(loader, mc)
            if not options:
                raise NovaError(f"{loader.title()} doesn't support Minecraft {mc} yet.")
            lv = next((o["version"] for o in options if o["stable"]), options[0]["version"])
        return loaders.install_fabric_like(loader, mc, lv, task)
    # installers need a java: use the one the vanilla version asks for
    vanilla = versions.resolve_version(mc)
    jpath, _ = javamod.ensure_java(vanilla, inst.get("java_path") or None,
                                   settingsmod.load().get("java_path") or None, task,
                                   settingsmod.load().get("auto_download_java", True))
    if loader == "forge":
        lv = inst.get("loader_version")
        if not lv:
            options = loaders.forge_versions(mc)
            if not options:
                raise NovaError(f"Forge doesn't support Minecraft {mc}.")
            lv = options[0]["version"]
        return loaders.install_forge(mc, lv, jpath, task)
    if loader == "neoforge":
        lv = inst.get("loader_version")
        if not lv:
            options = loaders.neoforge_versions(mc)
            if not options:
                raise NovaError(f"NeoForge doesn't support Minecraft {mc}.")
            lv = next((o["version"] for o in options if o["stable"]), options[0]["version"])
        return loaders.install_neoforge(lv, jpath, task)
    if loader == "optifine":
        if not inst.get("optifine_jar"):
            raise NovaError("Choose the OptiFine installer jar you downloaded from optifine.net.")
        return loaders.install_optifine(inst["optifine_jar"], mc, jpath, task)
    raise NovaError(f"Unknown loader: {loader}")


def ensure_ready(inst: dict, task: Task | None = None) -> dict:
    """Make everything available for launching. Returns {version, java, java_major}."""
    st = settingsmod.load()
    if task:
        task.stage("Preparing", 0.0, 0.02)
    vid = inst.get("version_id")
    if not vid or not versions.version_json_path(vid).exists():
        if task:
            task.stage(f"Installing {inst['loader'].title()}", 0.02, 0.2)
        vid = _install_loader(inst, task)
        inst = instances.update(inst["id"], {"version_id": vid})
    if task:
        task.stage("Downloading game files", 0.2, 0.9)
    sub = None
    if task:
        # reuse the task but remap prepare's 0..1 into 0.2..0.9
        sub = _SubTask(task, 0.2, 0.9)
    version = versions.prepare_version(vid, sub)  # type: ignore[arg-type]
    if task:
        task.stage("Preparing Java", 0.9, 0.95)
    jpath, jmajor = javamod.ensure_java(version, inst.get("java_path") or None, st.get("java_path") or None,
                                        task, st.get("auto_download_java", True))
    versions.extract_natives(version, versions.natives_dir_for(inst["id"]))
    log_arg = _ensure_logging(version)
    return {"version": version, "java": jpath, "java_major": jmajor, "log_arg": log_arg}


class _SubTask:
    """Remaps a Task's 0..1 stages into a window of the parent progress bar."""

    def __init__(self, parent: Task, lo: float, hi: float):
        self.p, self.lo, self.hi = parent, lo, hi

    def stage(self, message, lo, hi):
        span = self.hi - self.lo
        self.p.stage(message, self.lo + span * lo, self.lo + span * hi)

    def update(self, message=None, sub=None):
        self.p.update(message, sub)


def _ensure_logging(version: dict) -> str | None:
    """Mojang ships a log4j config that mitigates Log4Shell on 1.7-1.18."""
    lg = (version.get("logging") or {}).get("client")
    if not lg or not lg.get("file"):
        return None
    f = lg["file"]
    dest = paths.assets_dir() / "log_configs" / f["id"]
    try:
        download_file(f["url"], dest, sha1=f.get("sha1"), size=f.get("size"))
    except NovaError:
        return None
    return lg.get("argument", "").replace("${path}", str(dest))


# ------------------------------------------------------- command building

def _subst(s: str, variables: dict) -> str:
    return re.sub(r"\$\{([a-zA-Z0-9_]+)\}", lambda m: str(variables.get(m.group(1), m.group(0))), s)


def _expand(args: list, variables: dict, features: dict) -> list[str]:
    out: list[str] = []
    for a in args:
        if isinstance(a, str):
            out.append(_subst(a, variables))
        elif isinstance(a, dict):
            if not versions.rules_allow(a.get("rules"), features):
                continue
            v = a.get("value", [])
            for item in ([v] if isinstance(v, str) else v):
                out.append(_subst(item, variables))
    return out


def build_command(inst: dict, version: dict, account: dict, java_path: str, java_major: int,
                  log_arg: str | None = None) -> dict:
    st = settingsmod.load()
    gdir = instances.game_dir(inst["id"])
    gdir.mkdir(parents=True, exist_ok=True)
    sep = ";" if paths.os_name() == "windows" else ":"
    cp = sep.join(str(p) for p in versions.classpath_entries(version))
    natives = versions.natives_dir_for(inst["id"])
    assets_root = versions.assets_game_dir(version, gdir)
    features = {"has_custom_resolution": not inst.get("fullscreen", False), "is_demo_user": False,
                "has_quick_plays_support": False, "is_quick_play_singleplayer": False,
                "is_quick_play_multiplayer": False, "is_quick_play_realms": False}
    variables = {
        "auth_player_name": account["username"], "version_name": version["id"],
        "game_directory": str(gdir), "assets_root": str(paths.assets_dir()),
        "assets_index_name": version.get("assetIndex", {}).get("id", version.get("assets", "legacy")),
        "auth_uuid": account["uuid"].replace("-", ""),
        "auth_access_token": account.get("mc_token") or "0", "auth_session": account.get("mc_token") or "0",
        "clientid": "0", "auth_xuid": account.get("xuid") or "0",
        "user_type": "msa" if account.get("type") == "microsoft" else "legacy", "version_type": "Nova",
        "natives_directory": str(natives), "launcher_name": "NovaLauncher", "launcher_version": __version__,
        "classpath": cp, "classpath_separator": sep, "library_directory": str(paths.libraries_dir()),
        "user_properties": "{}", "resolution_width": inst.get("width", 1280),
        "resolution_height": inst.get("height", 720), "game_assets": str(assets_root),
    }
    if "arguments" in version:
        jvm_ver = _expand(version["arguments"].get("jvm", []), variables, features)
        game = _expand(version["arguments"].get("game", []), variables, features)
    else:
        jvm_ver = ["-Djava.library.path=" + str(natives), "-cp", cp]
        game = _expand(shlex.split(version.get("minecraftArguments", ""), posix=True), variables, features)
        if not inst.get("fullscreen"):
            game += ["--width", str(inst["width"]), "--height", str(inst["height"])]
    if not any(a in ("-cp", "-classpath", "--class-path") for a in jvm_ver):
        jvm_ver += ["-cp", cp]
    if not any(a.startswith("-Djava.library.path") for a in jvm_ver):
        jvm_ver.append("-Djava.library.path=" + str(natives))
    if inst.get("fullscreen") and "--fullscreen" not in game:
        game.append("--fullscreen")
    if inst.get("game_args"):
        game += shlex.split(inst["game_args"], posix=(paths.os_name() != "windows"))

    tuning = optimize.build_jvm_args(inst, java_major, st.get("global_jvm_args", ""))
    extra = ["-Dminecraft.launcher.brand=NovaLauncher", f"-Dminecraft.launcher.version={__version__}"]
    if log_arg:
        extra.append(log_arg)
    elif versions.mc_minor(version.get("_root_id", ""))[0] and 7 <= versions.mc_minor(version["_root_id"])[0] <= 18:
        extra.append("-Dlog4j2.formatMsgNoLookups=true")
    cmd = [java_path] + tuning + extra + jvm_ver + [version["mainClass"]] + game
    env = dict(os.environ)
    env.update(inst.get("env") or {})
    return {"cmd": cmd, "cwd": str(gdir), "env": env}


# ----------------------------------------------------------- running games

class GameProcess:
    def __init__(self, inst: dict, plan: dict):
        self.inst_id = inst["id"]
        self.name = inst["name"]
        self.plan = plan
        self.post_exit = inst.get("post_exit", "")
        self.log: deque = deque(maxlen=10000)
        self.seq = 0
        self.lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.status = "starting"     # starting | running | exited | crashed
        self.exit_code: int | None = None
        self.started = time.time()
        self.ended: float | None = None

    def add(self, line: str) -> None:
        with self.lock:
            self.seq += 1
            self.log.append((self.seq, line.rstrip("\r\n")))

    def start(self) -> None:
        self.add(f"[Nova] Launching: {' '.join(shlex.quote(c) for c in self.plan['cmd'][:1])} … ({len(self.plan['cmd'])} arguments)")
        self.proc = subprocess.Popen(self.plan["cmd"], cwd=self.plan["cwd"], env=self.plan["env"],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     encoding="utf-8", errors="replace", bufsize=1,
                                     creationflags=NO_WINDOW)
        self.status = "running"
        threading.Thread(target=self._pump, daemon=True, name=f"game-{self.inst_id}").start()

    def _pump(self) -> None:
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            self.add(line)
        code = self.proc.wait()
        self.exit_code = code
        self.ended = time.time()
        self.status = "exited" if code == 0 else "crashed"
        self.add(f"[Nova] Game process ended with exit code {code}.")
        instances.record_play(self.inst_id, int(self.ended - self.started))
        if self.post_exit.strip():
            try:
                subprocess.Popen(self.post_exit, shell=True, cwd=self.plan["cwd"], env=self.plan["env"],
                                 creationflags=NO_WINDOW)
            except OSError as e:
                self.add(f"[Nova] Post-exit command failed: {e}")

    def kill(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.add("[Nova] Stopping game…")
            self.proc.terminate()
            threading.Timer(5, lambda: self.proc and self.proc.poll() is None and self.proc.kill()).start()

    def logs_since(self, since: int) -> dict:
        with self.lock:
            lines = [(s, l) for s, l in self.log if s > since]
            return {"lines": [l for _s, l in lines], "next": lines[-1][0] if lines else since,
                    "status": self.status, "exit_code": self.exit_code}

    def info(self) -> dict:
        return {"instance": self.inst_id, "status": self.status, "exit_code": self.exit_code,
                "started": self.started, "pid": self.proc.pid if self.proc else None}


class Registry:
    def __init__(self):
        self.games: dict[str, GameProcess] = {}
        self.lock = threading.Lock()

    def running(self, inst_id: str) -> GameProcess | None:
        g = self.games.get(inst_id)
        return g if g and g.status in ("starting", "running") else None

    def get(self, inst_id: str) -> GameProcess | None:
        return self.games.get(inst_id)

    def launch(self, inst: dict, task: Task) -> dict:
        if self.running(inst["id"]):
            raise NovaError("This instance is already running.")
        acc = accounts.selected()
        if not acc:
            raise NovaError("Create a player profile first (Accounts tab).")
        if acc.get("type") == "microsoft":
            task.update("Checking your Microsoft sign-in…")
        acc = msauth.ensure_fresh(acc, settingsmod.load().get("ms_client_id", ""))
        prep = ensure_ready(inst, task)
        inst = instances.get(inst["id"])
        task.stage("Starting game", 0.95, 1.0)
        plan = build_command(inst, prep["version"], acc, prep["java"], prep["java_major"], prep["log_arg"])
        if inst.get("pre_launch", "").strip():
            task.update("Running pre-launch command…")
            r = subprocess.run(inst["pre_launch"], shell=True, cwd=plan["cwd"], env=plan["env"],
                               capture_output=True, text=True, timeout=300, creationflags=NO_WINDOW)
            if r.returncode != 0:
                raise NovaError("Pre-launch command failed:\n" + (r.stderr or r.stdout)[-400:])
        if inst.get("options_profile"):
            try:
                optimize.apply_options_profile(Path(plan["cwd"]), inst["options_profile"])
            except ValueError:
                pass
        g = GameProcess(inst, plan)
        with self.lock:
            self.games[inst["id"]] = g
        g.start()
        return g.info()

    def kill(self, inst_id: str) -> None:
        g = self.games.get(inst_id)
        if g:
            g.kill()

    def kill_all(self) -> None:
        for g in list(self.games.values()):
            g.kill()

    def all_info(self) -> list[dict]:
        return [g.info() for g in self.games.values()]
