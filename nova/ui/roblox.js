/* Nova Roblox pages. Loaded before app.js; only used when the server says app === "roblox". */
"use strict";

window.RBX_PAGES = { roblox: pageRoblox, sky: pageSky, flags: pageFlags, rbxmods: pageRbxMods };

function rbxInit() {
  NAV.length = 0;
  NAV.push(["roblox", "Roblox", "library"], ["sky", "Sky", "cosmetics"], ["flags", "FastFlags", "settings"], ["rbxmods", "Mods", "discover"], ["settings", "Appearance", "profiles"]);
  S.page = "roblox";
  document.title = "Nova Roblox";
  const name = document.querySelector(".brand-name"); if (name) name.textContent = "Nova Roblox";
}

const put = (v, ...kids) => v.append(...kids.filter(Boolean));       // append() would print "null" for an empty slot
const rbxPost = async (path, body) => { const r = await api(path, { method: "POST", body: body || {} }); return r; };
async function rbxRefresh() { await loadState(); render(); }

async function pageRoblox(v) {
  const r = S.data.roblox;
  if (r.running) setTimeout(() => { if (document.body.contains(v)) rbxRefresh().catch(() => {}); }, 3000);   // notice when Roblox closes
  const check = async () => {
    try {
      const c = await rbxPost("/api/roblox/check");
      if (!c.installed) return toast("Roblox still isn't on this PC.", "");
      toast(c.update ? "A newer Roblox is out. It updates the next time you open it." : "Your Roblox is up to date.", c.update ? "" : "ok");
    } catch (e) { fail(e); }
  };
  const rescan = async () => { try { await rbxPost("/api/roblox/rescan"); await rbxRefresh(); } catch (e) { fail(e); } };
  const step = (n, title, body, action) => el("div", { class: "row", style: { "align-items": "flex-start", gap: "14px", padding: "10px 0" } },
    el("div", { class: "avatar", style: { flex: "none" } }, String(n)), el("div", { class: "grow" }, el("b", {}, title), el("div", { class: "muted small" }, body)), action);
  put(v, el("div", { class: "page-head" }, el("div", { class: "grow" }, el("h1", {}, "Roblox"), el("p", {}, "Play the Roblox on this PC with your own settings, sky and mods."))),
    !r.supported ? el("div", { class: "section card" }, el("h2", {}, "Windows only"), el("p", { class: "muted", style: { margin: "6px 0 0" } }, "Roblox only runs on Windows, so finding and opening it works there. You can still set up FastFlags, skies, mods and the look here.")) : null,
    r.version ? el("div", { class: "section card" }, el("div", { class: "row" },
      el("div", { class: "grow" }, el("h2", {}, "Roblox found on this PC"), el("div", { class: "muted small" }, `Version ${r.version} · from ${r.from}` + (r.running ? " · running now" : ""))),
      el("button", { class: "btn", onclick: check }, icon("refresh"), "Check for updates"),
      el("button", { class: "btn", onclick: () => rbxPost("/api/roblox/open-folder", { what: "roblox" }).catch(fail) }, icon("folder"), "Open Roblox folder"))) :
      el("div", { class: "section card" }, el("div", { class: "row" },
        el("div", { class: "grow" }, el("h2", {}, "Roblox isn't on this PC"), el("div", { class: "muted small" }, "Nova looks for the Roblox app on your device. Install Roblox from roblox.com, then check again.")),
        el("button", { class: "btn", onclick: rescan }, icon("refresh"), "Check again"),
        el("button", { class: "btn primary", onclick: () => rbxPost("/api/roblox/open-download").catch(fail) }, icon("download"), "Get Roblox"))),
    el("div", { class: "section card" }, el("h2", {}, "How to play"),
      step(1, "Let Play open Roblox through Nova", r.registered ? "Done. Nova opens Roblox when you press Play on roblox.com." : "Do this once. Then Play on roblox.com starts Roblox with your FastFlags, sky and mods.",
        r.registered ? el("span", { class: "muted small" }, "Connected") : el("button", { class: "btn primary sm", disabled: !r.supported, onclick: async () => { try { await rbxPost("/api/roblox/register"); await rbxRefresh(); toast("Play now opens Roblox through Nova.", "ok"); } catch (e) { fail(e); } } }, "Connect")),
      step(2, "Open Roblox", "Starts the Roblox app with your FastFlags, sky and mods. Sign in there, or in your browser, whichever you use.",
        el("button", { class: "btn primary sm", disabled: !r.version || r.running, onclick: async () => { try { await rbxPost("/api/roblox/open-app"); toast("Opening Roblox…", "ok"); setTimeout(() => loadState().then(render), 1500); } catch (e) { fail(e); } } }, r.running ? "Running" : "Open Roblox")),
      step(3, "Or press Play on roblox.com", "Playing from the website also opens Roblox through Nova. If a newer Roblox is out, Roblox's own launcher updates it first.", el("button", { class: "btn ghost sm", onclick: () => rbxPost("/api/roblox/open-site").catch(fail) }, "Open website"))),
    el("div", { class: "section card" }, el("h2", {}, "Maintenance"), el("div", { style: { height: "10px" } }),
      el("div", { class: "row", style: { "flex-wrap": "wrap" } },
        el("button", { class: "btn", onclick: () => rbxPost("/api/roblox/open-folder", {}).catch(fail) }, icon("folder"), "Open Nova Roblox folder"),
        el("button", { class: "btn", onclick: async () => { try { const c = await rbxPost("/api/roblox/cleanup"); toast(`Cleared ${(c.freed / 1048576).toFixed(1)} MB of Roblox logs and temp files.`, "ok"); } catch (e) { fail(e); } } }, "Clean Roblox logs & temp files"),
        r.registered ? el("button", { class: "btn ghost", onclick: async () => { try { await rbxPost("/api/roblox/unregister"); await rbxRefresh(); toast("Play is back to Roblox's own launcher.", "ok"); } catch (e) { fail(e); } } }, "Stop using Nova for Play") : null),
      el("p", { class: "muted small", style: { margin: "12px 0 0" } }, "Nova Roblox doesn't install Roblox and isn't made by or connected to Roblox Corporation.")));
}

