"""Microsoft / Xbox / Minecraft sign-in using the OAuth device-code flow.

Chain: Microsoft token -> Xbox Live (XBL) -> XSTS -> Minecraft services token -> ownership check -> profile.
The user types a short code at microsoft.com/link, so Nova needs no redirect server and never sees a password.
It does need an Azure app (client) ID; see README.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import accounts
from .util import NovaError, USER_AGENT

# Overridable so tests can point at a fake server.
URLS = {
    "devicecode": "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode",
    "token": "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
    "xbl": "https://user.auth.xboxlive.com/user/authenticate",
    "xsts": "https://xsts.auth.xboxlive.com/xsts/authorize",
    "mc_login": "https://api.minecraftservices.com/authentication/login_with_xbox",
    "entitlements": "https://api.minecraftservices.com/entitlements/mcstore",
    "profile": "https://api.minecraftservices.com/minecraft/profile",
}
SCOPE = "XboxLive.signin offline_access"
GRANT_DEVICE = "urn:ietf:params:oauth:grant-type:device_code"

XSTS_ERRORS = {
    2148916227: "This Microsoft account has been banned from Xbox.",
    2148916233: "This Microsoft account has no Xbox profile yet. Sign in once at minecraft.net or xbox.com to create one, then try again.",
    2148916235: "Xbox Live isn't available in your country or region.",
    2148916236: "This account needs adult verification (Xbox requirement in your region).",
    2148916237: "This account needs adult verification (Xbox requirement in your region).",
    2148916238: "This is a child account. Add it to a Microsoft family group and allow online play, then try again.",
}


def _request(url: str, *, form: dict | None = None, body: dict | None = None,
             bearer: str | None = None, timeout: float = 30) -> tuple[int, dict]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    req = urllib.request.Request(url, headers=headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise NovaError(f"Couldn't reach Microsoft's sign-in service ({e}). Check your internet connection.") from e
    try:
        return status, json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        return status, {}


# ------------------------------------------------------------ device flow

def start_device_flow(client_id: str) -> dict:
    status, d = _request(URLS["devicecode"], form={"client_id": client_id, "scope": SCOPE})
    if status != 200 or "device_code" not in d:
        raise NovaError(_oauth_message(d, "Microsoft rejected the app ID. Check it in Settings → Microsoft sign-in."))
    return {"device_code": d["device_code"], "user_code": d["user_code"],
            "verification_uri": d.get("verification_uri") or "https://www.microsoft.com/link",
            "interval": int(d.get("interval", 5)), "expires_in": int(d.get("expires_in", 900))}


def _oauth_message(d: dict, default: str) -> str:
    desc = (d.get("error_description") or "").splitlines()[0] if d.get("error_description") else ""
    return desc or default


def finish_device_flow(client_id: str, flow: dict, cancel: threading.Event, task=None) -> dict:
    """Poll until the user approves the code, then run the full chain and store the account."""
    deadline = time.time() + flow["expires_in"]
    interval = max(1, flow["interval"])
    while True:
        if cancel.is_set():
            raise NovaError("Sign-in cancelled.")
        if time.time() > deadline:
            raise NovaError("The sign-in code expired. Start again.")
        if cancel.wait(interval):
            raise NovaError("Sign-in cancelled.")
        status, d = _request(URLS["token"], form={"grant_type": GRANT_DEVICE, "client_id": client_id,
                                                  "device_code": flow["device_code"]})
        if status == 200 and "access_token" in d:
            break
        err = d.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5
            continue
        if err in ("authorization_declined", "access_denied"):
            raise NovaError("Sign-in was declined.")
        if err == "expired_token":
            raise NovaError("The sign-in code expired. Start again.")
        raise NovaError(_oauth_message(d, "Microsoft sign-in failed."))
    if task:
        task.update("Signing in to Xbox and Minecraft…")
    result = minecraft_chain(d["access_token"])
    return accounts.upsert_microsoft(result, d.get("refresh_token", ""))


# ------------------------------------------------------------ token chain

def minecraft_chain(ms_access_token: str) -> dict:
    st, x = _request(URLS["xbl"], body={
        "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": "d=" + ms_access_token},
        "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT"})
    if st != 200 or "Token" not in x:
        raise NovaError("Xbox Live sign-in failed. Try again in a moment.")
    uhs = x["DisplayClaims"]["xui"][0]["uhs"]

    st, s = _request(URLS["xsts"], body={
        "Properties": {"SandboxId": "RETAIL", "UserTokens": [x["Token"]]},
        "RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT"})
    if st != 200 or "Token" not in s:
        raise NovaError(XSTS_ERRORS.get(int(s.get("XErr", 0) or 0), "Xbox authorization failed."))

    st, m = _request(URLS["mc_login"], body={"identityToken": f"XBL3.0 x={uhs};{s['Token']}"})
    if st == 403:
        raise NovaError("Minecraft's servers rejected this app ID (403). New Azure apps must be approved by "
                        "Mojang first: submit your app ID at https://aka.ms/mce-reviewappid and wait for approval.")
    if st != 200 or "access_token" not in m:
        raise NovaError("Minecraft sign-in failed. Try again in a moment.")
    token = m["access_token"]

    st, ent = _request(URLS["entitlements"], bearer=token)
    owned = {i.get("name") for i in ent.get("items", [])} if st == 200 else set()
    if not owned & {"product_minecraft", "game_minecraft"}:
        raise NovaError("This Microsoft account doesn't own Minecraft: Java Edition. "
                        "(Game Pass owners: launch the official launcher once so the entitlement appears.)")

    st, prof = _request(URLS["profile"], bearer=token)
    if st == 404 or "id" not in prof:
        raise NovaError("This account owns Minecraft but has no Java profile yet. Create one at minecraft.net/profile.")
    return {"username": prof["name"], "uuid": _dash(prof["id"]), "mc_token": token,
            "mc_expires": int(time.time()) + int(m.get("expires_in", 86400)), "xuid": uhs}


def _dash(u: str) -> str:
    u = u.replace("-", "")
    return f"{u[:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:]}"


# ----------------------------------------------------------------- refresh

def ensure_fresh(acc: dict, client_id: str) -> dict:
    """Return the account with a Minecraft token valid for at least 10 more minutes."""
    if acc.get("type") != "microsoft":
        return acc
    if acc.get("mc_token") and acc.get("mc_expires", 0) > time.time() + 600:
        return acc
    if not acc.get("refresh_token"):
        raise NovaError(f"Sign in again for {acc['username']}: the saved login expired.")
    if not client_id:
        raise NovaError("Add your Microsoft app ID in Settings to refresh this account.")
    st, d = _request(URLS["token"], form={"grant_type": "refresh_token", "client_id": client_id,
                                          "refresh_token": acc["refresh_token"], "scope": SCOPE})
    if st != 200 or "access_token" not in d:
        raise NovaError(f"Sign in again for {acc['username']}: Microsoft says the saved login is no longer valid.")
    result = minecraft_chain(d["access_token"])
    return accounts.upsert_microsoft(result, d.get("refresh_token") or acc["refresh_token"])
