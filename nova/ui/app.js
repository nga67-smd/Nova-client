/* Nova Launcher UI. Plain JS, no dependencies. All text goes through el()/text nodes, never innerHTML,
   because mod names and descriptions come from the internet. */
"use strict";

// ------------------------------------------------------------------ helpers
const $ = (s, r = document) => r.querySelector(s);

function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") n.className = v;
    else if (k === "style" && typeof v === "object") for (const [a, b] of Object.entries(v)) n.style.setProperty(a, b);
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "html") throw new Error("html attr is not allowed");
    else n.setAttribute(k, v === true ? "" : v);
  }
  const add = (c) => {
    if (c == null || c === false) return;
    if (Array.isArray(c)) return c.forEach(add);
    n.append(c.nodeType ? c : document.createTextNode(String(c)));
  };
  kids.forEach(add);
  return n;
}

const ICONS = {
  library: "M4 5h7v7H4zM13 5h7v7h-7zM4 14h7v6H4zM13 14h7v6h-7z",
  discover: "M11 4a7 7 0 1 0 4.2 12.6l4.4 4.4 1.4-1.4-4.4-4.4A7 7 0 0 0 11 4zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10z",
  profiles: "M12 12a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9zm0 2c-4.4 0-8 2.2-8 5v2h16v-2c0-2.8-3.6-5-8-5z",
  settings: "M19.4 13a7.6 7.6 0 0 0 0-2l2.1-1.6-2-3.4-2.5 1a7.6 7.6 0 0 0-1.7-1L15 3h-4l-.4 3a7.6 7.6 0 0 0-1.7 1l-2.5-1-2 3.4L6.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6 2 3.4 2.5-1c.5.4 1.1.7 1.7 1l.4 3h4l.4-3c.6-.3 1.2-.6 1.7-1l2.5 1 2-3.4zM12 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z",
  play: "M8 5v14l11-7z", stop: "M7 7h10v10H7z", plus: "M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6z",
  folder: "M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  trash: "M6 7h12l-1 13H7zM9 4h6l1 2H8z", copy: "M8 8h11v13H8zM5 3h11v3H8v10H5z",
  download: "M11 4h2v8l3-3 1.4 1.4L12 16l-5.4-5.6L8 9l3 3zM5 18h14v2H5z",
  refresh: "M12 5a7 7 0 0 1 6.3 4H21l-3.5 4L14 9h2.5A5 5 0 1 0 17 15l1.8 1A7 7 0 1 1 12 5z",
};
function icon(name) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("fill", "currentColor"); s.setAttribute("aria-hidden", "true");
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", ICONS[name] || ""); s.append(p); return s;
}

async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", headers: { "X-Nova-Token": window.NOVA_TOKEN } };
  if (opts.body !== undefined) { init.body = JSON.stringify(opts.body); init.headers["Content-Type"] = "application/json"; }
  if (opts.raw) { init.body = opts.raw; init.headers["X-Filename"] = opts.filename || "file"; init.method = "POST"; }
  let res;
  try { res = await fetch(path, init); } catch { throw new Error("Lost connection to Nova's local service. Restart the launcher."); }
  let data = {};
  try { data = await res.json(); } catch { /* ignore */ }
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function toast(msg, kind = "") {
  const t = el("div", { class: "toast " + kind, role: "status" }, msg);
  $("#toasts").append(t);
  setTimeout(() => t.remove(), kind === "err" ? 6500 : 3200);
}
const fail = (e) => toast(e.message || String(e), "err");

function fmtNum(n) { return n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(1) + "K" : String(n); }
function fmtMem(mb) { return mb % 1024 === 0 ? (mb / 1024) + " GB" : (mb / 1024).toFixed(1) + " GB"; }
function fmtTime(s) { if (!s) return "Not played yet"; const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60); return h ? `${h} h ${m} min` : `${m} min`; }
function ago(ts) {
  if (!ts) return "Never played";
  const d = Math.floor(Date.now() / 1000 - ts);
  if (d < 90) return "Played just now"; if (d < 3600) return `Played ${Math.floor(d / 60)} min ago`;
  if (d < 86400) return `Played ${Math.floor(d / 3600)} h ago`; return `Played ${Math.floor(d / 86400)} d ago`;
}
const LOADER_NAMES = { vanilla: "Vanilla", fabric: "Fabric", quilt: "Quilt", forge: "Forge", neoforge: "NeoForge", optifine: "OptiFine", custom: "Custom" };
const ICON_CHOICES = ["✦", "⚔", "⛏", "🌌", "🔮", "🧪", "🏰", "🐉", "🚀", "🌿", "🔥", "❄", "⚡", "🧭", "🎮", "💎", "🛡", "🌙"];

// ------------------------------------------------------------------ state
const S = { data: null, page: "library", inst: null, tab: "overview", tasks: [], running: {}, taskHandlers: {}, logSince: {}, logTimer: null };

async function loadState() {
  S.data = await api("/api/state");
  applyTheme();
  renderRail();
}

function applyTheme() {
  const s = S.data.settings, r = document.documentElement;
  r.style.setProperty("--accent", s.accent); r.style.setProperty("--accent2", s.accent2);
  r.style.setProperty("--radius", s.radius + "px"); r.style.setProperty("--scale", s.font_scale / 100);
  r.dataset.surface = s.surface; r.dataset.density = s.density;
  r.dataset.glow = s.glow ? "on" : "off"; r.dataset.anim = s.animations ? "on" : "off"; r.dataset.stars = s.starfield ? "on" : "off";
  stars.enabled = !!s.starfield;
}

const instById = (id) => S.data.instances.find((i) => i.id === id);

// ------------------------------------------------------------------ rail
const NAV = [["library", "Library", "library"], ["discover", "Discover", "discover"], ["profiles", "Profiles", "profiles"], ["settings", "Settings", "settings"]];
function renderRail() {
  const nav = $("#nav"); nav.replaceChildren();
  for (const [id, label, ic] of NAV) {
    nav.append(el("button", { "aria-current": (S.page === id || (S.page === "instance" && id === "library")) ? "page" : false, onclick: () => go(id) }, icon(ic), el("span", {}, label)));
  }
  const acc = S.data.accounts.find((a) => a.id === S.data.selected_account) || S.data.accounts[0];
  const p = $("#profile"); p.replaceChildren();
  p.onclick = () => go("profiles");
  if (acc) p.append(el("div", { class: "avatar" }, acc.username[0].toUpperCase()), el("div", { class: "meta" }, el("div", { class: "nm" }, acc.username), el("div", { class: "sub" }, acc.type === "microsoft" ? "Microsoft account" : "Offline profile")));
  else p.append(el("div", { class: "avatar" }, "+"), el("div", { class: "meta" }, el("div", { class: "nm" }, "Add a profile"), el("div", { class: "sub" }, "Needed to play")));
  $("#ver").textContent = "Nova " + S.data.version;
}

function go(page, inst, tab) {
  S.page = page; if (inst !== undefined) S.inst = inst; if (tab) S.tab = tab;
  stopLogs(); renderRail(); render(); $("#view").scrollTop = 0;
}

async function render() {
  const v = $("#view"); v.replaceChildren();
  try {
    const fn = { library: pageLibrary, discover: pageDiscover, profiles: pageProfiles, settings: pageSettings, instance: pageInstance }[S.page];
    await fn(v);
  } catch (e) { v.replaceChildren(el("div", { class: "empty" }, el("h2", {}, "Something went wrong"), el("p", {}, e.message))); }
}

// ------------------------------------------------------------------ tasks & polling
// Tell the service the window is closing so Nova can quit promptly (a reload cancels this with its next ping).
window.addEventListener("pagehide", () => { try { fetch("/api/bye", { method: "POST", headers: { "X-Nova-Token": window.NOVA_TOKEN }, keepalive: true }); } catch {} });

function runTask(taskId, onDone) { S.taskHandlers[taskId] = onDone; poll(); }

async function poll() {
  try {
    const r = await api("/api/ping");
    S.tasks = r.tasks; S.running = Object.fromEntries(r.running.map((g) => [g.instance, g]));
    renderTray();
    for (const t of r.tasks) {
      const h = S.taskHandlers[t.id];
      if (h && t.status !== "running") { delete S.taskHandlers[t.id]; h(t); }
    }
    syncLaunchState();
  } catch { /* transient */ }
}
setInterval(poll, 1000);

