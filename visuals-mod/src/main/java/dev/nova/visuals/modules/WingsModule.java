package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.ColorSpec;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.core.Colors;
import dev.nova.visuals.core.Easing;
import dev.nova.visuals.fx.ParticleEngine;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import dev.nova.visuals.gfx.Pose;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.entity.player.PlayerEntity;

/** Animated cosmetic wings: devil, gothic bat, angel and raven. They flap, glow and shed particles. */
public final class WingsModule extends Module {
    // finger tips (u outward, v up) of the membrane styles, relative to the wrist at (WX, WY)
    private static final float[][] DEVIL = {{0.95f, 0.85f}, {1.75f, 1.15f}, {1.95f, 0.55f}, {1.7f, -0.1f}, {1.15f, -0.6f}, {0.2f, -0.85f}};
    private static final float[][] BAT = {{0.9f, 0.8f}, {1.55f, 0.95f}, {1.6f, 0.3f}, {1.25f, -0.35f}, {0.2f, -0.7f}};

    private final Setting.Choice style = add(new Setting.Choice("style", "Style", 0, "Devil", "Gothic bat", "Angel", "Raven"));
    private final ColorSpec glowColor = new ColorSpec(this, 0xFF2A2A, 3);
    private final Setting.Color membrane = add(new Setting.Color("membrane", "Membrane color", 0x2B0610));
    private final Setting.Num membraneAlpha = add(new Setting.Num("membrane_alpha", "Membrane opacity", 0.88f, 0.2f, 1f, 0.02f, ""));
    private final Setting.Num size = add(new Setting.Num("size", "Size", 1.0f, 0.4f, 2.5f, 0.05f, "x"));
    private final Setting.Num flap = add(new Setting.Num("flap", "Flap speed", 1.0f, 0f, 3f, 0.05f, "x"));
    private final Setting.Num spread = add(new Setting.Num("spread", "Spread", 1.0f, 0.4f, 1.6f, 0.05f, "x"));
    private final Setting.Bool glowBones = add(new Setting.Bool("glow_bones", "Glowing bones", true));
    private final Setting.Bool particles = add(new Setting.Bool("particles", "Embers and feathers", true));
    private final Setting.Bool firstPerson = add(new Setting.Bool("first_person", "Show in first person", false));

    private float acc;

    public WingsModule() {
        super("wings", "Wings", "Flapping wings on your back: devil, gothic bat, angel or raven.", Category.COSMETICS, false);
        membrane.showIf(() -> style.index < 2);
        membraneAlpha.showIf(() -> style.index < 2);
    }

    @Override
    public void onWorld(Frame f) {
        for (PlayerEntity p : Fx.targets(f)) {
            if (p == f.player && Fx.firstPerson() && !firstPerson.value) continue;
            if (dev.nova.visuals.Compat.gliding(p) || p.isSleeping()) continue;
            draw(f, p);
        }
    }

