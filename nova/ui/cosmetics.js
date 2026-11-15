"use strict";
// ---------------------------------------------------------------- Nova cosmetics designer
// Everything is drawn on 64x64 skin / 64x32 cape canvases, so what you see is exactly what gets saved.

const COS = (() => {
  // ---- skin layout: every body part is a cuboid whose six faces sit at fixed places on the 64x64 texture
  const faces = (ox, oy, w, h, d) => ({
    top: [ox + d, oy, w, d], bottom: [ox + d + w, oy, w, d], right: [ox, oy + d, d, h],
    front: [ox + d, oy + d, w, h], left: [ox + d + w, oy + d, d, h], back: [ox + 2 * d + w, oy + d, w, h],
  });
  const parts = (slim) => { const aw = slim ? 3 : 4; return {
    head: faces(0, 0, 8, 8, 8), headO: faces(32, 0, 8, 8, 8), body: faces(16, 16, 8, 12, 4), bodyO: faces(16, 32, 8, 12, 4),
    rArm: faces(40, 16, aw, 12, 4), rArmO: faces(40, 32, aw, 12, 4), lArm: faces(32, 48, aw, 12, 4), lArmO: faces(48, 48, aw, 12, 4),
    rLeg: faces(0, 16, 4, 12, 4), rLegO: faces(0, 32, 4, 12, 4), lLeg: faces(16, 48, 4, 12, 4), lLegO: faces(0, 48, 4, 12, 4),
  }; };

  // ---- colors
  const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const hex = (c) => "#" + c.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
  const mix = (a, b, t) => { const x = rgb(a), y = rgb(b); return hex(x.map((v, i) => v + (y[i] - v) * t)); };
  const shade = (a, t) => (t >= 0 ? mix(a, "#ffffff", t) : mix(a, "#000000", -t));
  const palette = (c) => ({ main: c.main, trim: c.trim, hi: "#ffffff", dark: shade(c.main, -0.45), mid: mix(c.main, c.trim, 0.5) });

  // ---- painter: draws pixels addressed as (part, face, x, y) so cosmetics never touch the wrong place
  const painter = (ctx, slim) => {
    const P = parts(slim);
    const rect = (part, face, x, y, w, h, color, alpha = 1) => {
      const f = P[part][face]; if (!f) return;
      const x0 = Math.max(0, x), y0 = Math.max(0, y), x1 = Math.min(f[2], x + w), y1 = Math.min(f[3], y + h);
      if (x1 <= x0 || y1 <= y0) return;
      ctx.save(); ctx.globalAlpha = alpha; ctx.fillStyle = color; ctx.fillRect(f[0] + x0, f[1] + y0, x1 - x0, y1 - y0); ctx.restore();
    };
    const clear = (part, face) => { const f = P[part][face]; ctx.clearRect(f[0], f[1], f[2], f[3]); };
    const sides = ["front", "back", "left", "right"];
    return { rect, clear, sides, P, px: (part, face, x, y, c, a) => rect(part, face, x, y, 1, 1, c, a),
      shape: (part, face, x, y, rows, map) => rows.forEach((r, j) => [...r].forEach((ch, i) => { if (map[ch]) rect(part, face, x + i, y + j, 1, 1, map[ch]); })) };
  };

  // 8x8 four-point sparkle: the Nova mark
  const SPARK8 = ["...##...", "...##...", "..####..", "########", "########", "..####..", "...##...", "...##..."];
  const SPARK4 = [".#.", "###", ".#."];
  const SPARK5 = ["..#..", ".###.", "#####", ".###.", "..#.."];

  const sparkle = (p, part, face, x, y, c) => {
    p.shape(part, face, x, y, SPARK8, { "#": c.hi });
    p.rect(part, face, x + 3, y + 3, 2, 2, c.trim);
  };

  // ---- cosmetics (slot -> list). draw(p, c) paints onto the overlay layers.
  const HATS = [
    { id: "beanie", name: "Nova Beanie", draw: (p, c) => {
      p.rect("headO", "top", 0, 0, 8, 8, c.main);
      for (const f of p.sides) { p.rect("headO", f, 0, 0, 8, 3, c.main); p.rect("headO", f, 0, 3, 8, 1, c.trim); }
      p.shape("headO", "front", 2, 0, ["..##..", ".####.", "..##.."], { "#": c.hi });
      p.rect("headO", "front", 3, 1, 2, 1, c.trim);
    } },
    { id: "crown", name: "Star Crown", draw: (p, c) => {
      p.rect("headO", "top", 0, 0, 8, 8, c.trim, 0.95); p.rect("headO", "top", 1, 1, 6, 6, c.main);
      for (const f of p.sides) { p.rect("headO", f, 0, 1, 8, 1, c.trim); for (const x of [0, 2, 4, 6]) p.rect("headO", f, x, 0, 1, 1, c.trim); }
      p.rect("headO", "front", 3, 1, 2, 1, c.main); p.px("headO", "front", 3, 0, c.hi);
    } },
    { id: "headphones", name: "Nova Headphones", draw: (p, c) => {
      p.rect("headO", "top", 3, 0, 2, 8, c.main);
      for (const f of ["left", "right"]) { p.rect("headO", f, 3, 0, 2, 3, c.main); p.rect("headO", f, 2, 3, 4, 4, c.main); p.rect("headO", f, 3, 4, 2, 2, c.trim); p.px("headO", f, 3, 4, c.hi); }
      p.rect("headO", "front", 3, 0, 2, 1, c.main); p.rect("headO", "back", 3, 0, 2, 1, c.main);
    } },
    { id: "cap", name: "Nova Cap", draw: (p, c) => {
      p.rect("headO", "top", 0, 0, 8, 8, c.main);
      for (const f of p.sides) p.rect("headO", f, 0, 0, 8, 2, c.main);
      p.rect("headO", "front", 0, 2, 8, 1, c.trim); p.rect("headO", "right", 5, 2, 3, 1, c.trim); p.rect("headO", "left", 0, 2, 3, 1, c.trim);
      p.shape("headO", "front", 2, 0, ["..#..", ".###."], { "#": c.hi });
    } },
    { id: "ears", name: "Cat Ears", draw: (p, c) => {
      for (const x of [0, 6]) { p.rect("headO", "top", x, 1, 2, 3, c.main); p.rect("headO", "top", x + (x ? 0 : 1), 2, 1, 1, c.trim);
        p.rect("headO", "front", x, 0, 2, 2, c.main); p.rect("headO", "front", x + (x ? 0 : 1), 1, 1, 1, c.trim); p.rect("headO", "back", x, 0, 2, 2, c.main); }
      p.rect("headO", "right", 3, 0, 3, 1, c.main); p.rect("headO", "left", 2, 0, 3, 1, c.main);
    } },
    { id: "helmet", name: "Space Helmet", draw: (p, c) => {
      p.rect("headO", "top", 0, 0, 8, 8, c.main); p.rect("headO", "top", 1, 1, 6, 6, c.dark, 0.4);
      for (const f of ["back", "left", "right"]) { p.rect("headO", f, 0, 0, 8, 8, c.main); p.rect("headO", f, 0, 6, 8, 2, c.trim); }
      p.rect("headO", "front", 0, 0, 8, 1, c.trim); p.rect("headO", "front", 0, 7, 8, 1, c.trim); p.rect("headO", "front", 0, 1, 1, 6, c.trim); p.rect("headO", "front", 7, 1, 1, 6, c.trim);
      p.rect("headO", "front", 1, 1, 6, 6, c.mid, 0.28); p.px("headO", "front", 2, 2, c.hi, 0.9); p.px("headO", "front", 3, 2, c.hi, 0.6);
    } },
  ];
  const FACES = [
    { id: "visor", name: "Star Visor", draw: (p, c) => {
      p.rect("headO", "front", 0, 3, 8, 3, c.main, 0.82); p.px("headO", "front", 1, 3, c.hi, 0.9); p.px("headO", "front", 2, 4, c.hi, 0.5);
      p.rect("headO", "right", 5, 3, 3, 1, c.trim); p.rect("headO", "left", 0, 3, 3, 1, c.trim);
    } },
    { id: "shades", name: "Nova Shades", draw: (p, c) => {
      p.rect("headO", "front", 0, 3, 8, 1, c.trim); p.rect("headO", "front", 0, 4, 3, 2, c.main); p.rect("headO", "front", 5, 4, 3, 2, c.main);
      p.rect("headO", "front", 3, 4, 2, 1, c.trim); p.px("headO", "front", 0, 4, c.hi, 0.8); p.px("headO", "front", 5, 4, c.hi, 0.8);
      p.rect("headO", "right", 5, 3, 3, 1, c.trim); p.rect("headO", "left", 0, 3, 3, 1, c.trim);
    } },
    { id: "mask", name: "Gaiter", draw: (p, c) => {
      for (const f of p.sides) { p.rect("headO", f, 0, 5, 8, 3, c.main); }
      p.rect("headO", "front", 0, 5, 8, 1, c.trim); p.rect("headO", "right", 0, 5, 8, 1, c.trim); p.rect("headO", "left", 0, 5, 8, 1, c.trim); p.rect("headO", "back", 0, 5, 8, 1, c.trim);
      p.shape("headO", "front", 2, 6, ["#..#"], { "#": c.hi }); p.px("headO", "front", 3, 7, c.trim); p.px("headO", "front", 4, 7, c.trim);
    } },
  ];
  const CHEST = [
    { id: "emblem", name: "Nova Emblem", draw: (p, c) => { p.rect("bodyO", "front", 0, 0, 8, 12, c.main); sparkle(p, "bodyO", "front", 0, 2, c);
      p.rect("bodyO", "front", 0, 11, 8, 1, c.trim); } },
    { id: "hoodie", name: "Nova Hoodie", draw: (p, c) => {
      for (const f of p.sides) { p.rect("bodyO", f, 0, 0, 8, 12, c.main); p.rect("bodyO", f, 0, 10, 8, 2, c.trim); }
      for (const f of ["right", "left"]) { p.rect("bodyO", f, 0, 0, 4, 12, c.main); p.rect("bodyO", f, 0, 10, 4, 2, c.trim); }
      for (const a of ["rArmO", "lArmO"]) for (const f of [...p.sides]) { p.rect(a, f, 0, 0, 4, 12, c.main); p.rect(a, f, 0, 9, 4, 3, c.trim); }
      p.shape("bodyO", "front", 1, 2, SPARK4.map((r) => r), { "#": c.hi }); sparkle(p, "bodyO", "back", 0, 2, c);
    } },
    { id: "stripes", name: "Racing Stripes", draw: (p, c) => {
      for (const f of ["front", "back"]) { p.rect("bodyO", f, 0, 0, 1, 12, c.main); p.rect("bodyO", f, 7, 0, 1, 12, c.main); p.rect("bodyO", f, 1, 0, 1, 12, c.trim); p.rect("bodyO", f, 6, 0, 1, 12, c.trim); }
      for (const a of ["rArmO", "lArmO"]) for (const f of p.sides) { p.rect(a, f, 0, 4, 4, 1, c.main); p.rect(a, f, 0, 5, 4, 1, c.trim); }
    } },
  ];
  const FEET = [
    { id: "boots", name: "Nova Boots", draw: (p, c) => { for (const l of ["rLegO", "lLegO"]) for (const f of [...p.sides, "right"]) { p.rect(l, f, 0, 8, 4, 4, c.main); p.rect(l, f, 0, 8, 4, 1, c.trim); } } },
    { id: "sneakers", name: "Sneakers", draw: (p, c) => { for (const l of ["rLegO", "lLegO"]) for (const f of p.sides) { p.rect(l, f, 0, 10, 4, 2, c.hi); p.rect(l, f, 0, 11, 4, 1, c.main); } p.px("rLegO", "front", 1, 10, c.trim); p.px("lLegO", "front", 2, 10, c.trim); } },
  ];
  const SLOTS = [["hat", "Hats", HATS], ["face", "Face", FACES], ["chest", "Chest", CHEST], ["feet", "Feet", FEET]];

  // ---- capes (64x32 texture; the outside you see from behind is the 10x16 block at 1,1)
  const hash = (n) => { let x = Math.sin(n * 127.1) * 43758.5453; return x - Math.floor(x); };
  const CAPES = [
    { id: "classic", name: "Nova Classic", draw: (g, c) => {
      for (let y = 0; y < 16; y++) { g.fillStyle = mix(c.main, c.trim, y / 15 * 0.9); g.fillRect(1, 1 + y, 10, 1); }
      SPARK8.forEach((r, j) => [...r].forEach((ch, i) => { if (ch === "#") { g.fillStyle = "#ffffff"; g.fillRect(2 + i, 3 + j, 1, 1); } })); g.fillStyle = c.trim; g.fillRect(5, 6, 2, 2); } },
    { id: "nebula", name: "Nebula", draw: (g, c) => {
      g.fillStyle = mix("#070515", c.main, 0.25); g.fillRect(1, 1, 10, 16);
      for (let y = 0; y < 16; y++) for (let x = 0; x < 10; x++) { const k = Math.sin((x + y * 0.9) / 2.2); if (k > 0.55) { g.fillStyle = mix(c.main, c.trim, (x + y) / 26); g.globalAlpha = 0.55; g.fillRect(1 + x, 1 + y, 1, 1); g.globalAlpha = 1; } }
      for (let i = 0; i < 16; i++) { g.fillStyle = hash(i + 3) > 0.6 ? c.trim : "#ffffff"; g.fillRect(1 + Math.floor(hash(i) * 10), 1 + Math.floor(hash(i + 50) * 16), 1, 1); } } },
    { id: "void", name: "Void Edge", draw: (g, c) => {
      g.fillStyle = "#07050d"; g.fillRect(1, 1, 10, 16); g.fillStyle = c.trim; g.fillRect(1, 1, 10, 1); g.fillRect(1, 16, 10, 1); g.fillRect(1, 1, 1, 16); g.fillRect(10, 1, 1, 16);
      SPARK5.forEach((r, j) => [...r].forEach((ch, i) => { if (ch === "#") { g.fillStyle = c.main; g.fillRect(3 + i, 4 + j, 1, 1); } })); g.fillStyle = "#ffffff"; g.fillRect(5, 6, 1, 1);
      g.fillStyle = c.main; g.fillRect(2, 13, 8, 1); } },
    { id: "aurora", name: "Aurora", draw: (g, c) => {
      for (let y = 0; y < 16; y++) for (let x = 0; x < 10; x++) { const t = ((x * 1.3 + y) % 8) / 8; g.fillStyle = t < 0.5 ? mix(c.main, c.trim, t * 2) : mix(c.trim, c.main, (t - 0.5) * 2); g.fillRect(1 + x, 1 + y, 1, 1); }
      g.fillStyle = "rgba(255,255,255,.85)"; g.fillRect(5, 2, 1, 1); g.fillRect(8, 9, 1, 1); g.fillRect(3, 13, 1, 1); } },
    { id: "bigstar", name: "Big Nova", draw: (g, c) => {
      g.fillStyle = c.main; g.fillRect(1, 1, 10, 16);
      const S = ["....##....", "....##....", "...####...", "...####...", "..######..", "##########", "##########", "..######..", "...####...", "...####...", "....##....", "....##...."];
      S.forEach((r, j) => [...r].forEach((ch, i) => { if (ch === "#") { g.fillStyle = (i > 3 && i < 6 && j > 4 && j < 7) ? "#ffffff" : c.trim; g.fillRect(1 + i, 3 + j, 1, 1); } })); } },
  ];

  // ---- state
  const CS = { loaded: false, base: null, slim: false, sel: { hat: "", face: "", chest: "", feet: "", cape: "" },
    colors: { main: "#8b5cf6", trim: "#f0abfc" }, view: "front", ms: false, saved: false, baseNote: "Nova default skin", busy: false };
  const canvas = (w, h) => { const c = document.createElement("canvas"); c.width = w; c.height = h; return c; };

  // plain default skin so it works without any account (original art)
  const defaultBase = (slim) => {
    const c = canvas(64, 64), g = c.getContext("2d"), P = parts(slim);
    const box = (name, col) => { for (const f of Object.values(P[name])) { g.fillStyle = col; g.fillRect(...f); } };
    box("head", "#e6b794"); box("body", "#3a2a6b"); box("rArm", "#3a2a6b"); box("lArm", "#3a2a6b"); box("rLeg", "#1d1838"); box("lLeg", "#1d1838");
    g.fillStyle = "#24163f"; for (const f of ["top", "back", "left", "right"]) g.fillRect(...P.head[f]);
    const hf = P.head.front; g.fillRect(hf[0], hf[1], 8, 2); g.fillRect(hf[0], hf[1] + 2, 1, 1); g.fillRect(hf[0] + 7, hf[1] + 2, 1, 1);
    for (const f of ["left", "right"]) { const r = P.head[f]; g.fillRect(r[0], r[1], 8, 3); }
    g.fillStyle = "#ffffff"; g.fillRect(hf[0] + 1, hf[1] + 4, 2, 1); g.fillRect(hf[0] + 5, hf[1] + 4, 2, 1);
    g.fillStyle = "#6d4cff"; g.fillRect(hf[0] + 2, hf[1] + 4, 1, 1); g.fillRect(hf[0] + 5, hf[1] + 4, 1, 1);
    g.fillStyle = "#b3786a"; g.fillRect(hf[0] + 3, hf[1] + 6, 2, 1);
    g.fillStyle = "#2c2150"; g.fillRect(P.rArm.bottom[0], P.rArm.bottom[1], 4, 4);
    return c;
  };

  // legacy 64x32 skins -> 64x64 (per-face mirror of the right limbs onto the left)
  const upgradeLegacy = (img) => {
    const c = canvas(64, 64), g = c.getContext("2d"); g.imageSmoothingEnabled = false; g.drawImage(img, 0, 0);
    const flip = (sx, sy, w, h, dx, dy) => { g.save(); g.translate(dx + w, dy); g.scale(-1, 1); g.drawImage(c, sx, sy, w, h, 0, 0, w, h); g.restore(); };
    const mirror = (ox, oy, nx, ny) => { flip(ox + 4, oy, 4, 4, nx + 4, ny); flip(ox + 8, oy, 4, 4, nx + 8, ny);
      flip(ox, oy + 4, 4, 12, nx + 8, ny + 4); flip(ox + 4, oy + 4, 4, 12, nx + 4, ny + 4); flip(ox + 8, oy + 4, 4, 12, nx, ny + 4); flip(ox + 12, oy + 4, 4, 12, nx + 12, ny + 4); };
    mirror(0, 16, 16, 48); mirror(40, 16, 32, 48);
    return c;
  };

  const composeSkin = (only) => {
    const c = canvas(64, 64), g = c.getContext("2d"); g.imageSmoothingEnabled = false; g.drawImage(CS.base, 0, 0);
    const p = painter(g, CS.slim), pal = palette(CS.colors);
    for (const [slot, , list] of SLOTS) { if (only && only.slot !== slot) continue; const id = only ? only.id : CS.sel[slot]; const item = list.find((x) => x.id === id); if (item) item.draw(p, pal); }
    return c;
  };
  const composeCape = (id) => {
    id = id || CS.sel.cape; const item = CAPES.find((x) => x.id === id); if (!item) return null;
    const c = canvas(64, 32), g = c.getContext("2d"), pal = palette(CS.colors); g.imageSmoothingEnabled = false;
    g.fillStyle = pal.dark; g.fillRect(0, 0, 64, 32);                 // also what the elytra shows
    item.draw(g, pal);
    g.fillStyle = pal.trim; g.fillRect(0, 1, 1, 16); g.fillRect(11, 1, 1, 16); g.fillRect(1, 0, 10, 1); g.fillRect(11, 0, 10, 1);
    g.fillStyle = shade(pal.main, -0.55); g.fillRect(12, 1, 10, 16);   // inside of the cape
    return c;
  };

  // ---- flat "paper doll" preview, front or back, optionally with the cape
  const drawDoll = (g, skin, cape, view, slim, k) => {
    g.imageSmoothingEnabled = false; const P = parts(slim), aw = slim ? 3 : 4, back = view === "back";
    const blit = (part, face, dx, dy) => { for (const layer of [part, part + "O"]) { const f = P[layer][face]; g.drawImage(skin, f[0], f[1], f[2], f[3], dx * k, dy * k, f[2] * k, f[3] * k); } };
    const face = back ? "back" : "front";
    blit("head", face, 4, 0); blit("body", face, 4, 8);
    blit(back ? "lArm" : "rArm", face, 4 - aw, 8); blit(back ? "rArm" : "lArm", face, 12, 8);
    blit(back ? "lLeg" : "rLeg", face, 4, 20); blit(back ? "rLeg" : "lLeg", face, 8, 20);
    if (back && cape) g.drawImage(cape, 1, 1, 10, 16, 3 * k, 8 * k, 10 * k, 16 * k);
  };
  const cropTo = (src, sx, sy, sw, sh, size) => { const c = canvas(size, size), g = c.getContext("2d"); g.imageSmoothingEnabled = false; const s = Math.min(size / sw, size / sh); g.drawImage(src, sx, sy, sw, sh, (size - sw * s) / 2, (size - sh * s) / 2, sw * s, sh * s); return c; };

  const tilePreview = (slot, item) => {
    if (slot === "cape") { const cp = composeCape(item.id); return cropTo(cp, 1, 1, 10, 16, 72); }
    const sk = composeSkin({ slot, id: item.id }), d = canvas(16 * 6, 32 * 6); drawDoll(d.getContext("2d"), sk, null, "front", CS.slim, 6);
    const r = { hat: [4, 0, 8, 8], face: [4, 0, 8, 8], chest: [3, 8, 10, 12], feet: [4, 20, 8, 12] }[slot];
    return cropTo(d, r[0] * 6, r[1] * 6, r[2] * 6, r[3] * 6, 72);
  };

  const toDataURL = (c) => c.toDataURL("image/png");
  const loadImage = (src) => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error("Couldn't read that image.")); i.src = src; });
  const imageToBase = (img) => {
    if (img.width !== 64 || (img.height !== 64 && img.height !== 32)) throw new Error("Skins must be 64x64 (or old 64x32) PNG files.");
    if (img.height === 32) return upgradeLegacy(img);
    const c = canvas(64, 64); c.getContext("2d").drawImage(img, 0, 0); return c;
  };

  return { CS, SLOTS, CAPES, HATS, composeSkin, composeCape, drawDoll, tilePreview, defaultBase, imageToBase, loadImage, toDataURL, canvas, palette };
})();

