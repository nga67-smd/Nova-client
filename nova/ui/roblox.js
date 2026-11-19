/* Nova Roblox pages. Loaded before app.js; only used when the server says app === "roblox". */
"use strict";

window.RBX_PAGES = { roblox: pageRoblox, flags: pageFlags, rbxmods: pageRbxMods };

function rbxInit() {
  NAV.length = 0;
  NAV.push(["roblox", "Roblox", "library"], ["flags", "FastFlags", "settings"], ["rbxmods", "Mods", "discover"], ["settings", "Appearance", "cosmetics"]);
  S.page = "roblox";
  document.title = "Nova Roblox";
  const name = document.querySelector(".brand-name"); if (name) name.textContent = "Nova Roblox";
}

const rbxPost = async (path, body) => { const r = await api(path, { method: "POST", body: body || {} }); return r; };
async function rbxRefresh() { await loadState(); render(); }

async function pageRoblox(v) {
  const r = S.data.roblox;
  const runInstall = async (reinstall) => {
    try {
      if (reinstall) await rbxPost("/api/roblox/uninstall");
      const t = await rbxPost("/api/roblox/install");
      runTask(t.id, (x) => { if (x.status === "done") toast("Roblox is ready.", "ok"); rbxRefresh(); });
      poll();
    } catch (e) { fail(e); }
  };
  const check = async () => {
    try {
      const c = await rbxPost("/api/roblox/check");
      if (!c.installed) return toast("Roblox isn't installed yet.", "");
      if (c.update) confirmDialog("Update available", "A newer Roblox is available. Install it now?", "Update", () => runInstall(false), false);
      else toast("Roblox is up to date.", "ok");
    } catch (e) { fail(e); }
  };
  const step = (n, title, body, action) => el("div", { class: "row", style: { "align-items": "flex-start", gap: "14px", padding: "10px 0" } },
    el("div", { class: "avatar", style: { flex: "none" } }, String(n)), el("div", { class: "grow" }, el("b", {}, title), el("div", { class: "muted small" }, body)), action);
  v.append(el("div", { class: "page-head" }, el("div", { class: "grow" }, el("h1", {}, "Roblox"), el("p", {}, "Install and update Roblox, and play it with your own settings and mods."))),
    !r.supported ? el("div", { class: "section card" }, el("h2", {}, "Windows only"), el("p", { class: "muted", style: { margin: "6px 0 0" } }, "Roblox only runs on Windows, so installing and playing works there. You can still set up FastFlags, mods and the look here.")) : null,
    el("div", { class: "section card" }, el("div", { class: "row" },
      el("div", { class: "grow" }, el("h2", {}, r.version ? "Roblox is installed" : "Roblox isn't installed"), el("div", { class: "muted small" }, r.version ? `Version ${r.version}` + (r.running ? " · running now" : "") : "Nova downloads Roblox from Roblox's own servers.")),
      r.version ? el("button", { class: "btn", onclick: check }, icon("refresh"), "Check for updates") : null,
      !r.version ? el("button", { class: "btn primary", disabled: !r.supported, onclick: () => runInstall(false) }, icon("download"), "Install Roblox") : null)),
    el("div", { class: "section card" }, el("h2", {}, "How to play"),
      step(1, "Let Play open Roblox through Nova", r.registered ? "Done. Nova opens Roblox when you press Play on roblox.com." : "Do this once. Then Play on roblox.com starts Roblox with your FastFlags and mods.",
        r.registered ? el("span", { class: "muted small" }, "Connected") : el("button", { class: "btn primary sm", disabled: !r.supported, onclick: async () => { try { await rbxPost("/api/roblox/register"); await rbxRefresh(); toast("Play now opens Roblox through Nova.", "ok"); } catch (e) { fail(e); } } }, "Connect")),
      step(2, "Open roblox.com and sign in", "Roblox sign-in stays in your browser. Nova never sees your password.",
        el("button", { class: "btn sm", onclick: () => rbxPost("/api/roblox/open-site").catch(fail) }, "Open Roblox")),
      step(3, "Press Play on any game", "Nova checks for a Roblox update first, then starts the game.")),
    el("div", { class: "section card" }, el("h2", {}, "Maintenance"), el("div", { style: { height: "10px" } }),
      el("div", { class: "row", style: { "flex-wrap": "wrap" } },
        el("button", { class: "btn", onclick: () => rbxPost("/api/roblox/open-folder", {}).catch(fail) }, icon("folder"), "Open Nova Roblox folder"),
        r.version ? el("button", { class: "btn", onclick: () => confirmDialog("Reinstall Roblox?", "Nova removes its copy of Roblox and downloads it again. Your settings and mods stay.", "Reinstall", () => runInstall(true), false) }, icon("refresh"), "Reinstall") : null,
        r.version ? el("button", { class: "btn danger", onclick: () => confirmDialog("Uninstall Roblox?", "This removes the Roblox files Nova installed. Your settings and mods stay.", "Uninstall", async () => { try { await rbxPost("/api/roblox/uninstall"); await rbxRefresh(); } catch (e) { fail(e); } }) }, icon("trash"), "Uninstall") : null,
        r.registered ? el("button", { class: "btn ghost", onclick: async () => { try { await rbxPost("/api/roblox/unregister"); await rbxRefresh(); toast("Play no longer opens through Nova.", "ok"); } catch (e) { fail(e); } } }, "Stop using Nova for Play") : null),
      el("p", { class: "muted small", style: { margin: "12px 0 0" } }, "Nova Roblox isn't made by or connected to Roblox Corporation.")));
}

