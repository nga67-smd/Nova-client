package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.ColorSpec;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.fx.ParticleEngine;
import dev.nova.visuals.fx.RingPool;
import dev.nova.visuals.gfx.Frame;
import net.minecraft.client.MinecraftClient;
import net.minecraft.util.math.Vec3d;

/** Rings that spread over the ground when you jump and when you land. */
public final class RingsModule extends Module {
    private final ColorSpec color = new ColorSpec(this, 0x7A5CFF, 0);
    private final Setting.Num size = add(new Setting.Num("size", "Size", 1.6f, 0.5f, 5f, 0.1f, " blocks"));
    private final Setting.Num speed = add(new Setting.Num("speed", "Speed", 1.0f, 0.4f, 3f, 0.05f, "x"));
    private final Setting.Num opacity = add(new Setting.Num("opacity", "Opacity", 0.9f, 0.1f, 1f, 0.05f, ""));
    private final Setting.Bool onJump = add(new Setting.Bool("jump", "On jump", true));
    private final Setting.Bool onLand = add(new Setting.Bool("land", "On landing", true));
    private final Setting.Bool echo = add(new Setting.Bool("echo", "Second ring behind the first", true));
    private final Setting.Bool burst = add(new Setting.Bool("burst", "Sparks", true));

    private boolean wasGround = true;
    private double fall;

    public RingsModule() {
        super("rings", "Jump & Landing Rings", "Expanding rings on the ground when you jump or land.", Category.PARTICLES, true);
    }

    @Override
    public void onTick(MinecraftClient mc) {
        var p = mc.player;
        if (p == null) return;
        boolean ground = p.isOnGround();
        Vec3d pos = p.getPos();
        if (!ground && p.getVelocity().y < -0.1) fall = Math.max(fall, -p.getVelocity().y);
        if (wasGround && !ground && p.getVelocity().y > 0.1 && onJump.value && !p.isTouchingWater()) spawn(pos, 0.7f);
        if (!wasGround && ground && onLand.value && fall > 0.2) spawn(pos, (float) Math.min(1.8, 0.8 + fall * 0.9));
        if (ground) fall = 0;
        wasGround = ground;
    }

    private void spawn(Vec3d pos, float scale) {
        float life = 0.9f / speed.value;
        int c = color.at(0f);
        RingPool.spawn(true, pos.x, pos.y + 0.03, pos.z, size.value * scale, life, 0.07f * scale, c, opacity.value, 0f);
        if (echo.value) RingPool.spawn(true, pos.x, pos.y + 0.03, pos.z, size.value * scale * 0.65f, life * 0.9f, 0.04f * scale, color.at(0.5f), opacity.value * 0.7f, 0.12f);
        if (burst.value) {
            int n = dev.nova.visuals.config.Settings.count((int) (14 * scale));
            for (int i = 0; i < n; i++) {
                double a = Math.random() * Math.PI * 2;
                float s = Fx.rand(0.6f, 1.6f) * scale * size.value * 0.6f;
                ParticleEngine.spawn(ParticleEngine.GLOW, pos.x, pos.y + 0.05, pos.z, (float) Math.cos(a) * s, Fx.rand(0.3f, 1.4f), (float) Math.sin(a) * s,
                        Fx.rand(0.5f, 1.0f), 0.1f, 0.02f, color.at((float) Math.random()), 0.9f, 3f, 2.2f, 0f);
            }
        }
    }

    @Override public void onWorld(Frame f) { /* rings are drawn by the shared ring pool */ }
}
