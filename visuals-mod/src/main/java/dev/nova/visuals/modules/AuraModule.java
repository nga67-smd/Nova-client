package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.fx.ParticleEngine;
import dev.nova.visuals.gfx.Frame;
import net.minecraft.entity.player.PlayerEntity;

/** An aura of particles around the body: infernal embers, soul flames, blood motes or void wisps. */
public final class AuraModule extends Module {
    private final Setting.Choice style = add(new Setting.Choice("style", "Style", 0, "Infernal embers", "Soul fire", "Blood motes", "Void wisps", "Accent"));
    private final Setting.Num density = add(new Setting.Num("density", "Density", 1.0f, 0.1f, 3f, 0.05f, "x"));
    private final Setting.Num size = add(new Setting.Num("size", "Size", 1.0f, 0.3f, 3f, 0.05f, "x"));
    private final Setting.Num spread = add(new Setting.Num("spread", "Spread", 0.6f, 0.2f, 1.5f, 0.05f, ""));
    private float acc;

    public AuraModule() {
        super("aura", "Aura", "Particles swirling around your body.", Category.COSMETICS, false);
    }

    @Override
    public void onWorld(Frame f) {
        for (PlayerEntity p : Fx.targets(f)) {
            var pos = p.getLerpedPos(f.tickDelta);
            acc += f.dt * Settings.count(22) * density.value;
            int guard = 0;
            while (acc >= 1f && guard++ < 40) {
                acc -= 1f;
                double a = Math.random() * Math.PI * 2, r = spread.value * (0.6 + Math.random() * 0.5);
                double x = pos.x + Math.cos(a) * r, z = pos.z + Math.sin(a) * r, y = pos.y + Math.random() * p.getHeight();
                float s = size.value;
                switch (style.index) {
                    case 0 -> ParticleEngine.spawn(ParticleEngine.GLOW, x, y, z, Fx.rand(-0.15f, 0.15f), Fx.rand(0.6f, 1.3f), Fx.rand(-0.15f, 0.15f), Fx.rand(1f, 1.9f),
                            0.08f * s, 0.01f, Math.random() < 0.5 ? 0xFF3A12 : 0xFFA030, 0.95f, -0.3f, 0.5f, 2f);
                    case 1 -> ParticleEngine.spawn(ParticleEngine.GLOW, x, y, z, Fx.rand(-0.1f, 0.1f), Fx.rand(0.5f, 1f), Fx.rand(-0.1f, 0.1f), Fx.rand(1.2f, 2.2f),
                            0.1f * s, 0.02f, Math.random() < 0.5 ? 0x3FE8E0 : 0x2A8CFF, 0.9f, -0.2f, 0.4f, 0f);
                    case 2 -> ParticleEngine.spawn(ParticleEngine.DOT, x, pos.y + p.getHeight() * (0.5 + Math.random() * 0.5), z, Fx.rand(-0.05f, 0.05f), Fx.rand(-0.1f, 0.1f), Fx.rand(-0.05f, 0.05f), Fx.rand(1f, 1.8f),
                            0.06f * s, 0.03f * s, 0xB5101C, 0.95f, 1.2f, 0.3f, 0f);
                    case 3 -> ParticleEngine.spawn(ParticleEngine.GLOW, x, y, z, (float) (-Math.sin(a) * 0.8), Fx.rand(0.1f, 0.5f), (float) (Math.cos(a) * 0.8), Fx.rand(1f, 1.8f),
                            0.1f * s, 0.01f, Math.random() < 0.5 ? 0x8A3DFF : 0x4A1A9A, 0.9f, -0.1f, 0.6f, 0f);
                    default -> ParticleEngine.spawn(ParticleEngine.STAR, x, y, z, Fx.rand(-0.1f, 0.1f), Fx.rand(0.3f, 0.8f), Fx.rand(-0.1f, 0.1f), Fx.rand(1f, 1.8f),
                            0.1f * s, 0f, Math.random() < 0.5 ? Settings.accent() : Settings.accent2(), 0.9f, -0.1f, 0.4f, 3f);
                }
            }
        }
    }
}
