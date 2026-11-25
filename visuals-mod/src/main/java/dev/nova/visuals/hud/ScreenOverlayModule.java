package dev.nova.visuals.hud;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.core.Colors;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.DrawContext;

/**
 * Color grading by overlay: a tint over the whole picture plus a colored vignette.
 * (A true saturation or LUT grade needs a post-processing shader; this is the safe version that works with Sodium and Iris.)
 */
public final class ScreenOverlayModule extends Module {
    private final Setting.Choice grade = add(new Setting.Choice("grade", "Color grade", 0, "None", "Warm", "Cold", "Noir", "Blood", "Dusk", "Custom"));
    private final Setting.Color custom = add(new Setting.Color("tint", "Tint color", 0x8A3DFF));
    private final Setting.Num tint = add(new Setting.Num("tint_amount", "Tint strength", 0.12f, 0f, 0.5f, 0.01f, ""));
    private final Setting.Num vignette = add(new Setting.Num("vignette", "Vignette", 0.45f, 0f, 1f, 0.01f, ""));
    private final Setting.Color vignetteColor = add(new Setting.Color("vignette_color", "Vignette color", 0x14000A));
    private final Setting.Bool pulse = add(new Setting.Bool("pulse", "Slow breathing", true));
    private float t;

    public ScreenOverlayModule() {
        super("overlay", "Color Grade & Vignette", "Tint the whole picture and darken the edges with a color.", Category.VISUALS, false);
        custom.showIf(() -> grade.index == 6);
    }

    private int gradeColor() {
        return switch (grade.index) {
            case 1 -> 0xFF9A3C;
            case 2 -> 0x4C86FF;
            case 3 -> 0x808080;
            case 4 -> 0xC01020;
            case 5 -> 0xFF5C8A;
            case 6 -> custom.value;
            default -> 0;
        };
    }

    @Override
    public void onHud(DrawContext ctx, float dt) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc.options.hudHidden) return;
        t += dt;
        int w = ctx.getScaledWindowWidth(), h = ctx.getScaledWindowHeight();
        float breath = pulse.value ? 0.85f + 0.15f * (float) Math.sin(t * 0.8f) : 1f;
        if (grade.index != 0 && tint.value > 0f) {
            float a = tint.value * (grade.index == 3 ? 1.6f : 1f);
            ctx.fill(0, 0, w, h, ((int) (Math.min(0.75f, a) * 255) << 24) | gradeColor());
        }
        float v = vignette.value * breath;
        if (v > 0.01f) {
            int c = vignetteColor.value & 0xFFFFFF;
            int solid = (int) (Math.min(1f, v) * 200) << 24 | c, clear = c;
            int e = (int) (Math.min(w, h) * 0.38f);
            ctx.fillGradient(0, 0, w, e, solid, clear);
            ctx.fillGradient(0, h - e, w, h, clear, solid);
            // the left and right edges are drawn as columns of the same fade
            int steps = 14;
            for (int i = 0; i < steps; i++) {
                float k = 1f - i / (float) steps;
                int a = (int) (Math.min(1f, v) * 140 * k * k);
                int x = (int) (e * i / (float) steps * 1.0f), x2 = (int) (e * (i + 1) / (float) steps);
                ctx.fill(x, e, x2, h - e, a << 24 | c);
                ctx.fill(w - x2, e, w - x, h - e, a << 24 | c);
            }
        }
    }
}
