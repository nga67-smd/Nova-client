package dev.nova.visuals.gui;

import dev.nova.visuals.NovaVisuals;
import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Config;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.ModuleManager;
import dev.nova.visuals.config.Presets;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.core.Colors;
import dev.nova.visuals.core.Easing;
import dev.nova.visuals.core.Smooth;
import dev.nova.visuals.core.Time;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.text.Text;
import org.lwjgl.glfw.GLFW;

import java.util.ArrayList;
import java.util.List;
import java.util.function.BiConsumer;
import java.util.function.IntConsumer;

/** The menu: a dark, rounded, blurred panel with categories, searchable module cards, color pickers and a live preview. */
public final class ClickGui extends Screen {
    private static final int TEXT = 0xFFEDEDF5, DIM = 0xFF8E8EA0, PANEL = 0x0B0B12;
    private static Category lastCategory = Category.VISUALS;

    private final MinecraftClient mc = MinecraftClient.getInstance();
    private final Smooth open = new Smooth(0f, 11f);
    private final Smooth selY = new Smooth(0f, 16f);
    private final Smooth.Pool anim = new Smooth.Pool(16f);
    private boolean closing;

    private Category cat = lastCategory;
    private float scroll, scrollTarget, contentH;
    private final StringBuilder search = new StringBuilder(), hexText = new StringBuilder(), presetName = new StringBuilder();
    private String focus = "search";
    private Setting.Color picking;
    private float pickH, pickS, pickV;
    private String status = "";
    private float statusTime;
    private Module hovered;
    private List<String> presetCache = new ArrayList<>();
    private float presetCacheAt = -10f;

    // layout of the current frame (panel space)
    private float px, py, pw, ph, sideW, prevW, cx0, cy0, cx1, cy1;
    private float scale = 1f;

    private static final class Region {
        float x, y, w, h, clipY0, clipY1;
        Object owner;
        IntConsumer click;
        BiConsumer<Double, Double> drag;
        boolean has(double mx, double my) {
            return mx >= x && mx < x + w && my >= Math.max(y, clipY0) && my < Math.min(y + h, clipY1);
        }
    }

    private final List<Region> regions = new ArrayList<>();
    private Region active;

    public ClickGui() {
        super(Text.literal("Nova Visuals"));
    }

    @Override public boolean shouldPause() { return false; }
    @Override public boolean shouldCloseOnEsc() { return false; }

    @Override
    protected void init() {
        selY.snap(-1f);
    }

    @Override
    public void removed() {
        lastCategory = cat;
        Config.saveNow();
    }

    private void startClose() { closing = true; }

    private void say(String s) { status = s; statusTime = 4f; }

    // ---------------------------------------------------------------- regions
    private Region region(float x, float y, float w, float h, IntConsumer click) {
        Region r = new Region();
        r.x = x; r.y = y; r.w = w; r.h = h; r.click = click;
        r.clipY0 = -1e9f; r.clipY1 = 1e9f;
        regions.add(r);
        return r;
    }

    private Region clipped(float x, float y, float w, float h, IntConsumer click) {
        Region r = region(x, y, w, h, click);
        r.clipY0 = cy0; r.clipY1 = cy1;
        return r;
    }

    // ---------------------------------------------------------------- render
    @Override
    public void render(DrawContext ctx, int mouseX, int mouseY, float delta) {
        Time.frame();
        float dt = Time.dt() * Settings.get().menuSpeed.value;
        open.set(closing ? 0f : 1f);
        float o = open.update(dt);
        if (closing && o < 0.02f) { mc.setScreen(null); return; }
        float e = Easing.outCubic(Easing.clamp01(o));
        scale = 0.93f + 0.07f * e;

        int sw = ctx.getScaledWindowWidth(), sh = ctx.getScaledWindowHeight();
        if (Settings.get().menuBlur.value) {
            renderBackground(ctx, mouseX, mouseY, delta);
        } else {
            ctx.fill(0, 0, sw, sh, (int) (110 * e) << 24);
        }

        pw = Math.min(640, sw - 16); ph = Math.min(400, sh - 16);
        px = (sw - pw) / 2f; py = (sh - ph) / 2f;
        sideW = 118; prevW = pw >= 560 ? 142 : 0;
        cx0 = px + sideW + 12; cx1 = px + pw - prevW - (prevW > 0 ? 14 : 12);
        cy0 = py + 52; cy1 = py + ph - 10;

        float mx = (float) ((mouseX - sw / 2.0) / scale + sw / 2.0), my = (float) ((mouseY - sh / 2.0) / scale + sh / 2.0);
        regions.clear();
        hovered = null;

        dev.nova.visuals.Compat.push(ctx);
        dev.nova.visuals.Compat.translate(ctx, sw / 2f, sh / 2f);
        dev.nova.visuals.Compat.scale(ctx, scale);
        dev.nova.visuals.Compat.translate(ctx, -sw / 2f, -sh / 2f);

        drawPanel(ctx, e, dt);
        drawSidebar(ctx, e, dt, mx, my);
        drawHeader(ctx, e, mx, my);
        drawContent(ctx, e, dt, mx, my);
        if (prevW > 0) drawPreview(ctx, e, dt);
        if (picking != null) drawPicker(ctx, e, dt, mx, my);
        if (statusTime > 0f) {
            statusTime -= Time.dt();
            Draw.textCentered(ctx, textRenderer, status, px + pw / 2f, py + ph - 9, Draw.fade(0xFFFFFFFF, Math.min(1f, statusTime) * e), true);
        }
        dev.nova.visuals.Compat.pop(ctx);
    }