function renderTray() {
  const tray = $("#tray");
  const shown = S.tasks.filter((t) => t.status === "running" || t.status === "error" || (t.status === "done" && t.kind === "launch" && false));
  tray.replaceChildren(...shown.map((t) => el("div", { class: "job" },
    el("div", { class: "t" }, el("span", {}, t.title), t.status === "error" ? el("button", { class: "btn ghost sm", onclick: () => api(`/api/tasks/${t.id}/dismiss`, { method: "POST" }).then(poll) }, "Dismiss") : el("span", { class: "muted small" }, Math.round(t.progress * 100) + "%")),
    el("div", { class: "m" + (t.status === "error" ? " err" : "") }, t.status === "error" ? t.error : t.message),
    t.status === "running" ? el("div", { class: "bar" }, el("i", { style: { width: Math.round(t.progress * 100) + "%" } })) : null)));
}

function launchTaskFor(id) { return S.tasks.find((t) => t.kind === "launch" && t.status === "running" && t.title.endsWith(instById(id)?.name || "\0")); }
function syncLaunchState() {
  document.querySelectorAll("[data-play]").forEach((b) => {
    const id = b.dataset.play, running = !!S.running[id] && ["starting", "running"].includes(S.running[id].status), t = launchTaskFor(id);
    b.classList.toggle("running", running); b.classList.toggle("busy", !!t && !running);
    b.style.setProperty("--p", t ? Math.round(t.progress * 100) : 0);
    b.title = running ? "Stop game" : t ? t.message : "Play";
    b.replaceChildren(icon(running ? "stop" : "play"));
  });
}

async function playOrStop(id) {
  const running = S.running[id] && ["starting", "running"].includes(S.running[id].status);
  try {
    if (running) { await api(`/api/instances/${id}/kill`, { method: "POST" }); toast("Stopping the game…"); return; }
    if (launchTaskFor(id)) return;
    if (!S.data.accounts.length) { toast("Add a player profile first.", "err"); go("profiles"); return; }
    const r = await api(`/api/instances/${id}/launch`, { method: "POST" });
    runTask(r.task, async (t) => {
      if (t.status === "done") {
        toast("Game started. Have fun!", "ok");
        if (S.data.settings.show_console_on_launch) go("instance", id, "console");
        if (!S.data.settings.keep_launcher_open) { /* user chose to hide: nothing else to do in a browser window */ }
      }
      await loadState();
    });
    poll();
  } catch (e) { fail(e); }
}

// ------------------------------------------------------------------ library
function tile(i) {
  const g = S.running[i.id];
  const play = el("button", { class: "playbtn", "data-play": i.id, "aria-label": "Play " + i.name, onclick: (e) => { e.stopPropagation(); playOrStop(i.id); } }, icon("play"));
  return el("div", { class: "tile", role: "button", tabindex: "0", style: { "--c": i.color }, onclick: () => go("instance", i.id, "overview"), onkeydown: (e) => { if (e.key === "Enter") go("instance", i.id, "overview"); } },
    el("div", { class: "art" }, el("span", {}, i.icon)),
    el("div", { class: "play" }, play),
    el("div", { class: "body" },
      el("div", { class: "name" }, i.name),
      el("div", { class: "meta" }, el("span", { class: "chip" }, LOADER_NAMES[i.loader] || i.loader), el("span", { class: "chip plain" }, i.mc_version || "custom"), i.mod_count ? el("span", { class: "chip plain" }, i.mod_count + " mods") : null),
      el("div", { class: "foot" }, i.running ? "Running now" : ago(i.last_played))));
}
function listRow(i) {
  return el("div", { class: "list-row", role: "button", tabindex: "0", style: { "--c": i.color }, onclick: () => go("instance", i.id, "overview") },
    el("div", { class: "ic" }, i.icon), el("div", { class: "grow" }, el("b", {}, i.name), el("div", { class: "muted small" }, `${LOADER_NAMES[i.loader]} · ${i.mc_version || "custom"} · ${fmtMem(i.memory_max)}`)),
    el("span", { class: "muted small" }, ago(i.last_played)),
    el("button", { class: "playbtn", "data-play": i.id, "aria-label": "Play " + i.name, onclick: (e) => { e.stopPropagation(); playOrStop(i.id); } }, icon("play")));
}

async function pageLibrary(v) {
  const list = S.data.instances, view = S.data.settings.library_view;
  v.append(el("div", { class: "page-head" },
    el("div", { class: "grow" }, el("h1", {}, "Library"), el("p", {}, list.length ? `${list.length} instance${list.length === 1 ? "" : "s"}, each with its own mods, settings and saves.` : "Instances keep your mods, settings and worlds separate.")),
    el("div", { class: "seg", role: "group", "aria-label": "Layout" }, ...["grid", "list"].map((m) => el("button", { "aria-pressed": String(view === m), onclick: () => saveSettings({ library_view: m }).then(render) }, m === "grid" ? "Grid" : "List"))),
    el("button", { class: "btn", onclick: importPackDialog }, icon("download"), "Import pack"),
    el("button", { class: "btn primary", onclick: () => createDialog() }, icon("plus"), "New instance")));
  if (!list.length) {
    v.append(el("div", { class: "empty" }, el("svg", { class: "big-nova", viewBox: "0 0 64 64" }), el("h2", {}, "Create your first instance"),
      el("p", {}, "Pick a Minecraft version and a loader like Fabric or Forge. Nova can add a tuned set of performance mods in one click."),
      el("button", { class: "btn primary", onclick: () => createDialog() }, icon("plus"), "New instance")));
    const svg = v.querySelector(".big-nova"); svg.innerHTML = '<use href="/static/nova.svg#nova"/>';
    return;
  }
  v.append(view === "grid" ? el("div", { class: "grid" }, list.map(tile)) : el("div", { class: "stack" }, list.map(listRow)));
  syncLaunchState();
}

async function saveSettings(patch) { S.data.settings = await api("/api/settings", { method: "POST", body: patch }); applyTheme(); return S.data.settings; }

// ------------------------------------------------------------------ modals
function modal(title, body, actions, opts = {}) {
  const root = $("#modal-root"), prevFocus = document.activeElement;
  const close = () => { root.replaceChildren(); document.removeEventListener("keydown", onKey); prevFocus && prevFocus.focus && prevFocus.focus(); };
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  const m = el("div", { class: "modal", role: "dialog", "aria-modal": "true", "aria-label": title, style: opts.wide ? { width: "min(760px,100%)" } : {} }, el("h2", {}, title), body, el("div", { class: "actions" }, actions(close)));
  root.replaceChildren(el("div", { class: "scrim", onmousedown: (e) => { if (e.target.classList.contains("scrim")) close(); } }, m));
  const first = m.querySelector("input,select,textarea"); if (first) first.focus();
  return close;
}
function confirmDialog(title, msg, label, onYes, danger = true) {
  modal(title, el("p", { class: "muted" }, msg), (close) => [el("button", { class: "btn", onclick: close }, "Cancel"), el("button", { class: "btn " + (danger ? "danger" : "primary"), onclick: () => { close(); onYes(); } }, label)]);
}
function field(label, input, hint) { return el("div", { class: "field" }, el("label", {}, label), input, hint ? el("div", { class: "hint" }, hint) : null); }
function select(options, value, onchange) {
  const s = el("select", {}, options.map(([v, l]) => el("option", { value: v, selected: v === value }, l)));
  if (onchange) s.addEventListener("change", () => onchange(s.value)); return s;
}
function toggleRow(title, sub, checked, onchange) {
  const cb = el("input", { type: "checkbox", checked, "aria-label": title }); cb.addEventListener("change", () => onchange(cb.checked));
  return el("div", { class: "toggle-row" }, el("div", { class: "t" }, title, sub ? el("small", {}, sub) : null), el("label", { class: "switch" }, cb, el("i")));
}