    private void draw(Frame f, PlayerEntity p) {
        Pose pose = new Pose(f, p);
        float s = size.value;
        float phase = (p.getId() % 17) * 0.4f;
        boolean air = !pose.onGround;
        float rate = (air ? 5.2f : 1.7f) * flap.value;
        float wave = (float) Math.sin(f.time * rate + phase);
        float amp = air ? 0.42f : 0.12f;
        // phi: angle between the wing and the plane of the back; larger folds the wing back
        float phi = (0.62f - 0.25f * (spread.value - 1f)) + wave * amp - (p.isSneaking() ? 0.25f : 0f);
        float rootY = pose.sneaking ? 1.12f : 1.36f;
        float back = pose.sneaking ? -0.28f : -0.16f;
        int glow = glowColor.at(0f);

        for (int side = -1; side <= 1; side += 2) {
            Wing w = new Wing(pose, side, rootY, back, phi, s, wave);
            switch (style.index) {
                case 0 -> membraneWing(f, w, DEVIL, 0.5f, 0.45f, glow, true);
                case 1 -> membraneWing(f, w, BAT, 0.62f, 0.42f, glow, false);
                case 2 -> featherWing(f, w, 0xFFFFFF, 0xFFF3C4, 0xFFE9A0, true);
                default -> featherWing(f, w, 0x15131B, 0x3A3350, glowColor.at(0.5f), false);
            }
        }
        if (particles.value && (air || Math.random() < 0.3)) {
            acc += f.dt * Settings.count(air ? 18 : 5);
            while (acc >= 1f) {
                acc -= 1f;
                int sd = Math.random() < 0.5 ? -1 : 1;
                float u = Fx.rand(0.5f, 1.8f) * s, v = Fx.rand(-0.5f, 0.9f) * s;
                float cp = (float) Math.cos(phi), sp = (float) Math.sin(phi);
                double wx = pose.ax(sd * (0.1f + u * cp), -0.16f - u * sp * 0.8f), wz = pose.az(sd * (0.1f + u * cp), -0.16f - u * sp * 0.8f);
                double wy = pose.wy + rootY + v;
                if (style.index < 2) {
                    ParticleEngine.spawn(ParticleEngine.GLOW, wx, wy, wz, Fx.rand(-0.2f, 0.2f), Fx.rand(0.3f, 0.8f), Fx.rand(-0.2f, 0.2f), Fx.rand(0.8f, 1.6f),
                            0.06f, 0.01f, glow, 0.9f, -0.2f, 0.6f, 0f);
                } else {
                    ParticleEngine.spawn(ParticleEngine.DOT, wx, wy, wz, Fx.rand(-0.1f, 0.1f), Fx.rand(-0.1f, 0.1f), Fx.rand(-0.1f, 0.1f), Fx.rand(1.5f, 2.6f),
                            0.06f, 0.03f, style.index == 2 ? 0xFFFFFF : 0x3A3350, 0.85f, 0.35f, 0.5f, Fx.rand(-2f, 2f));
                }
            }
        }
    }

    /** Wing-plane (u outward, v up) to camera-relative world coordinates. */
    private static final class Wing {
        final Pose pose; final int side; final float rootY, back, cp, sp, s;
        Wing(Pose pose, int side, float rootY, float back, float phi, float s, float wave) {
            this.pose = pose; this.side = side; this.rootY = rootY; this.back = back; this.s = s;
            this.cp = (float) Math.cos(phi); this.sp = (float) Math.sin(phi);
        }
        float x(float u, float v) { return pose.x(side * (0.1f + u * s * cp), back - u * s * sp * 0.8f); }
        float y(float u, float v) { return pose.y(rootY + v * s + 0.0f); }
        float z(float u, float v) { return pose.z(side * (0.1f + u * s * cp), back - u * s * sp * 0.8f); }
    }