const SKY_SIDES = [["front", "Front"], ["back", "Back"], ["left", "Left"], ["right", "Right"], ["up", "Up"], ["down", "Down"]];

async function pageSky(v) {
  const r = S.data.roblox, sky = r.sky;
  // Roblox wants 512x512 pictures. The browser reads any image format and cuts a centered square, so Nova only gets a clean PNG.
  const toSkyPng = async (file) => {
    const bmp = await createImageBitmap(file), c = document.createElement("canvas"); c.width = c.height = 512;
    const side = Math.min(bmp.width, bmp.height), g = c.getContext("2d"); g.imageSmoothingQuality = "high";
    g.drawImage(bmp, (bmp.width - side) / 2, (bmp.height - side) / 2, side, side, 0, 0, 512, 512);
    return await new Promise((ok, no) => c.toBlob((b) => b ? ok(b) : no(new Error("Couldn't read that picture.")), "image/png"));
  };
  const pick = (face) => {
    const f = el("input", { type: "file", accept: "image/png,image/jpeg,image/webp,image/gif,image/bmp", style: { display: "none" } });
    f.addEventListener("change", async () => {
      if (!f.files[0]) return;
      try { toast("Converting\u2026"); const png = await toSkyPng(f.files[0]); const res = await api("/api/roblox/sky-upload", { raw: png, filename: "sky.png", face }); await rbxRefresh(); skyDone(res); }
      catch (e) { fail(e); }
    });
    f.click();
  };
  const color = el("input", { type: "color", value: "#6fa8dc", "aria-label": "Sky color" });
  const skyDone = (res) => toast(res.applied ? "Sky saved to Roblox. Restart Roblox to see it." : r.running ? "Sky saved, but Roblox is open so its files can't change. Close Roblox, then press Apply again." : "Sky saved. Nova couldn't find Roblox's files yet, so it applies when Roblox starts through Nova.", res.applied ? "ok" : "");
  const apply = async () => { try { const res = await rbxPost("/api/roblox/sky/apply"); await rbxRefresh(); skyDone(res); } catch (e) { fail(e); } };
  const check = async () => {
    try {
      const c = await rbxPost("/api/roblox/sky/check"), f = Object.values(c.files), yours = f.filter((x) => x === "yours").length, orig = f.filter((x) => x === "original").length;
      const lines = [`Roblox ${c.version} from ${c.from}.`, `Sky textures folder: ${c.folder} (${c.found_files} sky files found).`, c.launcher_folder ? `${c.from} keeps mods in ${c.launcher_folder}. Nova puts your sky there too.` : "",
        !f.some((x) => x !== "default") ? "No custom sky is set." : yours === f.filter((x) => x !== "default").length ? "Your sky is in Roblox's files. If a game still shows the old sky, that game builds its own sky, or Roblox was opened without Nova. Use Open Roblox in Nova, or press Connect and then Play on roblox.com."
          : orig ? "Roblox's own files are back. An update or a launcher put them back. Press Apply again, then start Roblox from Nova." : "Roblox's sky files couldn't be found in this version of Roblox.",
        c.running ? "Roblox is open right now. Close it before changing the sky." : "", c.registered ? "" : "Play on roblox.com is not connected to Nova yet, so games started from the website skip your sky."].filter(Boolean);
      confirmDialog("Sky check", lines.join("\n\n"), "OK", () => {}, false);
    } catch (e) { fail(e); }
  };
  const sendPack = async (files) => {
    const zips = files.filter((x) => /\.zip$/i.test(x.name)), tex = files.filter((x) => /\.(tex|dds)$/i.test(x.name));
    const groups = new Map();                                      // loose texture files, one sky per folder
    for (const x of tex) { const parts = (x.webkitRelativePath || "").split("/"), key = parts.length > 1 ? parts[parts.length - 2] : "My sky"; groups.set(key, [...(groups.get(key) || []), x]); }
    const total = zips.length + groups.size, apply = total === 1 ? "1" : "0";
    let res;
    for (const z of zips) res = await api("/api/roblox/sky-pack-upload", { raw: z, filename: z.name, headers: { "X-Name": encodeURIComponent(z.name.replace(/\.zip$/i, "")), "X-Apply": apply } });
    for (const [name, list] of groups) {
      for (let i = 0; i < list.length; i++) await api("/api/roblox/sky-file-upload", { raw: list[i], filename: list[i].name, headers: { "X-First": i === 0 ? "1" : "0" } });
      res = await rbxPost("/api/roblox/sky-files-done", { name, apply: apply === "1" });
    }
    if (total > 1) { toast(`Added ${total} skies to Your skies.`, "ok"); return { applied: null, many: true }; }
    if (total === 1) return res;
    const sideOf = (n) => { const w = n.toLowerCase().replace(/\.[a-z0-9]+$/, "").match(/[a-z]+/g) || []; for (const x of w.reverse()) { const k = { bk: "back", back: "back", dn: "down", down: "down", bottom: "down", ft: "front", front: "front", lf: "left", left: "left", rt: "right", right: "right", up: "up", top: "up" }[x]; if (k) return k; } return null; };
    const pics = files.filter((x) => /\.(png|jpe?g|webp|bmp|gif)$/i.test(x.name) && sideOf(x.name));
    if (!pics.length) throw new Error("Nova found no sky files in there. It looks for .tex or .dds files (like sky512_ft.tex), or pictures named front, back, left, right, up and down. What it saw: " + (files.slice(0, 8).map((x) => x.name).join(", ") || "nothing") + (files.length > 8 ? ", \u2026" : ""));
    for (const x of pics) res = await api("/api/roblox/sky-upload", { raw: await toSkyPng(x), filename: "sky.png", face: sideOf(x.name) });
    return res;
  };
  const pickPack = (folder) => {
    const f = el("input", { type: "file", style: { display: "none" } });
    if (folder) f.setAttribute("webkitdirectory", ""); else { f.accept = ".zip,.tex,.dds,image/*"; f.multiple = true; }
    f.addEventListener("change", async () => { if (!f.files.length) return; try { toast("Importing\u2026"); const res = await sendPack([...f.files]); await rbxRefresh(); if (!res.many) skyDone(res); } catch (e) { fail(e); } });
    f.click();
  };
  const saveName = el("input", { type: "text", placeholder: "Name for this sky", maxlength: "40", "aria-label": "Sky name", style: { flex: "1", "min-width": "140px" } });
  const lib = r.sky_library || [];
  put(v, el("div", { class: "page-head" }, el("div", { class: "grow" }, el("h1", {}, "Sky"), el("p", {}, "Change Roblox's default sky. It applies to every game that uses the default sky, the next time Roblox starts.")),
      el("button", { class: "btn", disabled: !r.sky_folder, onclick: () => rbxPost("/api/roblox/open-folder", { what: "sky" }).catch(fail) }, icon("folder"), "Open sky folder")),
    el("div", { class: "section card" }, el("h2", {}, sky.set ? "Custom sky is on" : "Using Roblox's own sky"),
      el("p", { class: "muted small", style: { margin: "4px 0 14px" } }, "Games that build their own sky keep it. Any picture works: Nova cuts a centered square and converts it to the format Roblox uses. Restart Roblox to see a change."),
      el("div", { class: "row", style: { "flex-wrap": "wrap", gap: "14px" } }, color, el("button", { class: "btn", onclick: async () => { try { const res = await rbxPost("/api/roblox/sky/color", { color: color.value }); await rbxRefresh(); skyDone(res); } catch (e) { fail(e); } } }, "Use this color"),
        el("button", { class: "btn", onclick: () => pick("all") }, icon("plus"), "Use one picture for every side"),
        el("button", { class: "btn", onclick: () => pickPack(false) }, icon("plus"), "Import sky pack (.zip or files)"),
        el("button", { class: "btn", onclick: () => pickPack(true) }, icon("folder"), "Import sky folder"),
        sky.set ? el("button", { class: "btn ghost", onclick: async () => { try { await rbxPost("/api/roblox/sky/clear"); await rbxRefresh(); toast("Back to Roblox's own sky.", "ok"); } catch (e) { fail(e); } } }, "Back to the default sky") : null),
      el("div", { class: "muted small", style: { margin: "16px 0 8px" } }, "Ready-made skies"),
      el("div", { class: "row", style: { "flex-wrap": "wrap", gap: "10px" } }, ...Object.entries(r.sky_presets || {}).map(([k, name]) => el("button", { class: "btn sm", onclick: async () => { try { const res = await rbxPost("/api/roblox/sky/preset", { name: k }); await rbxRefresh(); skyDone(res); } catch (e) { fail(e); } } }, name))),
      el("div", { class: "row", style: { "flex-wrap": "wrap", gap: "10px", "margin-top": "14px" } }, el("button", { class: "btn sm", disabled: !r.version, onclick: apply }, icon("refresh"), "Apply again"), el("button", { class: "btn sm", disabled: !r.version, onclick: check }, "Check sky"))),
    el("div", { class: "section card" }, el("h2", {}, "Your skies"),
      el("p", { class: "muted small", style: { margin: "4px 0 10px" } }, "Every sky pack you import is kept here. Pick one and it's your sky. You can import many at once: choose a folder that holds one folder per sky, or select several .zip files."),
      lib.length ? el("div", {}, ...lib.map((n) => el("div", { class: "toggle-row" }, el("div", { class: "t" }, n),
        el("div", { class: "row", style: { gap: "8px" } },
          el("button", { class: "btn sm primary", onclick: async () => { try { const res = await rbxPost("/api/roblox/sky-lib/use", { name: n }); await rbxRefresh(); skyDone(res); } catch (e) { fail(e); } } }, "Use"),
          el("button", { class: "btn sm ghost", "aria-label": "Remove " + n, onclick: async () => { try { await rbxPost("/api/roblox/sky-lib/delete", { name: n }); await rbxRefresh(); } catch (e) { fail(e); } } }, "Remove"))))) : el("p", { class: "muted small" }, "Nothing here yet. Import a sky pack to start your list."),
      sky.set ? el("div", { class: "row", style: { gap: "10px", "margin-top": "12px", "flex-wrap": "wrap" } }, saveName, el("button", { class: "btn sm", onclick: async () => { try { await rbxPost("/api/roblox/sky-lib/save", { name: saveName.value }); await rbxRefresh(); toast("Saved to Your skies.", "ok"); } catch (e) { fail(e); } } }, "Save current sky")) : null),
    el("div", { class: "section card" }, el("h2", {}, "Skybox fix"),
      toggleRow("Skybox fix", "Replaces Roblox's cached sky mesh with a corrected one so your sky shows in every game, not only some. It's on automatically while you use a custom sky and removed when you go back to the default. " + (r.skyfix.on ? "It is installed right now." : "It isn't installed right now."), !!r.skyfix.enabled, async (on) => { try { await rbxPost("/api/roblox/skyfix", { on }); await rbxRefresh(); toast(on ? "Skybox fix is on." : "Skybox fix is off.", "ok"); } catch (e) { fail(e); } })),
    el("div", { class: "section card" }, el("h2", {}, "Each side"), el("div", { style: { height: "8px" } }),
      ...SKY_SIDES.map(([k, name]) => el("div", { class: "toggle-row" }, el("div", { class: "t" }, name, el("small", {}, sky.faces[k] ? "Your picture" : "Roblox's own")),
        el("button", { class: "btn sm", onclick: () => pick(k) }, icon("plus"), sky.faces[k] ? "Change" : "Import")))),
    !r.version ? el("p", { class: "muted small", style: { margin: "12px 0 0" } }, "Nova couldn't find Roblox on this PC yet, so the sky applies once it does.") : null);
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
  put(v, el("div", { class: "page-head" }, el("div", { class: "grow" }, el("h1", {}, "FastFlags"), el("p", {}, "Roblox client settings, like the FPS limit and graphics options. They apply the next time Roblox starts."))),
    el("div", { class: "section card" }, el("h2", {}, "High optimization"),
      toggleRow(r.presets.max_perf.name, r.presets.max_perf.desc + " Roblox decides which flags it honors, so fog and similar effects may still show in some games.", !!r.preset_on.max_perf, async (on) => { try { await rbxPost("/api/roblox/preset", { id: "max_perf", on }); await rbxRefresh(); toast(on ? "High optimization is on. It applies the next time Roblox starts." : "High optimization is off.", "ok"); } catch (e) { fail(e); } })),
    el("div", { class: "section card" }, el("h2", {}, "Presets"), el("div", { style: { height: "6px" } }),
      ...Object.entries(r.presets).filter(([id]) => id !== "max_perf").map(([id, p]) => toggleRow(p.name, p.desc, !!r.preset_on[id], async (on) => { try { await rbxPost("/api/roblox/preset", { id, on }); await rbxRefresh(); } catch (e) { fail(e); } }))),
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
  put(v, el("div", { class: "page-head" }, el("div", { class: "grow" }, el("h1", {}, "Mods"), el("p", {}, "Change how Roblox looks and sounds, like cursors, skies, fonts and sounds. Mods are copied over Roblox's files when it starts.")),
      el("button", { class: "btn", onclick: () => rbxPost("/api/roblox/open-folder", { what: "mods" }).catch(fail) }, icon("folder"), "Open Mods folder"),
      el("button", { class: "btn primary", onclick: pick }, icon("plus"), "Import mod (.zip)")),
    r.mods.length ? el("div", { class: "section card" }, ...r.mods.map((m) => el("div", { class: "toggle-row" },
      el("div", { class: "t" }, m.name, el("small", {}, `${m.files} file${m.files === 1 ? "" : "s"}`)),
      el("button", { class: "btn ghost sm", "aria-label": "Delete " + m.name, onclick: () => confirmDialog("Delete " + m.name + "?", "This removes the mod from your Mods folder.", "Delete", async () => { try { await rbxPost("/api/roblox/mods/delete", { name: m.name }); await rbxRefresh(); } catch (e) { fail(e); } }) }, icon("trash")),
      el("label", { class: "switch" }, el("input", { type: "checkbox", checked: m.enabled, "aria-label": "Enable " + m.name, onchange: async (e) => { try { await rbxPost("/api/roblox/mods/toggle", { name: m.name, enabled: e.target.checked }); await loadState(); } catch (x) { fail(x); } } }), el("i"))))) :
      el("div", { class: "empty" }, el("h2", {}, "No mods yet"), el("p", {}, "Import a .zip whose folders match Roblox's (for example content/textures or content/sounds). Nova puts the files in place when Roblox starts and puts the originals back if you switch a mod off.")),
    el("p", { class: "muted small", style: { margin: "14px 0 0" } }, "Stick to looks and sounds. Mods can break when Roblox updates, and changes that give an unfair advantage in games can get your account banned."));
}