// ---- create instance
let versionCache = null;
async function createDialog() {
  const st = { name: "", mc: "", loader: "fabric", loaderVersion: "", showSnap: false, icon: ICON_CHOICES[0], color: S.data.settings.accent, optimize: true, versions: [], lv: [], supported: null, busy: false };
  const body = el("div", { class: "stack" });
  const loadVersions = async () => {
    const r = await api("/api/versions?types=" + (st.showSnap ? "release,snapshot" : "release"));
    st.versions = r.versions; if (!st.mc || !st.versions.some((x) => x.id === st.mc)) st.mc = r.latest.release || st.versions[0]?.id || "";
  };
  const loadLoader = async () => {
    st.lv = []; st.loaderVersion = ""; st.supported = null;
    if (["fabric", "quilt", "forge", "neoforge"].includes(st.loader)) {
      try { st.supported = (await api("/api/supported?loader=" + st.loader)).games; } catch { st.supported = null; }
      if (st.mc) { try { st.lv = (await api(`/api/loader-versions?loader=${st.loader}&mc=${encodeURIComponent(st.mc)}`)).versions; } catch { st.lv = []; } }
      st.loaderVersion = (st.lv.find((x) => x.stable) || st.lv[0] || {}).version || "";
    }
  };
  const draw = () => {
    const unsupported = ["fabric", "quilt", "forge", "neoforge"].includes(st.loader) && st.mc && st.lv.length === 0;
    const nameIn = el("input", { type: "text", placeholder: "My survival world", value: st.name, maxlength: "60" });
    nameIn.addEventListener("input", () => { st.name = nameIn.value; });
    const loaderSeg = el("div", { class: "seg", role: "group", "aria-label": "Mod loader" }, ["vanilla", "fabric", "quilt", "forge", "neoforge", "optifine"].map((l) => el("button", { "aria-pressed": String(st.loader === l), onclick: async () => { st.loader = l; await loadLoader(); draw(); } }, LOADER_NAMES[l])));
    const snap = toggleRow("Show snapshots", null, st.showSnap, async (c) => { st.showSnap = c; await loadVersions(); await loadLoader(); draw(); });
    body.replaceChildren(
      field("Name", nameIn),
      field("Minecraft version", select(st.versions.map((x) => [x.id, x.id + (x.type !== "release" ? " (snapshot)" : "")]), st.mc, async (v) => { st.mc = v; await loadLoader(); draw(); })),
      snap,
      field("Mod loader", loaderSeg, st.loader === "optifine" ? "You'll pick the OptiFine installer from your downloads after creating the instance, because OptiFine can't be downloaded automatically." : null),
      ["fabric", "quilt", "forge", "neoforge"].includes(st.loader) ? field("Loader version", unsupported ? el("div", { class: "notice warn" }, `${LOADER_NAMES[st.loader]} has no build for Minecraft ${st.mc} yet. Pick another version.`) : select(st.lv.map((x) => [x.version, x.version + (x.stable ? "" : " (beta)")]), st.loaderVersion, (v) => { st.loaderVersion = v; })) : null,
      ["fabric", "quilt", "forge", "neoforge"].includes(st.loader) && !unsupported ? toggleRow("Add performance mods", st.loader === "forge" || st.loader === "neoforge" ? "Embeddium, FerriteCore, ModernFix and more." : "Sodium, Lithium, FerriteCore, ModernFix and more.", st.optimize, (c) => { st.optimize = c; }) : null,
      el("div", { class: "field" }, el("label", {}, "Icon"), el("div", { class: "emoji-pick" }, ICON_CHOICES.map((e) => el("button", { type: "button", "aria-pressed": String(st.icon === e), "aria-label": "Icon " + e, onclick: () => { st.icon = e; draw(); } }, e)))));
  };
  await loadVersions(); await loadLoader(); draw();
  modal("New instance", body, (close) => [el("button", { class: "btn", onclick: close }, "Cancel"),
    el("button", { class: "btn primary", onclick: async () => {
      if (st.busy) return;
      if (["fabric", "quilt", "forge", "neoforge"].includes(st.loader) && !st.lv.length) { toast(`${LOADER_NAMES[st.loader]} isn't available for ${st.mc}.`, "err"); return; }
      st.busy = true;
      try {
        const name = st.name.trim() || `${LOADER_NAMES[st.loader]} ${st.mc}`;
        const inst = await api("/api/instances", { method: "POST", body: { name, mc_version: st.mc, loader: st.loader, loader_version: st.loaderVersion, icon: st.icon, color: st.color, memory_auto: true } });
        close(); await loadState();
        if (st.optimize && ["fabric", "quilt", "forge", "neoforge"].includes(st.loader)) {
          const slugs = (await api(`/api/instances/${inst.id}/optimization`)).pack.filter((p) => p.default).map((p) => p.slug);
          const r = await api(`/api/instances/${inst.id}/optimization/install-pack`, { method: "POST", body: { slugs } });
          runTask(r.task, (t) => { if (t.status === "done") { const n = t.result?.installed?.length || 0, sk = t.result?.skipped?.length || 0; toast(`Added ${n} performance mods${sk ? ` (${sk} not available for ${st.mc})` : ""}.`, "ok"); } loadState(); });
        }
        go("instance", inst.id, "overview");
      } catch (e) { fail(e); st.busy = false; }
    } }, "Create instance")]);
}

function importPackDialog() {
  const input = el("input", { type: "file", accept: ".novapack,.mrpack,.zip" });
  modal("Import pack", el("div", { class: "stack" }, el("p", { class: "muted" }, "Choose a Nova pack (.novapack) or a Modrinth pack (.mrpack). Mods are downloaded for you."), input),
    (close) => [el("button", { class: "btn", onclick: close }, "Cancel"), el("button", { class: "btn primary", onclick: async () => {
      const f = input.files[0]; if (!f) { toast("Choose a file first.", "err"); return; }
      try { const r = await api("/api/import-upload", { raw: f, filename: f.name }); close(); runTask(r.task, async (t) => { await loadState(); if (t.status === "done") { toast("Pack imported.", "ok"); go("instance", t.result.instance, "overview"); } }); poll(); } catch (e) { fail(e); }
    } }, "Import")]);
}

// ------------------------------------------------------------------ instance page
const TABS = [["overview", "Overview"], ["mods", "Mods"], ["content", "Shaders & packs"], ["optimize", "Optimize"], ["settings", "Settings"], ["console", "Console"]];

async function pageInstance(v) {
  const i = instById(S.inst);
  if (!i) { go("library"); return; }
  const rootEl = el("div", { style: { "--c": i.color } });
  v.append(rootEl);
  rootEl.append(
    el("div", { class: "crumb" }, el("button", { onclick: () => go("library") }, "Library"), " / ", i.name),
    el("div", { class: "inst-head" }, el("div", { class: "ic" }, i.icon),
      el("div", { class: "grow" }, el("h1", {}, i.name), el("div", { class: "row", style: { gap: "8px", "margin-top": "6px" } }, el("span", { class: "chip" }, LOADER_NAMES[i.loader]), el("span", { class: "chip plain" }, i.mc_version || "custom"), el("span", { class: "chip plain" }, fmtMem(i.memory_max) + " RAM"))),
      el("button", { class: "btn ghost", onclick: () => api(`/api/instances/${i.id}/open-folder`, { method: "POST", body: { sub: "" } }).catch(fail) }, icon("folder"), "Open folder"),
      el("button", { class: "playbtn lg", "data-play": i.id, "aria-label": "Play", onclick: () => playOrStop(i.id) }, icon("play"))),
    el("div", { class: "tabs", role: "tablist" }, TABS.map(([id, label]) => el("button", { role: "tab", "aria-selected": String(S.tab === id), onclick: () => { stopLogs(); S.tab = id; render(); } }, label))));
  const pane = el("div"); rootEl.append(pane);
  const fn = { overview: tabOverview, mods: tabMods, content: tabContent, optimize: tabOptimize, settings: tabSettings, console: tabConsole }[S.tab];
  await fn(pane, i);
  syncLaunchState();
}

