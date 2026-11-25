package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.ColorSpec;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.fx.ParticleEngine;
import dev.nova.visuals.fx.RingPool;
import net.minecraft.entity.Entity;
import net.minecraft.util.math.Vec3d;

/** Glowing particles and an expanding ring where you hit something. Cosmetic only: hits work exactly as before. */
public final class HitFxModule extends Module {
    private final ColorSpec color = new ColorSpec(this, 0xFF3355, 3);
    private final Setting.Num amount = add(new Setting.Num("amount", "Particles", 1.0f, 0.2f, 3f, 0.1f, "x"));
    private final Setting.Num ringSize = add(new Setting.Num("ring_size", "Ring size", 0.9f, 0.3f, 3f, 0.05f, " blocks"));
    private final Setting.Bool ring = add(new Setting.Bool("ring", "Impact ring", true));
    private final Setting.Bool stars = add(new Setting.Bool("stars", "Star sparks", true));

    public HitFxModule() {
        super("hit_fx", "Hit Effects", "Sparks and an expanding ring on every hit you land.", Category.PARTICLES, true);
    }

    /** Called when you attack an entity. */
    public void hit(Entity target) {
        Vec3d c = target.getBoundingBox().getCenter();
        int n = Settings.count(Math.round(18 * amount.value));
        ParticleEngine.burst(c.x, c.y, c.z, n, 3.2f, 0.7f, 0.16f, color.at(0f), stars.value);
        if (ring.value) {
            RingPool.spawn(false, c.x, c.y, c.z, ringSize.value, 0.45f, 0.05f, color.at(0.3f), 1f, 0f);
            RingPool.spawn(false, c.x, c.y, c.z, ringSize.value * 1.6f, 0.6f, 0.03f, color.at(0.7f), 0.7f, 0.07f);
        }
    }
}
