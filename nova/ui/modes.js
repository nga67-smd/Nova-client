"use strict";
// ---------------------------------------------------------------- App modes: Normal / Kawaii / Emo
// Normal changes nothing. Kawaii and Emo restyle the whole app (colors, shapes, fonts, decorations) through
// CSS keyed on <html data-mode>, plus a layer of drifting decorations built here. All art is original.

const MODES = {
  normal: { name: "Normal", tagline: "The classic Nova look. Your themes and backgrounds apply." },
  kawaii: { name: "Kawaii", tagline: "Pink, soft and sparkly, with hearts, bows and bunnies." },
  emo: { name: "Emo", tagline: "Black and gothic, with guitars, bats and a little drama." },
};


// Original chibi-style characters (not based on any existing anime or franchise)
const girl = (id, o) => `<symbol id="${id}" viewBox="0 0 120 172">
<defs><linearGradient id="${id}-h" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${o.hair2}"/><stop offset="1" stop-color="${o.hair}"/></linearGradient>
<linearGradient id="${id}-i" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${o.iris2}"/><stop offset="1" stop-color="${o.iris}"/></linearGradient></defs>
${o.back}
<path id="${id}-l" d="M44 150h12v14c0 4-3 6-7 6h-8c-3 0-3-4 0-5 3-1 3-3 3-6z" fill="#ffe4d6"/><use href="#${id}-l" transform="translate(120 0) scale(-1 1)"/>
<path d="M42 164c0 5 3 7 9 7h4v-5h-9zM78 164c0 5-3 7-9 7h-4v-5h9z" fill="${o.shoe}"/>
<path d="M38 108Q60 98 82 108L94 152Q60 160 26 152z" fill="${o.dress}" stroke="${o.line}" stroke-width="1.2" stroke-linejoin="round"/>
${o.collar}
<path d="M27 148Q60 158 93 148" stroke="${o.trim}" stroke-width="3" fill="none" stroke-linecap="round" stroke-dasharray="1 5"/>
<ellipse cx="33" cy="124" rx="6" ry="13" transform="rotate(14 33 124)" fill="#ffe4d6" stroke="${o.line}" stroke-width="1"/><ellipse cx="87" cy="124" rx="6" ry="13" transform="rotate(-14 87 124)" fill="#ffe4d6" stroke="${o.line}" stroke-width="1"/>
<ellipse cx="60" cy="62" rx="35" ry="32" fill="#ffe9dd" stroke="${o.line}" stroke-width="1.2"/>
<path d="M25 64C22 26 44 12 60 12s38 14 35 52C90 46 80 42 72 38c-3 8-18 8-24 0-8 4-18 8-23 26z" fill="url(#${id}-h)" stroke="${o.line}" stroke-width="1.2" stroke-linejoin="round"/>
<path d="M25 64c-3 16 0 30 8 36 0-14 2-24 7-34zM95 64c3 16 0 30-8 36 0-14-2-24-7-34z" fill="url(#${id}-h)" stroke="${o.line}" stroke-width="1"/>
<path d="M44 30c4 6 8 8 12 8M70 28c3 4 8 8 14 9" stroke="#fff" stroke-opacity=".45" stroke-width="2" fill="none" stroke-linecap="round"/>
<g id="${id}-e"><ellipse cx="45" cy="70" rx="8.5" ry="11" fill="url(#${id}-i)"/><ellipse cx="45" cy="71" rx="4.4" ry="6.6" fill="#241638"/><circle cx="42" cy="66" r="3.2" fill="#fff"/><circle cx="48.4" cy="75.6" r="1.6" fill="#fff" fill-opacity=".9"/><path d="M35 63Q45 54 55.600 62" stroke="#2a1a3a" stroke-width="3.200" fill="none" stroke-linecap="round"/></g>
<use href="#${id}-e" transform="translate(120 0) scale(-1 1)"/>
<ellipse cx="34" cy="82" rx="7" ry="3.400" fill="#ff8fb0" fill-opacity=".55"/><ellipse cx="86" cy="82" rx="7" ry="3.400" fill="#ff8fb0" fill-opacity=".55"/>
<path d="M54 86q6 6 12 0" stroke="#b8505a" stroke-width="2" fill="none" stroke-linecap="round"/>
${o.top}
</symbol>`;
const bowSvg = (x, y, c, k = 1) => `<g transform="translate(${x} ${y}) scale(${k})"><path d="M0 0L-15-9Q-18 0-15 9zM0 0l15-9q3 9 0 18z" fill="${c}" stroke="#d94a8a" stroke-width="1"/><circle r="4" fill="${c}" stroke="#d94a8a" stroke-width="1"/></g>`;
const GIRLS = {
  "sp-girl1": { hair: "#ff7fb6", hair2: "#ffb3d6", iris: "#7a4dff", iris2: "#d6b8ff", dress: "#ffb3d1", trim: "#fff", line: "#c0527f", shoe: "#ff5fa8",
    back: '<path d="M30 40C4 52 2 112 20 146c10-18 12-48 18-74z" fill="#ff7fb6" stroke="#c0527f" stroke-width="1.200"/><path d="M90 40c26 12 28 72 10 106-10-18-12-48-18-74z" fill="#ff7fb6" stroke="#c0527f" stroke-width="1.200"/>',
    collar: '<path d="M46 106l14 12 14-12z" fill="#fff" stroke="#c0527f" stroke-width="1"/>' + bowSvg(60, 118, "#ff5fa8", .7),
    top: bowSvg(27, 36, "#ff5fa8", .9) + bowSvg(93, 36, "#ff5fa8", .9) },
  "sp-girl2": { hair: "#a98bff", hair2: "#d3c4ff", iris: "#ff5fa8", iris2: "#ffc2dd", dress: "#d9cbff", trim: "#fff", line: "#6b4fb8", shoe: "#8a6bff",
    back: '<path d="M22 62C16 100 26 112 38 112h44c12 0 22-12 16-50z" fill="#a98bff" stroke="#6b4fb8" stroke-width="1.200"/>',
    collar: '<path d="M44 106q16 14 32 0l-4 10q-12 8-24 0z" fill="#fff" stroke="#6b4fb8" stroke-width="1"/><circle cx="60" cy="118" r="3.500" fill="#ff5fa8"/>',
    top: '<path d="M26 40L30 8l20 18zM94 40L90 8 70 26z" fill="#a98bff" stroke="#6b4fb8" stroke-width="1.200" stroke-linejoin="round"/><path d="M31 30l1-12 9 8zM89 30l-1-12-9 8z" fill="#ffc2dd"/><path d="M28 40Q60 8 92 40" stroke="#ff8fc0" stroke-width="3.500" fill="none"/>' },
  "sp-girl3": { hair: "#6fdcc2", hair2: "#b6f2e2", iris: "#2f9bff", iris2: "#a8d8ff", dress: "#ffffff", trim: "#6fdcc2", line: "#3b9c86", shoe: "#3b9c86",
    back: '<path d="M92 36C122 38 118 96 100 134c-6-24-4-46-10-62z" fill="#6fdcc2" stroke="#3b9c86" stroke-width="1.200"/>',
    collar: '<path d="M40 108l20 18 20-18-4-4H44z" fill="#6fdcc2" stroke="#3b9c86" stroke-width="1"/><path d="M60 122l-7 14h14z" fill="#ff5f7a"/><circle cx="60" cy="121" r="3" fill="#ff5f7a"/>',
    top: '<path d="M88 26l3.500 7 8 1-6 5 1.600 8-7-4-7 4 1.600-8-6-5 8-1z" fill="#ffd54f" stroke="#e0a800" stroke-width="1"/>' + bowSvg(30, 30, "#fff", .7) }
};
const GIRL_SYMBOLS = Object.entries(GIRLS).map(([id, o]) => girl(id, o)).join("\n");