async function tabOverview(p, i) {
  const o = await api(`/api/instances/${i.id}/optimization`);
  p.append(el("div", { class: "stats" },
    el("div", { class: "stat" }, el("b", {}, fmtTime(i.playtime_s)), el("span", {}, "Time played")),
    el("div", { class: "stat" }, el("b", {}, String(o.mod_count)), el("span", {}, "Mods enabled")),
    el("div", { class: "stat" }, el("b", {}, fmtMem(i.memory_max)), el("span", {}, "Memory limit")),
    el("div", { class: "stat" }, el("b", {}, o.game_dir_size), el("span", {}, "Disk used"))));
  const quick = [["Mods", "mods"], ["Optimize", "optimize"], ["Settings", "settings"]];
  const notes = el("textarea", { placeholder: "Notes about this instance…", style: { "font-family": "var(--font)", "min-height": "110px" } }, i.notes || "");
  let t; notes.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => api(`/api/instances/${i.id}`, { method: "POST", body: { notes: notes.value } }).then(loadState).catch(fail), 600); });
  const advice = [];
  if (i.loader !== "vanilla" && i.loader !== "custom" && o.pack.length && o.pack.filter((x) => x.default && !x.installed).length > 2) advice.push(el("div", { class: "notice" }, el("div", { class: "row" }, el("div", { class: "grow" }, el("b", {}, "Speed this instance up"), el("div", { class: "muted small" }, "Install a tuned set of performance mods in one click.")), el("button", { class: "btn primary", onclick: () => go("instance", i.id, "optimize") }, "Open Optimize"))));
  p.append(...advice, el("div", { style: { height: "18px" } }), el("div", { class: "section" }, el("h2", {}, "Notes"), el("div", { style: { height: "10px" } }), notes),
    el("div", { class: "row" }, el("button", { class: "btn", onclick: async () => { try { const d = await api(`/api/instances/${i.id}/duplicate`, { method: "POST", body: {} }); await loadState(); toast("Duplicated."); go("instance", d.id, "overview"); } catch (e) { fail(e); } } }, icon("copy"), "Duplicate"),
      el("button", { class: "btn", onclick: async () => { try { const r = await api(`/api/instances/${i.id}/export`, { method: "POST", body: {} }); toast(`Exported ${r.size} to ${r.path}`, "ok"); } catch (e) { fail(e); } } }, icon("download"), "Export pack"),
      el("div", { class: "grow" }),
      el("button", { class: "btn danger", onclick: () => confirmDialog("Delete this instance?", `“${i.name}” and everything inside it, including worlds, will be permanently deleted.`, "Delete instance", async () => { try { await api(`/api/instances/${i.id}`, { method: "DELETE" }); await loadState(); go("library"); toast("Instance deleted."); } catch (e) { fail(e); } }) }, icon("trash"), "Delete")));
}

// ---- mods
async function tabMods(p, i) {
  const [list, ups] = await Promise.all([api(`/api/instances/${i.id}/mods?type=mod`), Promise.resolve(null)]);
  const canMods = !["vanilla", "custom"].includes(i.loader) || i.loader === "custom";
  p.append(el("div", { class: "row", style: { "margin-bottom": "16px" } },
    el("div", { class: "grow" }, el("h2", {}, `${list.items.length} mod${list.items.length === 1 ? "" : "s"}`), el("div", { class: "muted small" }, i.loader === "vanilla" ? "Vanilla can't load mods. Change the loader in Settings." : "Disabled mods stay on disk but won't load.")),
    el("button", { class: "btn", onclick: () => api(`/api/instances/${i.id}/open-folder`, { method: "POST", body: { sub: "mods" } }).catch(fail) }, icon("folder"), "Mods folder"),
    el("button", { class: "btn", id: "chk", onclick: async (e) => { e.target.disabled = true; try { const r = await api(`/api/instances/${i.id}/mods/updates`); if (!r.updates.length) toast("Everything is up to date.", "ok"); else confirmDialog(`${r.updates.length} update${r.updates.length === 1 ? "" : "s"} available`, r.updates.map((u) => `${u.file} → ${u.new_version}`).join("\n"), "Update all", async () => { const t = await api(`/api/instances/${i.id}/mods/update-all`, { method: "POST", body: {} }); runTask(t.task, () => render()); poll(); }, false); } catch (x) { fail(x); } e.target.disabled = false; } }, icon("refresh"), "Check updates"),
    el("button", { class: "btn primary", onclick: () => { S.discover.inst = i.id; go("discover"); } }, icon("plus"), "Add mods")));
  if (!list.items.length) { p.append(el("div", { class: "empty" }, el("h2", {}, "No mods yet"), el("p", {}, "Browse Modrinth for mods that match this instance's version and loader."), el("button", { class: "btn primary", onclick: () => { S.discover.inst = i.id; go("discover"); } }, "Browse mods"))); return; }
  p.append(...list.items.map((m) => itemRow(i, "mod", m)));
}
function itemRow(i, type, m) {
  const thumb = el("div", { class: "thumb", style: m.icon_url ? { "background-image": `url("${m.icon_url.replace(/"/g, "%22")}")` } : {} }, m.icon_url ? "" : "▣");
  const cb = el("input", { type: "checkbox", checked: m.enabled, "aria-label": (m.enabled ? "Disable " : "Enable ") + m.title });
  const row = el("div", { class: "item" + (m.enabled ? "" : " off") }, thumb,
    el("div", { class: "info" }, el("b", {}, m.title), el("span", {}, [m.version, m.file, m.managed ? "" : "added manually"].filter(Boolean).join(" · "))),
    el("label", { class: "switch" }, cb, el("i")),
    el("button", { class: "btn ghost sm", "aria-label": "Remove " + m.title, onclick: () => confirmDialog("Remove " + m.title + "?", "The file will be deleted from this instance.", "Remove", async () => { try { await api(`/api/instances/${i.id}/mods/remove`, { method: "POST", body: { type, file: m.file } }); render(); } catch (e) { fail(e); } }) }, icon("trash")));
  cb.addEventListener("change", async () => { try { const r = await api(`/api/instances/${i.id}/mods/toggle`, { method: "POST", body: { type, file: m.file } }); row.classList.toggle("off", !r.enabled); } catch (e) { fail(e); cb.checked = !cb.checked; } });
  return row;
}

// ---- shaders / resource packs
async function tabContent(p, i) {
  const kinds = [["shader", "Shader packs", "shaderpacks"], ["resourcepack", "Resource packs", "resourcepacks"]];
  for (const [type, label, sub] of kinds) {
    const list = await api(`/api/instances/${i.id}/mods?type=${type}`);
    p.append(el("div", { class: "section" },
      el("div", { class: "row", style: { "margin-bottom": "12px" } }, el("div", { class: "grow" }, el("h2", {}, label), el("div", { class: "muted small" }, type === "shader" ? "Shaders need Iris (Fabric/Quilt) or Oculus (Forge), or OptiFine." : "Applied from Options → Resource Packs in game.")),
        el("button", { class: "btn", onclick: () => api(`/api/instances/${i.id}/open-folder`, { method: "POST", body: { sub } }).catch(fail) }, icon("folder"), "Open folder"),
        el("button", { class: "btn primary", onclick: () => { S.discover.inst = i.id; S.discover.type = type; go("discover"); } }, icon("plus"), "Browse")),
      list.items.length ? list.items.map((m) => itemRow(i, type, m)) : el("div", { class: "muted" }, "Nothing installed.")));
  }
}

