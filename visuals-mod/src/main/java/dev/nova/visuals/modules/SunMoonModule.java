package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.core.Colors;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import net.minecraft.client.render.VertexConsumer;

/** A glowing, customizable sun and moon (with an optional blood moon). */
public final class SunMoonModule extends Module {
    private final Setting.Num sunSize = add(new Setting.Num("sun_size", "Sun size", 1.0f, 0.4f, 3f, 0.05f, "x"));
    private final Setting.Color sunColor = add(new Setting.Color("sun_color", "Sun color", 0xFFC863));
    private final Setting.Num moonSize = add(new Setting.Num("moon_size", "Moon size", 1.0f, 0.4f, 3f, 0.05f, "x"));
    private final Setting.Color moonColor = add(new Setting.Color("moon_color", "Moon color", 0xB9CCFF));
    private final Setting.Bool blood = add(new Setting.Bool("blood", "Blood moon", false));
    private final Setting.Num glow = add(new Setting.Num("glow", "Glow", 1.0f, 0f, 2.5f, 0.05f, "x"));
    private final Setting.Bool rays = add(new Setting.Bool("rays", "Slowly turning rays", true));

    public SunMoonModule() {
        super("sunmoon", "Sun & Moon", "A big glowing sun and moon with soft halos.", Category.ENVIRONMENT, false);
    }

    @Override
    public void onWorld(Frame f) {
        if (!Sky.hasSky(f)) return;
        float[] s = Sky.sun(f.world, f.tickDelta);
        float clear = Sky.clear(f.world, f.tickDelta);
        body(f, s[0], s[1], s[2], sunColor.value, 9f * sunSize.value, clear, 1f);
        int mc = blood.value ? 0xFF2A22 : moonColor.value;
        body(f, -s[0], -s[1], -s[2], mc, (blood.value ? 8f : 6f) * moonSize.value, clear, blood.value ? 1.4f : 0.8f);
    }

    private void body(Frame f, float dx, float dy, float dz, int rgb, float size, float clear, float power) {
        if (dy < -0.08f) return;
        float horizon = Math.min(1f, (dy + 0.08f) * 6f) * clear;
        double d = 92;
        double x = f.cam.x + dx * d, y = f.cam.y + dy * d, z = f.cam.z + dz * d;
        VertexConsumer g = f.add(Gfx.GLOW), core = f.add(Gfx.CORE);
        float a = horizon * glow.value;
        // warm up the light when the body is low
        int tint = Colors.lerp(Colors.lerp(rgb, 0xFF7A30, 0.6f), rgb, Math.min(1f, Math.max(0f, dy) * 3f));
        f.sprite(g, x, y, z, size * 7f, 0f, tint, 0.22f * a * power);
        f.sprite(g, x, y, z, size * 3.4f, 0f, tint, 0.42f * a * power);
        f.sprite(core, x, y, z, size, 0f, Colors.lerp(tint, 0xFFFFFF, 0.55f), horizon * Math.min(1f, power));
        if (rays.value) {
            VertexConsumer st = f.add(Gfx.STAR);
            f.sprite(st, x, y, z, size * 5f, f.time * 0.06f, tint, 0.35f * a);
            f.sprite(st, x, y, z, size * 3.4f, -f.time * 0.09f, tint, 0.3f * a);
        }
    }
}
