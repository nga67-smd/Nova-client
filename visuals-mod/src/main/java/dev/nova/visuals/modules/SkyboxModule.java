package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.core.Colors;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import net.minecraft.client.render.VertexConsumer;

import java.util.Random;

/** An animated skybox: drifting nebula clouds and a glowing horizon band around the vanilla sky. */
public final class SkyboxModule extends Module {
    private static final int BLOBS = 26;
    private final float[] bx = new float[BLOBS], by = new float[BLOBS], bz = new float[BLOBS], bs = new float[BLOBS], bp = new float[BLOBS];

    private final Setting.Choice style = add(new Setting.Choice("style", "Style", 0, "Nebula", "Twilight", "Gothic mist", "Rainbow", "Accent"));
    private final Setting.Num intensity = add(new Setting.Num("intensity", "Intensity", 1.0f, 0.1f, 2.5f, 0.05f, "x"));
    private final Setting.Num speed = add(new Setting.Num("speed", "Drift speed", 1.0f, 0f, 4f, 0.05f, "x"));
    private final Setting.Num scale = add(new Setting.Num("scale", "Cloud size", 1.0f, 0.4f, 2.5f, 0.05f, "x"));
    private final Setting.Bool horizon = add(new Setting.Bool("horizon", "Glowing horizon", true));
    private final Setting.Bool day = add(new Setting.Bool("day", "Also visible by day", true));

    public SkyboxModule() {
        super("skybox", "Animated Skybox", "Drifting colored nebula clouds and a glowing horizon.", Category.ENVIRONMENT, false);
        Random r = new Random(77123L);
        for (int i = 0; i < BLOBS; i++) {
            double a = r.nextDouble() * Math.PI * 2, el = Math.asin(r.nextDouble() * 0.95 + 0.02);
            bx[i] = (float) (Math.cos(a) * Math.cos(el)); by[i] = (float) Math.sin(el); bz[i] = (float) (Math.sin(a) * Math.cos(el));
            bs[i] = 14f + r.nextFloat() * 30f; bp[i] = r.nextFloat();
        }
    }

    private int color(float k, float time) {
        float t = ((k % 1f) + 1f) % 1f;
        return switch (style.index) {
            case 1 -> Colors.lerp(Colors.lerp(0xFF7A4D, 0xFF4D8A, t), 0x7A4DFF, (float) Math.sin(t * 6.28f + time * 0.05f) * 0.5f + 0.5f);
            case 2 -> Colors.lerp(Colors.lerp(0x7A0A1E, 0x3A0B52, t), 0x14335A, (float) Math.sin(t * 9f + time * 0.04f) * 0.5f + 0.5f);
            case 3 -> Colors.rainbow(t + time * 0.02f * Settings.rgbSpeed());
            case 4 -> Colors.lerp(Settings.accent(), Settings.accent2(), t);
            default -> Colors.lerp(Colors.lerp(0x5B2BD6, 0x2B8FD6, t), 0xD62B9A, (float) Math.sin(t * 7f + time * 0.05f) * 0.5f + 0.5f);
        };
    }

    @Override
    public void onWorld(Frame f) {
        if (!Sky.hasSky(f)) return;
        float night = Sky.night(f.world, f.tickDelta);
        float vis = (day.value ? 0.16f + 0.84f * night : night) * Sky.clear(f.world, f.tickDelta) * intensity.value;
        if (vis < 0.02f) return;
        VertexConsumer g = f.add(Gfx.GLOW);
        float t = f.time * speed.value;
        double rot = t * 0.012;
        float c = (float) Math.cos(rot), s = (float) Math.sin(rot);
        for (int i = 0; i < BLOBS; i++) {
            float x = bx[i] * c - bz[i] * s, z = bx[i] * s + bz[i] * c;                      // the whole sky drifts slowly
            float breathe = 0.75f + 0.25f * (float) Math.sin(t * 0.3f + bp[i] * 6.28f);
            int col = color(bp[i] + i * 0.013f, t);
            f.sprite(g, f.cam.x + x * 92, f.cam.y + by[i] * 92, f.cam.z + z * 92, bs[i] * scale.value, bp[i] * 6.28f, col, 0.13f * vis * breathe);
        }
        if (horizon.value) {
            int n = 28;
            for (int i = 0; i < n; i++) {
                double a = i / (double) n * Math.PI * 2;
                float h = 0.05f + 0.03f * (float) Math.sin(t * 0.4f + i);
                float al = 0.2f * vis * (0.7f + 0.3f * (float) Math.sin(t * 0.5f + i * 0.8f));
                f.sprite(g, f.cam.x + Math.cos(a) * 92, f.cam.y + h * 92, f.cam.z + Math.sin(a) * 92, 22f * scale.value, 0f, color(i / (float) n, t), al);
            }
        }
    }
}
