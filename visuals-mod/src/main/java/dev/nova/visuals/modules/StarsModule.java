package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.ColorSpec;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.fx.ParticleEngine;
import dev.nova.visuals.gfx.Frame;
import net.minecraft.util.math.Vec3d;

/** Glowing stars and sparkles that drift around you. */
public final class StarsModule extends Module {
    private final ColorSpec color = new ColorSpec(this, 0xFFE9A8, 1);
    private final Setting.Num rate = add(new Setting.Num("rate", "Amount", 1.0f, 0.1f, 3f, 0.05f, "x"));
    private final Setting.Num size = add(new Setting.Num("size", "Size", 1.0f, 0.4f, 3f, 0.05f, "x"));
    private final Setting.Num radius = add(new Setting.Num("radius", "Spread", 1.6f, 0.5f, 5f, 0.1f, " blocks"));
    private final Setting.Num speed = add(new Setting.Num("speed", "Drift speed", 1.0f, 0.2f, 3f, 0.05f, "x"));
    private float acc;

    public StarsModule() {
        super("stars", "Floating Stars", "Twinkling stars and sparkles drifting around you.", Category.PARTICLES, true);
    }

    @Override
    public void onWorld(Frame f) {
        acc += f.dt * Settings.count(10) * rate.value;
        Vec3d p = Fx.at(f.player, f.tickDelta);
        while (acc >= 1f) {
            acc -= 1f;
            double a = Math.random() * Math.PI * 2, r = radius.value * (0.35 + Math.random() * 0.65);
            double yy = p.y + Math.random() * 2.4 - 0.1;
            float s = speed.value;
            boolean star = Math.random() < 0.6;
            ParticleEngine.spawn(star ? ParticleEngine.STAR : ParticleEngine.GLOW, p.x + Math.cos(a) * r, yy, p.z + Math.sin(a) * r,
                    Fx.rand(-0.12f, 0.12f) * s, Fx.rand(0.05f, 0.3f) * s, Fx.rand(-0.12f, 0.12f) * s,
                    Fx.rand(1.6f, 3.2f), Fx.rand(0.1f, 0.22f) * size.value, 0.02f, color.at((float) Math.random()), 0.95f, -0.02f, 0.3f,
                    star ? Fx.rand(-1.2f, 1.2f) : 0f);
        }
    }
}
