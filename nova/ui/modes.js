"use strict";
// ---------------------------------------------------------------- App modes: Normal / Kawaii / Emo
// Normal changes nothing. Kawaii and Emo restyle the whole app (colors, shapes, fonts, decorations) through
// CSS keyed on <html data-mode>, plus a layer of drifting decorations built here. All art is original.

const MODES = {
  normal: { name: "Normal", tagline: "The classic Nova look. Your themes and backgrounds apply." },
  kawaii: { name: "Kawaii", tagline: "Pink, soft and sparkly, with hearts, bows and bunnies." },
  emo: { name: "Emo", tagline: "Black and gothic, with guitars, bats and a little drama." },
};

const MODE_SPRITES = `<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">
<symbol id="sp-heart" viewBox="0 0 32 32"><path fill="currentColor" d="M16 28C4 19 3 11 8 7.5 11.5 5 15 7 16 10c1-3 4.5-5 8-2.500C29 11 28 19 16 28z"/></symbol>
<symbol id="sp-star" viewBox="0 0 32 32"><path fill="currentColor" d="M16 3l3.9 8.3 9.1 1.1-6.7 6.2 1.8 9L16 23.2 7.9 27.600l1.8-9L3 12.400l9.1-1.100z"/></symbol>
<symbol id="sp-sparkle" viewBox="0 0 32 32"><path fill="currentColor" d="M16 2c1 8 4 11 14 14-10 3-13 6-14 14-1-8-4-11-14-14 10-3 13-6 14-14z"/></symbol>
<symbol id="sp-bow" viewBox="0 0 32 32"><path fill="currentColor" d="M16 16L3 7Q1 16 3 25zM16 16l13-9q2 9 0 18z"/><circle cx="16" cy="16" r="3.6" fill="currentColor" stroke="#fff" stroke-opacity=".6" stroke-width="1"/></symbol>
<symbol id="sp-cloud" viewBox="0 0 32 32"><path fill="currentColor" d="M9 25a5 5 0 010-10 7 7 0 0113-2 6 6 0 012 12z"/></symbol>
<symbol id="sp-flower" viewBox="0 0 32 32"><g fill="currentColor"><circle cx="16" cy="7.5" r="5"/><circle cx="24.1" cy="13.4" r="5"/><circle cx="21" cy="23" r="5"/><circle cx="11" cy="23" r="5"/><circle cx="7.9" cy="13.4" r="5"/></g><circle cx="16" cy="16" r="3.6" fill="#ffd54f"/></symbol>
<symbol id="sp-bunny" viewBox="0 0 32 32"><ellipse cx="11" cy="8" rx="3.2" ry="8" fill="#fff" stroke="#ff8fc0" stroke-width="1.2"/><ellipse cx="21" cy="8" rx="3.2" ry="8" fill="#fff" stroke="#ff8fc0" stroke-width="1.2"/><ellipse cx="11" cy="9" rx="1.4" ry="5" fill="#ffc2dd"/><ellipse cx="21" cy="9" rx="1.4" ry="5" fill="#ffc2dd"/><circle cx="16" cy="20" r="10" fill="#fff" stroke="#ff8fc0" stroke-width="1.2"/><circle cx="12.2" cy="19.5" r="1.4" fill="#5b2145"/><circle cx="19.8" cy="19.5" r="1.4" fill="#5b2145"/><ellipse cx="9.6" cy="22.5" rx="2.2" ry="1.4" fill="#ffb3d1"/><ellipse cx="22.4" cy="22.5" rx="2.2" ry="1.4" fill="#ffb3d1"/><path d="M14.6 22.500q1.4 1.4 2.8 0" stroke="#5b2145" stroke-width="1.1" fill="none" stroke-linecap="round"/><path fill="#ff5fa8" d="M24 12l3-3 1 4zM24 12l3 3 1-4z"/></symbol>
<symbol id="sp-guitar" viewBox="0 0 32 32"><g fill="currentColor"><circle cx="16" cy="24" r="6.5"/><circle cx="16" cy="16.5" r="4.6"/><rect x="15" y="2" width="2" height="15"/><rect x="13.3" y="0.3" width="5.4" height="4.4" rx="1"/></g><rect x="12" y="21" width="8" height="1.8" fill="#000" opacity=".55"/><rect x="12" y="25.5" width="8" height="1.8" fill="#000" opacity=".55"/></symbol>
<symbol id="sp-skull" viewBox="0 0 32 32"><path fill="currentColor" d="M16 3C9.4 3 5 7.6 5 13.400c0 3.4 1.6 5.6 4 7V26h14v-5.600c2.4-1.4 4-3.6 4-7C27 7.6 22.6 3 16 3z"/><circle cx="11.6" cy="14.2" r="3" fill="#000"/><circle cx="20.4" cy="14.2" r="3" fill="#000"/><path d="M16 17.500l-1.8 3.200h3.600z" fill="#000"/><path d="M12 26v-3M16 26v-3M20 26v-3" stroke="#000" stroke-width="1.1"/></symbol>
<symbol id="sp-bat" viewBox="0 0 32 20"><path fill="currentColor" d="M16 4l-2-3-1 4C9 3 4 3 0 7c3 0 4 2 5 5 2-2 4-2 6 0 1-1 3-2 5-2s4 1 5 2c2-2 4-2 6 0 1-3 2-5 5-5-4-4-9-4-13-2l-1-4z"/></symbol>
<symbol id="sp-bolt" viewBox="0 0 32 32"><path fill="currentColor" d="M18 2L7 18h7l-2 12 12-18h-8z"/></symbol>
<symbol id="sp-broken" viewBox="0 0 32 32"><path fill="currentColor" d="M15 28C4 19 3 11 8 7.5 11.5 5 14.5 6.5 15.5 9.500L13.5 14l3 3-3 4z"/><path fill="currentColor" d="M18 22l-1-5 3-3-2-4c1-3 4.5-4.5 8-2 5 3.5 4 11.5-7 20z" transform="translate(1.5 1)"/></symbol>
<symbol id="sp-pick" viewBox="0 0 32 32"><path fill="currentColor" d="M16 3c7 0 11 4 11 10 0 8-8 16-11 16S5 21 5 13C5 7 9 3 16 3z"/></symbol>
<symbol id="sp-note" viewBox="0 0 32 32"><path fill="currentColor" d="M12 4v17a4 4 0 11-2-3.400V8l14-3v13a4 4 0 11-2-3.400V4z"/></symbol>
<symbol id="sp-web" viewBox="0 0 120 120"><g fill="none" stroke="currentColor" stroke-width="1.2"><path d="M0 0L120 0M0 0L105 45M0 0L75 75M0 0L45 105M0 0L0 120"/><path d="M30 0Q26 26 0 30M60 0Q52 52 0 60M90 0Q78 78 0 90M118 0Q102 102 0 118"/></g></symbol>
</svg>`;