// ---- optimize
async function tabOptimize(p, i) {
  const o = await api(`/api/instances/${i.id}/optimization`);
  const ram = S.data.system.ram_mb;
  // memory
  const maxIn = el("input", { type: "range", min: "1024", max: String(Math.max(2048, Math.floor(ram * 0.8 / 256) * 256)), step: "256", value: String(i.memory_max), "aria-label": "Maximum memory" });
  const label = el("b", {}, fmtMem(i.memory_max));
  const fill = el("div", { class: "fill", style: { width: Math.min(100, i.memory_max / ram * 100) + "%" } });
  const bar = el("div", { class: "membar" }, fill, el("div", { class: "rec", title: "Recommended", style: { left: Math.min(100, o.recommend.max / ram * 100) + "%" } }));
  let save; const patch = (b) => { clearTimeout(save); save = setTimeout(async () => { try { await api(`/api/instances/${i.id}`, { method: "POST", body: b }); await loadState(); refreshPreview(); } catch (e) { fail(e); } }, 350); };
  maxIn.addEventListener("input", () => { const mb = +maxIn.value; label.textContent = fmtMem(mb); fill.style.width = Math.min(100, mb / ram * 100) + "%"; patch({ memory_max: mb, memory_min: Math.min(i.memory_min, mb) }); });
  const flags = el("div", { class: "flags" }, o.jvm_preview.join(" "));
  const refreshPreview = async () => { const r = await api("/api/preview-jvm", { method: "POST", body: { ...instById(i.id), java_major: o.java_major_assumed } }); flags.textContent = r.args.join(" "); };

  p.append(el("div", { class: "section card" },
    el("div", { class: "row" }, el("div", { class: "grow" }, el("h2", {}, "Memory"), el("div", { class: "muted small" }, `Your PC has ${fmtMem(ram)}. More isn't always faster: oversized heaps cause longer garbage-collection pauses.`)), label),
    bar, el("div", { class: "row small muted" }, el("span", {}, "1 GB"), el("div", { class: "grow" }), el("span", { style: { color: "var(--good)" } }, `Recommended for ${o.mod_count} mod${o.mod_count === 1 ? "" : "s"}: ${fmtMem(o.recommend.max)}`)),
    el("div", { style: { height: "10px" } }), maxIn,
    el("div", { style: { height: "12px" } }), el("button", { class: "btn sm", onclick: async () => { await api(`/api/instances/${i.id}`, { method: "POST", body: { memory_max: o.recommend.max, memory_min: o.recommend.min } }); await loadState(); render(); toast("Memory set to " + fmtMem(o.recommend.max), "ok"); } }, "Use recommended")));

  // presets
  const presetBox = el("div", { class: "presets" });
  const drawPresets = () => { presetBox.replaceChildren(...Object.entries(S.data.presets).map(([k, pr]) => el("button", { class: "preset", "aria-pressed": String(instById(i.id).jvm_preset === k), onclick: async () => { await api(`/api/instances/${i.id}`, { method: "POST", body: { jvm_preset: k } }); await loadState(); drawPresets(); refreshPreview(); } }, el("b", {}, pr.icon, " ", pr.name), el("p", {}, pr.desc)))); };
  drawPresets();
  p.append(el("div", { class: "section card" }, el("h2", {}, "Java tuning"), el("div", { style: { height: "12px" } }), presetBox, el("div", { style: { height: "14px" } }), el("div", { class: "label", style: { "margin-bottom": "6px" } }, "Arguments Nova will pass to Java"), flags));

  // optimization pack
  if (o.pack.length) {
    const picks = new Set(o.pack.filter((x) => x.default && !x.installed).map((x) => x.slug));
    const rows = o.pack.map((m) => { const cb = el("input", { type: "checkbox", checked: m.installed || picks.has(m.slug), disabled: m.installed }); cb.addEventListener("change", () => cb.checked ? picks.add(m.slug) : picks.delete(m.slug));
      return el("label", { class: "check" }, cb, el("div", { class: "t" }, el("b", {}, m.name), m.installed ? el("span", { class: "chip good", style: { "margin-left": "8px" } }, "Installed") : null, el("small", {}, m.why))); });
    p.append(el("div", { class: "section card" }, el("div", { class: "row" }, el("div", { class: "grow" }, el("h2", {}, "Performance mods"), el("div", { class: "muted small" }, `Chosen for ${LOADER_NAMES[i.loader]}. Mods without a build for ${i.mc_version} are skipped automatically.`)),
      el("button", { class: "btn primary", onclick: async (e) => { if (!picks.size) { toast("Nothing new to install.", ""); return; } e.target.disabled = true; try { const r = await api(`/api/instances/${i.id}/optimization/install-pack`, { method: "POST", body: { slugs: [...picks] } }); runTask(r.task, (t) => { if (t.status === "done") toast(`Installed ${t.result.installed.length} mods` + (t.result.skipped.length ? `, ${t.result.skipped.length} unavailable for ${i.mc_version}` : ""), "ok"); loadState().then(render); }); poll(); } catch (x) { fail(x); e.target.disabled = false; } } }, "Install selected")),
      el("div", { style: { height: "8px" } }), ...rows));
  } else if (i.loader === "vanilla") {
    p.append(el("div", { class: "notice" }, "Vanilla can't run performance mods. Switch this instance to Fabric, Quilt, Forge or NeoForge in Settings to unlock them."));
  }

  // graphics profile
  const prof = S.data.options_profiles, cur = o.options;
  p.append(el("div", { class: "section card" }, el("h2", {}, "Graphics profile"),
    el("div", { class: "muted small", style: { margin: "4px 0 12px" } }, "Rewrites only the video settings in options.txt. Your keybinds and other options stay as they are." + (cur.renderDistance ? ` Currently: render distance ${cur.renderDistance}, max FPS ${cur.maxFps || "?"}.` : "")),
    el("div", { class: "presets" }, Object.entries(prof).map(([k, v]) => el("button", { class: "preset", onclick: async () => { try { const r = await api(`/api/instances/${i.id}/options-profile`, { method: "POST", body: { profile: k } }); toast(`${v.name} applied (${r.changed.length} settings).`, "ok"); } catch (e) { fail(e); } } }, el("b", {}, v.name), el("p", {}, v.desc)))),
    el("div", { style: { height: "10px" } }), toggleRow("Apply this profile every launch", "Useful if you share the instance and settings keep drifting.", !!i.options_profile, async (c) => { await api(`/api/instances/${i.id}`, { method: "POST", body: { options_profile: c ? "balanced" : "" } }); await loadState(); })));

  // cleanup
  const sel = new Set(o.cleanup.filter((c) => c.bytes > 0).map((c) => c.key));
  const human = (b) => b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : b > 1024 ? Math.round(b / 1024) + " KB" : b + " B";
  p.append(el("div", { class: "section card" }, el("div", { class: "row" }, el("div", { class: "grow" }, el("h2", {}, "Clean up"), el("div", { class: "muted small" }, `This instance uses ${o.game_dir_size}. Worlds and screenshots are never touched.`)),
    el("button", { class: "btn", onclick: async () => { try { const r = await api(`/api/instances/${i.id}/cleanup`, { method: "POST", body: { keys: [...sel] } }); toast(`Freed ${r.freed}.`, "ok"); render(); } catch (e) { fail(e); } } }, icon("trash"), "Clean selected")),
    ...o.cleanup.map((c) => { const cb = el("input", { type: "checkbox", checked: sel.has(c.key) }); cb.addEventListener("change", () => cb.checked ? sel.add(c.key) : sel.delete(c.key)); return el("label", { class: "check" }, cb, el("div", { class: "t" }, c.label, el("small", {}, human(c.bytes)))); })));
}