// Detailed, hand-drawn-style emo pieces: real instrument proportions, matte shading, no neon.
const EMO_SYMBOLS = `
<symbol id="sp-guitar-a" viewBox="0 0 64 160">
<defs><radialGradient id="gA" cx=".5" cy=".4" r=".7"><stop offset="0" stop-color="#d6322f"/><stop offset=".55" stop-color="#7d0f19"/><stop offset="1" stop-color="#1c0408"/></radialGradient>
<linearGradient id="nA" x1="0" x2="1"><stop offset="0" stop-color="#8a5a33"/><stop offset=".5" stop-color="#b98551"/><stop offset="1" stop-color="#7a4d2a"/></linearGradient></defs>
<path d="M28 16V5q4-6 8 0v11z" fill="url(#nA)" stroke="#2a170a" stroke-width=".6"/>
<g fill="#cfcfcf" stroke="#555" stroke-width=".3"><circle cx="27" cy="7" r="1.200"/><circle cx="27" cy="11" r="1.200"/><circle cx="27" cy="15" r="1.200"/><circle cx="37" cy="7" r="1.200"/><circle cx="37" cy="11" r="1.200"/><circle cx="37" cy="15" r="1.200"/></g>
<rect x="29" y="16" width="6" height="66" fill="url(#nA)"/><rect x="29.600" y="16" width="4.800" height="66" fill="#241209"/>
<g stroke="#c9c2b8" stroke-width=".5">${[22,28,34,40,46,52,58,64,70,76].map(y=>`<path d="M29.600 ${y}h4.800"/>`).join("")}</g>
<g fill="#e8e0d0"><circle cx="32" cy="37" r=".9"/><circle cx="32" cy="49" r=".9"/><circle cx="32" cy="61" r=".9"/></g>
<path d="M32 80C22 70 13 75 13 86c0 8 4 9 3 15-2 9-1 28 11 34 3 1.500 7 1.500 10 0 12-6 13-25 11-34-1-6 3-7 3-15 0-11-9-16-19-6z" fill="url(#gA)" stroke="#12030a" stroke-width="1"/>
<path d="M22 92c-3 10-1 24 7 30 8-5 13-19 11-30-5 4-13 4-18 0z" fill="#efe9e2" fill-opacity=".92" stroke="#6b6560" stroke-width=".4"/>
<g fill="#0e0e0e" stroke="#777" stroke-width=".4"><rect x="23" y="96" width="18" height="4" rx="1"/><rect x="23" y="104" width="18" height="4" rx="1"/><rect x="23" y="112" width="18" height="4" rx="1"/></g>
<g fill="#aaa"><circle cx="26" cy="98" r=".5"/><circle cx="30" cy="98" r=".5"/><circle cx="34" cy="98" r=".5"/><circle cx="38" cy="98" r=".5"/><circle cx="26" cy="106" r=".5"/><circle cx="30" cy="106" r=".5"/><circle cx="34" cy="106" r=".5"/><circle cx="38" cy="106" r=".5"/></g>
<rect x="22" y="121" width="20" height="3" rx="1" fill="#bdbdbd" stroke="#555" stroke-width=".3"/>
<circle cx="41" cy="127" r="2.200" fill="#141414" stroke="#888" stroke-width=".4"/><circle cx="36" cy="131" r="2.200" fill="#141414" stroke="#888" stroke-width=".4"/>
<g stroke="#e6e6e6" stroke-width=".28" opacity=".85"><path d="M30.200 6V122M31.100 6V122M32 6V122M32.900 6V122M33.800 6V122"/></g>
</symbol>
<symbol id="sp-guitar-b" viewBox="0 0 90 150">
<defs><linearGradient id="gB" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3a3a3e"/><stop offset=".5" stop-color="#111114"/><stop offset="1" stop-color="#050506"/></linearGradient></defs>
<path d="M42 18V6q3-5 6 0v12z" fill="#2c1b10" stroke="#000" stroke-width=".5"/><rect x="42" y="18" width="6" height="62" fill="#1a0f08" stroke="#3a2412" stroke-width=".6"/>
<g stroke="#bdb6aa" stroke-width=".5">${[24,30,36,42,48,54,60,66,72].map(y=>`<path d="M42 ${y}h6"/>`).join("")}</g>
<path d="M45 76L12 146l14 2 15-30 4-8 4 8 15 30 14-2z" fill="url(#gB)" stroke="#000" stroke-width="1"/>
<path d="M45 90L24 138l8 1 13-28 13 28 8-1z" fill="#000" opacity=".25"/>
<g fill="#0a0a0a" stroke="#8a8a8a" stroke-width=".5"><rect x="38" y="92" width="14" height="4" rx="1"/><rect x="38" y="102" width="14" height="4" rx="1"/></g>
<rect x="36" y="114" width="18" height="3" rx="1" fill="#c9c9c9" stroke="#555" stroke-width=".3"/>
<circle cx="30" cy="132" r="2.200" fill="#222" stroke="#999" stroke-width=".4"/><circle cx="60" cy="132" r="2.200" fill="#222" stroke="#999" stroke-width=".4"/>
<g stroke="#ddd" stroke-width=".25" opacity=".8"><path d="M43 7V114M44.200 7V114M45 7V114M45.800 7V114M47 7V114"/></g>
</symbol>
<symbol id="sp-skull2" viewBox="0 0 64 64">
<defs><radialGradient id="sk" cx=".5" cy=".35" r=".75"><stop offset="0" stop-color="#f1ead9"/><stop offset=".7" stop-color="#cbbfa7"/><stop offset="1" stop-color="#8f836d"/></radialGradient></defs>
<path d="M32 4C17 4 8 14 8 27c0 8 4 13 9 16v8c0 3 2 5 5 5h20c3 0 5-2 5-5v-8c5-3 9-8 9-16C56 14 47 4 32 4z" fill="url(#sk)" stroke="#2b2418" stroke-width="1"/>
<path d="M13 30c2 6 6 9 10 10M51 30c-2 6-6 9-10 10" stroke="#8f836d" stroke-width="1.500" fill="none" opacity=".7"/>
<path d="M12 28c0-6 5-10 11-9 6 1 8 7 7 12-1 5-6 8-12 7-4-1-6-5-6-10zM52 28c0-6-5-10-11-9-6 1-8 7-7 12 1 5 6 8 12 7 4-1 6-5 6-10z" fill="#0e0b08"/>
<path d="M32 33l-4 9q4 2 8 0z" fill="#17120c"/>
<path d="M22 46h20v8H22z" fill="#d9cfb8" stroke="#2b2418" stroke-width=".8"/><path d="M26 46v8M30 46v8M34 46v8M38 46v8" stroke="#2b2418" stroke-width=".8"/>
<path d="M38 6l-4 9 5 6-3 8" stroke="#2b2418" stroke-width=".8" fill="none" opacity=".65"/>
</symbol>
<symbol id="sp-vinyl" viewBox="0 0 64 64"><circle cx="32" cy="32" r="30" fill="#0c0c0c" stroke="#333" stroke-width="1"/><g fill="none" stroke="#2a2a2a" stroke-width=".6"><circle cx="32" cy="32" r="26"/><circle cx="32" cy="32" r="22"/><circle cx="32" cy="32" r="18"/></g><path d="M12 18a24 24 0 0 1 20-10" stroke="#fff" stroke-opacity=".18" stroke-width="2" fill="none"/><circle cx="32" cy="32" r="9" fill="#a3101e"/><circle cx="32" cy="32" r="1.500" fill="#0c0c0c"/></symbol>
<symbol id="sp-pin" viewBox="0 0 64 32"><g fill="none" stroke="currentColor" stroke-width="2.200" stroke-linecap="round"><path d="M8 10h44a6 6 0 0 1 0 12H12"/><path d="M8 10a6 6 0 0 0 0 12h4"/><path d="M12 22L52 10"/></g></symbol>
`;

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
${GIRL_SYMBOLS}
${EMO_SYMBOLS}
</svg>`;

const DECOR = {
  kawaii: { sprites: ["sp-heart", "sp-heart", "sp-star", "sp-sparkle", "sp-bow", "sp-cloud", "sp-flower", "sp-girl1", "sp-girl2", "sp-girl3"], colors: ["#ff8fc0", "#ff5fa8", "#c9a7ff", "#ffffff", "#ffb3d1", "#ffd1e8"], n: 20, kind: "rise", op: [0.5, 0.92] },
  emo: { sprites: ["sp-guitar-a", "sp-guitar-b", "sp-skull2", "sp-bat", "sp-bat", "sp-vinyl", "sp-pin", "sp-pick"], colors: ["#b3202e", "#8f8f8f", "#cfc8c8", "#5a5252"], n: 12, kind: "fall", op: [0.25, 0.5] },
};
const TALL = { "sp-guitar-a": [0.4, 2.5], "sp-guitar-b": [0.6, 1.67], "sp-girl1": [0.7, 1.43], "sp-girl2": [0.7, 1.43], "sp-girl3": [0.7, 1.43], "sp-bat": [32, 20], "sp-pin": [2, 1] };
const FIXED_COLOR = new Set(["sp-girl1", "sp-girl2", "sp-girl3", "sp-bunny", "sp-guitar-a", "sp-guitar-b", "sp-skull2", "sp-vinyl", "sp-flower"]);
const MODE_MASCOT = { kawaii: "sp-bunny", emo: "sp-skull2" };

function installModeSprites() {
  if (document.getElementById("sp-heart")) return;
  const d = document.createElement("div"); d.innerHTML = MODE_SPRITES; document.body.prepend(d.firstElementChild);
}

const svgEl = (n) => document.createElementNS("http://www.w3.org/2000/svg", n);
const useSvg = (id, w, h, vb, cls) => { const s = svgEl("svg"); s.setAttribute("viewBox", vb); s.setAttribute("width", w); s.setAttribute("height", h); if (cls) s.setAttribute("class", cls);
  const u = svgEl("use"); u.setAttribute("href", "#" + id); s.append(u); return s; };
const VIEWBOX = { "sp-guitar-a": "0 0 64 160", "sp-guitar-b": "0 0 90 150", "sp-girl1": "0 0 120 172", "sp-girl2": "0 0 120 172", "sp-girl3": "0 0 120 172", "sp-bat": "0 0 32 20", "sp-pin": "0 0 64 32" };
const artUrl = (id) => `/modeart/${id}?t=${window.NOVA_TOKEN}`;

function buildDecor(mode, art) {
  installModeSprites();
  const host = document.getElementById("decor"); if (!host) return;
  host.replaceChildren();
  const cfg = DECOR[mode]; if (!cfg) return;
  const rnd = (a, b) => a + Math.random() * (b - a);
  const mine = (art || []).filter((a) => a.mode === mode);
  for (let i = 0; i < cfg.n; i++) {
    const photo = mine.length && i % 4 === 0 ? mine[(i / 4) % mine.length | 0] : null;
    const dur = rnd(cfg.kind === "rise" ? 18 : 30, cfg.kind === "rise" ? 36 : 64), common = `left:${rnd(0, 94).toFixed(1)}%;animation-duration:${dur.toFixed(1)}s;animation-delay:-${rnd(0, dur).toFixed(1)}s;--spin:${rnd(-18, 18).toFixed(0)}deg;`;
    let node;
    if (photo) {                                   // your own pictures drift by in little frames
      node = document.createElement("img"); node.src = artUrl(photo.id); node.alt = ""; node.className = "decor-item decor-photo decor-" + cfg.kind; node.style.cssText = common + `width:${rnd(64, 104).toFixed(0)}px;opacity:.95`;
    } else {
      const id = cfg.sprites[Math.floor(Math.random() * cfg.sprites.length)], bat = id === "sp-bat";
      const ratio = (TALL[id] || [1, 1]); const base = rnd(18, mode === "kawaii" ? 40 : 46);
      let w = base, h = base; if (id === "sp-bat") { w = rnd(26, 52); h = w * 0.62; } else if (id === "sp-pin") { w = base * 1.6; h = base * 0.8; } else if (TALL[id]) { h = base * 2.2; w = h * ratio[0] * (id.startsWith("sp-girl") ? 0.7 : 1); if (id.startsWith("sp-girl")) { h = base * 1.8; w = h * 0.7; } }
      node = useSvg(id, w.toFixed(0), h.toFixed(0), VIEWBOX[id] || "0 0 32 32", "decor-item " + (bat ? "decor-bat" : "decor-" + cfg.kind));
      node.style.cssText = common + (FIXED_COLOR.has(id) ? "" : `color:${cfg.colors[Math.floor(Math.random() * cfg.colors.length)]};`) + `opacity:${rnd(...cfg.op).toFixed(2)};` + (bat ? `top:${rnd(4, 70).toFixed(0)}%;` : "");
    }
    host.append(node);
  }
}

let railTimer = null;
function buildRailArt(mode, art) {
  const host = document.getElementById("railart"); if (!host) return;
  clearInterval(railTimer); host.replaceChildren(); host.dataset.kind = "";
  if (!MODE_MASCOT[mode]) return;
  const mine = (art || []).filter((a) => a.mode === mode);
  if (mine.length) {
    host.dataset.kind = "photos";
    const frame = document.createElement("div"); frame.className = "rail-frame";
    mine.forEach((a, i) => { const im = document.createElement("img"); im.src = artUrl(a.id); im.alt = "Your picture"; if (!i) im.className = "on"; frame.append(im); });
    host.append(frame);
    if (mine.length > 1) { let k = 0; railTimer = setInterval(() => { const ims = frame.querySelectorAll("img"); ims[k].classList.remove("on"); k = (k + 1) % ims.length; ims[k].classList.add("on"); }, 6000); }
  } else {
    host.dataset.kind = "art";
    const id = mode === "kawaii" ? "sp-girl1" : "sp-guitar-a";
    host.append(useSvg(id, mode === "kawaii" ? 128 : 84, mode === "kawaii" ? 176 : 210, VIEWBOX[id], "rail-svg"));
  }
}

function applyMode(mode, animated, art) {
  const r = document.documentElement; mode = MODES[mode] ? mode : "normal";
  const sig = mode + "|" + (animated ? 1 : 0) + "|" + (art || []).filter((a) => a.mode === mode).map((a) => a.id).join(",");
  r.dataset.mode = mode; r.dataset.decorAnim = animated ? "1" : "0";
  if (r.dataset.modeSig !== sig) { r.dataset.modeSig = sig; buildDecor(animated || mode !== "normal" ? mode : "normal", art); buildRailArt(mode, art); }
  const mark = document.querySelector(".brand-mark use");
  if (mark) mark.setAttribute("href", MODE_MASCOT[mode] ? "#" + MODE_MASCOT[mode] : "/static/nova.svg#nova");
  return mode;
}
