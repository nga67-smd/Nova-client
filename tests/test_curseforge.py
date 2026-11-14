"""CurseForge backend against a local fake of api.curseforge.com and its CDN."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from nova import config, curseforge, instances, mods
from nova.util import NovaError

JAR = b"PK\x03\x04fake-jar-bytes"


class Fake:
    def __init__(self):
        self.keys = []
        self.queries = []
        self.latest = 101
        self.no_url = False


def make(fake):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _json(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
            if u.path.startswith("/cdn/"):
                self.send_response(200); self.send_header("Content-Length", str(len(JAR))); self.end_headers()
                return self.wfile.write(JAR)
            fake.keys.append(self.headers.get("x-api-key")); fake.queries.append((u.path, q))
            if self.headers.get("x-api-key") != "K" * 32:
                return self._json(403, {})
            base = f"http://127.0.0.1:{self.server.server_port}"
            if u.path == "/v1/games/432":
                return self._json(200, {"data": {"id": 432}})
            if u.path == "/v1/mods/search":
                return self._json(200, {"data": [{"id": 11, "slug": "cool", "name": "Cool Mod", "summary": "does cool",
                                                  "downloadCount": 5000, "thumbsUpCount": 3, "authors": [{"name": "Ann"}],
                                                  "categories": [{"name": "Tech"}], "logo": {"thumbnailUrl": "http://x/i.png"}}],
                                        "pagination": {"totalCount": 1}})
            if u.path == "/v1/mods/11":
                return self._json(200, {"data": {"id": 11, "slug": "cool", "name": "Cool Mod", "logo": {"thumbnailUrl": "http://x/i.png"}}})
            if u.path == "/v1/mods/22":
                return self._json(200, {"data": {"id": 22, "slug": "lib", "name": "Cool Lib"}})
            if u.path == "/v1/mods/11/files":
                files = [
                    {"id": fake.latest, "displayName": "cool-2.0", "fileName": "cool-2.0.jar", "releaseType": 1, "fileDate": "2026-05-01T00:00:00Z",
                     "downloadUrl": None if fake.no_url else base + "/cdn/cool-2.0.jar", "isAvailable": True, "hashes": [],
                     "dependencies": [{"modId": 22, "relationType": 3}, {"modId": 33, "relationType": 2}]},
                    {"id": 100, "displayName": "cool-1.0", "fileName": "cool-1.0.jar", "releaseType": 1, "fileDate": "2026-01-01T00:00:00Z",
                     "downloadUrl": base + "/cdn/cool-1.0.jar", "isAvailable": True, "hashes": [], "dependencies": []},
                    {"id": 999, "displayName": "cool-3.0-alpha", "fileName": "cool-3.0a.jar", "releaseType": 3, "fileDate": "2026-09-01T00:00:00Z",
                     "downloadUrl": base + "/cdn/cool-3.0a.jar", "isAvailable": True, "hashes": [], "dependencies": []}]
                return self._json(200, {"data": files})
            if u.path == "/v1/mods/22/files":
                return self._json(200, {"data": [{"id": 5, "displayName": "lib-1", "fileName": "lib-1.jar", "releaseType": 1, "fileDate": "2026-01-01T00:00:00Z",
                                                  "downloadUrl": base + "/cdn/lib-1.jar", "isAvailable": True, "hashes": [], "dependencies": []}]})
            self._json(404, {})

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    monkeypatch.delenv("NOVA_CURSEFORGE_KEY", raising=False)
    fake = Fake(); srv = make(fake)
    monkeypatch.setenv("NOVA_CURSEFORGE_API", f"http://127.0.0.1:{srv.server_port}/v1")
    inst = instances.create({"name": "T", "mc_version": "1.20.1", "loader": "fabric"})
    yield fake, inst
    srv.shutdown()


def test_key_storage_validation_and_env(env, tmp_path, monkeypatch):
    assert not curseforge.has_key()
    with pytest.raises(NovaError):
        curseforge.set_key("short key")
    with pytest.raises(NovaError, match="rejected"):      # wrong key is checked against CurseForge and not kept
        curseforge.set_key("W" * 32)
    assert not curseforge.has_key()
    curseforge.set_key('"' + "K" * 32 + '"\n')
    assert curseforge.get_key() == "K" * 32 and (tmp_path / "curseforge.key").exists()
    curseforge.set_key("")
    assert not curseforge.has_key()
    monkeypatch.setenv("NOVA_CURSEFORGE_KEY", "E" * 32)
    assert curseforge.get_key() == "E" * 32


def test_search_needs_key_and_rejects_bad_key(env):
    with pytest.raises(NovaError, match="API key"):
        mods.search("cool", "1.20.1", "fabric", source="curseforge")
    with pytest.raises(NovaError, match="rejected"):
        curseforge.set_key("B" * 32)
    with pytest.raises(NovaError, match="API key"):
        mods.search("cool", "1.20.1", "fabric", source="curseforge")


def test_search_maps_results_and_filters(env):
    fake, _ = env
    curseforge.set_key("K" * 32)
    r = mods.search("cool", "1.20.1", "fabric", "mod", "downloads", 0, source="curseforge")
    h = r["hits"][0]
    assert h["project_id"] == "cf:11" and h["title"] == "Cool Mod" and h["downloads"] == 5000 and h["author"] == "Ann"
    path, q = fake.queries[-1]
    assert q["gameVersion"] == "1.20.1" and q["modLoaderType"] == "4" and q["classId"] == "6" and q["sortField"] == "6"
    mods.search("x", "1.20.1", "forge", "shader", source="curseforge")
    assert fake.queries[-1][1]["classId"] == "6552" and "modLoaderType" not in fake.queries[-1][1]


def test_install_picks_release_installs_required_deps_only_and_records_meta(env):
    fake, inst = env
    curseforge.set_key("K" * 32)
    res = mods.install_project(inst, "cf:11")
    assert [r["title"] for r in res] == ["Cool Mod", "Cool Lib"]          # alpha ignored, optional dep 33 skipped
    names = {m["file"]: m for m in mods.list_installed(inst)}
    assert set(names) == {"cool-2.0.jar", "lib-1.jar"}
    assert names["cool-2.0.jar"]["source"] == "curseforge" and names["cool-2.0.jar"]["managed"]
    assert (instances.game_dir(inst["id"]) / "mods" / "cool-2.0.jar").read_bytes() == JAR


def test_update_detection_and_replacement(env):
    fake, inst = env
    curseforge.set_key("K" * 32)
    fake.latest = 90                                   # older id than 100 -> make 1.0 look newest? keep deterministic below
    mods.install_project(inst, "cf:11")
    assert mods.check_updates(inst) == []              # just installed the newest
    meta = mods._load_meta(inst["id"]); fn = next(k for k, m in meta.items() if m["project_id"] == "cf:11")
    meta[fn]["version_id"] = "1"                       # pretend an older file is installed
    mods.write_json(mods._meta_path(inst["id"]), meta)
    ups = mods.check_updates(inst)
    assert len(ups) == 1 and ups[0]["project_id"] == "cf:11" and ups[0]["new_version"] == "cool-2.0"


def test_download_disabled_by_author_gives_clear_error(env):
    fake, inst = env
    curseforge.set_key("K" * 32); fake.no_url = True
    with pytest.raises(NovaError, match="outside CurseForge"):
        mods.install_project(inst, "cf:11")


def test_modrinth_ids_still_route_to_modrinth(env, monkeypatch):
    monkeypatch.setattr(mods, "pick_version", lambda *a, **k: None)
    with pytest.raises(NovaError, match="no version"):
        mods.install_project(env[1], "sodium")