// ---- settings (instance)
async function tabSettings(p, i) {
  const f = { ...i }; const javas = (await api("/api/java")).javas;
  const patchBtn = el("button", { class: "btn primary" }, "Save changes");
  const inp = (key, props = {}) => { const n = el("input", { type: props.type || "text", value: f[key] ?? "", ...props }); n.addEventListener("input", () => { f[key] = props.type === "number" ? +n.value : n.value; }); return n; };
  const colorIn = el("input", { type: "color", value: f.color }); colorIn.addEventListener("input", () => { f.color = colorIn.value; });
  const iconBox = el("div", { class: "emoji-pick" }); const drawIcons = () => iconBox.replaceChildren(...ICON_CHOICES.map((e) => el("button", { type: "button", "aria-pressed": String(f.icon === e), "aria-label": "Icon " + e, onclick: () => { f.icon = e; drawIcons(); } }, e))); drawIcons();
  const mcSel = el("input", { type: "text", value: f.mc_version }); mcSel.addEventListener("input", () => { f.mc_version = mcSel.value.trim(); });
  const envIn = el("textarea", { placeholder: "KEY=value, one per line" }, Object.entries(f.env || {}).map(([k, v]) => `${k}=${v}`).join("\n"));
  envIn.addEventListener("input", () => { f.env = Object.fromEntries(envIn.value.split("\n").map((l) => l.trim()).filter((l) => l.includes("=")).map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1)])); });
  const loaderSel = select(Object.entries(LOADER_NAMES), f.loader, (v) => { f.loader = v; f.loader_version = ""; drawLoaderExtra(); });
  const loaderExtra = el("div", { class: "stack" });
  const drawLoaderExtra = async () => {
    loaderExtra.replaceChildren();
    if (["fabric", "quilt", "forge", "neoforge"].includes(f.loader)) {
      let lv = []; try { lv = (await api(`/api/loader-versions?loader=${f.loader}&mc=${encodeURIComponent(f.mc_version)}`)).versions; } catch { /* offline */ }
      loaderExtra.append(field("Loader version", select([["", "Latest stable (automatic)"], ...lv.map((x) => [x.version, x.version + (x.stable ? "" : " (beta)")])], f.loader_version, (v) => { f.loader_version = v; }), lv.length ? null : `No ${LOADER_NAMES[f.loader]} builds found for ${f.mc_version}.`));
    } else if (f.loader === "optifine") {
      const file = el("input", { type: "file", accept: ".jar" });
      file.addEventListener("change", async () => { if (!file.files[0]) return; try { const r = await api(`/api/instances/${i.id}/optifine-upload`, { raw: file.files[0], filename: file.files[0].name }); f.optifine_jar = r.optifine_jar; toast("OptiFine installer saved.", "ok"); drawLoaderExtra(); } catch (e) { fail(e); } });
      loaderExtra.append(field("OptiFine installer (.jar)", file, f.optifine_jar ? "Using: " + f.optifine_jar.split(/[\\/]/).pop() : "Download it from optifine.net, then choose it here. Nova installs it for you on first launch."));
    } else if (f.loader === "custom") {
      let vs = []; try { vs = (await api("/api/installed-versions")).versions; } catch { /* ignore */ }
      loaderExtra.append(field("Installed version", select([["", "Choose…"], ...vs.map((v) => [v, v])], f.version_id, (v) => { f.version_id = v; })));
    }
  };
  drawLoaderExtra();
  patchBtn.onclick = async () => {
    try { const body = { ...f }; delete body.id; delete body.running; delete body.last_status; delete body.mod_count; await api(`/api/instances/${i.id}`, { method: "POST", body }); await loadState(); toast("Saved.", "ok"); render(); } catch (e) { fail(e); }
  };
  p.append(
    el("div", { class: "section card" }, el("h2", {}, "General"), el("div", { style: { height: "14px" } }), el("div", { class: "fields" }, field("Name", inp("name", { maxlength: "60" })), field("Color", colorIn)), el("div", { style: { height: "14px" } }), field("Icon", iconBox)),
    el("div", { class: "section card" }, el("h2", {}, "Game version"), el("div", { style: { height: "14px" } }), el("div", { class: "fields" }, field("Minecraft version", mcSel, "Changing this reinstalls the loader on next launch."), field("Mod loader", loaderSel)), el("div", { style: { height: "14px" } }), loaderExtra),
    el("div", { class: "section card" }, el("h2", {}, "Java & memory"), el("div", { style: { height: "14px" } }), el("div", { class: "fields" },
      field("Java runtime", select([["", "Automatic (Nova picks or downloads the right one)"], ...javas.map((j) => [j.path, `Java ${j.major} — ${j.path}`])], f.java_path, (v) => { f.java_path = v; })),
      field("Minimum memory (MB)", inp("memory_min", { type: "number", min: "256", step: "256" })), field("Maximum memory (MB)", inp("memory_max", { type: "number", min: "512", step: "256" })),
      field("Extra Java arguments", inp("jvm_args", { placeholder: "-Dexample=1" }), "Added after the preset from the Optimize tab.")), ),
    el("div", { class: "section card" }, el("h2", {}, "Game window"), el("div", { style: { height: "14px" } }), el("div", { class: "fields" }, field("Width", inp("width", { type: "number" })), field("Height", inp("height", { type: "number" })), field("Extra game arguments", inp("game_args", { placeholder: "--quickPlayMultiplayer example.com" }))),
      toggleRow("Start in fullscreen", null, f.fullscreen, (c) => { f.fullscreen = c; })),
    el("details", { class: "section card" }, el("summary", { style: { cursor: "pointer", "font-weight": "600" } }, "Advanced: commands & environment"), el("div", { style: { height: "14px" } }), el("div", { class: "notice warn", style: { "margin-bottom": "14px" } }, "These run on your computer. Only add commands you trust. They are never exported with packs."),
      el("div", { class: "fields" }, field("Run before launch", inp("pre_launch", { placeholder: "e.g. ./backup.sh" }), "If it fails, the game won't start."), field("Run after the game closes", inp("post_exit"))), el("div", { style: { height: "14px" } }), field("Environment variables", envIn)),
    el("div", { class: "row" }, patchBtn));
}

// ---- console
function stopLogs() { if (S.logTimer) { clearInterval(S.logTimer); S.logTimer = null; } }
async function tabConsole(p, i) {
  const box = el("div", { class: "console", tabindex: "0", "aria-label": "Game output" });
  S.logSince[i.id] = 0;
  const status = el("span", { class: "chip plain" }, "Idle");
  p.append(el("div", { class: "row", style: { "margin-bottom": "12px" } }, el("div", { class: "grow" }, el("h2", {}, "Console"), el("div", { class: "muted small" }, "Live output from the game. Useful when a mod crashes.")), status,
    el("button", { class: "btn", onclick: () => { const t = box.innerText; navigator.clipboard.writeText(t).then(() => toast("Log copied."), () => toast("Couldn't copy. Select the text instead.", "err")); } }, icon("copy"), "Copy log"),
    el("button", { class: "btn", onclick: () => api(`/api/instances/${i.id}/open-folder`, { method: "POST", body: { sub: "crash-reports" } }).catch(fail) }, icon("folder"), "Crash reports")), box);
  const tick = async () => {
    try {
      const r = await api(`/api/instances/${i.id}/logs?since=${S.logSince[i.id]}`);
      status.textContent = { none: "Not started", starting: "Starting", running: "Running", exited: "Closed normally", crashed: "Crashed" }[r.status] || r.status;
      status.className = "chip " + (r.status === "running" ? "good" : r.status === "crashed" ? "warn" : "plain");
      if (r.lines.length) {
        const atEnd = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
        for (const l of r.lines) box.append(el("div", { class: /\[Nova\]/.test(l) ? "l-nova" : /ERROR|Exception|FATAL/.test(l) ? "l-err" : /WARN/.test(l) ? "l-warn" : "" }, l));
        while (box.childElementCount > 3000) box.firstChild.remove();
        if (atEnd) box.scrollTop = box.scrollHeight;
        S.logSince[i.id] = r.next;
      } else if (!box.childElementCount && r.status === "none") { box.textContent = "Nothing to show yet. Press Play to start the game."; box.dataset.empty = "1"; }
      if (box.dataset.empty && r.lines.length) { delete box.dataset.empty; box.firstChild?.nodeType === 3 && box.firstChild.remove(); }
    } catch { /* ignore */ }
  };
  await tick(); S.logTimer = setInterval(tick, 800);
}

