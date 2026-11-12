"""Local HTTP server: serves the UI and a small JSON API.

Security model: the server only binds to 127.0.0.1, every API call needs the
per-run secret token, and the Host header is validated (blocks DNS rebinding).
"""
from __future__ import annotations

import hmac
import json
import mimetypes
import os
import re
import secrets
import shutil
import sys
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import (__version__, accounts, instances, java as javamod, launch, loaders, mods, msauth, optimize, paths,
               settings as settingsmod, versions)
from .util import NovaError, TaskManager, human_size, dir_size, slugify

MAX_UPLOAD = 2 * 1024 * 1024 * 1024
OPEN_SUBDIRS = {"", "mods", "resourcepacks", "shaderpacks", "screenshots", "saves", "config", "logs", "crash-reports"}


class App:
    def __init__(self, token: str | None = None):
        self.token = token or secrets.token_urlsafe(24)
        self.tasks = TaskManager()
        self.games = launch.Registry()
        self.last_ping = time.time()
        self.seen_ping = False
        self.bye_at = 0.0          # when the window last said it was closing
        self.port = 0
        self.ms_flows: dict[str, threading.Event] = {}
        self.httpd: ThreadingHTTPServer | None = None

    # ------------------------------------------------------------- state
    def instance_view(self, inst: dict) -> dict:
        v = dict(inst)
        g = self.games.get(inst["id"])
        v["running"] = bool(self.games.running(inst["id"]))
        v["last_status"] = g.status if g else None
        mdir = instances.game_dir(inst["id"]) / "mods"
        v["mod_count"] = sum(1 for f in mdir.glob("*.jar")) if mdir.exists() else 0
        return v

    def state(self) -> dict:
        accs = accounts.load()
        return {
            "version": __version__,
            "settings": settingsmod.load(),
            "themes": settingsmod.THEME_PRESETS,
            "surfaces": settingsmod.SURFACES,
            "instances": [self.instance_view(i) for i in instances.list_all()],
            "accounts": [accounts.public(a) for a in accs["accounts"]], "selected_account": accs.get("selected"),
            "system": optimize.system_info(),
            "presets": optimize.PRESETS,
            "options_profiles": {k: {"name": v["name"], "desc": v["desc"]} for k, v in optimize.OPTIONS_PROFILES.items()},
            "loaders": loaders.LOADERS,
            "tasks": self.tasks.list(),
            "data_dir": str(paths.data_dir()),
        }


# --------------------------------------------------------------- handlers

def _inst(iid: str) -> dict:
    return instances.get(iid)


