"""Microsoft sign-in against a local fake of the Microsoft/Xbox/Minecraft services."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import pytest

from nova import accounts, msauth, settings
from nova.util import NovaError

UUID_RAW = "069a79f444e94726a5befca90e38aaf5"


class Fake:
    def __init__(self):
        self.pending_polls = 1       # polls answered "authorization_pending" first
        self.xsts_err = None         # XErr code to return
        self.mc_status = 200
        self.owns = True
        self.has_profile = True
        self.refresh_ok = True
        self.calls = []


def make_server(fake: Fake):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _out(self, code, obj):
            b = json.dumps(obj).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def _body(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
            if "json" in (self.headers.get("Content-Type") or ""):
                return json.loads(raw or "{}")
            return {k: v[0] for k, v in parse_qs(raw).items()}

        def do_POST(self):
            b = self._body(); fake.calls.append((self.path, b))
            if self.path == "/devicecode":
                assert b["scope"] == msauth.SCOPE
                return self._out(200, {"device_code": "DEV", "user_code": "ABCD1234", "interval": 1, "expires_in": 60,
                                       "verification_uri": "https://www.microsoft.com/link"})
            if self.path == "/token":
                if b["grant_type"] == "refresh_token":
                    if not fake.refresh_ok:
                        return self._out(400, {"error": "invalid_grant"})
                    return self._out(200, {"access_token": "MSA2", "refresh_token": "R2"})
                assert b["grant_type"] == "urn:ietf:params:oauth:grant-type:device_code"
                if fake.pending_polls > 0:
                    fake.pending_polls -= 1
                    return self._out(400, {"error": "authorization_pending"})
                return self._out(200, {"access_token": "MSA1", "refresh_token": "R1"})
            if self.path == "/xbl":
                assert b["Properties"]["RpsTicket"].startswith("d=MSA")
                return self._out(200, {"Token": "XBLTOK", "DisplayClaims": {"xui": [{"uhs": "UHS9"}]}})
            if self.path == "/xsts":
                if fake.xsts_err:
                    return self._out(401, {"XErr": fake.xsts_err})
                assert b["RelyingParty"] == "rp://api.minecraftservices.com/"
                return self._out(200, {"Token": "XSTSTOK"})
            if self.path == "/mclogin":
                if fake.mc_status != 200:
                    return self._out(fake.mc_status, {"error": "x"})
                assert b["identityToken"] == "XBL3.0 x=UHS9;XSTSTOK"
                return self._out(200, {"access_token": "MCTOKEN", "expires_in": 86400})
            self._out(404, {})

        def do_GET(self):
            assert self.headers["Authorization"] == "Bearer MCTOKEN"
            if self.path == "/ent":
                return self._out(200, {"items": [{"name": "product_minecraft"}] if fake.owns else []})
            if self.path == "/profile":
                if not fake.has_profile:
                    return self._out(404, {})
                return self._out(200, {"id": UUID_RAW, "name": "Steve"})
            self._out(404, {})

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    fake = Fake(); srv = make_server(fake)
    base = f"http://127.0.0.1:{srv.server_port}"
    monkeypatch.setitem(msauth.URLS, "devicecode", base + "/devicecode")
    monkeypatch.setitem(msauth.URLS, "token", base + "/token")
    monkeypatch.setitem(msauth.URLS, "xbl", base + "/xbl")
    monkeypatch.setitem(msauth.URLS, "xsts", base + "/xsts")
    monkeypatch.setitem(msauth.URLS, "mc_login", base + "/mclogin")
    monkeypatch.setitem(msauth.URLS, "entitlements", base + "/ent")
    monkeypatch.setitem(msauth.URLS, "profile", base + "/profile")
    yield fake
    srv.shutdown()


def sign_in():
    flow = msauth.start_device_flow("cid")
    assert flow["user_code"] == "ABCD1234"
    return msauth.finish_device_flow("cid", flow, threading.Event())


def test_full_sign_in_stores_account_and_hides_secrets(env):
    acc = sign_in()
    assert acc["username"] == "Steve" and acc["uuid"] == "069a79f4-44e9-4726-a5be-fca90e38aaf5"
    stored = accounts.load()["accounts"][0]
    assert stored["mc_token"] == "MCTOKEN" and stored["refresh_token"] == "R1" and stored["type"] == "microsoft"
    pub = accounts.public(stored)
    assert not {"mc_token", "refresh_token", "mc_expires"} & set(pub)
    assert accounts.load()["selected"] == stored["id"]


def test_signing_in_twice_updates_same_account(env):
    sign_in(); env.pending_polls = 0; sign_in()
    assert len(accounts.load()["accounts"]) == 1


def test_fresh_token_is_reused_and_expired_one_refreshed(env):
    acc = sign_in()
    n = len(env.calls)
    assert msauth.ensure_fresh(acc, "cid")["mc_token"] == "MCTOKEN"
    assert len(env.calls) == n                      # no network
    d = accounts.load(); d["accounts"][0]["mc_expires"] = int(time.time()) + 30; accounts.save(d)
    out = msauth.ensure_fresh(accounts.load()["accounts"][0], "cid")
    assert out["refresh_token"] == "R2" and out["mc_expires"] > time.time() + 3600


def test_refresh_rejected_asks_to_sign_in_again(env):
    sign_in(); env.refresh_ok = False
    d = accounts.load(); d["accounts"][0]["mc_expires"] = 0; accounts.save(d)
    with pytest.raises(NovaError, match="Sign in again"):
        msauth.ensure_fresh(accounts.load()["accounts"][0], "cid")


def test_offline_account_passes_through(env):
    a = accounts.add_offline("Alex")
    assert msauth.ensure_fresh(a, "") is a


@pytest.mark.parametrize("setup,match", [
    (lambda f: setattr(f, "xsts_err", 2148916233), "no Xbox profile"),
    (lambda f: setattr(f, "xsts_err", 2148916238), "child account"),
    (lambda f: setattr(f, "mc_status", 403), "approved by Mojang"),
    (lambda f: setattr(f, "owns", False), "doesn't own Minecraft"),
    (lambda f: setattr(f, "has_profile", False), "no Java profile"),
])
def test_failure_messages(env, setup, match):
    setup(env)
    with pytest.raises(NovaError, match=match):
        sign_in()
    assert accounts.load()["accounts"] == []


def test_cancel(env):
    env.pending_polls = 99
    flow = msauth.start_device_flow("cid"); ev = threading.Event()
    threading.Timer(0.3, ev.set).start()
    with pytest.raises(NovaError, match="cancelled"):
        msauth.finish_device_flow("cid", flow, ev)


def test_launch_arguments_use_real_token():
    from nova import launch
    import inspect
    src = inspect.getsource(launch.build_command)
    assert '"msa"' in src and "mc_token" in src


def test_client_id_validation(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    with pytest.raises(NovaError):
        settings.update({"ms_client_id": "not-an-id"})
    assert settings.update({"ms_client_id": " 12345678-abcd-1234-abcd-1234567890ab "})["ms_client_id"].startswith("12345678")


def test_builtin_client_id_is_default_but_user_can_override(tmp_path, monkeypatch):
    from nova import config
    monkeypatch.setenv("NOVA_HOME", str(tmp_path))
    monkeypatch.setattr(config, "BUILTIN_MS_CLIENT_ID", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
    assert settings.load()["ms_client_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    settings.update({"ms_client_id": "12345678-abcd-1234-abcd-1234567890ab"})
    assert settings.load()["ms_client_id"].startswith("12345678")
    monkeypatch.setenv("NOVA_MS_CLIENT_ID", "99999999-bbbb-cccc-dddd-eeeeeeeeeeee")
    settings.update({"ms_client_id": ""})
    assert settings.load()["ms_client_id"].startswith("99999999")