// ------------------------------------------------------------------ discover
S.discover = { q: "", type: "mod", sort: "relevance", inst: null, results: null, offset: 0, total: 0, loading: false };
async function pageDiscover(v) {
  const D = S.discover, insts = S.data.instances;
  if (!D.inst || !instById(D.inst)) D.inst = insts[0]?.id || null;
  if (!insts.length) { v.append(el("div", { class: "empty" }, el("h2", {}, "Create an instance first"), el("p", {}, "Mods are installed into an instance so they match its Minecraft version and loader."), el("button", { class: "btn primary", onclick: () => createDialog() }, "New instance"))); return; }
  const inst = instById(D.inst);
  const results = el("div");
  const search = async (append = false) => {
    if (D.loading) return; D.loading = true;
    if (!append) { D.offset = 0; results.replaceChildren(el("div", { class: "muted" }, el("span", { class: "spinner" }), " Searching Modrinth…")); }
    try {
      const qs = new URLSearchParams({ q: D.q, mc: inst.mc_version, loader: inst.loader, type: D.type, sort: D.sort, offset: D.offset });
      const r = await api("/api/modrinth/search?" + qs); D.total = r.total;
      if (!append) results.replaceChildren();
      results.querySelector(".more")?.remove();
      if (!r.hits.length && !append) results.append(el("div", { class: "empty" }, el("h2", {}, "No matches"), el("p", {}, `Nothing found for Minecraft ${inst.mc_version}${D.type === "mod" && inst.loader !== "vanilla" ? " on " + LOADER_NAMES[inst.loader] : ""}. Try another search.`)));
      r.hits.forEach((h) => results.append(resultRow(h, inst)));
      D.offset += r.hits.length;
      if (D.offset < D.total) results.append(el("div", { class: "more row", style: { "justify-content": "center", "margin-top": "16px" } }, el("button", { class: "btn", onclick: () => search(true) }, "Show more")));
    } catch (e) { results.replaceChildren(el("div", { class: "notice warn" }, e.message)); }
    D.loading = false;
  };
  const q = el("input", { type: "search", placeholder: D.type === "mod" ? "Search mods" : D.type === "shader" ? "Search shader packs" : "Search resource packs", value: D.q, "aria-label": "Search" });
  let tm; q.addEventListener("input", () => { D.q = q.value; clearTimeout(tm); tm = setTimeout(() => search(), 350); });
  v.append(el("div", { class: "page-head" }, el("div", { class: "grow" }, el("h1", {}, "Discover"), el("p", {}, "Search Modrinth. Results are filtered to what works in the selected instance.")),
    el("div", { style: { width: "260px" } }, select(insts.map((x) => [x.id, `${x.name} (${x.mc_version})`]), D.inst, (val) => { D.inst = val; render(); }))),
    el("div", { class: "row", style: { "margin-bottom": "18px" } }, el("div", { class: "grow", style: { "min-width": "220px" } }, q),
      el("div", { class: "seg", role: "group", "aria-label": "Type" }, [["mod", "Mods"], ["shader", "Shaders"], ["resourcepack", "Resource packs"]].map(([k, l]) => el("button", { "aria-pressed": String(D.type === k), onclick: () => { D.type = k; render(); } }, l))),
      el("div", { style: { width: "170px" } }, select([["relevance", "Most relevant"], ["downloads", "Most downloaded"], ["follows", "Most followed"], ["newest", "Newest"], ["updated", "Recently updated"]], D.sort, (s) => { D.sort = s; search(); }))),
    results);
  search();
}
function resultRow(h, inst) {
  const btn = el("button", { class: "btn primary sm" }, icon("download"), "Install");
  btn.onclick = async () => {
    btn.disabled = true;
    try { const r = await api(`/api/instances/${inst.id}/mods/install`, { method: "POST", body: { project: h.project_id, type: S.discover.type, title: h.title } });
      runTask(r.task, (t) => { if (t.status === "done") { btn.replaceChildren("Installed"); const n = t.result?.installed?.length || 1; toast(n > 1 ? `Installed ${h.title} and ${n - 1} required ${n === 2 ? "mod" : "mods"}.` : `Installed ${h.title}.`, "ok"); } else { btn.disabled = false; } }); poll();
    } catch (e) { fail(e); btn.disabled = false; }
  };
  return el("div", { class: "result" },
    el("div", { class: "thumb", style: h.icon_url ? { "background-image": `url("${h.icon_url.replace(/"/g, "%22")}")` } : {} }, h.icon_url ? "" : "▣"),
    el("div", { class: "info" }, el("h3", {}, h.title, el("span", { class: "muted small", style: { "font-weight": "400" } }, "by " + h.author)), el("p", {}, h.description), el("div", { class: "row", style: { gap: "6px" } }, el("span", { class: "chip plain" }, fmtNum(h.downloads) + " downloads"), ...(h.categories || []).slice(0, 3).map((c) => el("span", { class: "chip plain" }, c)))),
    el("div", {}, btn));
}

// ------------------------------------------------------------------ profiles
function msSetupDialog(then) {
  const id = el("input", { type: "text", placeholder: "12345678-abcd-1234-abcd-1234567890ab", value: S.data.settings.ms_client_id || "", spellcheck: "false", "aria-label": "Application (client) ID" });
  const steps = el("ol", { class: "muted small", style: { "padding-left": "18px", "line-height": "1.7", margin: "0 0 14px" } },
    el("li", {}, "Open ", el("a", { href: "https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade", target: "_blank", rel: "noopener" }, "Azure → App registrations"), " and choose New registration."),
    el("li", {}, "Account type: “Personal Microsoft accounts only”. No redirect URI needed."),
    el("li", {}, "Authentication → Advanced settings → Allow public client flows: Yes."),
    el("li", {}, "Copy the Application (client) ID and paste it below."),
    el("li", {}, "Mojang must approve that ID once (", el("a", { href: "https://aka.ms/mce-reviewappid", target: "_blank", rel: "noopener" }, "aka.ms/mce-reviewappid"), "). Until then sign-in stops at the last step."));
  modal("Set up Microsoft sign-in", el("div", {}, el("p", { class: "muted", style: { "margin-bottom": "10px" } }, "Nova signs in with your own free Azure app, so no one else's keys are involved. One-time setup:"), steps, field("Application (client) ID", id)),
    (close) => [el("button", { class: "btn", onclick: close }, "Cancel"), el("button", { class: "btn primary", onclick: async () => { try { S.data.settings = await api("/api/settings", { method: "POST", body: { ms_client_id: id.value } }); close(); if (S.data.settings.ms_client_id) then(); else render(); } catch (e) { fail(e); } } }, "Save & continue")], { wide: true });
}

async function msSignIn() {
  if (!S.data.settings.ms_client_id) return msSetupDialog(msSignIn);
  let f;
  try { f = await api("/api/accounts/microsoft/start", { method: "POST", body: {} }); } catch (e) { return fail(e); }
  const close = modal("Sign in with Microsoft", el("div", { style: { "text-align": "center" } },
    el("p", { class: "muted" }, "Open the page below, enter this code, and approve the sign-in."),
    el("div", { class: "mono", style: { "font-size": "2rem", "letter-spacing": ".18em", margin: "16px 0", color: "var(--accent-text)" }, "aria-label": "Sign-in code" }, f.user_code),
    el("a", { class: "btn primary", href: f.verification_uri, target: "_blank", rel: "noopener" }, "Open " + f.verification_uri.replace("https://www.", "").replace("https://", "")),
    el("p", { class: "faint small", style: { "margin-top": "14px" } }, "Waiting for you… this window updates on its own.")),
    (c) => [el("button", { class: "btn", onclick: () => { api(`/api/accounts/microsoft/${f.flow}`, { method: "DELETE" }).catch(() => {}); c(); } }, "Cancel")]);
  runTask(f.task, async (t) => {
    close();
    if (t.status === "error") { if (!/cancelled/i.test(t.error || "")) toast(t.error, "err"); return; }
    await loadState(); render(); toast(`Signed in as ${t.result?.username || "your account"}.`, "ok");
  });
}

async function pageProfiles(v) {
  const accs = S.data.accounts;
  const name = el("input", { type: "text", placeholder: "Username", maxlength: "16", "aria-label": "Offline username" });
  const add = async () => { try { await api("/api/accounts", { method: "POST", body: { username: name.value } }); await loadState(); name.value = ""; render(); toast("Offline profile added.", "ok"); } catch (e) { fail(e); } };
  name.addEventListener("keydown", (e) => { if (e.key === "Enter") add(); });
  const ms = !!S.data.settings.ms_client_id;
  v.append(el("div", { class: "page-head" }, el("div", { class: "grow" }, el("h1", {}, "Profiles"), el("p", {}, "The account you play under."))),
    el("div", { class: "card section", style: { "margin-bottom": "20px", "max-width": "720px" } }, el("h2", {}, "Microsoft account"),
      el("p", { class: "muted small", style: { margin: "4px 0 12px" } }, "Needed for online-mode servers, skins and Realms. Your password never touches Nova; you approve a short code on microsoft.com."),
      el("div", { class: "row" }, el("button", { class: "btn primary", onclick: msSignIn }, icon("profiles"), "Sign in with Microsoft"),
        el("button", { class: "btn ghost", onclick: () => msSetupDialog(() => render()) }, ms ? "Change app ID" : "Set up app ID"),
        ms ? el("span", { class: "chip good" }, "App ID set") : el("span", { class: "chip warn" }, "Setup needed"))),
    el("h3", { style: { margin: "0 0 8px" } }, "Offline profile"),
    el("p", { class: "muted small", style: { "margin-bottom": "10px", "max-width": "720px" } }, "Single-player and offline-mode servers only."),
    el("div", { class: "row", style: { "margin-bottom": "20px", "max-width": "520px" } }, el("div", { class: "grow" }, name), el("button", { class: "btn", onclick: add }, icon("plus"), "Add offline profile")),
    accs.length ? el("div", { class: "stack", style: { "max-width": "720px" } }, accs.map((a) => el("div", { class: "item" }, el("div", { class: "avatar" }, a.username[0].toUpperCase()), el("div", { class: "info" }, el("b", {}, a.username), el("span", { class: "mono" }, a.uuid)),
      el("span", { class: "chip " + (a.type === "microsoft" ? "good" : "plain") }, a.type === "microsoft" ? "Microsoft" : "Offline"),
      a.id === S.data.selected_account ? el("span", { class: "chip" }, "In use") : el("button", { class: "btn sm", onclick: async () => { await api(`/api/accounts/${a.id}/select`, { method: "POST" }); await loadState(); render(); } }, "Use"),
      el("button", { class: "btn ghost sm", "aria-label": "Remove " + a.username, onclick: () => confirmDialog("Remove " + a.username + "?", a.type === "microsoft" ? "The saved login is deleted from this computer. You can sign in again any time." : "The profile is removed from Nova. Worlds stay in your instances.", "Remove", async () => { await api(`/api/accounts/${a.id}`, { method: "DELETE" }); await loadState(); render(); }) }, icon("trash"))))) : el("div", { class: "muted" }, "No profiles yet."));
}