def build_routes(app: App):
    R: list[tuple[str, re.Pattern, callable]] = []

    def route(method: str, pattern: str):
        rx = re.compile("^" + re.sub(r"<(\w+)>", r"(?P<\1>[^/]+)", pattern) + "$")

        def deco(fn):
            R.append((method, rx, fn))
            return fn
        return deco

    # ---- global
    @route("GET", "/api/state")
    def _state(ctx):
        return app.state()

    @route("GET", "/api/ping")
    def _ping(ctx):
        app.last_ping = time.time()
        app.seen_ping = True
        return {"ok": True, "tasks": app.tasks.list(), "running": app.games.all_info()}

    @route("POST", "/api/bye")
    def _bye(ctx):
        # The window is closing (or reloading: the next ping cancels this).
        app.bye_at = time.time()
        return {"ok": True}

    @route("POST", "/api/settings")
    def _settings(ctx):
        return settingsmod.update(ctx.body)

    @route("GET", "/api/tasks")
    def _tasks(ctx):
        return {"tasks": app.tasks.list()}

    @route("POST", "/api/tasks/<tid>/dismiss")
    def _dismiss(ctx, tid):
        app.tasks.dismiss(tid)
        return {"ok": True}

    @route("GET", "/api/java")
    def _java(ctx):
        return {"javas": javamod.detect()}

    @route("POST", "/api/quit")
    def _quit(ctx):
        threading.Timer(0.3, lambda: os._exit(0)).start()
        return {"ok": True}

    # ---- version data
    @route("GET", "/api/versions")
    def _versions(ctx):
        kinds = set((ctx.q("types") or "release").split(","))
        return {"versions": versions.list_versions(kinds), "latest": versions.latest()}

    @route("GET", "/api/loader-versions")
    def _loader_versions(ctx):
        loader, mc = ctx.q("loader"), ctx.q("mc")
        if not mc:
            raise NovaError("Missing Minecraft version.")
        return {"versions": loaders.available_loader_versions(loader, mc)}

    @route("GET", "/api/supported")
    def _supported(ctx):
        s = loaders.supported_games(ctx.q("loader"))
        return {"games": sorted(s) if s is not None else None}

    @route("GET", "/api/installed-versions")
    def _installed_versions(ctx):
        return {"versions": loaders.list_installed_versions()}

    # ---- instances
    @route("POST", "/api/instances")
    def _create(ctx):
        body = dict(ctx.body)
        auto = body.pop("memory_auto", False)
        if auto:
            rec = optimize.recommend_memory(body.get("loader", "vanilla"), 0)
            body.setdefault("memory_max", rec["max"])
            body.setdefault("memory_min", rec["min"])
        return app.instance_view(instances.create(body))

    @route("GET", "/api/instances/<iid>")
    def _get(ctx, iid):
        return app.instance_view(_inst(iid))

    @route("POST", "/api/instances/<iid>")
    def _update(ctx, iid):
        return app.instance_view(instances.update(iid, ctx.body))

    @route("DELETE", "/api/instances/<iid>")
    def _delete(ctx, iid):
        if app.games.running(iid):
            raise NovaError("Stop the game before deleting this instance.")
        instances.delete(iid)
        return {"ok": True}

    @route("POST", "/api/instances/<iid>/duplicate")
    def _dup(ctx, iid):
        return app.instance_view(instances.duplicate(iid, ctx.body.get("name")))

    @route("POST", "/api/instances/<iid>/launch")
    def _launch(ctx, iid):
        inst = _inst(iid)
        if app.games.running(iid):
            raise NovaError("This instance is already running.")
        t = app.tasks.run(f"Launching {inst['name']}", lambda task: app.games.launch(inst, task), kind="launch")
        return {"task": t.id}

    @route("POST", "/api/instances/<iid>/kill")
    def _kill(ctx, iid):
        instances.check_id(iid)
        app.games.kill(iid)
        return {"ok": True}

    @route("GET", "/api/instances/<iid>/logs")
    def _logs(ctx, iid):
        instances.check_id(iid)
        g = app.games.get(iid)
        if not g:
            return {"lines": [], "next": 0, "status": "none", "exit_code": None}
        return g.logs_since(int(ctx.q("since") or 0))

    @route("POST", "/api/instances/<iid>/open-folder")
    def _open(ctx, iid):
        instances.check_id(iid)
        sub = ctx.body.get("sub", "")
        if sub not in OPEN_SUBDIRS:
            raise NovaError("Not allowed.")
        paths.open_in_file_manager(instances.game_dir(iid) / sub if sub else instances.game_dir(iid))
        return {"ok": True}

    @route("POST", "/api/instances/<iid>/export")
    def _export(ctx, iid):
        inst = _inst(iid)
        out = paths.sub("exports") / f"{slugify(inst['name'])}.novapack"
        instances.export_pack(iid, out, bool(ctx.body.get("include_saves")))
        return {"path": str(out), "size": human_size(out.stat().st_size)}

    @route("POST", "/api/instances/<iid>/optifine-upload")
    def _optifine_upload(ctx, iid):
        _inst(iid)
        name = Path(ctx.header("X-Filename") or "OptiFine.jar").name
        if not name.lower().endswith(".jar"):
            raise NovaError("That doesn't look like a .jar file.")
        dest = instances.instance_dir(iid) / "optifine" / name
        ctx.save_upload(dest)
        return app.instance_view(instances.update(iid, {"optifine_jar": str(dest)}))

    @route("POST", "/api/import-upload")
    def _import(ctx):
        name = Path(ctx.header("X-Filename") or "pack.zip").name
        dest = paths.downloads_dir() / ("import-" + name)
        ctx.save_upload(dest)

        def work(task):
            try:
                task.update("Importing pack…")
                inst = instances.import_pack(dest)
                return {"instance": inst["id"]}
            finally:
                dest.unlink(missing_ok=True)
        return {"task": app.tasks.run(f"Importing {name}", work).id}

    # ---- mods
    @route("GET", "/api/instances/<iid>/mods")
    def _mods(ctx, iid):
        return {"items": mods.list_installed(_inst(iid), ctx.q("type") or "mod")}

    @route("POST", "/api/instances/<iid>/mods/toggle")
    def _toggle(ctx, iid):
        return {"enabled": mods.toggle(_inst(iid), ctx.body.get("type", "mod"), ctx.body.get("file", ""))}

    @route("POST", "/api/instances/<iid>/mods/remove")
    def _remove(ctx, iid):
        mods.remove(_inst(iid), ctx.body.get("type", "mod"), ctx.body.get("file", ""))
        return {"ok": True}

    @route("POST", "/api/instances/<iid>/mods/install")
    def _install(ctx, iid):
        inst = _inst(iid)
        project, ptype = str(ctx.body.get("project", "")), ctx.body.get("type", "mod")
        if not project:
            raise NovaError("No project given.")
        t = app.tasks.run(f"Installing {ctx.body.get('title') or project}",
                          lambda task: {"installed": mods.install_project(inst, project, ptype, task)}, kind="install")
        return {"task": t.id}

    @route("GET", "/api/instances/<iid>/mods/updates")
    def _updates(ctx, iid):
        return {"updates": mods.check_updates(_inst(iid))}

    @route("POST", "/api/instances/<iid>/mods/update-all")
    def _update_all(ctx, iid):
        inst = _inst(iid)
        t = app.tasks.run(f"Updating mods in {inst['name']}", lambda task: {"updated": mods.update_all(inst, task)})
        return {"task": t.id}

    @route("GET", "/api/modrinth/search")
    def _search(ctx):
        return mods.search(ctx.q("q") or "", ctx.q("mc") or "", ctx.q("loader") or "", ctx.q("type") or "mod",
                           ctx.q("sort") or "relevance", int(ctx.q("offset") or 0))

    # ---- optimization
    @route("GET", "/api/instances/<iid>/optimization")
    def _opt(ctx, iid):
        inst = _inst(iid)
        gd = instances.game_dir(iid)
        installed = mods.list_installed(inst, "mod")
        enabled = [m for m in installed if m["enabled"]]
        have = {m["slug"] for m in installed if m["slug"]}
        javas = javamod.detect()
        jm = None
        if inst.get("java_path"):
            jm = javamod.java_major(inst["java_path"]) if Path(inst["java_path"]).exists() else None
        if not jm:
            jm = javas[-1]["major"] if javas else 21
        pack = [dict(p, installed=p["slug"] in have) for p in mods.optimization_pack(inst["loader"])]
        return {
            "pack": pack, "recommend": optimize.recommend_memory(inst["loader"], len(enabled)),
            "jvm_preview": optimize.build_jvm_args(inst, jm, settingsmod.load().get("global_jvm_args", "")),
            "java_major_assumed": jm, "cleanup": optimize.cleanup_report(gd),
            "mod_count": len(enabled), "game_dir_size": human_size(dir_size(gd)),
            "options": {k: v for k, v in optimize.read_options(gd / "options.txt").items()
                        if k in ("renderDistance", "simulationDistance", "maxFps", "enableVsync", "graphicsMode",
                                 "fancyGraphics", "particles")},
        }

    @route("POST", "/api/instances/<iid>/optimization/install-pack")
    def _install_pack(ctx, iid):
        inst = _inst(iid)
        slugs = [str(s) for s in ctx.body.get("slugs", [])]
        t = app.tasks.run(f"Optimizing {inst['name']}", lambda task: mods.install_optimization_pack(inst, slugs, task),
                          kind="install")
        return {"task": t.id}

    @route("POST", "/api/instances/<iid>/options-profile")
    def _options_profile(ctx, iid):
        _inst(iid)
        try:
            changed = optimize.apply_options_profile(instances.game_dir(iid), ctx.body.get("profile", ""))
        except ValueError as e:
            raise NovaError(str(e))
        return {"changed": changed}

    @route("POST", "/api/instances/<iid>/cleanup")
    def _cleanup(ctx, iid):
        _inst(iid)
        freed = optimize.cleanup(instances.game_dir(iid), [str(k) for k in ctx.body.get("keys", [])])
        return {"freed": human_size(freed)}

    @route("POST", "/api/preview-jvm")
    def _preview(ctx):
        inst = dict(instances.DEFAULTS)
        inst.update(instances._clean_fields(ctx.body))
        jm = int(ctx.body.get("java_major") or 21)
        return {"args": optimize.build_jvm_args(inst, jm, settingsmod.load().get("global_jvm_args", ""))}

    # ---- accounts
    @route("POST", "/api/accounts")
    def _acc_add(ctx):
        return accounts.add_offline(str(ctx.body.get("username", "")))

    @route("POST", "/api/accounts/microsoft/start")
    def _ms_start(ctx):
        cid = settingsmod.load().get("ms_client_id", "").strip()
        if not cid:
            raise NovaError("Add your Microsoft app ID first.")
        flow = msauth.start_device_flow(cid)
        fid, cancel = secrets.token_hex(5), threading.Event()
        app.ms_flows[fid] = cancel

        def work(task):
            try:
                task.update("Waiting for you to approve the code…")
                acc = msauth.finish_device_flow(cid, flow, cancel, task)
                return {"account": acc["id"], "username": acc["username"]}
            finally:
                app.ms_flows.pop(fid, None)
        t = app.tasks.run("Microsoft sign-in", work)
        return {"task": t.id, "flow": fid, "user_code": flow["user_code"],
                "verification_uri": flow["verification_uri"], "expires_in": flow["expires_in"]}

    @route("DELETE", "/api/accounts/microsoft/<fid>")
    def _ms_cancel(ctx, fid):
        ev = app.ms_flows.get(fid)
        if ev:
            ev.set()
        return {"ok": True}

    @route("DELETE", "/api/accounts/<aid>")
    def _acc_del(ctx, aid):
        accounts.remove(aid)
        return {"ok": True}

    @route("POST", "/api/accounts/<aid>/select")
    def _acc_sel(ctx, aid):
        accounts.select(aid)
        return {"ok": True}

    return R


