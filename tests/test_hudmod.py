"""Auto-installing the Nova in-game mod, against a fake GitHub release."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from nova import cosmetics, hudmod, instances, mods
from nova.util import NovaError

JAR = b"PK\x03\x04" + b"nova-mod" * 50


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_GET(self):
            base = f"http://127.0.0.1:{self.server.server_port}"
            if self.path == "/release":
                b = json.dumps({"assets": [
                    {"name": "nova-hud-1.0.0+mc1.21.1.jar", "browser_download_url": base + "/dl", "size": len(JAR)},
                    {"name": "nova-hud-1.0.0+mc1.21.8.jar", "browser_download_url": base + "/dl", "size": len(JAR)}]}).encode()
            else:
                b = JAR
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("NOVA_HUD_RELEASE_API", f"http://127.0.0.1:{srv.server_port}/release")
    calls = []
    monkeypatch.setattr(mods, "install_project", lambda inst, project, *a, **k: calls.append(project) or [])
    yield calls
    srv.shutdown()


def fabric(mc="1.21.1"):
    return instances.create({"name": "F", "mc_version": mc, "loader": "fabric"})


def test_installs_mod_and_fabric_api_then_is_idempotent(env):
    inst = fabric()
    assert hudmod.supported(inst) and not hudmod.installed(inst)
    assert hudmod.ensure(inst) == "installed" and env == ["fabric-api"]
    d = instances.game_dir(inst["id"]) / "mods"
    assert (d / "nova-hud-1.0.0+mc1.21.1.jar").read_bytes() == JAR and hudmod.installed(inst)
    (d / "fabric-api-0.1.jar").write_bytes(b"x")                 # pretend Fabric API arrived
    env.clear()
    assert hudmod.ensure(inst) == "current" and env == []


def test_replaces_older_nova_jar(env):
    inst = fabric("1.21.8")
    d = instances.game_dir(inst["id"]) / "mods"; d.mkdir(parents=True, exist_ok=True)
    (d / "nova-hud-0.9.0+mc1.21.8.jar").write_bytes(b"old"); (d / "fabric-api-1.jar").write_bytes(b"x")
    assert hudmod.ensure(inst) == "installed"
    assert [f.name for f in d.glob("nova-hud-*.jar")] == ["nova-hud-1.0.0+mc1.21.8.jar"]


@pytest.mark.parametrize("loader,mc", [("forge", "1.21.1"), ("fabric", "1.20.1"), ("vanilla", "1.21.1")])
def test_unsupported_instances_are_left_alone(env, loader, mc):
    inst = instances.create({"name": "X", "mc_version": mc, "loader": loader})
    assert not hudmod.supported(inst) and hudmod.ensure(inst) == "unsupported" and env == []


def test_missing_release_asset_is_a_clear_error(env, monkeypatch):
    monkeypatch.setattr(hudmod, "SUPPORTED", ("1.21.1", "1.21.8", "1.99"))
    with pytest.raises(NovaError, match="isn't published"):
        hudmod.ensure(instances.create({"name": "Y", "mc_version": "1.99", "loader": "fabric"}))