// ------------------------------------------------------------------ settings
async function pageSettings(v) {
  const s = S.data.settings, th = S.data.themes;
  const set = async (patch) => { try { await saveSettings(patch); renderRail(); } catch (e) { fail(e); } };
  const swatchBox = el("div", { class: "swatches" });
  const drawSw = () => swatchBox.replaceChildren(...Object.entries(th).map(([k, t]) => el("button", { class: "swatch", "aria-pressed": String(S.data.settings.theme_preset === k), onclick: async () => { await set({ theme_preset: k, accent: t.accent, accent2: t.accent2 }); drawSw(); drawColors(); } }, el("i", { style: { background: `linear-gradient(135deg, ${t.accent}, ${t.accent2})` } }), el("span", {}, t.name))));
  const colorsBox = el("div", { class: "row", style: { gap: "22px" } });
  const drawColors = () => { const a = el("input", { type: "color", value: S.data.settings.accent, "aria-label": "Accent color" }), b = el("input", { type: "color", value: S.data.settings.accent2, "aria-label": "Second accent color" });
    a.addEventListener("input", () => { set({ accent: a.value, theme_preset: "custom" }); }); b.addEventListener("input", () => { set({ accent2: b.value, theme_preset: "custom" }); });
    colorsBox.replaceChildren(el("div", { class: "row" }, a, el("span", {}, "Accent")), el("div", { class: "row" }, b, el("span", {}, "Glow & gradients"))); };
  drawSw(); drawColors();
  const range = (key, min, max, fmt) => { const out = el("b", {}, fmt(s[key])); const r = el("input", { type: "range", min, max, value: s[key], "aria-label": key }); r.addEventListener("input", () => { out.textContent = fmt(+r.value); set({ [key]: +r.value }); }); return el("div", { class: "row" }, el("div", { class: "grow" }, r), out); };
  const javaIn = el("input", { type: "text", value: s.java_path, placeholder: "Automatic" }); javaIn.addEventListener("change", () => set({ java_path: javaIn.value.trim() }));
  const gj = el("input", { type: "text", value: s.global_jvm_args, placeholder: "-Dexample=1" }); gj.addEventListener("change", () => set({ global_jvm_args: gj.value }));
  v.append(el("div", { class: "page-head" }, el("div", { class: "grow" }, el("h1", {}, "Settings"), el("p", {}, "Make Nova look and behave the way you like. Changes apply instantly."))),
    el("div", { class: "section card" }, el("h2", {}, "Theme"), el("div", { style: { height: "14px" } }), swatchBox, el("div", { style: { height: "18px" } }), colorsBox,
      el("div", { style: { height: "22px" } }), field("Background", el("div", { class: "seg", role: "group" }, Object.entries(S.data.surfaces).map(([k, x]) => el("button", { "aria-pressed": String(S.data.settings.surface === k), onclick: async (e) => { await set({ surface: k }); render(); } }, x.name))))),
    el("div", { class: "section card" }, el("h2", {}, "Layout"), el("div", { style: { height: "14px" } }), el("div", { class: "fields" }, field("Corner roundness", range("radius", 0, 28, (x) => x + " px")), field("Text size", range("font_scale", 80, 140, (x) => x + "%"))),
      el("div", { style: { height: "14px" } }), field("Density", el("div", { class: "seg", role: "group" }, [["comfortable", "Comfortable"], ["compact", "Compact"]].map(([k, l]) => el("button", { "aria-pressed": String(S.data.settings.density === k), onclick: async () => { await set({ density: k }); render(); } }, l))))),
    el("div", { class: "section card" }, el("h2", {}, "Effects"), toggleRow("Starfield background", "Slowly drifting stars behind the interface.", s.starfield, (c) => set({ starfield: c })), toggleRow("Glow", "Violet glow on buttons and the background.", s.glow, (c) => set({ glow: c })), toggleRow("Animations", "Turn off to save battery on laptops.", s.animations, (c) => set({ animations: c }))),
    el("div", { class: "section card" }, el("h2", {}, "Game"), el("div", { style: { height: "10px" } }),
      toggleRow("Download Java automatically", "Nova fetches the right Java version when none is installed.", s.auto_download_java, (c) => set({ auto_download_java: c })),
      toggleRow("Open console when the game starts", null, s.show_console_on_launch, (c) => set({ show_console_on_launch: c })),
      el("div", { style: { height: "14px" } }), el("div", { class: "fields" }, field("Java for every instance", javaIn, "Leave empty to let Nova choose. Instances can override this."), field("Java arguments for every instance", gj))),
    el("div", { class: "section card" }, el("h2", {}, "About"), el("p", { class: "muted", style: { margin: "6px 0 12px" } }, `Nova Launcher ${S.data.version}. Your data lives in ${S.data.data_dir}`), el("div", { class: "row" }, el("button", { class: "btn", onclick: () => api("/api/quit", { method: "POST" }).then(() => { document.body.textContent = "Nova has closed. You can close this window."; }) }, "Quit Nova"))));
}

// ------------------------------------------------------------------ starfield
const stars = { enabled: true, pts: [], raf: 0 };
(function initStars() {
  const c = $("#stars"), ctx = c.getContext("2d"); let w, h;
  const resize = () => { w = c.width = innerWidth; h = c.height = innerHeight; stars.pts = Array.from({ length: Math.min(140, Math.floor(w * h / 11000)) }, () => ({ x: Math.random() * w, y: Math.random() * h, r: Math.random() * 1.3 + .2, s: Math.random() * .12 + .02, a: Math.random() * .6 + .2, t: Math.random() * 6 })); };
  addEventListener("resize", resize); resize();
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const frame = (ts) => {
    stars.raf = requestAnimationFrame(frame);
    if (!stars.enabled) { ctx.clearRect(0, 0, w, h); return; }
    ctx.clearRect(0, 0, w, h);
    const acc = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#8b5cf6";
    for (const p of stars.pts) {
      if (!reduce && document.documentElement.dataset.anim !== "off") { p.y -= p.s; if (p.y < -2) { p.y = h + 2; p.x = Math.random() * w; } }
      const tw = reduce ? 1 : .65 + .35 * Math.sin(ts / 1200 + p.t);
      ctx.globalAlpha = p.a * tw; ctx.fillStyle = p.r > 1.1 ? acc : "#e7ddff"; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.283); ctx.fill();
    }
    ctx.globalAlpha = 1;
  };
  frame(0);
  document.addEventListener("visibilitychange", () => { if (document.hidden) cancelAnimationFrame(stars.raf); else frame(0); });
})();

// ------------------------------------------------------------------ boot
(async function boot() {
  try { await loadState(); await render(); poll(); }
  catch (e) { document.body.replaceChildren(el("div", { class: "empty", style: { padding: "80px 20px" } }, el("h2", {}, "Nova can't start"), el("p", {}, e.message))); }
})();