    private void membraneWing(Frame f, Wing w, float[][] tips, float wristU, float wristV, int glow, boolean devil) {
        // arm: shoulder (0,0) -> elbow -> wrist
        float eu = wristU * 0.55f, ev = wristV * 0.9f + 0.05f;
        float wu = tips[0][0], wv = tips[0][1];
        int n = tips.length;
        // outline ring with scalloped points between the fingertips
        int m = n * 2;
        float[] ru = new float[m + 1], rv = new float[m + 1];
        for (int i = 0; i < n; i++) {
            ru[i * 2] = tips[i][0]; rv[i * 2] = tips[i][1];
            float nu = i + 1 < n ? tips[i + 1][0] : 0.05f, nv = i + 1 < n ? tips[i + 1][1] : -0.2f;
            float mu = (tips[i][0] + nu) / 2f, mv = (tips[i][1] + nv) / 2f;
            float pull = i + 1 < n ? 0.3f : 0.15f;
            ru[i * 2 + 1] = Easing.lerp(mu, wu * 0.7f, pull); rv[i * 2 + 1] = Easing.lerp(mv, wv * 0.5f, pull);
        }
        float al = membraneAlpha.value;
        int mc = membrane.value;
        float mr = Colors.r(mc) / 255f, mg = Colors.g(mc) / 255f, mb = Colors.b(mc) / 255f;
        VertexConsumer solid = f.solid(Gfx.WHITE);
        for (int i = 0; i < m; i++) {
            Gfx.tri(solid, f.m, w.x(wu, wv), w.y(wu, wv), w.z(wu, wv), w.x(ru[i], rv[i]), w.y(ru[i], rv[i]), w.z(ru[i], rv[i]),
                    w.x(ru[i + 1], rv[i + 1]), w.y(ru[i + 1], rv[i + 1]), w.z(ru[i + 1], rv[i + 1]), mr, mg, mb, al);
        }
        // closing triangle from the last outline point back to the shoulder
        Gfx.tri(solid, f.m, w.x(wu, wv), w.y(wu, wv), w.z(wu, wv), w.x(ru[m], rv[m]), w.y(ru[m], rv[m]), w.z(ru[m], rv[m]),
                w.x(0, 0), w.y(0, 0), w.z(0, 0), mr, mg, mb, al);

        VertexConsumer line = f.add(Gfx.LINE);
        float t = f.time;
        float bw = devil ? 0.035f : 0.026f;
        float ga = glowBones.value ? 1f : 0.55f;
        int boneBase = Colors.lerp(mc, 0x000000, 0.1f);
        bone(f, line, w, 0, 0, eu, ev, bw * 1.5f, boneBase, glow, ga, true);
        bone(f, line, w, eu, ev, wu, wv, bw * 1.2f, boneBase, glow, ga, true);
        for (int i = 1; i < n; i++) bone(f, line, w, wu, wv, tips[i][0], tips[i][1], bw, boneBase, glow, ga, true);
        bone(f, line, w, wu, wv, tips[0][0] + 0.3f, tips[0][1] + (devil ? 0.28f : 0.18f), bw, boneBase, glow, ga, true);   // the thumb claw
        // glowing tips and the edge between them
        for (int i = 0; i < n; i++) {
            f.bloom(w.pose.wx + (w.x(ru[i * 2], rv[i * 2]) - w.pose.ox), w.pose.wy + (w.y(ru[i * 2], rv[i * 2]) - w.pose.oy),
                    w.pose.wz + (w.z(ru[i * 2], rv[i * 2]) - w.pose.oz), 0.05f, glowColor.at(i / (float) n + t * 0.05f), 0.9f);
        }
        for (int i = 0; i < m; i++) {
            bone(f, line, w, ru[i], rv[i], ru[i + 1], rv[i + 1], 0.012f, glow, glow, 0.5f * ga, false);
        }
    }

    /** One bone as a dark core with an optional glowing edge. */
    private void bone(Frame f, VertexConsumer line, Wing w, float u0, float v0, float u1, float v1, float width, int base, int glow, float ga, boolean core) {
        double ax = w.pose.wx + (w.x(u0, v0) - w.pose.ox), ay = w.pose.wy + (w.y(u0, v0) - w.pose.oy), az = w.pose.wz + (w.z(u0, v0) - w.pose.oz);
        double bx = w.pose.wx + (w.x(u1, v1) - w.pose.ox), by = w.pose.wy + (w.y(u1, v1) - w.pose.oy), bz = w.pose.wz + (w.z(u1, v1) - w.pose.oz);
        if (core) f.line(line, ax, ay, az, bx, by, bz, width * 2.6f, width * 1.6f, glow, 0.32f * ga, glow, 0.2f * ga);
        f.line(line, ax, ay, az, bx, by, bz, width, width * 0.7f, Colors.lerp(base, glow, 0.35f), core ? 0.95f : 0.8f * ga, glow, core ? 0.8f : 0.6f * ga);
    }