async function pageCosmetics(v) {
  const { CS } = COS;
  const info = await api("/api/cosmetics");
  CS.ms = info.microsoft; const saved = info.cosmetics; CS.saved = saved.has_skin;
  if (!CS.loaded) {
    CS.sel = { ...saved.selected }; CS.colors = { ...saved.colors }; CS.slim = saved.variant === "slim";
    CS.base = null;
    if (saved.has_base) { try { const r = await api("/api/cosmetics/file?kind=base"); CS.base = COS.imageToBase(await COS.loadImage("data:image/png;base64," + r.png)); CS.baseNote = "Your saved base skin"; } catch { CS.base = null; } }
    if (!CS.base) { CS.base = COS.defaultBase(CS.slim); CS.baseNote = "Nova default skin"; }
    CS.loaded = true;
  }
  const preview = el("canvas", { width: "384", height: "384", class: "cos-preview", role: "img", "aria-label": "Preview of your character" });
  const draw = () => {
    const g = preview.getContext("2d"); g.clearRect(0, 0, 384, 384); const skin = COS.composeSkin(), cape = COS.composeCape();
    const k = 11, d = COS.canvas(16 * k, 32 * k); COS.drawDoll(d.getContext("2d"), skin, cape, CS.view, CS.slim, k);
    g.imageSmoothingEnabled = false; g.drawImage(d, (384 - 16 * k) / 2, 16);
  };
  const tabs = el("div", { class: "seg", role: "group", "aria-label": "Category" });
  const grid = el("div", { class: "cos-grid" });
  let slot = CS.slot || "hat";
  const refreshGrid = () => {
    tabs.replaceChildren(...[...COS.SLOTS.map(([id, label]) => [id, label]), ["cape", "Capes"]].map(([id, label]) => el("button", { "aria-pressed": String(slot === id), onclick: () => { slot = id; CS.slot = id; refreshGrid(); } }, label)));
    const items = slot === "cape" ? COS.CAPES : COS.SLOTS.find((s) => s[0] === slot)[2];
    const none = el("button", { class: "cos-tile", "aria-pressed": String(!CS.sel[slot]), title: "None", onclick: () => { CS.sel[slot] = ""; update(); } }, el("div", { class: "cos-none" }, "∅"), el("span", {}, "None"));
    grid.replaceChildren(none, ...items.map((it) => el("button", { class: "cos-tile", "aria-pressed": String(CS.sel[slot] === it.id), title: it.name, onclick: () => { CS.sel[slot] = it.id; update(); } }, COS.tilePreview(slot, it), el("span", {}, it.name))));
  };
  const update = () => { draw(); refreshGrid(); };
  const colorInput = (label, key) => { const c = el("input", { type: "color", value: CS.colors[key], "aria-label": label }); c.addEventListener("input", () => { CS.colors[key] = c.value; draw(); }); c.addEventListener("change", update); return el("div", { class: "row" }, c, el("span", {}, label)); };
  const model = el("div", { class: "seg", role: "group", "aria-label": "Arm style" });
  const refreshModel = () => model.replaceChildren(...[["classic", "Classic arms"], ["slim", "Slim arms"]].map(([k, l]) => el("button", { "aria-pressed": String((CS.slim ? "slim" : "classic") === k), onclick: () => { CS.slim = k === "slim"; refreshModel(); update(); } }, l)));
  const viewSeg = el("div", { class: "seg", role: "group", "aria-label": "View" });
  const refreshView = () => viewSeg.replaceChildren(...[["front", "Front"], ["back", "Back"]].map(([k, l]) => el("button", { "aria-pressed": String(CS.view === k), onclick: () => { CS.view = k; refreshView(); draw(); } }, l)));

  const payload = () => ({ skin: COS.toDataURL(COS.composeSkin()), cape: CS.sel.cape ? COS.toDataURL(COS.composeCape()) : null, base: COS.toDataURL(CS.base),
    state: { selected: CS.sel, colors: CS.colors, variant: CS.slim ? "slim" : "classic" } });
  const save = async () => { await api("/api/cosmetics/save", { method: "POST", body: payload() }); CS.saved = true; };
  const busy = (btn, fn) => async () => { if (CS.busy) return; CS.busy = true; btn.disabled = true; try { await fn(); } catch (e) { fail(e); } CS.busy = false; btn.disabled = false; };
  const bSave = el("button", { class: "btn primary" }, "Save");
  bSave.addEventListener("click", busy(bSave, async () => { await save(); toast("Saved. Nova copies it into your games when you launch.", "ok"); }));
  const bApply = el("button", { class: "btn" }, "Save & use on my Minecraft account");
  bApply.addEventListener("click", busy(bApply, async () => { await save(); await api("/api/cosmetics/apply-skin", { method: "POST", body: {} }); toast("Your Minecraft skin was updated. Other players see it after a minute or two.", "ok"); }));
  const bDl = el("button", { class: "btn ghost", onclick: () => { const a = document.createElement("a"); a.href = COS.toDataURL(COS.composeSkin()); a.download = "nova-skin.png"; a.click(); } }, icon("download"), "Download skin");
  const bMine = el("button", { class: "btn ghost" }, "Use my Minecraft skin");
  bMine.addEventListener("click", busy(bMine, async () => {
    const r = await api("/api/cosmetics/current-skin"); if (!r.png) { toast("No skin found on your account.", "err"); return; }
    CS.base = COS.imageToBase(await COS.loadImage("data:image/png;base64," + r.png)); CS.slim = r.variant === "slim"; CS.baseNote = "Your Minecraft skin"; refreshModel(); update(); toast("Loaded your Minecraft skin.", "ok");
  }));
  const bUp = el("button", { class: "btn ghost", onclick: () => { const f = el("input", { type: "file", accept: "image/png,.png" });
    f.addEventListener("change", async () => { if (!f.files[0]) return; try { CS.base = COS.imageToBase(await COS.loadImage(URL.createObjectURL(f.files[0]))); CS.baseNote = "Uploaded skin"; update(); } catch (e) { fail(e); } }); f.click(); } }, "Upload a skin…");
  const bDef = el("button", { class: "btn ghost", onclick: () => { CS.base = COS.defaultBase(CS.slim); CS.baseNote = "Nova default skin"; update(); } }, "Nova default skin");
  const bClear = el("button", { class: "btn ghost", onclick: () => confirmDialog("Reset cosmetics?", "This clears your selection and the saved skin and cape. Your Minecraft account's skin isn't touched.", "Reset", async () => { await api("/api/cosmetics/reset", { method: "POST", body: {} }); CS.loaded = false; CS.slot = null; render(); }) }, "Reset");

  refreshModel(); refreshView(); update();
  v.append(
    el("div", { class: "page-head" }, el("div", { class: "grow" }, el("h1", {}, "Cosmetics"), el("p", {}, "Design a Nova look: hats, face gear, chest emblems, boots and capes with the Nova mark. Colors are fully yours."))),
    el("div", { class: "cos" },
      el("div", { class: "card section cos-left" }, preview, el("div", { class: "row", style: { "justify-content": "center", gap: "12px", "flex-wrap": "wrap", "margin-top": "8px" } }, viewSeg, model),
        el("p", { class: "muted small", style: { "text-align": "center", margin: "8px 0 0" } }, "Base: " + CS.baseNote)),
      el("div", { class: "card section cos-right" }, tabs, el("div", { style: { height: "14px" } }), grid, el("div", { style: { height: "16px" } }),
        el("div", { class: "row", style: { gap: "24px", "flex-wrap": "wrap" } }, colorInput("Main color", "main"), colorInput("Trim color", "trim")),
        el("div", { style: { height: "16px" } }),
        el("div", { class: "row", style: { "flex-wrap": "wrap" } }, bSave, CS.ms ? bApply : null, bDl),
        el("div", { style: { height: "10px" } }),
        el("div", { class: "row", style: { "flex-wrap": "wrap" } }, CS.ms ? bMine : null, bUp, bDef, bClear),
        el("p", { class: "muted small", style: { margin: "14px 0 0", "line-height": "1.5" } },
          "Hats, face gear, chest and boots are painted into your skin, so “Use on my Minecraft account” shows them to everyone online (Microsoft profiles only). " +
          "Minecraft can't upload custom capes, so the Nova cape and your skin show on your own character through the Nova in-game mod (Fabric 1.21.1 and 1.21.8)."))));
}