    private void drawPanel(DrawContext ctx, float e, float dt) {
        int ac = Settings.accent();
        Draw.shadow(ctx, px, py, pw, ph, 14, 10, 26, 0.6f * e);
        Draw.glow(ctx, px, py, pw, ph, 14, ac, 0.22f * e, 6, 10);
        Draw.round(ctx, px, py, pw, ph, 14, (int) (0.9f * 255 * e) << 24 | PANEL);
        Draw.round(ctx, px, py, sideW, ph, 14, (int) (0.55f * 255 * e) << 24 | 0x050509);
        ctx.fill((int) (px + sideW - 14), (int) py + 4, (int) (px + sideW), (int) (py + ph - 4), (int) (0.55f * 255 * e) << 24 | 0x050509);
        Draw.outline(ctx, px, py, pw, ph, 14, 1, Draw.fade(0xFF000000 | Colors.lerp(ac, 0xFFFFFF, 0.2f), 0.35f * e));
        // thin animated accent line on top
        Draw.gradientBar(ctx, (int) px + 16, (int) py + 1, (int) pw - 32, 1, ac, Settings.accent2(), Time.time() * 0.2f);
    }

    private void drawSidebar(DrawContext ctx, float e, float dt, float mx, float my) {
        TextRenderer tr = textRenderer;
        int ac = Settings.accent();
        Draw.text(ctx, tr, "NOVA", px + 16, py + 14, Draw.fade(0xFF000000 | ac, e), true);
        Draw.text(ctx, tr, "VISUALS", px + 16 + tr.getWidth("NOVA ") , py + 14, Draw.fade(0xFFFFFFFF, e), true);
        Draw.text(ctx, tr, "client-side cosmetics", px + 16, py + 26, Draw.fade(DIM, e), false);
        float y = py + 50;
        Category[] cats = Category.values();
        for (int i = 0; i < cats.length; i++) {
            Category c = cats[i];
            float ty = y + i * 28;
            boolean sel = c == cat && search.length() == 0;
            if (sel && selY.get() < 0) selY.snap(ty);
            if (sel) selY.set(ty);
        }
        float sy = selY.update(dt);
        if (search.length() == 0) {
            Draw.round(ctx, px + 8, sy, sideW - 16, 24, 8, Draw.fade(0xFF000000 | Colors.lerp(PANEL, ac, 0.35f), 0.85f * e));
            Draw.round(ctx, px + 8, sy + 5, 3, 14, 1, Draw.fade(0xFF000000 | ac, e));
        }
        for (int i = 0; i < cats.length; i++) {
            Category c = cats[i];
            float ty = y + i * 28;
            boolean hover = Draw.in(mx, my, px + 8, ty, sideW - 16, 24);
            float h = anim.to("cat" + i, hover ? 1f : 0f, dt);
            if (h > 0.01f && !(c == cat && search.length() == 0)) Draw.round(ctx, px + 8, ty, sideW - 16, 24, 8, Draw.fade(0x22FFFFFF, h * e));
            int col = c == cat && search.length() == 0 ? TEXT : Colors.lerp(0x8E8EA0, 0xFFFFFF, h) | 0xFF000000;
            Draw.text(ctx, tr, c.label, px + 20, ty + 8, Draw.fade(col, e), false);
            int on = 0, all = 0;
            for (Module m : ModuleManager.in(c)) { all++; if (m.enabled()) on++; }
            String n = c == Category.SETTINGS ? "" : on + "/" + all;
            Draw.text(ctx, tr, n, px + sideW - 14 - tr.getWidth(n), ty + 8, Draw.fade(0xFF6A6A7C, e), false);
            final Category cc = c;
            region(px + 8, ty, sideW - 16, 24, b -> { cat = cc; search.setLength(0); scrollTarget = 0; scroll = 0; });
        }
    }

    private void drawHeader(DrawContext ctx, float e, float mx, float my) {
        TextRenderer tr = textRenderer;
        String title = search.length() > 0 ? "Search" : cat.label;
        Draw.text(ctx, tr, title, cx0, py + 16, Draw.fade(TEXT, e), true);
        float sw = Math.min(190, cx1 - cx0 - tr.getWidth(title) - 20);
        float sx = cx1 - sw, sy = py + 11;
        boolean f = "search".equals(focus);
        float k = anim.to("searchfocus", f ? 1f : 0f, Time.dt());
        Draw.round(ctx, sx, sy, sw, 20, 8, Draw.fade(0xFF000000 | Colors.lerp(0x15151F, Settings.accent(), 0.2f * k), 0.9f * e));
        if (k > 0.05f) Draw.outline(ctx, sx, sy, sw, 20, 8, 1, Draw.fade(0xFF000000 | Settings.accent(), 0.7f * k * e));
        String shown = search.length() == 0 ? "Search modules..." : tr.trimToWidth(search.toString(), (int) sw - 16);
        Draw.text(ctx, tr, shown, sx + 8, sy + 6, Draw.fade(search.length() == 0 ? 0xFF5E5E70 : TEXT, e), false);
        if (f && (int) (Time.time() * 2) % 2 == 0) {
            int w = search.length() == 0 ? 0 : tr.getWidth(shown);
            ctx.fill((int) (sx + 8 + w), (int) sy + 5, (int) (sx + 9 + w), (int) sy + 15, Draw.fade(0xFFFFFFFF, e));
        }
        region(sx, sy, sw, 20, b -> focus = "search");
        // divider
        ctx.fill((int) cx0, (int) py + 40, (int) cx1, (int) py + 41, Draw.fade(0x22FFFFFF, e));
    }