# ----------------------------------------------------------- HTTP plumbing

class Ctx:
    def __init__(self, handler: "Handler", query: dict, body: dict):
        self.h, self.query, self.body = handler, query, body

    def q(self, key: str) -> str:
        v = self.query.get(key)
        return v[0] if v else ""

    def header(self, key: str) -> str:
        return self.h.headers.get(key, "")

    def save_upload(self, dest: Path) -> None:
        n = int(self.h.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_UPLOAD:
            raise NovaError("Upload is empty or too large.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        left = n
        with open(tmp, "wb") as f:
            while left > 0:
                chunk = self.h.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        if left:
            tmp.unlink(missing_ok=True)
            raise NovaError("Upload was interrupted.")
        os.replace(tmp, dest)


def make_handler(app: App):
    routes = build_routes(app)
    allowed_hosts = None

    class Handler(BaseHTTPRequestHandler):
        server_version = "NovaLauncher"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # quiet
            if os.environ.get("NOVA_DEBUG"):
                sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        # -- helpers
        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").lower()
            return host in (f"127.0.0.1:{app.port}", f"localhost:{app.port}")

        def _send(self, code: int, body: bytes, ctype: str = "application/json", extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj):
            self._send(code, json.dumps(obj).encode("utf-8"))

        def _authed(self) -> bool:
            return hmac.compare_digest(self.headers.get("X-Nova-Token", ""), app.token)

        # -- dispatch
        def _handle(self, method: str):
            try:
                if not self._host_ok():
                    return self._json(403, {"error": "Bad host."})
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path
                query = urllib.parse.parse_qs(parsed.query)
                if method == "GET" and not path.startswith("/api/"):
                    return self._static(path, query)
                if not path.startswith("/api/"):
                    return self._json(404, {"error": "Not found."})
                if not self._authed():
                    return self._json(401, {"error": "Unauthorized."})
                is_upload = path.endswith("-upload")
                body: dict = {}
                if method in ("POST", "DELETE") and not is_upload:
                    n = int(self.headers.get("Content-Length") or 0)
                    if n > 5_000_000:
                        return self._json(413, {"error": "Request too large."})
                    raw = self.rfile.read(n) if n else b""
                    if raw:
                        try:
                            body = json.loads(raw.decode("utf-8"))
                        except ValueError:
                            return self._json(400, {"error": "Invalid JSON."})
                        if not isinstance(body, dict):
                            return self._json(400, {"error": "Expected a JSON object."})
                for m, rx, fn in routes:
                    if m != method:
                        continue
                    match = rx.match(path)
                    if match:
                        ctx = Ctx(self, query, body)
                        try:
                            result = fn(ctx, **match.groupdict())
                        except NovaError as e:
                            return self._json(400, {"error": str(e)})
                        return self._json(200, result)
                self._json(404, {"error": "Not found."})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                traceback.print_exc()
                try:
                    self._json(500, {"error": "Something went wrong inside Nova. Check the terminal for details."})
                except Exception:
                    pass

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def do_DELETE(self):
            self._handle("DELETE")

        # -- static files
        def _static(self, path: str, query: dict):
            ui = paths.ui_dir().resolve()
            if path in ("/", "/index.html"):
                t = (query.get("t") or [""])[0]
                if not hmac.compare_digest(t, app.token):
                    return self._send(403, b"Open Nova Launcher from the app window (this link needs its secret token).",
                                      "text/plain; charset=utf-8")
                html = (ui / "index.html").read_text(encoding="utf-8").replace("__NOVA_TOKEN__", app.token)
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8",
                                  {"Content-Security-Policy": "default-src 'self'; img-src 'self' https: data:; "
                                                              "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                                                              "connect-src 'self'; frame-ancestors 'none'"})
            rel = path.lstrip("/")
            if rel.startswith("static/"):
                rel = rel[len("static/"):]
                target = (ui / rel).resolve()
                if ui in target.parents and target.is_file():
                    ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                    if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
                        ctype += "; charset=utf-8" if "charset" not in ctype else ""
                    return self._send(200, target.read_bytes(), ctype)
            self._send(404, b"Not found", "text/plain")

    return Handler


# ------------------------------------------------------------------ run

def start_server(app: App, port: int = 0) -> ThreadingHTTPServer:
    handler = make_handler(app)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    httpd.daemon_threads = True
    app.port = httpd.server_address[1]
    app.httpd = httpd
    threading.Thread(target=httpd.serve_forever, daemon=True, name="http").start()
    return httpd
