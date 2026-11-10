"""A local fake of Mojang / Fabric / Forge / NeoForge / Modrinth so the whole
launcher pipeline can be exercised offline, including spawning a real JVM."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

JAVA_SRC = {
    "FakeMain.java": r'''
public class FakeMain {
    public static void main(String[] a) {
        System.out.println("FAKE_MC_START");
        for (String s : a) System.out.println("ARG " + s);
        System.out.println("PROP " + System.getProperty("java.library.path"));
        System.out.println("XMX " + Runtime.getRuntime().maxMemory());
        if (System.getenv("NOVA_TEST_ENV") != null) System.out.println("ENV " + System.getenv("NOVA_TEST_ENV"));
        System.err.println("FAKE_STDERR_LINE");
        System.out.println("FAKE_MC_STOP");
    }
}''',
    # behaves like Forge's installer: --installClient <dir> -> writes a version folder
    "FakeInstaller.java": r'''
import java.io.*;
import java.nio.file.*;
public class FakeInstaller {
    public static void main(String[] a) throws Exception {
        String dir = null;
        for (int i = 0; i < a.length; i++) if (a[i].equals("--installClient")) dir = a[i + 1];
        if (dir == null) { System.err.println("no dir"); System.exit(3); }
        if (!new File(dir, "launcher_profiles.json").exists()) { System.err.println("launcher_profiles.json missing"); System.exit(4); }
        String id = System.getProperty("fake.id", "1.20.1-forge-47.2.0");
        Path p = Paths.get(dir, "versions", id);
        Files.createDirectories(p);
        String json = "{\"id\":\"" + id + "\",\"inheritsFrom\":\"" + System.getProperty("fake.parent", "1.20.1")
            + "\",\"type\":\"release\",\"mainClass\":\"FakeMain\",\"libraries\":[],\"arguments\":{\"game\":[\"--fake-loader\"],\"jvm\":[\"-Dfake.loader=1\"]}}";
        Files.write(p.resolve(id + ".json"), json.getBytes("UTF-8"));
        System.out.println("installed " + id);
    }
}''',
    "optifine/Installer.java": r'''
package optifine;
import java.io.*;
import java.nio.file.*;
public class Installer {
    public static void doInstall(File dir) throws Exception {
        String id = "1.20.1-OptiFine_HD_U_I6";
        Path p = dir.toPath().resolve("versions").resolve(id);
        Files.createDirectories(p);
        String json = "{\"id\":\"" + id + "\",\"inheritsFrom\":\"1.20.1\",\"type\":\"release\",\"mainClass\":\"FakeMain\",\"libraries\":[]}";
        Files.write(p.resolve(id + ".json"), json.getBytes("UTF-8"));
    }
}''',
}


def sha1(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def sha512(b: bytes) -> str:
    return hashlib.sha512(b).hexdigest()


def make_zip(files: dict[str, bytes]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items():
            z.writestr(k, v)
    return bio.getvalue()


def java_major() -> int:
    out = subprocess.run(["java", "-version"], capture_output=True, text=True).stderr
    m = re.search(r'version "(\d+)', out)
    return int(m.group(1)) if m else 17


class Fake:
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="nova-fake-"))
        self.routes: dict[str, tuple] = {}
        self.requests: list[tuple[str, str]] = []
        self.posts: list[tuple[str, dict]] = []
        self._compile()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self._build_routes()
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()

    # ------------------------------------------------------------ build
    def _compile(self):
        src = self.tmp / "src"
        out = self.tmp / "classes"
        for name, code in JAVA_SRC.items():
            p = src / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(code)
        out.mkdir()
        files = [str(p) for p in src.rglob("*.java")]
        r = subprocess.run(["javac", "--release", "8", "-d", str(out)] + files, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("javac failed: " + r.stderr)
        self.classes = {str(p.relative_to(out)).replace(os.sep, "/"): p.read_bytes() for p in out.rglob("*.class")}

    def add(self, path: str, body: bytes | str | dict | list, ctype: str | None = None, code: int = 200):
        if isinstance(body, (dict, list)):
            body, ctype = json.dumps(body).encode(), "application/json"
        elif isinstance(body, str):
            body = body.encode()
        self.routes[path] = (code, body, ctype or "application/octet-stream")

    def _build_routes(self):
        b = self.base
        jm = java_major()
        # ---- client jar contains FakeMain
        self.client_jar = make_zip({"FakeMain.class": self.classes["FakeMain.class"]})
        self.add("/dl/client-1.20.1.jar", self.client_jar)
        self.add("/dl/client-1.21.4.jar", self.client_jar)

        lib_jar = make_zip({"hello.txt": b"lib"})
        native_jar = make_zip({"libfake.so": b"\x7fELF", "fake.dll": b"MZ", "META-INF/MANIFEST.MF": b"x"})
        self.add("/libs/com/example/lib/1.0/lib-1.0.jar", lib_jar)
        self.add("/libs/com/example/nat/1.0/nat-1.0-natives-linux.jar", native_jar)
        self.add("/libs/com/example/nat/1.0/nat-1.0-natives-windows.jar", native_jar)
        self.add("/libs/com/example/nat/1.0/nat-1.0-natives-osx.jar", native_jar)
        self.add("/maven/net/fake/loader/0.15.0/loader-0.15.0.jar", lib_jar)

        # ---- assets
        objs = {"icons/a.png": b"AAAA", "sounds/b.ogg": b"BBBBBB"}
        index = {"objects": {}}
        for name, data in objs.items():
            h = sha1(data)
            index["objects"][name] = {"hash": h, "size": len(data)}
            self.add(f"/assets/{h[:2]}/{h}", data)
        idx_bytes = json.dumps(index).encode()
        self.add("/dl/assets-index-12.json", idx_bytes, "application/json")

        log_cfg = b"<Configuration/>"
        self.add("/dl/client-log4j2.xml", log_cfg)

        def vjson(vid, jar):
            client = self.client_jar
            return {
                "id": vid, "type": "release", "mainClass": "FakeMain", "assets": "12",
                "assetIndex": {"id": "12", "url": b + "/dl/assets-index-12.json", "sha1": sha1(idx_bytes), "size": len(idx_bytes)},
                "downloads": {"client": {"url": b + jar, "sha1": sha1(client), "size": len(client)}},
                "javaVersion": {"component": "x", "majorVersion": jm},
                "logging": {"client": {"argument": "-Dlog4j.configurationFile=${path}",
                                       "file": {"id": "client-1.12.xml", "sha1": sha1(log_cfg), "size": len(log_cfg),
                                                "url": b + "/dl/client-log4j2.xml"}}},
                "libraries": [
                    {"name": "com.example:lib:1.0", "downloads": {"artifact": {
                        "path": "com/example/lib/1.0/lib-1.0.jar", "url": b + "/libs/com/example/lib/1.0/lib-1.0.jar",
                        "sha1": sha1(lib_jar), "size": len(lib_jar)}}},
                    {"name": "com.example:nat:1.0",
                     "natives": {"linux": "natives-linux", "windows": "natives-windows", "osx": "natives-osx"},
                     "extract": {"exclude": ["META-INF/"]},
                     "downloads": {"classifiers": {
                         k: {"path": f"com/example/nat/1.0/nat-1.0-{k}.jar",
                             "url": b + f"/libs/com/example/nat/1.0/nat-1.0-{k}.jar",
                             "sha1": sha1(native_jar), "size": len(native_jar)}
                         for k in ("natives-linux", "natives-windows", "natives-osx")}}},
                    {"name": "com.example:winonly:1.0", "rules": [{"action": "allow", "os": {"name": "windows"}}],
                     "downloads": {"artifact": {"path": "x/winonly.jar", "url": b + "/does-not-exist.jar"}}},
                ],
                "arguments": {
                    "game": ["--username", "${auth_player_name}", "--version", "${version_name}",
                             "--gameDir", "${game_directory}", "--assetsDir", "${assets_root}",
                             "--assetIndex", "${assets_index_name}", "--uuid", "${auth_uuid}",
                             "--accessToken", "${auth_access_token}", "--userType", "${user_type}",
                             {"rules": [{"action": "allow", "features": {"has_custom_resolution": True}}],
                              "value": ["--width", "${resolution_width}", "--height", "${resolution_height}"]},
                             {"rules": [{"action": "allow", "features": {"is_demo_user": True}}], "value": "--demo"}],
                    "jvm": [{"rules": [{"action": "allow", "os": {"name": "osx"}}], "value": ["-XstartOnFirstThread"]},
                            "-Djava.library.path=${natives_directory}",
                            "-Dminecraft.launcher.brand=${launcher_name}",
                            "-cp", "${classpath}"],
                },
            }

        v1201, v1214 = vjson("1.20.1", "/dl/client-1.20.1.jar"), vjson("1.21.4", "/dl/client-1.21.4.jar")
        self.add("/mojang/1.21.1.json", vjson("1.21.1", "/dl/client-1.21.4.jar"))
        self.add("/mojang/1.20.1.json", v1201)
        self.add("/mojang/1.21.4.json", v1214)
        # legacy-format version (minecraftArguments, old natives)
        old = vjson("1.7.10", "/dl/client-1.20.1.jar")
        old.pop("arguments")
        old["minecraftArguments"] = "--username ${auth_player_name} --version ${version_name} --gameDir ${game_directory} --assetsDir ${assets_root} --uuid ${auth_uuid} --accessToken ${auth_access_token}"
        old["javaVersion"] = {"majorVersion": jm}
        self.add("/mojang/1.7.10.json", old)
        self.add("/mojang/manifest.json", {
            "latest": {"release": "1.21.4", "snapshot": "25w01a"},
            "versions": [
                {"id": "25w01a", "type": "snapshot", "url": b + "/mojang/1.21.4.json", "releaseTime": "2026-01-01T00:00:00+00:00"},
                {"id": "1.21.4", "type": "release", "url": b + "/mojang/1.21.4.json", "releaseTime": "2024-12-03T00:00:00+00:00"},
                {"id": "1.21.1", "type": "release", "url": b + "/mojang/1.21.1.json", "releaseTime": "2024-08-08T00:00:00+00:00"},
                {"id": "1.20.1", "type": "release", "url": b + "/mojang/1.20.1.json", "releaseTime": "2023-06-12T00:00:00+00:00"},
                {"id": "1.7.10", "type": "release", "url": b + "/mojang/1.7.10.json", "releaseTime": "2014-06-26T00:00:00+00:00"},
            ]})

        # ---- fabric / quilt meta
        for name in ("fabric", "quilt"):
            self.add(f"/{name}/versions/game", [{"version": "1.21.4"}, {"version": "1.20.1"}])
            for mc in ("1.20.1", "1.21.4"):
                self.add(f"/{name}/versions/loader/{mc}", [
                    {"loader": {"version": "0.16.0-beta.1", "stable": False}},
                    {"loader": {"version": "0.15.0", "stable": True}}])
                for lv in ("0.15.0", "0.16.0-beta.1"):
                    pid = f"{name}-loader-{lv}-{mc}"
                    self.add(f"/{name}/versions/loader/{mc}/{lv}/profile/json", {
                        "id": pid, "inheritsFrom": mc, "type": "release",
                        "mainClass": "FakeMain",
                        "arguments": {"game": [], "jvm": ["-DFabricMcEmu= net.minecraft.client.main.Main "]},
                        "libraries": [{"name": "net.fake:loader:0.15.0", "url": b + "/maven/"}]})

        # ---- forge / neoforge
        self.add("/forge/net/minecraftforge/forge/maven-metadata.xml",
                 "<metadata><versioning><versions><version>1.20.1-47.1.0</version><version>1.20.1-47.2.0</version>"
                 "<version>1.21.4-54.0.1</version></versions></versioning></metadata>", "application/xml")
        forge_installer = make_zip({"FakeInstaller.class": self.classes["FakeInstaller.class"],
                                    "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\nMain-Class: FakeInstaller\n\n"})
        self.add("/forge/net/minecraftforge/forge/1.20.1-47.2.0/forge-1.20.1-47.2.0-installer.jar", forge_installer)
        self.add("/neoforge-api", {"versions": ["20.4.1", "21.1.5-beta", "21.1.6", "21.4.2"]})
        self.add("/neoforge/net/neoforged/neoforge/21.1.6/neoforge-21.1.6-installer.jar", forge_installer)

        # ---- optifine installer (user supplied) available as bytes for tests
        self.optifine_jar = make_zip({"optifine/Installer.class": self.classes["optifine/Installer.class"]})

        # ---- modrinth
        self._modrinth()

    def _modrinth(self):
        b = self.base

        def proj(slug, title, deps=None):
            return {"id": f"id-{slug}", "slug": slug, "title": title, "icon_url": f"{b}/icon/{slug}.png"}

        self.mods = {}
        for slug, title, deps in [("sodium", "Sodium", ["fabric-api"]), ("lithium", "Lithium", []),
                                  ("fabric-api", "Fabric API", []), ("ferrite-core", "FerriteCore", []),
                                  ("embeddium", "Embeddium", [])]:
            jar = make_zip({"fabric.mod.json": json.dumps({"id": slug}).encode(), "v": b"1"})
            fname = f"{slug}-1.0.jar"
            self.add(f"/files/{fname}", jar)
            ver = {"id": f"ver-{slug}-1", "project_id": f"id-{slug}", "version_number": "1.0",
                   "version_type": "release", "date_published": "2025-01-02T00:00:00Z",
                   "loaders": ["fabric", "forge", "neoforge"], "game_versions": ["1.20.1", "1.21.4"],
                   "dependencies": [{"project_id": f"id-{d}", "dependency_type": "required"} for d in deps]
                   + [{"project_id": "id-optional-thing", "dependency_type": "optional"}],
                   "files": [{"primary": True, "filename": fname, "url": f"{b}/files/{fname}",
                              "hashes": {"sha1": sha1(jar), "sha512": sha512(jar)}}]}
            self.mods[slug] = (proj(slug, title), ver, jar)
            self.add(f"/modrinth/project/id-{slug}", proj(slug, title))
            self.add(f"/modrinth/project/{slug}", proj(slug, title))
            self.add(f"/modrinth/project/{slug}/version", [ver])
            self.add(f"/modrinth/project/id-{slug}/version", [ver])
        # a project with no builds
        self.add("/modrinth/project/ghost/version", [])
        # a newer build of lithium for the update check
        jar2 = make_zip({"v": b"2"})
        self.add("/files/lithium-2.0.jar", jar2)
        self.new_lithium = {"id": "ver-lithium-2", "project_id": "id-lithium", "version_number": "2.0",
                            "version_type": "release", "files": [{"primary": True, "filename": "lithium-2.0.jar",
                                                                     "url": f"{b}/files/lithium-2.0.jar",
                                                                     "hashes": {"sha1": sha1(jar2), "sha512": sha512(jar2)}}]}
        self.search_hits = [{"project_id": "id-sodium", "slug": "sodium", "title": "Sodium",
                             "description": "A modern rendering engine", "icon_url": "", "downloads": 90000000,
                             "follows": 100, "author": "jellysquid3", "display_categories": ["optimization"],
                             "client_side": "required", "server_side": "unsupported"},
                            {"project_id": "id-lithium", "slug": "lithium", "title": "Lithium",
                             "description": "Game logic optimizations", "icon_url": "", "downloads": 50000000,
                             "follows": 90, "author": "jellysquid3", "display_categories": ["optimization"],
                             "client_side": "optional", "server_side": "optional"}]

    # ---------------------------------------------------------- handler
    def env(self) -> dict:
        b = self.base
        return {
            "NOVA_MOJANG_MANIFEST": b + "/mojang/manifest.json", "NOVA_ASSET_BASE": b + "/assets",
            "NOVA_LIBRARIES_BASE": b + "/libs", "NOVA_FABRIC_META": b + "/fabric", "NOVA_QUILT_META": b + "/quilt",
            "NOVA_FORGE_MAVEN": b + "/forge", "NOVA_NEOFORGE_MAVEN": b + "/neoforge",
            "NOVA_NEOFORGE_API": b + "/neoforge-api", "NOVA_MODRINTH_API": b + "/modrinth",
            "NOVA_ADOPTIUM_API": b + "/adoptium",
        }

    def _handler(self):
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                u = urlparse(self.path)
                fake.requests.append(("GET", self.path))
                if u.path == "/modrinth/search":
                    q = parse_qs(u.query)
                    hits = [h for h in fake.search_hits if q.get("query", [""])[0].lower() in h["title"].lower()]
                    return self._send(200, json.dumps({"hits": hits, "total_hits": len(hits)}).encode(), "application/json")
                r = fake.routes.get(u.path)
                if not r:
                    return self._send(404, b"nope", "text/plain")
                self._send(r[0], r[1], r[2])

            def do_POST(self):
                u = urlparse(self.path)
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                fake.posts.append((u.path, body))
                if u.path == "/modrinth/version_files/update":
                    out = {}
                    for h in body["hashes"]:
                        if h == sha1(fake.mods["lithium"][2]):
                            out[h] = fake.new_lithium
                        else:  # already newest: same hash as current primary
                            out[h] = {"id": "same", "project_id": "x", "version_number": "1",
                                      "files": [{"primary": True, "hashes": {"sha1": h}}]}
                    return self._send(200, json.dumps(out).encode(), "application/json")
                self._send(404, b"nope", "text/plain")

        return H