    // ---------------------------------------------------------------- content
    private void drawContent(DrawContext ctx, float e, float dt, float mx, float my) {
        scrollTarget = Easing.clamp(scrollTarget, 0f, Math.max(0f, contentH - (cy1 - cy0)));
        scroll += (scrollTarget - scroll) * (1f - (float) Math.exp(-18f * dt));
        ctx.enableScissor((int) cx0 - 6, (int) cy0, (int) cx1 + 6, (int) cy1);
        float y = cy0 - scroll;
        float w = cx1 - cx0;
        List<Module> list = new ArrayList<>();
        if (search.length() > 0) {
            for (Module m : ModuleManager.all()) if (m.matches(search.toString())) list.add(m);
        } else {
            list.addAll(ModuleManager.in(cat));
        }
        if (search.length() == 0 && cat == Category.HUD) {
            y += button(ctx, "Edit HUD layout (drag and resize)", cx0, y, w, e, dt, mx, my, Settings.accent(), b -> mc.setScreen(new HudEditor(this))) + 8;
        }
        for (Module m : list) y += card(ctx, m, cx0, y, w, e, dt, mx, my) + 6;
        if (list.isEmpty()) Draw.textCentered(ctx, textRenderer, "No modules match.", (cx0 + cx1) / 2, y + 30, Draw.fade(DIM, e), false);
        if (search.length() == 0 && cat == Category.SETTINGS) y = presets(ctx, cx0, y + 4, w, e, dt, mx, my);
        contentH = y + scroll - cy0 + 4;
        ctx.disableScissor();
        // scrollbar
        float view = cy1 - cy0;
        if (contentH > view) {
            float bh = Math.max(24, view * view / contentH), by = cy0 + (view - bh) * (scroll / (contentH - view));
            Draw.round(ctx, cx1 + 4, by, 3, bh, 1, Draw.fade(0x55FFFFFF, e));
        }
    }

    private int rowHeight(Setting s) {
        if (s instanceof Setting.Num) return 30;
        return 22;
    }

    private float bodyHeight(Module m) {
        float h = 8;
        for (Setting s : m.settings) if (s.visible.getAsBoolean()) h += rowHeight(s);
        return h;
    }

    private float card(DrawContext ctx, Module m, float x, float y, float w, float e, float dt, float mx, float my) {
        TextRenderer tr = textRenderer;
        int ac = Settings.accent();
        boolean canOpen = !m.settings.isEmpty();
        m.openAnim.set(m.expanded ? 1f : 0f);
        float k = m.openAnim.update(dt);
        float body = bodyHeight(m) * Easing.smoothstep(k);
        float h = 32 + (k > 0.001f ? body : 0);
        float sw = m.switchAnim.update(dt);
        boolean visible = y + h > cy0 - 4 && y < cy1 + 4;
        if (visible) {
            boolean hover = Draw.in(mx, my, x, y, w, 32) && my >= cy0 && my < cy1;
            if (hover) hovered = m;
            float hv = anim.to("card" + m.id, hover ? 1f : 0f, dt);
            if (sw > 0.02f) Draw.glow(ctx, x, y, w, h, 9, ac, 0.28f * sw * e, 3, 5);
            Draw.round(ctx, x, y, w, h, 9, Draw.fade(0xFF000000 | Colors.lerp(0x13131C, 0x1B1B28, hv), 0.92f * e));
            if (sw > 0.02f) Draw.outline(ctx, x, y, w, h, 9, 1, Draw.fade(0xFF000000 | ac, 0.45f * sw * e));
            Draw.text(ctx, tr, m.name, x + 12, y + 6, Draw.fade(TEXT, e), true);
            String d = tr.trimToWidth(m.description, (int) (w - 90));
            Draw.text(ctx, tr, d, x + 12, y + 18, Draw.fade(DIM, e), false);
            if (!(m instanceof Settings)) toggle(ctx, x + w - 44, y + 8, 32, 16, sw, e, ac);
            if (canOpen) Draw.text(ctx, tr, k > 0.5f ? "v" : ">", x + w - 58, y + 12, Draw.fade(DIM, e), false);
            if (!(m instanceof Settings)) {
                clipped(x + w - 46, y + 6, 36, 20, b -> m.toggle());
            }
            if (canOpen) clipped(x, y, w - 48, 32, b -> { m.expanded = !m.expanded; });
            if (k > 0.001f) {
                ctx.enableScissor((int) x, (int) Math.max(cy0, y + 32), (int) (x + w), (int) Math.min(cy1, y + h));
                float ry = y + 36;
                for (Setting s : m.settings) {
                    if (!s.visible.getAsBoolean()) continue;
                    drawSetting(ctx, s, x + 12, ry, w - 24, e * Easing.smoothstep(k), dt, mx, my, k > 0.95f);
                    ry += rowHeight(s);
                }
                ctx.disableScissor();
            }
        }
        return h;
    }

