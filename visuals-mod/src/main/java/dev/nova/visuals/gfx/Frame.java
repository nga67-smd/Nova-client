package dev.nova.visuals.gfx;

import dev.nova.visuals.config.Settings;
import dev.nova.visuals.core.Colors;
import net.minecraft.client.network.ClientPlayerEntity;
import net.minecraft.client.render.RenderLayer;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.client.world.ClientWorld;
import net.minecraft.util.Identifier;
import net.minecraft.util.math.Vec3d;
import org.joml.Matrix4f;

import java.util.LinkedHashSet;
import java.util.Set;

/**
 * Everything an effect needs to draw one frame of the world: the camera, the matrices and a vertex provider.
 * Positions given to the drawing methods are world positions; they are shifted to the camera here.
 */
public final class Frame {
    public final ClientWorld world;
    public final ClientPlayerEntity player;
    public final Matrix4f m;
    public final Vec3d cam;
    public final float tickDelta, dt, time;
    /** Directions the camera's right, up and forward point to. */
    public final float rx, ry, rz, ux, uy, uz, fx, fy, fz;
    private final VertexConsumerProvider.Immediate imm;
    private final Set<RenderLayer> used = new LinkedHashSet<>();

    public Frame(ClientWorld world, ClientPlayerEntity player, Matrix4f m, Vec3d cam, float yaw, float pitch,
                 float tickDelta, float dt, float time, VertexConsumerProvider.Immediate imm) {
        this.world = world; this.player = player; this.m = m; this.cam = cam;
        this.tickDelta = tickDelta; this.dt = dt; this.time = time; this.imm = imm;
        float y = (float) Math.toRadians(yaw), p = (float) Math.toRadians(pitch);
        fx = -(float) Math.sin(y) * (float) Math.cos(p);
        fy = -(float) Math.sin(p);
        fz = (float) Math.cos(y) * (float) Math.cos(p);
        rx = -(float) Math.cos(y);
        ry = 0f;
        rz = -(float) Math.sin(y);
        ux = -rz * fy;
        uy = rz * fx - rx * fz;
        uz = rx * fy;
    }

    public VertexConsumer add(Identifier tex) {
        RenderLayer l = Gfx.additive(tex);
        used.add(l);
        return imm.getBuffer(l);
    }

    public VertexConsumer solid(Identifier tex) {
        RenderLayer l = Gfx.solid(tex);
        used.add(l);
        return imm.getBuffer(l);
    }

    /** Sends everything that was drawn to the screen. */
    public void flush() {
        imm.draw();
        used.clear();
    }

    public float rel(double world, double camera) { return (float) (world - camera); }

    /** A camera-facing sprite. Color is premultiplied by alpha here, as additive blending needs. */
    public void sprite(VertexConsumer b, double wx, double wy, double wz, float size, float rot, int rgb, float alpha) {
        float x = rel(wx, cam.x), y = rel(wy, cam.y), z = rel(wz, cam.z);
        float cs = (float) Math.cos(rot) * size, sn = (float) Math.sin(rot) * size;
        float ax = rx * cs + ux * sn, ay = ry * cs + uy * sn, az = rz * cs + uz * sn;      // rotated right
        float bx = -rx * sn + ux * cs, by = -ry * sn + uy * cs, bz = -rz * sn + uz * cs;   // rotated up
        float[] p = {x - ax - bx, y - ay - by, z - az - bz, x + ax - bx, y + ay - by, z + az - bz,
                x + ax + bx, y + ay + by, z + az + bz, x - ax + bx, y - ay + by, z - az + bz};
        float k = Math.max(0f, alpha);
        Gfx.quad(b, m, p, Colors.r(rgb) / 255f * k, Colors.g(rgb) / 255f * k, Colors.b(rgb) / 255f * k, 1f, 0f, 0f, 1f, 1f);
    }

    /**
     * A glowing point: a bright core, and (by the bloom settings) one to three wider soft halos.
     * This is the "bloom" every glowing effect shares.
     */
    public void bloom(double wx, double wy, double wz, float size, int rgb, float alpha) {
        float strength = Settings.bloom();
        sprite(add(Gfx.CORE), wx, wy, wz, size, 0f, rgb, alpha);
        if (strength <= 0.01f) return;
        VertexConsumer g = add(Gfx.GLOW);
        float s = Settings.bloomSize();
        int layers = Settings.glowLayers();
        for (int i = 0; i < layers; i++) {
            float scale = size * (2.6f + i * 2.4f) * s;
            float a = alpha * strength * (0.55f / (1f + i * 1.2f));
            sprite(g, wx, wy, wz, scale, 0f, rgb, a);
        }
    }

    /** A flat ribbon between two world points that always faces the camera. Used for trails and neon lines. */
    public void line(VertexConsumer b, double x0, double y0, double z0, double x1, double y1, double z1,
                     float w0, float w1, int rgb0, float a0, int rgb1, float a1) {
        float ax = rel(x0, cam.x), ay = rel(y0, cam.y), az = rel(z0, cam.z);
        float bx = rel(x1, cam.x), by = rel(y1, cam.y), bz = rel(z1, cam.z);
        float dx = bx - ax, dy = by - ay, dz = bz - az;
        // side = direction x view, so the ribbon is wide as seen from the camera
        float sx = dy * az - dz * ay, sy = dz * ax - dx * az, sz = dx * ay - dy * ax;
        float len = (float) Math.sqrt(sx * sx + sy * sy + sz * sz);
        if (len < 1e-6f) return;
        sx /= len; sy /= len; sz /= len;
        float[] p = {ax - sx * w0, ay - sy * w0, az - sz * w0, bx - sx * w1, by - sy * w1, bz - sz * w1,
                bx + sx * w1, by + sy * w1, bz + sz * w1, ax + sx * w0, ay + sy * w0, az + sz * w0};
        float[] col = {Colors.r(rgb0) / 255f * a0, Colors.g(rgb0) / 255f * a0, Colors.b(rgb0) / 255f * a0, 1f,
                Colors.r(rgb1) / 255f * a1, Colors.g(rgb1) / 255f * a1, Colors.b(rgb1) / 255f * a1, 1f,
                Colors.r(rgb1) / 255f * a1, Colors.g(rgb1) / 255f * a1, Colors.b(rgb1) / 255f * a1, 1f,
                Colors.r(rgb0) / 255f * a0, Colors.g(rgb0) / 255f * a0, Colors.b(rgb0) / 255f * a0, 1f};
        Gfx.gradQuad(b, m, p, col, 0f, 0f, 1f, 1f);
    }
}
