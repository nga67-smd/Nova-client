package dev.nova.visuals.fx;

import dev.nova.visuals.config.Settings;
import dev.nova.visuals.core.Colors;
import dev.nova.visuals.core.Easing;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import net.minecraft.client.render.VertexConsumer;

/** Expanding circles: flat on the ground (jump and landing) or facing the camera (hit impacts). */
public final class RingPool {
    private static final int MAX = 96;
    private static final double[] x = new double[MAX], y = new double[MAX], z = new double[MAX];
    private static final float[] age = new float[MAX], life = new float[MAX], radius = new float[MAX], width = new float[MAX], alpha = new float[MAX];
    private static final float[] delay = new float[MAX];
    private static final int[] color = new int[MAX];
    private static final boolean[] flat = new boolean[MAX];
    private static int count;

    private RingPool() {}

    public static void clear() { count = 0; }

    public static void spawn(boolean onGround, double px, double py, double pz, float maxRadius, float lifeSeconds,
                             float halfWidth, int rgb, float a, float delaySeconds) {
        if (count >= MAX) {                                  // the oldest ring makes room
            System.arraycopy(x, 1, x, 0, MAX - 1); System.arraycopy(y, 1, y, 0, MAX - 1); System.arraycopy(z, 1, z, 0, MAX - 1);
            System.arraycopy(age, 1, age, 0, MAX - 1); System.arraycopy(life, 1, life, 0, MAX - 1);
            System.arraycopy(radius, 1, radius, 0, MAX - 1); System.arraycopy(width, 1, width, 0, MAX - 1);
            System.arraycopy(alpha, 1, alpha, 0, MAX - 1); System.arraycopy(delay, 1, delay, 0, MAX - 1);
            System.arraycopy(color, 1, color, 0, MAX - 1); System.arraycopy(flat, 1, flat, 0, MAX - 1);
            count = MAX - 1;
        }
        int i = count++;
        x[i] = px; y[i] = py; z[i] = pz;
        age[i] = 0; life[i] = lifeSeconds; radius[i] = maxRadius; width[i] = halfWidth; alpha[i] = a;
        delay[i] = delaySeconds; color[i] = rgb; flat[i] = onGround;
    }

    public static void update(float dt) {
        for (int i = 0; i < count; ) {
            if (delay[i] > 0) {
                delay[i] -= dt;
            } else {
                age[i] += dt;
            }
            if (age[i] >= life[i]) {
                int l = --count;
                if (i != l) {
                    x[i] = x[l]; y[i] = y[l]; z[i] = z[l]; age[i] = age[l]; life[i] = life[l]; radius[i] = radius[l];
                    width[i] = width[l]; alpha[i] = alpha[l]; delay[i] = delay[l]; color[i] = color[l]; flat[i] = flat[l];
                }
                continue;
            }
            i++;
        }
    }

    public static void render(Frame f) {
        if (count == 0) return;
        VertexConsumer b = f.add(Gfx.LINE);
        int seg = Settings.segments();
        for (int i = 0; i < count; i++) {
            if (delay[i] > 0) continue;
            float t = age[i] / life[i];
            float r = radius[i] * Easing.outCubic(t);
            float a = alpha[i] * (1f - Easing.inQuad(t)) * Easing.clamp01(t / 0.05f);
            float w = width[i] * (1f + t * 0.6f);
            drawRing(f, b, x[i], y[i], z[i], flat[i], r, w, color[i], a, seg);
        }
    }

    /** One ring: flat ones lie on the ground, the others turn to face the camera. */
    public static void drawRing(Frame f, VertexConsumer b, double cx, double cy, double cz, boolean flatRing,
                                float r, float halfWidth, int rgb, float a, int seg) {
        if (a < 0.003f || r <= 0.001f) return;
        float ux, uy, uz, vx, vy, vz;
        if (flatRing) { ux = 1; uy = 0; uz = 0; vx = 0; vy = 0; vz = 1; }
        else { ux = f.rx; uy = f.ry; uz = f.rz; vx = f.ux; vy = f.uy; vz = f.uz; }
        float x0 = (float) (cx - f.cam.x), y0 = (float) (cy - f.cam.y), z0 = (float) (cz - f.cam.z);
        float pr = Colors.r(rgb) / 255f * a, pg = Colors.g(rgb) / 255f * a, pb = Colors.b(rgb) / 255f * a;
        float[] col = {pr, pg, pb, 1f, pr, pg, pb, 1f, pr, pg, pb, 1f, pr, pg, pb, 1f};
        float[] p = new float[12];
        float ri = Math.max(0f, r - halfWidth), ro = r + halfWidth;
        for (int s = 0; s < seg; s++) {
            double a0 = s * 2 * Math.PI / seg, a1 = (s + 1) * 2 * Math.PI / seg;
            float c0 = (float) Math.cos(a0), s0 = (float) Math.sin(a0), c1 = (float) Math.cos(a1), s1 = (float) Math.sin(a1);
            put(p, 0, x0, y0, z0, ux, uy, uz, vx, vy, vz, c0 * ri, s0 * ri);
            put(p, 3, x0, y0, z0, ux, uy, uz, vx, vy, vz, c1 * ri, s1 * ri);
            put(p, 6, x0, y0, z0, ux, uy, uz, vx, vy, vz, c1 * ro, s1 * ro);
            put(p, 9, x0, y0, z0, ux, uy, uz, vx, vy, vz, c0 * ro, s0 * ro);
            Gfx.gradQuad(b, f.m, p, col, 0f, 0f, 1f, 1f);
        }
    }

    private static void put(float[] p, int o, float x0, float y0, float z0, float ux, float uy, float uz,
                            float vx, float vy, float vz, float a, float b) {
        p[o] = x0 + ux * a + vx * b;
        p[o + 1] = y0 + uy * a + vy * b;
        p[o + 2] = z0 + uz * a + vz * b;
    }
}
