package dev.nova.visuals.gfx;

import net.minecraft.client.render.LightmapTextureManager;
import net.minecraft.client.render.OverlayTexture;
import net.minecraft.client.render.RenderLayer;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.util.Identifier;
import org.joml.Matrix4f;

/** Textures and low-level vertex helpers. All world effects are built from these. */
public final class Gfx {
    private Gfx() {}

    private static Identifier tex(String n) { return Identifier.of("nova_visuals", "textures/effect/" + n + ".png"); }

    /** Soft round glow, a tight bright dot, a four-point sparkle, a thin ring, a ribbon edge and plain white. */
    public static final Identifier GLOW = tex("glow"), CORE = tex("core"), STAR = tex("star"), RING = tex("ring"),
            LINE = tex("line"), WHITE = tex("white");

    /** Light adds to what is behind it (glows). Colors must be multiplied by their alpha first. */
    public static RenderLayer additive(Identifier t) { return RenderLayer.getEyes(t); }

    /** Normal see-through blending (solid-looking shapes such as wing membranes). */
    public static RenderLayer solid(Identifier t) { return RenderLayer.getEntityTranslucentEmissive(t); }

    public static void vert(VertexConsumer b, Matrix4f m, float x, float y, float z, float u, float v, float r, float g, float bl, float a) {
        b.vertex(m, x, y, z)
                .color(c(r), c(g), c(bl), c(a))
                .texture(u, v)
                .overlay(OverlayTexture.DEFAULT_UV)
                .light(LightmapTextureManager.MAX_LIGHT_COORDINATE)
                .normal(0f, 1f, 0f);
    }

    private static int c(float v) { return v <= 0f ? 0 : v >= 1f ? 255 : (int) (v * 255f); }

    /** A flat four-cornered shape, drawn from both sides so it never disappears when seen from behind. */
    public static void quad(VertexConsumer b, Matrix4f m, float[] p, float r, float g, float bl, float a,
                            float u0, float v0, float u1, float v1) {
        vert(b, m, p[0], p[1], p[2], u0, v1, r, g, bl, a);
        vert(b, m, p[3], p[4], p[5], u1, v1, r, g, bl, a);
        vert(b, m, p[6], p[7], p[8], u1, v0, r, g, bl, a);
        vert(b, m, p[9], p[10], p[11], u0, v0, r, g, bl, a);
        vert(b, m, p[9], p[10], p[11], u0, v0, r, g, bl, a);
        vert(b, m, p[6], p[7], p[8], u1, v0, r, g, bl, a);
        vert(b, m, p[3], p[4], p[5], u1, v1, r, g, bl, a);
        vert(b, m, p[0], p[1], p[2], u0, v1, r, g, bl, a);
    }

    /** A triangle (a quad with a repeated corner), both sides. */
    public static void tri(VertexConsumer b, Matrix4f m, float ax, float ay, float az, float bx, float by, float bz,
                           float cx, float cy, float cz, float r, float g, float bl, float a) {
        float[] p = {ax, ay, az, bx, by, bz, cx, cy, cz, cx, cy, cz};
        quad(b, m, p, r, g, bl, a, 0.5f, 0.5f, 0.5f, 0.5f);
    }

    /** Per-corner colors, for gradients across a strip (used by the aurora and ribbons). */
    public static void gradQuad(VertexConsumer b, Matrix4f m, float[] p, float[] col, float u0, float v0, float u1, float v1) {
        // col = 4 corners x (r,g,b,a) in the same order as p
        vert(b, m, p[0], p[1], p[2], u0, v1, col[0], col[1], col[2], col[3]);
        vert(b, m, p[3], p[4], p[5], u1, v1, col[4], col[5], col[6], col[7]);
        vert(b, m, p[6], p[7], p[8], u1, v0, col[8], col[9], col[10], col[11]);
        vert(b, m, p[9], p[10], p[11], u0, v0, col[12], col[13], col[14], col[15]);
        vert(b, m, p[9], p[10], p[11], u0, v0, col[12], col[13], col[14], col[15]);
        vert(b, m, p[6], p[7], p[8], u1, v0, col[8], col[9], col[10], col[11]);
        vert(b, m, p[3], p[4], p[5], u1, v1, col[4], col[5], col[6], col[7]);
        vert(b, m, p[0], p[1], p[2], u0, v1, col[0], col[1], col[2], col[3]);
    }
}
