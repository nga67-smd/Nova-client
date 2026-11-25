package dev.nova.visuals.hud;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.ColorSpec;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.core.Smooth;
import dev.nova.visuals.gui.Draw;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.DrawContext;

/** A custom crosshair that replaces the vanilla one. It opens up a little while you move. */
public final class CrosshairModule extends Module {
    private static CrosshairModule instance;

    private final Setting.Choice style = add(new Setting.Choice("style", "Style", 0, "Cross", "Dot", "Circle", "Cross + dot", "Brackets", "Diamond"));
    private final ColorSpec color = new ColorSpec(this, 0xFFFFFF, 0);
    private final Setting.Num size = add(new Setting.Num("size", "Size", 5f, 1f, 16f, 0.5f, "px"));
    private final Setting.Num gap = add(new Setting.Num("gap", "Gap", 3f, 0f, 12f, 0.5f, "px"));
    private final Setting.Num thickness = add(new Setting.Num("thickness", "Thickness", 1f, 1f, 4f, 1f, "px"));
    private final Setting.Num opacity = add(new Setting.Num("opacity", "Opacity", 1f, 0.1f, 1f, 0.05f, ""));
    private final Setting.Bool outline = add(new Setting.Bool("outline", "Dark outline", true));
    private final Setting.Bool dynamic = add(new Setting.Bool("dynamic", "Opens while moving", true));
    private final Setting.Bool hideVanilla = add(new Setting.Bool("hide_vanilla", "Hide the vanilla crosshair", true));
    private final Smooth open = new Smooth(0f, 12f);

    public CrosshairModule() {
        super("hud_crosshair", "Custom Crosshair", "A crosshair you can restyle and recolor.", Category.HUD, true);
        instance = this;
    }

    /** Asked by the optional mixin: should the vanilla crosshair be skipped? */
    public static boolean replacingVanilla() {
        return instance != null && instance.enabled() && instance.hideVanilla.value;
    }

    @Override
    public void onHud(DrawContext ctx, float dt) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc.options.hudHidden || mc.currentScreen != null || mc.player == null) return;
        if (!mc.options.getPerspective().isFirstPerson()) return;
        boolean moving = dynamic.value && mc.player.getVelocity().horizontalLengthSquared() > 0.003 || (dynamic.value && !mc.player.isOnGround());
        open.set(moving ? 1f : 0f);
        float k = open.update(dt);
        int cx = ctx.getScaledWindowWidth() / 2, cy = ctx.getScaledWindowHeight() / 2;
        int c = Draw.fade(0xFF000000 | color.at(0f), opacity.value);
        int dark = Draw.fade(0xFF000000, opacity.value * 0.75f);
        int t = (int) thickness.value, s = Math.round(size.value), g = Math.round(gap.value + k * 3f);
        switch (style.index) {
            case 1 -> dot(ctx, cx, cy, t + 1, c, dark);
            case 2 -> Draw.ring(ctx, cx, cy, s + g * 0.5f, t, c);
            case 3 -> { cross(ctx, cx, cy, s, g, t, c, dark); dot(ctx, cx, cy, t, c, dark); }
            case 4 -> brackets(ctx, cx, cy, s, g + 1, t, c, dark);
            case 5 -> {
                int r = s + g;
                for (int i = 0; i <= r; i++) {
                    for (int sx = -1; sx <= 1; sx += 2) for (int sy = -1; sy <= 1; sy += 2) ctx.fill(cx + sx * i - (sx < 0 ? t - 1 : 0), cy + sy * (r - i) - (sy < 0 ? t - 1 : 0), cx + sx * i + (sx < 0 ? 0 : t) , cy + sy * (r - i) + (sy < 0 ? 0 : t), c);
                }
            }
            default -> cross(ctx, cx, cy, s, g, t, c, dark);
        }
    }

    private void bar(DrawContext ctx, int x0, int y0, int x1, int y1, int c, int dark) {
        if (outline.value) ctx.fill(x0 - 1, y0 - 1, x1 + 1, y1 + 1, dark);
        ctx.fill(x0, y0, x1, y1, c);
    }

    private void cross(DrawContext ctx, int cx, int cy, int s, int g, int t, int c, int dark) {
        int h = t / 2, h2 = t - h;
        bar(ctx, cx - g - s, cy - h, cx - g, cy + h2, c, dark);
        bar(ctx, cx + g, cy - h, cx + g + s, cy + h2, c, dark);
        bar(ctx, cx - h, cy - g - s, cx + h2, cy - g, c, dark);
        bar(ctx, cx - h, cy + g, cx + h2, cy + g + s, c, dark);
    }

    private void dot(DrawContext ctx, int cx, int cy, int t, int c, int dark) {
        bar(ctx, cx - t / 2, cy - t / 2, cx - t / 2 + t, cy - t / 2 + t, c, dark);
    }

    private void brackets(DrawContext ctx, int cx, int cy, int s, int g, int t, int c, int dark) {
        int r = s + g;
        for (int sx = -1; sx <= 1; sx += 2) for (int sy = -1; sy <= 1; sy += 2) {
            int x = cx + sx * r, y = cy + sy * r;
            bar(ctx, Math.min(x, x - sx * s), y - (sy < 0 ? 0 : t), Math.max(x, x - sx * s) + (sx > 0 ? t : 0), y + (sy < 0 ? t : 0), c, dark);
            bar(ctx, x - (sx < 0 ? 0 : t), Math.min(y, y - sy * s), x + (sx < 0 ? t : 0), Math.max(y, y - sy * s), c, dark);
        }
    }
}
