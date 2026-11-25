package dev.nova.visuals.hud;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.core.Smooth;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.DrawContext;

/** Letterbox bars that slide in smoothly for a cinematic look. */
public final class CinematicBarsModule extends Module {
    private final Setting.Num height = add(new Setting.Num("height", "Bar height", 0.11f, 0.03f, 0.25f, 0.005f, ""));
    private final Setting.Choice when = add(new Setting.Choice("when", "Show", 0, "Always", "While sprinting", "While sneaking", "In third person"));
    private final Setting.Num opacity = add(new Setting.Num("opacity", "Opacity", 1f, 0.2f, 1f, 0.05f, ""));
    private final Smooth amount = new Smooth(0f, 5f);

    public CinematicBarsModule() {
        super("cine_bars", "Cinematic Bars", "Letterbox bars that glide in and out.", Category.ANIMATIONS, false);
    }

    @Override public void onEnable() { amount.snap(0f); }

    @Override
    public void onHud(DrawContext ctx, float dt) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc.options.hudHidden || mc.player == null) return;
        boolean on = switch (when.index) {
            case 1 -> mc.player.isSprinting();
            case 2 -> mc.player.isSneaking();
            case 3 -> !mc.options.getPerspective().isFirstPerson();
            default -> true;
        };
        amount.set(on ? 1f : 0f);
        float k = amount.update(dt);
        if (k < 0.005f) return;
        float e = k * k * (3f - 2f * k);
        int w = ctx.getScaledWindowWidth(), h = ctx.getScaledWindowHeight();
        int bar = (int) (h * height.value * e);
        int c = (int) (opacity.value * 255) << 24;
        ctx.fill(0, 0, w, bar, c);
        ctx.fill(0, h - bar, w, h, c);
    }
}
