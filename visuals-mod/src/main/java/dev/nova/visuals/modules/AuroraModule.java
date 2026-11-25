package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.core.Colors;
import dev.nova.visuals.core.Easing;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import net.minecraft.client.render.VertexConsumer;

/** Shimmering aurora curtains over the northern sky at night. */
public final class AuroraModule extends Module {
    private final Setting.Choice palette = add(new Setting.Choice("palette", "Colors", 0, "Classic green", "Violet", "Crimson", "Accent", "Rainbow"));
    private final Setting.Num intensity = add(new Setting.Num("intensity", "Brightness", 0.8f, 0.1f, 2f, 0.05f, "x"));
    private final Setting.Num height = add(new Setting.Num("height", "Curtain height", 1.0f, 0.4f, 2f, 0.05f, "x"));
    private final Setting.Num speed = add(new Setting.Num("speed", "Speed", 1.0f, 0.1f, 3f, 0.05f, "x"));
    private final Setting.Num curtains = add(new Setting.Num("curtains", "Curtains", 3f, 1f, 5f, 1f, ""));
    private final Setting.Bool always = add(new Setting.Bool("always", "Also during the day", false));

    public AuroraModule() {
        super("aurora", "Aurora Borealis", "Animated northern lights curtains in the night sky.", Category.ENVIRONMENT, false);
    }

    private int tint(float k, float level) {
        return switch (palette.index) {
            case 1 -> Colors.lerp(0x6A3DFF, 0xE35BFF, k);
            case 2 -> Colors.lerp(0xFF1744, 0xFF7A3D, k);
            case 3 -> Colors.lerp(Settings.accent(), Settings.accent2(), k);
            case 4 -> Colors.rainbow(k * 0.6f + level * 0.1f + dev.nova.visuals.core.Time.time() * 0.03f);
            default -> Colors.lerp(Colors.lerp(0x3DFF8A, 0x2EE6C8, k), 0x9B5CFF, Easing.smoothstep((level - 0.55f) * 2.2f));
        };
    }

    @Override
    public void onWorld(Frame f) {
        if (!Sky.hasSky(f)) return;
        float vis = (always.value ? 1f : Sky.night(f.world, f.tickDelta)) * Sky.clear(f.world, f.tickDelta) * intensity.value;
        if (vis < 0.02f) return;
        VertexConsumer b = f.add(Gfx.WHITE);
        int seg = Math.max(24, Settings.segments());
        float t = f.time * speed.value;
        float[] p = new float[12], col = new float[16];
        for (int c = 0; c < (int) curtains.value; c++) {
            float radius = 105f + c * 9f;
            float baseY = 34f + c * 7f;
            for (int s = 0; s < seg; s++) {
                float u0 = s / (float) seg, u1 = (s + 1) / (float) seg;
                float a0 = Easing.lerp(-1.25f, 1.25f, u0) + c * 0.18f, a1 = Easing.lerp(-1.25f, 1.25f, u1) + c * 0.18f;
                float w0 = wave(u0, c, t), w1 = wave(u1, c, t);
                float h0 = (24f + 30f * w0) * height.value, h1 = (24f + 30f * w1) * height.value;
                float r0 = radius + 7f * (float) Math.sin(u0 * 9f + t * 0.7f + c), r1 = radius + 7f * (float) Math.sin(u1 * 9f + t * 0.7f + c);
                float edge0 = (float) Math.sin(Math.PI * u0), edge1 = (float) Math.sin(Math.PI * u1);   // fades at the two ends
                float ray0 = 0.55f + 0.45f * (float) Math.sin(u0 * 53f + t * 1.3f + c * 2f), ray1 = 0.55f + 0.45f * (float) Math.sin(u1 * 53f + t * 1.3f + c * 2f);
                float al0 = vis * edge0 * (0.35f + 0.65f * w0) * ray0, al1 = vis * edge1 * (0.35f + 0.65f * w1) * ray1;
                float x0 = (float) Math.sin(a0) * r0, z0 = -(float) Math.cos(a0) * r0, x1 = (float) Math.sin(a1) * r1, z1 = -(float) Math.cos(a1) * r1;
                // bottom edge is bright, the top fades away
                p[0] = x0; p[1] = baseY; p[2] = z0;
                p[3] = x1; p[4] = baseY; p[5] = z1;
                p[6] = x1; p[7] = baseY + h1; p[8] = z1;
                p[9] = x0; p[10] = baseY + h0; p[11] = z0;
                put(col, 0, tint(0.1f, 0f), al0 * 0.9f);
                put(col, 4, tint(0.1f, 0f), al1 * 0.9f);
                put(col, 8, tint(0.9f, 1f), al1 * 0.0f);
                put(col, 12, tint(0.9f, 1f), al0 * 0.0f);
                // a second, shorter quad adds a brighter band at the bottom
                Gfx.gradQuad(b, f.m, p, col, 0f, 0f, 1f, 1f);
                float m0 = baseY + h0 * 0.45f, m1 = baseY + h1 * 0.45f;
                float[] q = {x0, baseY, z0, x1, baseY, z1, x1, m1, z1, x0, m0, z0};
                put(col, 0, tint(0.2f, 0.2f), al0 * 0.6f);
                put(col, 4, tint(0.2f, 0.2f), al1 * 0.6f);
                put(col, 8, tint(0.5f, 0.6f), al1 * 0.25f);
                put(col, 12, tint(0.5f, 0.6f), al0 * 0.25f);
                Gfx.gradQuad(b, f.m, q, col, 0f, 0f, 1f, 1f);
            }
        }
    }

    private static float wave(float u, int c, float t) {
        return 0.5f + 0.5f * (float) (Math.sin(u * 6.5 + t * 0.45 + c * 1.7) * 0.6 + Math.sin(u * 14 - t * 0.8 + c) * 0.4);
    }

    private static void put(float[] col, int o, int rgb, float a) {
        a = Math.max(0f, a);
        col[o] = Colors.r(rgb) / 255f * a;
        col[o + 1] = Colors.g(rgb) / 255f * a;
        col[o + 2] = Colors.b(rgb) / 255f * a;
        col[o + 3] = 1f;
    }
}
