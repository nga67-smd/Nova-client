package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.ColorSpec;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.fx.ParticleEngine;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.entity.player.PlayerEntity;

/** A rotating pentagram circle with runes on the ground under your feet. */
public final class MagicCircleModule extends Module {
    private final ColorSpec color = new ColorSpec(this, 0xFF2030, 4);
    private final Setting.Num radius = add(new Setting.Num("radius", "Radius", 1.5f, 0.6f, 4f, 0.05f, ""));
    private final Setting.Num spin = add(new Setting.Num("spin", "Spin speed", 1.0f, 0f, 4f, 0.05f, "x"));
    private final Setting.Num opacity = add(new Setting.Num("opacity", "Opacity", 0.9f, 0.1f, 1f, 0.05f, ""));
    private final Setting.Bool star = add(new Setting.Bool("pentagram", "Pentagram", true));
    private final Setting.Bool embers = add(new Setting.Bool("embers", "Rising embers", true));
    private final Setting.Bool stillOnly = add(new Setting.Bool("still", "Only while standing still", false));
    private float acc;
    private float fade;

    public MagicCircleModule() {
        super("circle", "Magic Circle", "A rotating pentagram with runes at your feet.", Category.COSMETICS, false);
    }

    @Override
    public void onWorld(Frame f) {
        for (PlayerEntity p : Fx.targets(f)) {
            if (!p.isOnGround()) continue;
            if (stillOnly.value && p == f.player && p.getVelocity().horizontalLengthSquared() > 0.0004) { fade = Math.max(0f, fade - f.dt * 3f); }
            else fade = Math.min(1f, fade + f.dt * 3f);
            if (stillOnly.value && p == f.player && fade <= 0.01f) continue;
            draw(f, p, stillOnly.value && p == f.player ? fade : 1f);
        }
    }

    private void draw(Frame f, PlayerEntity p, float vis) {
        var pos = p.getLerpedPos(f.tickDelta);
        double y = pos.y + 0.03;
        float r = radius.value * (0.9f + 0.1f * vis);
        float a = opacity.value * vis;
        float w = 0.025f;
        float rot = f.time * spin.value * 0.5f;
        VertexConsumer line = f.add(Gfx.LINE);
        int seg = Math.max(32, Settings.segments());
        ring(f, line, pos.x, y, pos.z, r, w, seg, a, 0f, 0);
        ring(f, line, pos.x, y, pos.z, r * 0.88f, w * 0.7f, seg, a * 0.8f, 0f, 1);
        ring(f, line, pos.x, y, pos.z, r * 0.55f, w * 0.7f, seg, a * 0.7f, 0f, 2);
        for (int i = 0; i < 24; i++) {                                         // runes between the two outer rings
            double ang = i * Math.PI * 2 / 24 - rot * 0.6;
            float len = (i % 3 == 0) ? 0.09f : 0.05f;
            double r0 = r * 0.9, r1 = r * 0.9 + len * r;
            int c = color.at(i / 24f);
            double cx = Math.cos(ang), sz = Math.sin(ang);
            f.line(line, pos.x + cx * r0, y, pos.z + sz * r0, pos.x + cx * r1, y, pos.z + sz * r1, w * 0.8f, w * 0.8f, c, a, c, a);
            if (i % 2 == 0) {                                                  // a little cross-stroke to look like a glyph
                double mx = pos.x + cx * (r0 + r1) / 2, mz = pos.z + sz * (r0 + r1) / 2;
                f.line(line, mx - sz * 0.04, y, mz + cx * 0.04, mx + sz * 0.04, y, mz - cx * 0.04, w * 0.6f, w * 0.6f, c, a * 0.8f, c, a * 0.8f);
            }
        }
        if (star.value) {
            for (int i = 0; i < 5; i++) {
                double a0 = rot + i * Math.PI * 2 / 5 - Math.PI / 2, a1 = rot + ((i + 2) % 5) * Math.PI * 2 / 5 - Math.PI / 2;
                int c = color.at(i / 5f);
                float rr = r * 0.88f;
                double x0 = pos.x + Math.cos(a0) * rr, z0 = pos.z + Math.sin(a0) * rr, x1 = pos.x + Math.cos(a1) * rr, z1 = pos.z + Math.sin(a1) * rr;
                f.line(line, x0, y, z0, x1, y, z1, w * 3f, w * 3f, c, 0.25f * a * Settings.bloom(), c, 0.25f * a * Settings.bloom());
                f.line(line, x0, y, z0, x1, y, z1, w, w, c, a, c, a);
                f.bloom(x0, y, z0, 0.06f, c, 0.8f * a);
            }
        }
        if (embers.value) {
            acc += f.dt * Settings.count(10) * vis;
            while (acc >= 1f) {
                acc -= 1f;
                double ang = Math.random() * Math.PI * 2, rr = r * (0.4 + Math.random() * 0.5);
                ParticleEngine.spawn(ParticleEngine.GLOW, pos.x + Math.cos(ang) * rr, y, pos.z + Math.sin(ang) * rr, 0f, Fx.rand(0.5f, 1.3f), 0f, Fx.rand(1f, 2f),
                        0.07f, 0.01f, color.at((float) Math.random()), 0.9f, -0.2f, 0.4f, 0f);
            }
        }
    }

    private void ring(Frame f, VertexConsumer line, double cx, double y, double cz, float r, float w, int seg, float a, float off, int idx) {
        for (int i = 0; i < seg; i++) {
            double a0 = i * Math.PI * 2 / seg, a1 = (i + 1) * Math.PI * 2 / seg;
            int c = color.at(i / (float) seg + idx * 0.2f);
            f.line(line, cx + Math.cos(a0) * r, y, cz + Math.sin(a0) * r, cx + Math.cos(a1) * r, y, cz + Math.sin(a1) * r, w, w, c, a, c, a);
        }
    }
}