    private void toggle(DrawContext ctx, float x, float y, float w, float h, float on, float e, int ac) {
        int track = Colors.lerp(0x2A2A38, ac, on);
        Draw.round(ctx, x, y, w, h, h / 2f, Draw.fade(0xFF000000 | track, e));
        float kx = x + 2 + (w - h) * on + h / 2f - 2;
        Draw.disc(ctx, kx, y + h / 2f, h / 2f - 3, Draw.fade(0xFF000000 | Colors.lerp(0xA0A0B0, 0xFFFFFF, on), e));
    }

    private void drawSetting(DrawContext ctx, Setting s, float x, float y, float w, float e, float dt, float mx, float my, boolean live) {
        TextRenderer tr = textRenderer;
        int ac = Settings.accent();
        if (s instanceof Setting.Bool b) {
            Draw.text(ctx, tr, s.name, x, y + 4, Draw.fade(0xFFD0D0DC, e), false);
            float a = anim.to(b, b.value ? 1f : 0f, dt, b.value ? 1f : 0f);
            toggle(ctx, x + w - 28, y + 2, 28, 14, a, e, ac);
            if (live) clipped(x, y, w, 20, btn -> { b.value = !b.value; Config.markDirty(); });
        } else if (s instanceof Setting.Num n) {
            Draw.text(ctx, tr, s.name, x, y + 2, Draw.fade(0xFFD0D0DC, e), false);
            String v = n.step >= 1f ? String.valueOf(n.asInt()) : (n.step >= 0.1f ? String.format("%.1f", n.value) : String.format("%.2f", n.value));
            v += n.suffix;
            Draw.text(ctx, tr, v, x + w - tr.getWidth(v), y + 2, Draw.fade(0xFF000000 | ac, e), false);
            float ty = y + 18, tw = w;
            float t = (n.value - n.min) / (n.max - n.min);
            boolean hv = Draw.in(mx, my, x, ty - 5, tw, 12) && live;
            float hk = anim.to(n, hv || isDragging(n) ? 1f : 0f, dt);
            Draw.round(ctx, x, ty, tw, 4, 2, Draw.fade(0xFF2A2A38, e));
            Draw.round(ctx, x, ty, Math.max(4, tw * t), 4, 2, Draw.fade(0xFF000000 | ac, e));
            Draw.disc(ctx, x + tw * t, ty + 2, 4 + hk * 1.5f, Draw.fade(0xFFFFFFFF, e));
            if (live) {
                Region r = clipped(x - 4, ty - 6, tw + 8, 16, b -> { });
                BiConsumer<Double, Double> set = (px2, py2) -> { n.set((float) (n.min + Easing.clamp01((float) ((px2 - x) / tw)) * (n.max - n.min))); Config.markDirty(); };
                r.click = b -> { };
                r.drag = set;
                r.owner = n;
            }
        } else if (s instanceof Setting.Choice c) {
            Draw.text(ctx, tr, s.name, x, y + 4, Draw.fade(0xFFD0D0DC, e), false);
            String v = c.get();
            float cw = tr.getWidth(v) + 16, bx = x + w - cw;
            Draw.round(ctx, bx, y + 1, cw, 16, 6, Draw.fade(0xFF000000 | Colors.lerp(0x1E1E2A, ac, 0.25f), e));
            Draw.textCentered(ctx, tr, v, bx + cw / 2f, y + 5, Draw.fade(TEXT, e), false);
            if (live) clipped(bx - 20, y, cw + 24, 20, b -> {
                c.index = b == 1 ? (c.index - 1 + c.options.length) % c.options.length : (c.index + 1) % c.options.length;
                Config.markDirty();
            });
        } else if (s instanceof Setting.Color col) {
            Draw.text(ctx, tr, s.name, x, y + 4, Draw.fade(0xFFD0D0DC, e), false);
            String hx = Colors.hex(col.value);
            float bw = tr.getWidth(hx) + 30, bx = x + w - bw;
            Draw.round(ctx, bx, y + 1, bw, 16, 6, Draw.fade(0xFF1E1E2A, e));
            Draw.round(ctx, bx + 3, y + 4, 16, 10, 4, Draw.fade(0xFF000000 | col.value, e));
            Draw.text(ctx, tr, hx, bx + 23, y + 5, Draw.fade(0xFFB8B8C8, e), false);
            if (live) clipped(bx, y, bw, 18, b -> openPicker(col));
        }
    }

    private boolean isDragging(Object o) { return active != null && active.owner == o; }

    private float button(DrawContext ctx, String label, float x, float y, float w, float e, float dt, float mx, float my, int color, IntConsumer click) {
        return buttonRect(ctx, label, x, y, w, 24, e, dt, mx, my, color, click);
    }

    private float buttonRect(DrawContext ctx, String label, float x, float y, float w, float h, float e, float dt, float mx, float my, int color, IntConsumer click) {
        boolean hv = Draw.in(mx, my, x, y, w, h) && my >= cy0 && my < cy1;
        float k = anim.to("btn" + label + (int) x + "_" + (int) (y + scroll), hv ? 1f : 0f, dt);
        Draw.round(ctx, x, y, w, h, 8, Draw.fade(0xFF000000 | Colors.lerp(Colors.lerp(0x16161F, color, 0.22f), color, 0.35f * k), 0.95f * e));
        Draw.outline(ctx, x, y, w, h, 8, 1, Draw.fade(0xFF000000 | color, (0.35f + 0.4f * k) * e));
        Draw.textCentered(ctx, textRenderer, label, x + w / 2f, y + (h - 8) / 2f, Draw.fade(TEXT, e), false);
        clipped(x, y, w, h, click);
        return h;
    }

