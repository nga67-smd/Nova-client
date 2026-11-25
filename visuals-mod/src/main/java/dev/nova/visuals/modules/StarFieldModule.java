package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.core.Colors;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import net.minecraft.client.render.VertexConsumer;

import java.util.Random;

/** A dense field of twinkling stars with different colors and sizes, and shooting stars. */
public final class StarFieldModule extends Module {
    private static final int MAX_STARS = 1400;
    private final float[] dx = new float[MAX_STARS], dy = new float[MAX_STARS], dz = new float[MAX_STARS];
    private final float[] size = new float[MAX_STARS], phase = new float[MAX_STARS];
    private final int[] tint = new int[MAX_STARS];

    private final Setting.Num density = add(new Setting.Num("density", "Stars", 1.0f, 0.2f, 2f, 0.05f, "x"));
    private final Setting.Num brightness = add(new Setting.Num("brightness", "Brightness", 1.0f, 0.2f, 2f, 0.05f, "x"));
    private final Setting.Num starSize = add(new Setting.Num("size", "Star size", 1.0f, 0.4f, 2.5f, 0.05f, "x"));
    private final Setting.Num twinkle = add(new Setting.Num("twinkle", "Twinkle", 1.0f, 0f, 2f, 0.05f, "x"));
    private final Setting.Bool shooting = add(new Setting.Bool("shooting", "Shooting stars", true));
    private final Setting.Num shootRate = add(new Setting.Num("shoot_rate", "Shooting star rate", 1.0f, 0.2f, 4f, 0.05f, "x")
    );
    private final Setting.Bool always = add(new Setting.Bool("always", "Also during the day", false));

    // shooting stars
    private final float[] mx = new float[6], my = new float[6], mz = new float[6], mdx = new float[6], mdy = new float[6], mdz = new float[6], mage = new float[6];
    private final boolean[] mon = new boolean[6];
    private float nextMeteor = 2f;

    public StarFieldModule() {
        super("starfield", "Star Field", "A realistic night sky full of stars, with shooting stars.", Category.ENVIRONMENT, false);
        Random r = new Random(20240607L);
        for (int i = 0; i < MAX_STARS; i++) {
            double z = r.nextDouble() * 2 - 1, a = r.nextDouble() * Math.PI * 2, rr = Math.sqrt(1 - z * z);
            dx[i] = (float) (Math.cos(a) * rr); dy[i] = (float) z; dz[i] = (float) (Math.sin(a) * rr);
            float m = r.nextFloat();
            size[i] = 0.25f + m * m * m * 1.1f;                                  // most are faint, a few are bright
            phase[i] = r.nextFloat() * 6.28f;
            float k = r.nextFloat();
            tint[i] = k < 0.55f ? 0xFFFFFF : k < 0.78f ? 0xBBD4FF : k < 0.92f ? 0xFFE2B0 : 0xFFB4A0;   // white, blue-white, yellow, orange
        }
    }

    @Override
    public void onWorld(Frame f) {
        if (!Sky.hasSky(f)) return;
        float vis = (always.value ? 1f : Sky.night(f.world, f.tickDelta)) * Sky.clear(f.world, f.tickDelta);
        if (vis < 0.02f) return;
        float angle = f.world.getSkyAngle(f.tickDelta);
        int n = (int) (MAX_STARS * Math.min(1f, density.value / 2f) * 1.0f);
        n = Math.min(MAX_STARS, Math.max(40, (int) (700 * density.value)));
        VertexConsumer core = f.add(Gfx.CORE);
        VertexConsumer star = null;
        double cx = f.cam.x, cy = f.cam.y, cz = f.cam.z;
        for (int i = 0; i < n; i++) {
            float[] d = Sky.rotate(dx[i], dy[i], dz[i], angle);
            if (d[1] < -0.12f) continue;                                         // below the horizon
            float tw = 1f - 0.45f * twinkle.value * (0.5f + 0.5f * (float) Math.sin(f.time * (1.2f + phase[i] * 0.25f) + phase[i] * 3f));
            float horizon = Math.min(1f, (d[1] + 0.12f) * 4f);
            float a = vis * tw * horizon * brightness.value * (0.35f + size[i] * 0.65f);
            float sz = (0.7f + size[i] * 1.5f) * starSize.value;
            f.sprite(core, cx + d[0] * 100, cy + d[1] * 100, cz + d[2] * 100, sz, 0f, tint[i], a);
            if (size[i] > 0.9f) {                                                // the brightest ones get a sparkle
                if (star == null) star = f.add(Gfx.STAR);
                f.sprite(star, cx + d[0] * 100, cy + d[1] * 100, cz + d[2] * 100, sz * 3.2f, 0f, tint[i], a * 0.7f);
            }
        }
        if (shooting.value) meteors(f, vis, angle);
    }

    private void meteors(Frame f, float vis, float angle) {
        nextMeteor -= f.dt;
        if (nextMeteor <= 0f) {
            nextMeteor = (3f + (float) Math.random() * 8f) / shootRate.value;
            for (int i = 0; i < mon.length; i++) {
                if (mon[i]) continue;
                double a = Math.random() * Math.PI * 2, el = 0.35 + Math.random() * 0.5;
                mx[i] = (float) (Math.cos(a) * Math.cos(el)); my[i] = (float) Math.sin(el); mz[i] = (float) (Math.sin(a) * Math.cos(el));
                double b = Math.random() * Math.PI * 2;                          // the way it travels, sideways along the sky
                mdx[i] = (float) Math.cos(b) * 0.9f; mdy[i] = -0.35f - (float) Math.random() * 0.3f; mdz[i] = (float) Math.sin(b) * 0.9f;
                mage[i] = 0f; mon[i] = true;
                break;
            }
        }
        VertexConsumer line = null;
        for (int i = 0; i < mon.length; i++) {
            if (!mon[i]) continue;
            mage[i] += f.dt;
            float life = 0.9f, t = mage[i] / life;
            if (t >= 1f) { mon[i] = false; continue; }
            float hx = mx[i] + mdx[i] * mage[i] * 0.55f, hy = my[i] + mdy[i] * mage[i] * 0.55f, hz = mz[i] + mdz[i] * mage[i] * 0.55f;
            float tl = Math.max(0f, mage[i] - 0.28f);
            float tx = mx[i] + mdx[i] * tl * 0.55f, ty = my[i] + mdy[i] * tl * 0.55f, tz = mz[i] + mdz[i] * tl * 0.55f;
            float hl = (float) Math.sqrt(hx * hx + hy * hy + hz * hz), tlen = (float) Math.sqrt(tx * tx + ty * ty + tz * tz);
            float[] h = Sky.rotate(hx / hl, hy / hl, hz / hl, 0f), tt = Sky.rotate(tx / tlen, ty / tlen, tz / tlen, 0f);
            float fade = (float) Math.sin(Math.PI * t) * vis;
            if (line == null) line = f.add(Gfx.LINE);
            f.line(line, f.cam.x + tt[0] * 98, f.cam.y + tt[1] * 98, f.cam.z + tt[2] * 98, f.cam.x + h[0] * 98, f.cam.y + h[1] * 98, f.cam.z + h[2] * 98,
                    0.02f, 0.5f, 0x9FC4FF, 0f, 0xFFFFFF, fade);
            f.sprite(f.add(Gfx.GLOW), f.cam.x + h[0] * 98, f.cam.y + h[1] * 98, f.cam.z + h[2] * 98, 2.2f, 0f, 0xDDEBFF, fade * 0.8f);
            line = f.add(Gfx.LINE);
        }
    }
}