const DECOR = {
  kawaii: { sprites: ["sp-heart", "sp-heart", "sp-star", "sp-sparkle", "sp-bow", "sp-cloud", "sp-flower"], colors: ["#ff8fc0", "#ff5fa8", "#c9a7ff", "#ffffff", "#ffb3d1", "#ffd1e8"], n: 20, kind: "rise", op: [0.45, 0.9] },
  emo: { sprites: ["sp-guitar", "sp-guitar", "sp-guitar", "sp-skull", "sp-bat", "sp-bat", "sp-bolt", "sp-pick", "sp-note", "sp-broken"], colors: ["#d11a2a", "#8a0f1c", "#e9e4e4", "#6b6060", "#4a0a12"], n: 16, kind: "fall", op: [0.22, 0.5] },
};

const MODE_MASCOT = { kawaii: "sp-bunny", emo: "sp-skull" };

function installModeSprites() {
  if (document.getElementById("sp-heart")) return;
  const d = document.createElement("div"); d.innerHTML = MODE_SPRITES; document.body.prepend(d.firstElementChild);
}

// Deterministic-ish random so rebuilding doesn't flicker layouts too wildly
function buildDecor(mode, animated) {
  installModeSprites();
  const host = document.getElementById("decor"); if (!host) return;
  host.replaceChildren();
  const cfg = DECOR[mode]; if (!cfg) return;
  const rnd = (a, b) => a + Math.random() * (b - a);
  for (let i = 0; i < cfg.n; i++) {
    const id = cfg.sprites[Math.floor(Math.random() * cfg.sprites.length)];
    const bat = id === "sp-bat", size = bat ? rnd(26, 52) : rnd(16, mode === "kawaii" ? 36 : 44);
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", bat ? "0 0 32 20" : "0 0 32 32"); s.setAttribute("width", size); s.setAttribute("height", bat ? size * 0.62 : size);
    s.classList.add("decor-item", bat ? "decor-bat" : "decor-" + cfg.kind);
    const u = document.createElementNS("http://www.w3.org/2000/svg", "use"); u.setAttribute("href", "#" + id); s.append(u);
    const dur = bat ? rnd(18, 34) : rnd(cfg.kind === "rise" ? 16 : 28, cfg.kind === "rise" ? 34 : 60);
    s.style.cssText = `left:${rnd(0, 96).toFixed(1)}%;color:${cfg.colors[Math.floor(Math.random() * cfg.colors.length)]};opacity:${rnd(...cfg.op).toFixed(2)};` +
      `animation-duration:${dur.toFixed(1)}s;animation-delay:-${rnd(0, dur).toFixed(1)}s;` + (bat ? `top:${rnd(4, 70).toFixed(0)}%;` : "") + `--spin:${rnd(-40, 40).toFixed(0)}deg`;
    host.append(s);
  }
}

function applyMode(mode, animated) {
  const r = document.documentElement; mode = MODES[mode] ? mode : "normal";
  const changed = r.dataset.mode !== mode || (r.dataset.decorAnim !== (animated ? "1" : "0"));
  r.dataset.mode = mode; r.dataset.decorAnim = animated ? "1" : "0";
  if (changed) buildDecor(animated || mode !== "normal" ? mode : "normal", animated);
  const mark = document.querySelector(".brand-mark use");
  if (mark) mark.setAttribute("href", MODE_MASCOT[mode] ? "#" + MODE_MASCOT[mode] : "/static/nova.svg#nova");
  return mode;
}