    private float presets(DrawContext ctx, float x, float y, float w, float e, float dt, float mx, float my) {
        TextRenderer tr = textRenderer;
        int ac = Settings.accent();
        Draw.text(ctx, tr, "PRESETS", x + 2, y, Draw.fade(DIM, e), false);
        y += 14;
        float bw = (w - 8) / 2f;
        for (int i = 0; i < Presets.NAMES.length; i++) {
            String n = Presets.NAMES[i];
            float bx = x + (i % 2) * (bw + 8), by = y + (i / 2) * 28;
            buttonRect(ctx, n, bx, by, bw, 22, e, dt, mx, my, ac, b -> { Presets.apply(n); say("Preset applied: " + n); });
        }
        y += ((Presets.NAMES.length + 1) / 2) * 28 + 6;
        Draw.text(ctx, tr, "YOUR PRESETS", x + 2, y, Draw.fade(DIM, e), false);
        y += 14;
        if (Time.time() - presetCacheAt > 1f) { presetCache = Config.userPresets(); presetCacheAt = Time.time(); }
        List<String> mine = presetCache;
        if (mine.isEmpty()) { Draw.text(ctx, tr, "None saved yet.", x + 4, y + 2, Draw.fade(0xFF5E5E70, e), false); y += 18; }
        for (String n : mine) {
            Draw.round(ctx, x, y, w, 22, 8, Draw.fade(0xFF13131C, e));
            Draw.text(ctx, tr, tr.trimToWidth(n, (int) w - 120), x + 10, y + 7, Draw.fade(TEXT, e), false);
            buttonRect(ctx, "Load", x + w - 98, y + 2, 44, 18, e, dt, mx, my, ac, b -> { if (Config.loadPreset(n)) say("Loaded " + n); else say("Could not load " + n); });
            buttonRect(ctx, "Delete", x + w - 50, y + 2, 46, 18, e, dt, mx, my, 0xFF4D5A, b -> { Config.deletePreset(n); presetCacheAt = -10f; say("Deleted " + n); });
            y += 26;
        }
        // save current as ...
        boolean f = "preset".equals(focus);
        float fw = w - 78;
        Draw.round(ctx, x, y, fw, 22, 8, Draw.fade(0xFF000000 | Colors.lerp(0x15151F, ac, f ? 0.2f : 0f), e));
        if (f) Draw.outline(ctx, x, y, fw, 22, 8, 1, Draw.fade(0xFF000000 | ac, 0.7f * e));
        String shown = presetName.length() == 0 ? "Name for a new preset" : presetName.toString();
        Draw.text(ctx, tr, shown, x + 8, y + 7, Draw.fade(presetName.length() == 0 ? 0xFF5E5E70 : TEXT, e), false);
        if (f && (int) (Time.time() * 2) % 2 == 0) {
            int cw = presetName.length() == 0 ? 0 : tr.getWidth(shown);
            ctx.fill((int) (x + 8 + cw), (int) y + 5, (int) (x + 9 + cw), (int) y + 17, Draw.fade(0xFFFFFFFF, e));
        }
        clipped(x, y, fw, 22, b -> focus = "preset");
        buttonRect(ctx, "Save", x + fw + 8, y, 70, 22, e, dt, mx, my, ac, b -> savePreset());
        y += 34;
        Draw.text(ctx, tr, "CONFIG", x + 2, y, Draw.fade(DIM, e), false);
        y += 14;
        float tw = (w - 16) / 3f;
        buttonRect(ctx, "Export", x, y, tw, 22, e, dt, mx, my, ac, b -> { mc.keyboard.setClipboard(Config.export()); say("Config copied to the clipboard"); });
        buttonRect(ctx, "Import", x + tw + 8, y, tw, 22, e, dt, mx, my, ac, b -> {
            String err = Config.importFrom(mc.keyboard.getClipboard());
            say(err == null ? "Config imported from the clipboard" : err);
        });
        buttonRect(ctx, "Reset all", x + (tw + 8) * 2, y, tw, 22, e, dt, mx, my, 0xFF4D5A, b -> { ModuleManager.resetAll(); say("Everything reset to defaults"); });
        y += 30;
        Draw.text(ctx, tr, "Settings are saved automatically to config/nova-visuals.json.", x + 2, y, Draw.fade(0xFF5E5E70, e), false);
        return y + 14;
    }

    private void savePreset() {
        if (Config.savePreset(presetName.toString())) { presetCacheAt = -10f; say("Saved preset " + presetName); presetName.setLength(0); }
        else say("Type a name first");
    }

    // ---------------------------------------------------------------- color picker
    private void openPicker(Setting.Color c) {
        picking = c;
        float[] hsv = Colors.toHsv(c.value);
        pickH = hsv[0]; pickS = hsv[1]; pickV = hsv[2];
        hexText.setLength(0);
        hexText.append(Colors.hex(c.value).substring(1));
        focus = null;
    }

    private void applyPick() {
        picking.value = Colors.hsv(pickH, pickS, pickV);
        hexText.setLength(0);
        hexText.append(Colors.hex(picking.value).substring(1));
        Config.markDirty();
    }

