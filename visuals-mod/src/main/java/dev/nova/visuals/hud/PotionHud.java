package dev.nova.visuals.hud;

import dev.nova.visuals.config.Setting;
import dev.nova.visuals.core.Colors;
import dev.nova.visuals.gui.Draw;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.entity.effect.StatusEffectInstance;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Active potion effects with their remaining time and a colored bar. */
public final class PotionHud extends HudModule {
    private final Setting.Bool showBar = add(new Setting.Bool("bar", "Time bar", true));
    private final Setting.Bool blink = add(new Setting.Bool("blink", "Blink when about to run out", true));

    public PotionHud() {
        super("hud_potions", "Potion Effects", "Your active effects with timers.", true, 0.01f, 0.28f);
    }

    private List<StatusEffectInstance> effects() {
        MinecraftClient mc = MinecraftClient.getInstance();
        List<StatusEffectInstance> out = new ArrayList<>();
        if (mc.player != null) out.addAll(mc.player.getStatusEffects());
        out.sort(Comparator.comparingInt(StatusEffectInstance::getDuration).reversed());
        return out;
    }

    private static String roman(int n) {
        String[] r = {"", " II", " III", " IV", " V", " VI", " VII", " VIII", " IX", " X"};
        return n >= 0 && n < r.length ? r[n] : " " + (n + 1);
    }

    private static String time(StatusEffectInstance e) {
        if (e.isInfinite()) return "∞";
        int s = e.getDuration() / 20;
        return String.format("%d:%02d", s / 60, s % 60);
    }

    private static String label(StatusEffectInstance e) {
        return e.getEffectType().value().getName().getString() + roman(e.getAmplifier());
    }

    @Override protected boolean visible() { return !effects().isEmpty(); }

    @Override
    protected int width(TextRenderer tr) {
        int w = 90;
        for (StatusEffectInstance e : effects()) w = Math.max(w, tr.getWidth(label(e)) + tr.getWidth(time(e)) + 28);
        return w;
    }

    @Override protected int height(TextRenderer tr) { return Math.max(1, effects().size()) * 17 + 4; }

    @Override
    protected void draw(DrawContext ctx, TextRenderer tr, float dt, float alpha) {
        int y = 4;
        int w = width(tr);
        for (StatusEffectInstance e : effects()) {
            int col = e.getEffectType().value().getColor() & 0xFFFFFF;
            col = Colors.lerp(col, 0xFFFFFF, 0.25f);
            float blinkK = 1f;
            if (blink.value && !e.isInfinite() && e.getDuration() < 200) blinkK = 0.55f + 0.45f * (float) Math.sin(System.nanoTime() / 1.5e8);
            Draw.round(ctx, 5, y + 2, 4, 4, 2, Draw.fade(0xFF000000 | col, alpha * blinkK));
            Draw.text(ctx, tr, label(e), 13, y, Draw.fade(0xFFFFFFFF, alpha * blinkK), true);
            String t = time(e);
            Draw.text(ctx, tr, t, w - 6 - tr.getWidth(t), y, Draw.fade(0xFFB8B8C4, alpha * blinkK), true);
            if (showBar.value && !e.isInfinite()) {
                float k = Math.min(1f, e.getDuration() / 1200f);
                Draw.round(ctx, 13, y + 11, w - 19, 2, 1, Draw.fade(0x33FFFFFF, alpha));
                Draw.round(ctx, 13, y + 11, (w - 19) * k, 2, 1, Draw.fade(0xFF000000 | col, alpha));
            }
            y += 17;
        }
    }
}