async function pageFlags(v) {
  const r = S.data.roblox;
  const rows = Object.entries(r.flags).map(([k, val]) => [k, String(val)]);
  const list = el("div", { class: "stack" });
  const draw = () => list.replaceChildren(...rows.map((row, i) => {
    const n = el("input", { type: "text", value: row[0], placeholder: "FlagName", "aria-label": "Flag name" });
    const val = el("input", { type: "text", value: row[1], placeholder: "value", "aria-label": "Flag value" });
    n.addEventListener("input", () => { row[0] = n.value.trim(); }); val.addEventListener("input", () => { row[1] = val.value; });
    return el("div", { class: "flag-row" }, n, val, el("button", { class: "btn ghost sm", "aria-label": "Remove flag", onclick: () => { rows.splice(i, 1); draw(); } }, icon("trash")));
  }));
  draw();
  const save = async () => {
    const flags = {};
    for (const [k, val] of rows) if (k) flags[k] = val;
    try { await rbxPost("/api/roblox/flags", { flags }); await loadState(); toast("Flags saved. They apply the next time Roblox starts.", "ok"); } catch (e) { fail(e); }
  };
  v.append(el("div", { class: "page-head" }, el("div", { class: "grow" }, el("h1", {}, "FastFlags"), el("p", {}, "Roblox client settings, like the FPS limit and graphics options. They apply the next time Roblox starts."))),
    el("div", { class: "section card" }, el("h2", {}, "Presets"), el("div", { style: { height: "6px" } }),
      ...Object.entries(r.presets).map(([id, p]) => toggleRow(p.name, p.desc, !!r.preset_on[id], async (on) => { try { await rbxPost("/api/roblox/preset", { id, on }); await rbxRefresh(); } catch (e) { fail(e); } }))),
    el("div", { class: "section card" }, el("h2", {}, "Your own flags"),
      el("p", { class: "muted small", style: { margin: "4px 0 12px" } }, "Add any flag by name. A value can be true, false, a whole number or text. Roblox ignores flags it doesn't allow, so some may do nothing."),
      list, el("div", { style: { height: "12px" } }),
      el("div", { class: "row" }, el("button", { class: "btn sm", onclick: () => { rows.push(["", ""]); draw(); } }, icon("plus"), "Add flag"), el("button", { class: "btn primary sm", onclick: save }, "Save flags"))));
}

async function pageRbxMods(v) {
  const r = S.data.roblox;
  const pick = () => {
    const f = el("input", { type: "file", accept: ".zip,application/zip", style: { display: "none" } });
    f.addEventListener("change", async () => { if (!f.files[0]) return; try { toast("Importing…"); await api("/api/roblox/mods-upload", { raw: f.files[0], filename: f.files[0].name }); await rbxRefresh(); toast("Mod imported.", "ok"); } catch (e) { fail(e); } });
    f.click();
  };
  v.append(el("div", { class: "page-head" }, el("div", { class: "grow" }, el("h1", {}, "Mods"), el("p", {}, "Change how Roblox looks and sounds, like cursors, skies, fonts and sounds. Mods are copied over Roblox's files when it starts.")),
      el("button", { class: "btn", onclick: () => rbxPost("/api/roblox/open-folder", { what: "mods" }).catch(fail) }, icon("folder"), "Open Mods folder"),
      el("button", { class: "btn primary", onclick: pick }, icon("plus"), "Import mod (.zip)")),
    r.mods.length ? el("div", { class: "section card" }, ...r.mods.map((m) => el("div", { class: "toggle-row" },
      el("div", { class: "t" }, m.name, el("small", {}, `${m.files} file${m.files === 1 ? "" : "s"}`)),
      el("button", { class: "btn ghost sm", "aria-label": "Delete " + m.name, onclick: () => confirmDialog("Delete " + m.name + "?", "This removes the mod from your Mods folder.", "Delete", async () => { try { await rbxPost("/api/roblox/mods/delete", { name: m.name }); await rbxRefresh(); } catch (e) { fail(e); } }) }, icon("trash")),
      el("label", { class: "switch" }, el("input", { type: "checkbox", checked: m.enabled, "aria-label": "Enable " + m.name, onchange: async (e) => { try { await rbxPost("/api/roblox/mods/toggle", { name: m.name, enabled: e.target.checked }); await loadState(); } catch (x) { fail(x); } } }), el("i"))))) :
      el("div", { class: "empty" }, el("h2", {}, "No mods yet"), el("p", {}, "Import a .zip whose folders match Roblox's (for example content/textures or content/sounds). Nova puts the files in place when Roblox starts and puts the originals back if you switch a mod off.")),
    el("p", { class: "muted small", style: { margin: "14px 0 0" } }, "Stick to looks and sounds. Mods can break when Roblox updates, and changes that give an unfair advantage in games can get your account banned."));
}