    private void drawPicker(DrawContext ctx, float e, float dt, float mx, float my) {
        TextRenderer tr = textRenderer;
        int ac = Settings.accent();
        // anything outside the popup closes it
        region(0, 0, 4000, 4000, b -> picking = null);
        float w = 262, h = 168;
        float x = (cx0 + cx1) / 2f - w / 2f, y = py + (ph - h) / 2f;
        Draw.shadow(ctx, x, y, w, h, 12, 8, 18, 0.7f * e);
        Draw.round(ctx, x, y, w, h, 12, Draw.fade(0xF2101018, e));
        Draw.outline(ctx, x, y, w, h, 12, 1, Draw.fade(0xFF000000 | ac, 0.5f * e));
        region(x, y, w, h, b -> { });
        Draw.text(ctx, tr, picking.name, x + 12, y + 8, Draw.fade(TEXT, e), true);
        // saturation / value square
        float sx = x + 12, sy = y + 24, ss = 112;
        int cells = 28;
        float cs = ss / cells;
        for (int i = 0; i < cells; i++) {
            for (int j = 0; j < cells; j++) {
                int c = Colors.hsv(pickH, i / (cells - 1f), 1f - j / (cells - 1f));
                ctx.fill((int) (sx + i * cs), (int) (sy + j * cs), (int) (sx + (i + 1) * cs + 0.99f), (int) (sy + (j + 1) * cs + 0.99f), 0xFF000000 | c);
            }
        }
        float mxp = sx + pickS * ss, myp = sy + (1f - pickV) * ss;
        Draw.ring(ctx, mxp, myp, 4, 1, 0xFFFFFFFF);
        Draw.ring(ctx, mxp, myp, 5, 1, 0xFF000000);
        Region sq = region(sx, sy, ss, ss, b -> { });
        sq.drag = (dx, dy) -> { pickS = Easing.clamp01((float) ((dx - sx) / ss)); pickV = 1f - Easing.clamp01((float) ((dy - sy) / ss)); applyPick(); };
        // hue bar
        float hx = sx + ss + 10;
        for (int j = 0; j < cells; j++) {
            ctx.fill((int) hx, (int) (sy + j * cs), (int) hx + 12, (int) (sy + (j + 1) * cs + 0.99f), 0xFF000000 | Colors.hsv(j / (cells - 1f), 1f, 1f));
        }
        float hy = sy + pickH * ss;
        ctx.fill((int) hx - 2, (int) hy - 1, (int) hx + 14, (int) hy + 1, 0xFFFFFFFF);
        Region hue = region(hx, sy, 12, ss, b -> { });
        hue.drag = (dx, dy) -> { pickH = Easing.clamp01((float) ((dy - sy) / ss)) * 0.999f; applyPick(); };
        // RGB sliders
        float rx = hx + 26, rw = x + w - 12 - rx;
        int cur = picking.value;
        String[] names = {"R", "G", "B"};
        int[] vals = {Colors.r(cur), Colors.g(cur), Colors.b(cur)};
        int[] cols = {0xFF4D5A, 0x4DFF7A, 0x4D8AFF};
        for (int i = 0; i < 3; i++) {
            float ry = sy + 2 + i * 24;
            Draw.text(ctx, tr, names[i], rx, ry, Draw.fade(DIM, e), false);
            Draw.text(ctx, tr, String.valueOf(vals[i]), rx + rw - tr.getWidth(String.valueOf(vals[i])), ry, Draw.fade(TEXT, e), false);
            Draw.round(ctx, rx, ry + 11, rw, 4, 2, Draw.fade(0xFF2A2A38, e));
            Draw.round(ctx, rx, ry + 11, Math.max(4, rw * vals[i] / 255f), 4, 2, Draw.fade(0xFF000000 | cols[i], e));
            Draw.disc(ctx, rx + rw * vals[i] / 255f, ry + 13, 4, Draw.fade(0xFFFFFFFF, e));
            final int idx = i;
            Region r = region(rx - 3, ry + 5, rw + 6, 16, b -> { });
            r.drag = (dx, dy) -> {
                int v = Math.round(Easing.clamp01((float) ((dx - rx) / rw)) * 255);
                int rr = Colors.r(picking.value), gg = Colors.g(picking.value), bb = Colors.b(picking.value);
                if (idx == 0) rr = v; else if (idx == 1) gg = v; else bb = v;
                picking.value = Colors.rgb(rr, gg, bb);
                float[] hsv = Colors.toHsv(picking.value);
                if (hsv[1] > 0.001f && hsv[2] > 0.001f) pickH = hsv[0];
                pickS = hsv[1]; pickV = hsv[2];
                hexText.setLength(0); hexText.append(Colors.hex(picking.value).substring(1));
                Config.markDirty();
            };
        }
        // HEX field and preview swatch
        float fy = sy + ss + 10;
        boolean f = "hex".equals(focus);
        Draw.round(ctx, sx, fy, 92, 20, 7, Draw.fade(0xFF000000 | Colors.lerp(0x1A1A24, ac, f ? 0.22f : 0f), e));
        if (f) Draw.outline(ctx, sx, fy, 92, 20, 7, 1, Draw.fade(0xFF000000 | ac, 0.7f * e));
        Draw.text(ctx, tr, "#" + hexText, sx + 8, fy + 6, Draw.fade(TEXT, e), false);
        if (f && (int) (Time.time() * 2) % 2 == 0) ctx.fill((int) (sx + 8 + tr.getWidth("#" + hexText)), (int) fy + 4, (int) (sx + 9 + tr.getWidth("#" + hexText)), (int) fy + 16, 0xFFFFFFFF);
        region(sx, fy, 92, 20, b -> focus = "hex");
        Draw.round(ctx, sx + 100, fy, 28, 20, 7, Draw.fade(0xFF000000 | picking.value, e));
        buttonRect(ctx, "Done", x + w - 12 - 70, fy, 70, 20, e, dt, mx, my, ac, b -> picking = null);
        // the buttonRect above registers a clipped region; make sure it is not cut by the list's viewport
        regions.get(regions.size() - 1).clipY0 = -1e9f;
        regions.get(regions.size() - 1).clipY1 = 1e9f;
    }

