package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.core.Colors;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import dev.nova.visuals.gfx.Pose;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.entity.player.PlayerEntity;

/** Curved horns on your head that follow where you look. */
public final class HornsModule extends Module {
    private final Setting.Choice style = add(new Setting.Choice("style", "Style", 0, "Devil", "Ram", "Crown spikes"));
    private final Setting.Color base = add(new Setting.Color("base", "Base color", 0x1A0508));
    private final Setting.Color tip = add(new Setting.Color("tip", "Tip color", 0xFF3030));
    private final Setting.Num size = add(new Setting.Num("size", "Size", 1.0f, 0.4f, 2.5f, 0.05f, "x"));
    private final Setting.Bool glow = add(new Setting.Bool("glow", "Glowing tips", true));
    private final Setting.Bool firstPerson = add(new Setting.Bool("first_person", "Show in first person", false));

    public HornsModule() {
        super("horns", "Horns", "Devil, ram or spiked horns on your head.", Category.COSMETICS, false);
    }

    @Override
    public void onWorld(Frame f) {
        for (PlayerEntity p : Fx.targets(f)) {
            if (p == f.player && Fx.firstPerson() && !firstPerson.value) continue;
            draw(f, p);
        }
    }

    private void draw(Frame f, PlayerEntity p) {
        Pose pose = new Pose(f, p, true);
        float top = p.getHeight() - 0.22f - (p.isSneaking() ? 0.05f : 0f);
        VertexConsumer solid = f.solid(Gfx.WHITE);
        float s = size.value;
        for (int side = -1; side <= 1; side += 2) {
            float[][] pts;
            if (style.index == 1) {                                           // ram: curls outward, down and forward
                pts = new float[][]{{0.2f, 0f, 0f}, {0.3f, 0.1f, -0.02f}, {0.36f, 0.22f, 0.02f}, {0.34f, 0.32f, 0.1f}, {0.26f, 0.32f, 0.17f}, {0.2f, 0.25f, 0.16f}};
            } else if (style.index == 2) {
                pts = new float[][]{{0.1f, 0f, 0f}, {0.12f, 0.12f, 0f}, {0.14f, 0.3f, 0f}};
            } else {                                                          // devil: up, slightly outward and curving back
                pts = new float[][]{{0.16f, 0f, 0.02f}, {0.2f, 0.12f, 0f}, {0.25f, 0.26f, -0.05f}, {0.3f, 0.38f, -0.12f}, {0.3f, 0.48f, -0.2f}};
            }
            int n = pts.length;
            for (int i = 0; i + 1 < n; i++) {
                double[] a = world(pose, side, pts[i], top, s), b = world(pose, side, pts[i + 1], top, s);
                float k0 = i / (float) (n - 1), k1 = (i + 1) / (float) (n - 1);
                float w0 = (0.055f * (1f - k0 * 0.9f) + 0.005f) * s, w1 = (0.055f * (1f - k1 * 0.9f) + 0.005f) * s;
                f.line(solid, a[0], a[1], a[2], b[0], b[1], b[2], w0, w1, Colors.lerp(base.value, tip.value, k0 * k0), 1f, Colors.lerp(base.value, tip.value, k1 * k1), 1f);
            }
            if (glow.value) {
                double[] t = world(pose, side, pts[n - 1], top, s);
                f.bloom(t[0], t[1], t[2], 0.05f * s, tip.value, 0.9f);
            }
        }
        if (style.index == 2) {                                               // a crown of spikes across the forehead
            for (int k = -2; k <= 2; k++) {
                if (k == 0) continue;
                float[][] sp = {{k * 0.07f, 0f, 0.2f}, {k * 0.07f, 0.16f - Math.abs(k) * 0.03f, 0.2f}};
                double[] a = world(pose, 1, sp[0], top, s), b = world(pose, 1, sp[1], top, s);
                f.line(solid, a[0], a[1], a[2], b[0], b[1], b[2], 0.035f * s, 0.004f, base.value, 1f, tip.value, 1f);
            }
        }
    }

    /** Head-local (right, up, forward) to world coordinates. */
    private static double[] world(Pose p, int side, float[] pt, float top, float s) {
        float r = side * pt[0] * s, fwd = pt[2] * s;
        return new double[]{p.ax(r, fwd), p.wy + top + pt[1] * s, p.az(r, fwd)};
    }
}
