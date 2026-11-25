package dev.nova.visuals.hud;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.core.Smooth;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;

/**
 * A HUD element that can be moved and resized. Position is stored as a fraction of the screen
 * (so it survives a window resize) and the scale as a multiplier; both are saved with the module.
 */
public abstract class HudModule extends Module {
    public final Setting.Num px, py, scale;
    public final Setting.Bool background = add(new Setting.Bool("background", "Rounded background", true));
    public final Setting.Num bgOpacity = add(new Setting.Num("bg_opacity", "Background opacity", 0.45f, 0f, 1f, 0.05f, ""));
    /** Last drawn rectangle in GUI pixels, used by the layout editor. */
    public float bx, by, bw, bh;
    private final Smooth fade = new Smooth(0f, 10f);

    protected HudModule(String id, String name, String description, boolean defaultOn, float defX, float defY) {
        super(id, name, description, Category.HUD, defaultOn);
        scale = add(new Setting.Num("scale", "Size", 1.0f, 0.5f, 2.5f, 0.05f, "x"));
        px = add(new Setting.Num("x", "X", defX, 0f, 1f, 0.001f, ""));
        py = add(new Setting.Num("y", "Y", defY, 0f, 1f, 0.001f, ""));
        px.showIf(() -> false);
        py.showIf(() -> false);
        background.showIf(() -> usesBackground());
        bgOpacity.showIf(() -> usesBackground() && background.value);
    }

    protected boolean usesBackground() { return true; }

    /** Content width and height in unscaled pixels. */
    protected abstract int width(TextRenderer tr);
    protected abstract int height(TextRenderer tr);
    /** Draws the content with its top-left corner at (0, 0). */
    protected abstract void draw(DrawContext ctx, TextRenderer tr, float dt, float alpha);

    /** False hides the element for now (for example: no potion effects active). */
    protected boolean visible() { return true; }

    @Override
    public void onHud(DrawContext ctx, float dt) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc.options.hudHidden) return;
        fade.set(visible() ? 1f : 0f);
        float a = fade.update(dt);
        if (a < 0.01f) return;
        TextRenderer tr = mc.textRenderer;
        int w = width(tr), h = height(tr);
        int sw = ctx.getScaledWindowWidth(), sh = ctx.getScaledWindowHeight();
        float s = scale.value;
        float x = Math.max(0, Math.min(px.value * sw, sw - w * s)), y = Math.max(0, Math.min(py.value * sh, sh - h * s));
        bx = x; by = y; bw = w * s; bh = h * s;
        dev.nova.visuals.Compat.push(ctx);
        dev.nova.visuals.Compat.translate(ctx, x, y + (1f - a) * 4f);
        dev.nova.visuals.Compat.scale(ctx, s);
        if (usesBackground() && background.value) dev.nova.visuals.gui.Draw.round(ctx, 0, 0, w, h, 4, ((int) (bgOpacity.value * 255 * a) << 24) | 0x0B0B12);
        draw(ctx, tr, dt, a);
        dev.nova.visuals.Compat.pop(ctx);
    }
}