    // ---------------------------------------------------------------- live preview
    private boolean on(String... ids) {
        for (String id : ids) { Module m = ModuleManager.get(id); if (m != null && m.enabled()) return true; }
        return false;
    }

    private void drawPreview(DrawContext ctx, float e, float dt) {
        TextRenderer tr = textRenderer;
        float x = px + pw - prevW - 12, y = py + 52, w = prevW, h = 186;
        int a1 = Settings.accent(), a2 = Settings.accent2();
        float t = Time.time();
        Draw.text(ctx, tr, "LIVE PREVIEW", x, py + 16, Draw.fade(DIM, e), false);
        Draw.round(ctx, x, y, w, h, 10, Draw.fade(0xFF07070D, e));
        ctx.enableScissor((int) x, (int) y, (int) (x + w), (int) (y + h));
        float cxm = x + w / 2f, cym = y + h / 2f + 8;
        float bloom = Settings.get().bloom.value;
        // sky tint
        if (on("aurora")) {
            for (int i = 0; i < (int) w; i += 3) {
                float k = 0.5f + 0.5f * (float) Math.sin(i * 0.09f + t * 1.1f);
                int c = Colors.lerp(0x3DFF8A, 0x9B5CFF, k);
                int hh = (int) (24 + 20 * (0.5f + 0.5f * Math.sin(i * 0.05f - t * 0.7f)));
                ctx.fillGradient((int) (x + i), (int) y, (int) (x + i + 3), (int) y + hh, 0x00000000 | c, ((int) (60 * e) << 24) | c);
            }
        }
        if (on("sunmoon", "starfield")) {
            float mxp = x + w - 28 + (float) Math.sin(t * 0.3f) * 6, myp = y + 22;
            Draw.orb(ctx, mxp, myp, 6, 0xB9CCFF, 0.9f * e * Math.min(1f, bloom));
        }
        if (on("stars", "starfield")) {
            for (int i = 0; i < 12; i++) {
                float sx = x + 8 + (i * 37 % (int) (w - 16)), sy2 = y + 8 + (i * 53 % 70);
                float tw = 0.5f + 0.5f * (float) Math.sin(t * 2f + i);
                int c = (int) (200 * tw * e) << 24 | 0xFFFFFF;
                ctx.fill((int) sx, (int) sy2, (int) sx + 1, (int) sy2 + 1, c);
                if (i % 3 == 0) { ctx.fill((int) sx - 2, (int) sy2, (int) sx + 3, (int) sy2 + 1, (int) (100 * tw * e) << 24 | 0xFFFFFF); ctx.fill((int) sx, (int) sy2 - 2, (int) sx + 1, (int) sy2 + 3, (int) (100 * tw * e) << 24 | 0xFFFFFF); }
            }
        }
        if (on("rings", "hit_fx", "circle")) {
            for (int i = 0; i < 2; i++) {
                float p = ((t * 0.6f + i * 0.5f) % 1f);
                Draw.ring(ctx, cxm, cym + 24, 6 + p * 46, 1, ((int) (210 * (1f - p) * e) << 24) | Colors.lerp(a1, a2, p));
            }
        }
        if (on("trail", "aura", "atmosphere", "halo")) {
            for (int i = 0; i < 18; i++) {
                float p = i / 18f;
                float ang = t * 1.6f - p * 1.5f;
                float ox = cxm + (float) Math.cos(ang) * 40, oy = cym + (float) Math.sin(ang * 1.0f) * 18;
                Draw.orb(ctx, ox, oy, 1.5f + (1f - p) * 2.5f, Colors.lerp(a1, a2, p), (1f - p) * e * Math.min(1f, 0.5f + bloom * 0.5f));
            }
        }
        if (on("wings")) {
            for (int s = -1; s <= 1; s += 2) {
                float flap = (float) Math.sin(t * 3f) * 6;
                for (int i = 0; i < 5; i++) {
                    float len = 22 + i * 4, up = 10 - i * 8 + flap * (0.4f + i * 0.1f);
                    Draw.round(ctx, cxm + s * 6 - (s < 0 ? len : 0), cym - 8 + up, len, 2, 1, Draw.fade(0xFF000000 | Colors.lerp(0x3A0A14, 0xFF2A2A, i / 4f), 0.9f * e));
                }
            }
        }
        Draw.round(ctx, cxm - 4, cym - 8, 8, 22, 3, Draw.fade(0xFF2A2A3A, e));        // a little player silhouette to hang the effects on
        Draw.round(ctx, cxm - 4, cym - 18, 8, 8, 3, Draw.fade(0xFF3A3A4C, e));
        if (on("horns")) { ctx.fill((int) cxm - 5, (int) cym - 24, (int) cxm - 3, (int) cym - 18, 0xFFFF3030); ctx.fill((int) cxm + 3, (int) cym - 24, (int) cxm + 5, (int) cym - 18, 0xFFFF3030); }
        ctx.disableScissor();
        Draw.outline(ctx, x, y, w, h, 10, 1, Draw.fade(0xFF000000 | a1, 0.3f * e));
        // color bar and hovered module
        Draw.gradientBar(ctx, (int) x + 6, (int) (y + h + 8), (int) w - 12, 3, a1, a2, t * Settings.get().rgbSpeed.value * 4f);
        String info = hovered != null ? hovered.name : "Hover a module";
        Draw.text(ctx, tr, tr.trimToWidth(info, (int) w), x, y + h + 18, Draw.fade(TEXT, e), false);
        String st = hovered != null ? (hovered.enabled() ? "Enabled" : "Disabled") : "The preview shows what is switched on";
        Draw.text(ctx, tr, tr.trimToWidth(st, (int) w), x, y + h + 30, Draw.fade(DIM, e), false);
    }

