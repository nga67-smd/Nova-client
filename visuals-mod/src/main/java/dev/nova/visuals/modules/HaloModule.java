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

/** A glowing ring above your head: holy, dark thorn crown or rune circle. */
public final class HaloModule extends Module {
    private final Setting.Choice style = add(new Setting.Choice("style", "Style", 0, "Holy", "Dark thorns", "Runes"));
    private final ColorSpec color = new ColorSpec(this, 0xFFD870, 4);
    private final Setting.Num radius = add(new Setting.Num("radius", "Radius", 0.34f, 0.2f, 0.8f, 0.01f, ""));
    private final Setting.Num height = add(new Setting.Num("height", "Height", 0.3f, 0.05f, 0.9f, 0.01f, ""));
    private final Setting.Num thickness = add(new Setting.Num("thickness", "Thickness", 0.035f, 0.01f, 0.12f, 0.005f, ""));
    private final Setting.Num spin = add(new Setting.Num("spin", "Spin speed", 1.0f, 0f, 4f, 0.05f, "x"));
    private final Setting.Bool sparkles = add(new Setting.Bool("sparkles", "Sparkles", true));
    private final Setting.Bool firstPerson = add(new Setting.Bool("first_person", "Show in first person", false));
    private float acc;

    public HaloModule() {
        super("halo", "Halo", "A glowing halo, thorn crown or rune circle above your head.", Category.COSMETICS, false);
    }

    @Override
    public void onWorld(Frame f) {
        for (PlayerEntity p : Fx.targets(f)) {
            if (p == f.player && Fx.firstPerson() && !firstPerson.value) continue;
            draw(f, p);
        }
    }

    private void draw(Frame f, PlayerEntity p) {
        var pos = p.getLerpedPos(f.tickDelta);
        double cy = pos.y + p.getHeight() + height.value + 0.03 * Math.sin(f.time * 2f + p.getId());
        VertexConsumer line = f.add(Gfx.LINE);
        int seg = Math.max(24, Settings.segments());
        float r = radius.value, w = thickness.value, rot = f.time * spin.value * 0.8f;
        float tiltX = 0.12f * (float) Math.sin(f.time * 1.3f), tiltZ = 0.12f * (float) Math.cos(f.time * 1.1f);
        for (int i = 0; i < seg; i++) {
            double a0 = i * Math.PI * 2 / seg, a1 = (i + 1) * Math.PI * 2 / seg;
            int c = color.at(i / (float) seg);
            float shimmer = 0.75f + 0.25f * (float) Math.sin(f.time * 3f + i * 0.5f);
            double x0 = pos.x + Math.cos(a0) * r, z0 = pos.z + Math.sin(a0) * r, x1 = pos.x + Math.cos(a1) * r, z1 = pos.z + Math.sin(a1) * r;
            double y0 = cy + Math.cos(a0) * tiltX + Math.sin(a0) * tiltZ, y1 = cy + Math.cos(a1) * tiltX + Math.sin(a1) * tiltZ;
            f.line(line, x0, y0, z0, x1, y1, z1, w * 3.2f, w * 3.2f, c, 0.3f * Settings.bloom() * shimmer, c, 0.3f * Settings.bloom() * shimmer);
            f.line(line, x0, y0, z0, x1, y1, z1, w, w, c, shimmer, c, shimmer);
        }
        if (style.index == 1) {                                               // thorns
            int thorns = 9;
            for (int k = 0; k < thorns; k++) {
                double a = k * Math.PI * 2 / thorns + rot;
                double bx = pos.x + Math.cos(a) * r, bz = pos.z + Math.sin(a) * r;
                int c = color.at(k / (float) thorns);
                f.line(line, bx, cy, bz, bx + Math.cos(a) * 0.04, cy + 0.2 + 0.04 * Math.sin(f.time * 2 + k), bz + Math.sin(a) * 0.04, w * 1.6f, 0.002f, c, 1f, c, 0.1f);
            }
        } else if (style.index == 2) {                                        // an inner counter-rotating ring of rune ticks
            int ticks = 16;
            for (int k = 0; k < ticks; k++) {
                double a = k * Math.PI * 2 / ticks - rot * 1.4;
                double r0 = r * 0.72, r1 = r * (k % 2 == 0 ? 0.9 : 0.8);
                int c = color.at(k / (float) ticks);
                f.line(line, pos.x + Math.cos(a) * r0, cy, pos.z + Math.sin(a) * r0, pos.x + Math.cos(a) * r1, cy, pos.z + Math.sin(a) * r1, w * 0.8f, w * 0.8f, c, 0.9f, c, 0.9f);
            }
        }
        if (sparkles.value) {
            acc += f.dt * Settings.count(6);
            while (acc >= 1f) {
                acc -= 1f;
                double a = Math.random() * Math.PI * 2;
                ParticleEngine.spawn(ParticleEngine.STAR, pos.x + Math.cos(a) * r, cy, pos.z + Math.sin(a) * r, 0f, Fx.rand(0.1f, 0.35f), 0f, Fx.rand(0.7f, 1.3f),
                        Fx.rand(0.06f, 0.12f), 0f, color.at((float) Math.random()), 0.9f, 0f, 0.3f, Fx.rand(-2f, 2f));
            }
        }
    }
}
