package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.ColorSpec;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.core.Easing;
import dev.nova.visuals.fx.ParticleEngine;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.util.math.Vec3d;

/** A glowing ribbon that follows you and fades out behind. */
public final class TrailModule extends Module {
    private static final int CAP = 512;
    private final double[] px = new double[CAP], py = new double[CAP], pz = new double[CAP];
    private final float[] born = new float[CAP];
    private int head, size;
    private double lastX, lastY, lastZ;
    private float sparkAcc;

    private final ColorSpec color = new ColorSpec(this, 0xFF3B6B, 2);
    private final Setting.Num length = add(new Setting.Num("length", "Length", 1.2f, 0.3f, 4f, 0.1f, "s"));
    private final Setting.Num width = add(new Setting.Num("width", "Width", 0.14f, 0.03f, 0.5f, 0.01f, ""));
    private final Setting.Num opacity = add(new Setting.Num("opacity", "Opacity", 0.9f, 0.1f, 1f, 0.05f, ""));
    private final Setting.Num height = add(new Setting.Num("height", "Height on body", 0.35f, 0f, 1.8f, 0.05f, ""));
    private final Setting.Bool sparks = add(new Setting.Bool("sparks", "Sparkles along the trail", true));
    private final Setting.Bool glow = add(new Setting.Bool("glow", "Soft glow around the ribbon", true));

    public TrailModule() {
        super("trail", "Movement Trail", "A glowing, color-shifting ribbon behind you.", Category.PARTICLES, true);
    }

    @Override public void onDisable() { size = 0; }

    @Override
    public void onWorld(Frame f) {
        Vec3d p = Fx.at(f.player, f.tickDelta);
        double y = p.y + height.value;
        double dx = p.x - lastX, dy = y - lastY, dz = p.z - lastZ;
        if (size == 0 || dx * dx + dy * dy + dz * dz > 0.0016) {
            int i = (head + size) % CAP;
            if (size == CAP) { head = (head + 1) % CAP; size--; }
            px[i] = p.x; py[i] = y; pz[i] = p.z; born[i] = f.time;
            size++;
            lastX = p.x; lastY = y; lastZ = p.z;
        }
        while (size > 0 && f.time - born[head] > length.value) { head = (head + 1) % CAP; size--; }
        if (size < 2) return;

        VertexConsumer line = f.add(Gfx.LINE);
        float w = width.value;
        for (int k = 0; k < size - 1; k++) {
            int a = (head + k) % CAP, b = (a + 1) % CAP;
            float ta = 1f - (f.time - born[a]) / length.value, tb = 1f - (f.time - born[b]) / length.value;
            float fa = Easing.smoothstep(ta) * Easing.smoothstep((f.time - born[a]) / 0.18f) * opacity.value;
            float fb = Easing.smoothstep(tb) * Easing.smoothstep((f.time - born[b]) / 0.18f) * opacity.value;
            int ca = color.at(ta), cb = color.at(tb);
            if (glow.value) f.line(line, px[a], py[a], pz[a], px[b], py[b], pz[b], w * 2.6f * ta, w * 2.6f * tb, ca, fa * 0.35f * Settings.bloom(), cb, fb * 0.35f * Settings.bloom());
            f.line(line, px[a], py[a], pz[a], px[b], py[b], pz[b], w * ta, w * tb, ca, fa, cb, fb);
        }
        if (sparks.value && Math.abs(dx) + Math.abs(dz) > 0.002) {
            sparkAcc += f.dt * Settings.count(14);
            while (sparkAcc >= 1f) {
                sparkAcc -= 1f;
                int k = (int) (Math.random() * (size - 1));
                int a = (head + k) % CAP;
                float t = 1f - (f.time - born[a]) / length.value;
                ParticleEngine.spawn(ParticleEngine.STAR, px[a] + Fx.rand(-0.1f, 0.1f), py[a] + Fx.rand(-0.1f, 0.1f), pz[a] + Fx.rand(-0.1f, 0.1f),
                        Fx.rand(-0.15f, 0.15f), Fx.rand(0.05f, 0.35f), Fx.rand(-0.15f, 0.15f), Fx.rand(0.5f, 1.1f),
                        Fx.rand(0.08f, 0.16f), 0.01f, color.at(t), 0.9f, 0f, 0.6f, Fx.rand(-2f, 2f));
            }
        }
    }
}
