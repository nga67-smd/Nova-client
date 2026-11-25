package dev.nova.visuals.fx;

import dev.nova.visuals.core.Colors;
import dev.nova.visuals.core.Easing;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import net.minecraft.client.render.VertexConsumer;

/**
 * Glowing particles. They live in fixed arrays (nothing is allocated per particle) and are drawn together
 * in one batch per texture. Size and alpha follow easing curves over each particle's life.
 */
public final class ParticleEngine {
    public static final int GLOW = 0, STAR = 1, DOT = 2;
    private static final int MAX = 8192;

    private static final float[] x = new float[MAX], y = new float[MAX], z = new float[MAX];
    private static final float[] vx = new float[MAX], vy = new float[MAX], vz = new float[MAX];
    private static final float[] age = new float[MAX], life = new float[MAX], s0 = new float[MAX], s1 = new float[MAX];
    private static final float[] alpha = new float[MAX], grav = new float[MAX], drag = new float[MAX], rot = new float[MAX], spin = new float[MAX];
    private static final int[] color = new int[MAX];
    private static final byte[] kind = new byte[MAX];
    private static final double[] ox = new double[MAX];       // world origin kept in doubles so far-away particles don't jitter
    private static final double[] oy = new double[MAX], oz = new double[MAX];
    private static int count;

    private ParticleEngine() {}

    public static int size() { return count; }

    public static void clear() { count = 0; }

    /**
     * Adds one particle. Returns false when the pool is full (the particle is dropped).
     * gravity is blocks/second squared (negative floats up), drag is the fraction of speed lost per second.
     */
    public static boolean spawn(int type, double px, double py, double pz, float velX, float velY, float velZ, float lifeSeconds,
                                float startSize, float endSize, int rgb, float a, float gravity, float dragPerSecond, float spinSpeed) {
        if (count >= MAX) return false;
        int i = count++;
        ox[i] = px; oy[i] = py; oz[i] = pz;
        x[i] = 0; y[i] = 0; z[i] = 0;
        vx[i] = velX; vy[i] = velY; vz[i] = velZ;
        age[i] = 0; life[i] = Math.max(0.05f, lifeSeconds);
        s0[i] = startSize; s1[i] = endSize; alpha[i] = a; grav[i] = gravity; drag[i] = dragPerSecond;
        rot[i] = (float) (Math.random() * Math.PI * 2); spin[i] = spinSpeed;
        color[i] = rgb; kind[i] = (byte) type;
        return true;
    }

    public static void update(float dt) {
        for (int i = 0; i < count; ) {
            age[i] += dt;
            if (age[i] >= life[i]) {                       // swap the last live particle into this slot
                int l = --count;
                if (i != l) copy(l, i);
                continue;
            }
            float d = (float) Math.exp(-drag[i] * dt);
            vx[i] *= d; vy[i] = (vy[i] - grav[i] * dt) * d; vz[i] *= d;
            x[i] += vx[i] * dt; y[i] += vy[i] * dt; z[i] += vz[i] * dt;
            rot[i] += spin[i] * dt;
            i++;
        }
    }

    private static void copy(int from, int to) {
        ox[to] = ox[from]; oy[to] = oy[from]; oz[to] = oz[from];
        x[to] = x[from]; y[to] = y[from]; z[to] = z[from];
        vx[to] = vx[from]; vy[to] = vy[from]; vz[to] = vz[from];
        age[to] = age[from]; life[to] = life[from]; s0[to] = s0[from]; s1[to] = s1[from];
        alpha[to] = alpha[from]; grav[to] = grav[from]; drag[to] = drag[from]; rot[to] = rot[from]; spin[to] = spin[from];
        color[to] = color[from]; kind[to] = kind[from];
    }

    /** Draws every live particle. Additive: overlapping glows get brighter, as they should. */
    public static void render(Frame f, float bloom, float bloomSize) {
        if (count == 0) return;
        for (int pass = 0; pass < 3; pass++) {
            VertexConsumer core = null, halo = null;
            for (int i = 0; i < count; i++) {
                if (kind[i] != pass) continue;
                float t = age[i] / life[i];
                float fadeIn = Easing.clamp01(t / 0.12f);
                float a = alpha[i] * fadeIn * (1f - Easing.inQuad(t));
                float size = Easing.lerp(s0[i], s1[i], Easing.outCubic(t));
                if (a < 0.004f || size <= 0f) continue;
                double wx = ox[i] + x[i], wy = oy[i] + y[i], wz = oz[i] + z[i];
                if (pass == STAR) {
                    if (core == null) core = f.add(Gfx.STAR);
                    f.sprite(core, wx, wy, wz, size, rot[i], color[i], a);
                } else {
                    if (core == null) core = f.add(Gfx.CORE);
                    f.sprite(core, wx, wy, wz, size, 0f, color[i], a);
                }
            }
            if (bloom > 0.01f && pass != DOT) {
                for (int i = 0; i < count; i++) {
                    if (kind[i] != pass) continue;
                    float t = age[i] / life[i];
                    float a = alpha[i] * Easing.clamp01(t / 0.12f) * (1f - Easing.inQuad(t)) * bloom * 0.45f;
                    float size = Easing.lerp(s0[i], s1[i], Easing.outCubic(t)) * 3.2f * bloomSize;
                    if (a < 0.004f || size <= 0f) continue;
                    if (halo == null) halo = f.add(Gfx.GLOW);
                    f.sprite(halo, ox[i] + x[i], oy[i] + y[i], oz[i] + z[i], size, 0f, color[i], a);
                }
            }
        }
    }

    /** A little burst of glowing sparks flying out from a point. */
    public static void burst(double px, double py, double pz, int n, float speed, float life, float size, int rgb, boolean stars) {
        for (int k = 0; k < n; k++) {
            double a = Math.random() * Math.PI * 2, e = Math.random() * 2 - 1, r = Math.sqrt(1 - e * e);
            float s = speed * (0.4f + (float) Math.random() * 0.6f);
            spawn(stars && k % 2 == 0 ? STAR : GLOW, px, py, pz, (float) (Math.cos(a) * r) * s, (float) e * s, (float) (Math.sin(a) * r) * s,
                    life * (0.6f + (float) Math.random() * 0.6f), size, size * 0.2f, Colors.lerp(rgb, 0xFFFFFF, (float) Math.random() * 0.35f), 1f, 1.5f, 2.2f, 4f);
        }
    }
}