    private void featherWing(Frame f, Wing w, int baseCol, int tipCol, int glow, boolean angel) {
        VertexConsumer solid = f.solid(Gfx.WHITE);
        int rows = 2;
        int perRow = 7;
        float al = angel ? 0.97f : 0.95f;
        // the wing's arm goes up and out; feathers hang from it
        for (int row = rows - 1; row >= 0; row--) {
            for (int i = 0; i < perRow; i++) {
                float k = i / (float) (perRow - 1);
                float bu = 0.1f + k * 1.15f, bv = 0.12f + (float) Math.sin(k * 2.2f) * 0.42f;     // base point along the arm
                float ang = Easing.lerp(-0.2f, -1.15f, k) - row * 0.15f;                          // feather direction: out and down
                float len = (0.75f + 0.55f * (float) Math.sin(k * 2.6f + 0.2f)) * (row == 0 ? 1f : 0.62f);
                float du = (float) Math.cos(ang) * len, dv = (float) Math.sin(ang) * len;
                float tu = bu + du, tv = bv + dv;
                float wid = 0.12f;
                float px = -dv / len * wid, pv = du / len * wid;                                   // sideways in the wing plane
                int c0 = Colors.lerp(baseCol, tipCol, row == 0 ? 0.35f : 0f);
                float cr = Colors.r(c0) / 255f, cg = Colors.g(c0) / 255f, cb = Colors.b(c0) / 255f;
                float mu = bu + du * 0.45f, mv = bv + dv * 0.45f;
                Gfx.tri(solid, f.m, w.x(bu - px * 0.4f, bv - pv * 0.4f), w.y(bu - px * 0.4f, bv - pv * 0.4f), w.z(bu - px * 0.4f, bv - pv * 0.4f),
                        w.x(mu + px, mv + pv), w.y(mu + px, mv + pv), w.z(mu + px, mv + pv), w.x(tu, tv), w.y(tu, tv), w.z(tu, tv), cr, cg, cb, al);
                Gfx.tri(solid, f.m, w.x(bu + px * 0.4f, bv + pv * 0.4f), w.y(bu + px * 0.4f, bv + pv * 0.4f), w.z(bu + px * 0.4f, bv + pv * 0.4f),
                        w.x(mu - px, mv - pv), w.y(mu - px, mv - pv), w.z(mu - px, mv - pv), w.x(tu, tv), w.y(tu, tv), w.z(tu, tv), cr * 0.85f, cg * 0.85f, cb * 0.85f, al);
                Gfx.tri(solid, f.m, w.x(bu - px * 0.4f, bv - pv * 0.4f), w.y(bu - px * 0.4f, bv - pv * 0.4f), w.z(bu - px * 0.4f, bv - pv * 0.4f),
                        w.x(bu + px * 0.4f, bv + pv * 0.4f), w.y(bu + px * 0.4f, bv + pv * 0.4f), w.z(bu + px * 0.4f, bv + pv * 0.4f), w.x(mu + px, mv + pv), w.y(mu + px, mv + pv), w.z(mu + px, mv + pv), cr, cg, cb, al);
                if (row == 0 && glowBones.value && i % 2 == 0) {
                    f.bloom(w.pose.wx + (w.x(tu, tv) - w.pose.ox), w.pose.wy + (w.y(tu, tv) - w.pose.oy), w.pose.wz + (w.z(tu, tv) - w.pose.oz), 0.04f, glow, 0.7f);
                }
            }
        }
        VertexConsumer line = f.add(Gfx.LINE);
        bone(f, line, w, 0, 0, 0.55f, 0.55f, 0.03f, baseCol, glow, glowBones.value ? 0.8f : 0.4f, true);
        bone(f, line, w, 0.55f, 0.55f, 1.3f, 0.5f, 0.026f, baseCol, glow, glowBones.value ? 0.8f : 0.4f, true);
    }
}
