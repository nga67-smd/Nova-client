package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.fx.ParticleEngine;
import dev.nova.visuals.gfx.Frame;

/** Floating motes in the air around you: dust, fireflies, embers or sparkles. */
public final class AtmosphereModule extends Module {
    private final Setting.Choice style = add(new Setting.Choice("style", "Style", 1, "Dust motes", "Fireflies", "Embers", "Sparkles", "Ash"));
    private final Setting.Num density = add(new Setting.Num("density", "Density", 1.0f, 0.1f, 3f, 0.05f, "x"));
    private final Setting.Num size = add(new Setting.Num("size", "Size", 1.0f, 0.3f, 3f, 0.05f, "x"));
    private final Setting.Num radius = add(new Setting.Num("radius", "Radius", 12f, 4f, 24f, 1f, "m"));
    private final Setting.Num brightness = add(new Setting.Num("brightness", "Brightness", 1.0f, 0.2f, 2f, 0.05f, "x"));
    private float acc;

    public AtmosphereModule() {
        super("atmosphere", "Floating Particles", "Atmospheric motes drifting through the air.", Category.PARTICLES, false);
    }

    @Override
    public void onWorld(Frame f) {
        acc += f.dt * Settings.count(26) * density.value;
        int guard = 0;
        while (acc >= 1f && guard++ < 60) {
            acc -= 1f;
            double a = Math.random() * Math.PI * 2, d = Math.sqrt(Math.random()) * radius.value;
            double x = f.cam.x + Math.cos(a) * d, z = f.cam.z + Math.sin(a) * d, y = f.cam.y + Fx.rand(-3f, 5f);
            float s = size.value, br = Math.min(1f, brightness.value);
            switch (style.index) {
                case 0 -> ParticleEngine.spawn(ParticleEngine.DOT, x, y, z, Fx.rand(-0.1f, 0.1f), Fx.rand(-0.03f, 0.08f), Fx.rand(-0.1f, 0.1f), Fx.rand(4f, 8f),
                        0.035f * s, 0.035f * s, 0xFFF1D6, 0.55f * br, 0f, 0.3f, 0f);
                case 1 -> ParticleEngine.spawn(ParticleEngine.GLOW, x, y, z, Fx.rand(-0.25f, 0.25f), Fx.rand(-0.1f, 0.2f), Fx.rand(-0.25f, 0.25f), Fx.rand(3f, 6f),
                        0.09f * s, 0.02f, Math.random() < 0.5 ? 0xC6FF5A : 0xFFE96A, 0.95f * br, 0f, 0.6f, 0f);
                case 2 -> ParticleEngine.spawn(ParticleEngine.GLOW, x, f.cam.y + Fx.rand(-3f, 1f), z, Fx.rand(-0.3f, 0.3f), Fx.rand(0.5f, 1.2f), Fx.rand(-0.3f, 0.3f), Fx.rand(2f, 4f),
                        0.07f * s, 0.01f, Math.random() < 0.5 ? 0xFF5A1F : 0xFFB03A, 0.95f * br, -0.15f, 0.5f, 3f);
                case 3 -> ParticleEngine.spawn(ParticleEngine.STAR, x, y, z, Fx.rand(-0.1f, 0.1f), Fx.rand(0.05f, 0.25f), Fx.rand(-0.1f, 0.1f), Fx.rand(2f, 4f),
                        0.12f * s, 0f, 0xFFFFFF, 0.9f * br, 0f, 0.4f, Fx.rand(-2f, 2f));
                default -> ParticleEngine.spawn(ParticleEngine.DOT, x, f.cam.y + Fx.rand(2f, 6f), z, Fx.rand(0.1f, 0.3f), Fx.rand(-0.4f, -0.2f), Fx.rand(-0.1f, 0.1f), Fx.rand(4f, 7f),
                        0.04f * s, 0.03f * s, 0x9A9A9A, 0.5f * br, 0f, 0.1f, 1f);
            }
        }
    }
}