    // ---------------------------------------------------------------- input
    private double toPanelX(double mx) { return (mx - width / 2.0) / scale + width / 2.0; }
    private double toPanelY(double my) { return (my - height / 2.0) / scale + height / 2.0; }

    @Override
    public boolean mouseClicked(double mouseX, double mouseY, int button) {
        double mx = toPanelX(mouseX), my = toPanelY(mouseY);
        String before = focus;
        focus = null;
        for (int i = regions.size() - 1; i >= 0; i--) {
            Region r = regions.get(i);
            if (!r.has(mx, my)) continue;
            if (r.click != null) r.click.accept(button);
            if (r.drag != null) { active = r; r.drag.accept(mx, my); }
            if (focus == null && "search".equals(before) && picking == null) focus = before;
            return true;
        }
        return true;
    }

    @Override
    public boolean mouseDragged(double mouseX, double mouseY, int button, double dx, double dy) {
        if (active != null && active.drag != null) { active.drag.accept(toPanelX(mouseX), toPanelY(mouseY)); return true; }
        return false;
    }

    @Override
    public boolean mouseReleased(double mouseX, double mouseY, int button) {
        active = null;
        return true;
    }

    @Override
    public boolean mouseScrolled(double mouseX, double mouseY, double h, double v) {
        scrollTarget -= (float) v * 34f;
        scrollTarget = Easing.clamp(scrollTarget, 0f, Math.max(0f, contentH - (cy1 - cy0)));
        return true;
    }

    private StringBuilder focused() {
        if ("search".equals(focus)) return search;
        if ("hex".equals(focus)) return hexText;
        if ("preset".equals(focus)) return presetName;
        return null;
    }

    @Override
    public boolean keyPressed(int key, int scan, int mods) {
        if (NovaVisuals.menuKey != null && NovaVisuals.menuKey.matchesKey(key, scan) && key != GLFW.GLFW_KEY_ESCAPE) { startClose(); return true; }
        if (key == GLFW.GLFW_KEY_ESCAPE) {
            if (picking != null) picking = null;
            else if (focus != null && !"search".equals(focus)) focus = null;
            else if (search.length() > 0) search.setLength(0);
            else startClose();
            return true;
        }
        StringBuilder sb = focused();
        if (sb != null) {
            if (key == GLFW.GLFW_KEY_BACKSPACE && sb.length() > 0) { sb.setLength(sb.length() - 1); onTextChanged(); scrollTarget = 0; return true; }
            if (key == GLFW.GLFW_KEY_ENTER || key == GLFW.GLFW_KEY_KP_ENTER) {
                if ("preset".equals(focus)) savePreset();
                else focus = null;
                return true;
            }
            if (key == GLFW.GLFW_KEY_V && (mods & GLFW.GLFW_MOD_CONTROL) != 0) {
                String clip = mc.keyboard.getClipboard();
                if (clip != null) for (char ch : clip.toCharArray()) accept(ch);
                return true;
            }
        }
        return super.keyPressed(key, scan, mods);
    }

    @Override
    public boolean charTyped(char chr, int mods) {
        accept(chr);
        return true;
    }

    private void accept(char chr) {
        StringBuilder sb = focused();
        if (sb == null || chr < 32 || chr == 127) return;
        if (sb == hexText) {
            if (Character.digit(chr, 16) < 0) return;
            if (sb.length() >= 6) return;
            sb.append(Character.toUpperCase(chr));
        } else if (sb == presetName) {
            if (!(Character.isLetterOrDigit(chr) || chr == ' ' || chr == '-' || chr == '_') || sb.length() >= 24) return;
            sb.append(chr);
        } else {
            if (sb.length() >= 40) return;
            sb.append(chr);
        }
        onTextChanged();
    }

    private void onTextChanged() {
        if ("search".equals(focus)) { scrollTarget = 0; scroll = 0; }
        if ("hex".equals(focus) && picking != null && hexText.length() == 6) {
            int c = Colors.parseHex(hexText.toString());
            if (c >= 0) {
                picking.value = c;
                float[] hsv = Colors.toHsv(c);
                pickH = hsv[0]; pickS = hsv[1]; pickV = hsv[2];
                Config.markDirty();
            }
        }
    }
}
