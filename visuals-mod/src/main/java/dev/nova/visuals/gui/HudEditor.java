package dev.nova.visuals.gui;

import dev.nova.visuals.config.Config;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.ModuleManager;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.core.Easing;
import dev.nova.visuals.core.Smooth;
import dev.nova.visuals.core.Time;
import dev.nova.visuals.hud.HudModule;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.text.Text;
import org.lwjgl.glfw.GLFW;

import java.util.ArrayList;
import java.util.List;

/** Drag HUD elements around and resize them (corner handle or mouse wheel). Switched-off elements can be switched on from the bar. */
public final class HudEditor extends Screen {
    private final Screen parent;
    private final Smooth.Pool anim = new Smooth.Pool(16f);
    private HudModule dragging, resizing;
    private float grabX, grabY;

    public HudEditor(Screen parent) {
        super(Text.literal("HUD layout"));
        this.parent = parent;
    }

    @Override public boolean shouldPause() { return false; }

    private List<HudModule> all() {
        List<HudModule> out = new ArrayList<>();
        for (Module m : ModuleManager.all()) if (m instanceof HudModule h) out.add(h);
        return out;
    }

    @Override
    public void removed() { Config.saveNow(); }

    @Override
    public void close() { MinecraftClient.getInstance().setScreen(parent); }

    @Override
    public void render(DrawContext ctx, int mx, int my, float delta) {
        Time.frame();
        float dt = Time.dt();
        ctx.fill(0, 0, width, height, 0x66000000);
        int ac = Settings.accent();
        // faint center guides
        ctx.fill(width / 2, 0, width / 2 + 1, height, 0x14FFFFFF);
        ctx.fill(0, height / 2, width, height / 2 + 1, 0x14FFFFFF);
        for (HudModule h : all()) {
            if (!h.enabled() || h.bw <= 0) continue;
            boolean hv = Draw.in(mx, my, h.bx, h.by, h.bw, h.bh);
            float k = anim.to(h, hv || h == dragging || h == resizing ? 1f : 0f, dt);
            Draw.outline(ctx, h.bx - 2, h.by - 2, h.bw + 4, h.bh + 4, 5, 1, Draw.fade(0xFF000000 | ac, 0.35f + 0.55f * k));
            Draw.text(ctx, textRenderer, h.name, h.bx, h.by - 12, Draw.fade(0xFFFFFFFF, 0.5f + 0.5f * k), true);
            Draw.round(ctx, h.bx + h.bw - 3, h.by + h.bh - 3, 8, 8, 3, Draw.fade(0xFF000000 | ac, 0.5f + 0.5f * k));
        }
        Draw.textCentered(ctx, textRenderer, "Drag to move  -  drag the corner or scroll to resize  -  Esc to go back", width / 2f, 10, 0xFFFFFFFF, true);
        // bar with the elements that are switched off
        float x = 10, y = height - 24;
        for (HudModule h : all()) {
            if (h.enabled()) continue;
            int w = textRenderer.getWidth(h.name) + 14;
            boolean hv = Draw.in(mx, my, x, y, w, 18);
            float k = anim.to("off" + h.id, hv ? 1f : 0f, dt);
            Draw.round(ctx, x, y, w, 18, 7, Draw.fade(0xFF000000 | dev.nova.visuals.core.Colors.lerp(0x16161F, ac, 0.3f * k), 0.9f));
            Draw.text(ctx, textRenderer, h.name, x + 7, y + 5, 0xFFD0D0DC, false);
            x += w + 6;
        }
        Draw.round(ctx, width - 74, height - 26, 64, 20, 8, Draw.fade(0xFF000000 | ac, 0.85f));
        Draw.textCentered(ctx, textRenderer, "Done", width - 42, height - 20, 0xFFFFFFFF, true);
        Draw.round(ctx, width - 150, height - 26, 70, 20, 8, 0xCC2A2A38);
        Draw.textCentered(ctx, textRenderer, "Reset", width - 115, height - 20, 0xFFFFFFFF, false);
    }

    @Override
    public boolean mouseClicked(double mx, double my, int button) {
        if (Draw.in(mx, my, width - 74, height - 26, 64, 20)) { close(); return true; }
        if (Draw.in(mx, my, width - 150, height - 26, 70, 20)) {
            for (HudModule h : all()) { h.px.set(0.01f); h.py.set(0.02f + 0.12f * all().indexOf(h)); h.scale.set(1f); }
            Config.markDirty();
            return true;
        }
        float x = 10, y = height - 24;
        for (HudModule h : all()) {
            if (h.enabled()) continue;
            int w = textRenderer.getWidth(h.name) + 14;
            if (Draw.in(mx, my, x, y, w, 18)) { h.setEnabled(true); return true; }
            x += w + 6;
        }
        List<HudModule> list = all();
        for (int i = list.size() - 1; i >= 0; i--) {
            HudModule h = list.get(i);
            if (!h.enabled() || h.bw <= 0) continue;
            if (Draw.in(mx, my, h.bx + h.bw - 6, h.by + h.bh - 6, 14, 14)) { resizing = h; return true; }
            if (Draw.in(mx, my, h.bx, h.by, h.bw, h.bh)) { dragging = h; grabX = (float) mx - h.bx; grabY = (float) my - h.by; return true; }
        }
        return false;
    }

    @Override
    public boolean mouseDragged(double mx, double my, int button, double dx, double dy) {
        if (dragging != null) {
            float nx = (float) mx - grabX, ny = (float) my - grabY;
            nx = Easing.clamp(nx, 0, Math.max(0, width - dragging.bw));
            ny = Easing.clamp(ny, 0, Math.max(0, height - dragging.bh));
            if (Math.abs(nx + dragging.bw / 2f - width / 2f) < 5) nx = width / 2f - dragging.bw / 2f;      // snap to the middle
            dragging.px.set(nx / width);
            dragging.py.set(ny / height);
            Config.markDirty();
            return true;
        }
        if (resizing != null) {
            float base = resizing.bw / resizing.scale.value;
            resizing.scale.set(((float) mx - resizing.bx) / Math.max(1f, base));
            Config.markDirty();
            return true;
        }
        return false;
    }

    @Override
    public boolean mouseReleased(double mx, double my, int button) { dragging = null; resizing = null; return true; }

    @Override
    public boolean mouseScrolled(double mx, double my, double h, double v) {
        for (HudModule m : all()) {
            if (m.enabled() && Draw.in(mx, my, m.bx, m.by, m.bw, m.bh)) {
                m.scale.set(m.scale.value + (float) v * 0.1f);
                Config.markDirty();
                return true;
            }
        }
        return false;
    }

    @Override
    public boolean keyPressed(int key, int scan, int mods) {
        if (key == GLFW.GLFW_KEY_ESCAPE) { close(); return true; }
        return super.keyPressed(key, scan, mods);
    }
}
