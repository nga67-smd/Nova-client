package dev.nova.visuals.gui;

import dev.nova.visuals.core.Colors;
import dev.nova.visuals.core.Easing;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;

/** Small 2D drawing helpers on top of DrawContext: rounded rectangles, discs, shadows, glow, text. */
public final class Draw {
    private Draw() {}

    /** Multiplies the alpha of an ARGB color. */
    public static int fade(int argb, float k) {
        int a = (int) (((argb >>> 24) & 255) * Easing.clamp01(k));
        return (a << 24) | (argb & 0xFFFFFF);
    }

    public static int rgba(int rgb, float a) { return Colors.argb(rgb, a); }

    /** A filled rectangle with rounded corners (stair-stepped, which is how the pixel grid draws a curve). */
    public static void round(DrawContext c, float fx, float fy, float fw, float fh, float fr, int argb) {
        int x = Math.round(fx), y = Math.round(fy), w = Math.round(fw), h = Math.round(fh);
        if (w <= 0 || h <= 0 || ((argb >>> 24) & 255) == 0) return;
        int r = Math.max(0, Math.min((int) fr, Math.min(w, h) / 2));
        if (r == 0) { c.fill(x, y, x + w, y + h, argb); return; }
        c.fill(x, y + r, x + w, y + h - r, argb);
        for (int i = 0; i < r; i++) {
            double dy = r - i - 0.5;
            int inset = r - (int) Math.round(Math.sqrt(r * r - dy * dy));
            c.fill(x + inset, y + i, x + w - inset, y + i + 1, argb);
            c.fill(x + inset, y + h - 1 - i, x + w - inset, y + h - i, argb);
        }
    }

    private static int inset(int d, int r) {
        if (r <= 0 || d >= r) return 0;
        double dy = r - d - 0.5;
        return r - (int) Math.round(Math.sqrt(r * r - dy * dy));
    }

    /** The outline of a rounded rectangle, t pixels thick. */
    public static void outline(DrawContext c, float fx, float fy, float fw, float fh, float fr, float ft, int argb) {
        int x = Math.round(fx), y = Math.round(fy), w = Math.round(fw), h = Math.round(fh), t = Math.max(1, Math.round(ft));
        if (w <= 0 || h <= 0 || ((argb >>> 24) & 255) == 0) return;
        int r = Math.max(0, Math.min((int) fr, Math.min(w, h) / 2));
        int zone = Math.min(Math.max(r, t), h / 2);
        for (int d = 0; d < zone; d++) {
            int o = inset(d, r);
            int inn = d < t ? -1 : (r - t > 0 ? t + inset(d - t, r - t) : t);
            for (int side = 0; side < 2; side++) {
                int yy = side == 0 ? y + d : y + h - 1 - d;
                if (inn < 0) {
                    c.fill(x + o, yy, x + w - o, yy + 1, argb);
                } else {
                    int e = Math.max(inn, o + 1);
                    c.fill(x + o, yy, x + e, yy + 1, argb);
                    c.fill(x + w - e, yy, x + w - o, yy + 1, argb);
                }
            }
        }
        if (h - 2 * zone > 0) {
            c.fill(x, y + zone, x + t, y + h - zone, argb);
            c.fill(x + w - t, y + zone, x + w, y + h - zone, argb);
        }
    }

    /** A soft shadow: several expanding translucent layers under a rounded rectangle. */
    public static void shadow(DrawContext c, float x, float y, float w, float h, float r, int layers, float spread, float alpha) {
        for (int i = layers; i >= 1; i--) {
            float k = i / (float) layers, grow = spread * k;
            round(c, x - grow, y - grow + spread * 0.35f, w + grow * 2, h + grow * 2, r + grow, ((int) (alpha * 255 * (1f - k) * (1f - k) / layers * 2.2f) << 24));
        }
    }

    /** Same as a shadow but colored: the glowing edge around something. */
    public static void glow(DrawContext c, float x, float y, float w, float h, float r, int rgb, float alpha, int layers, float spread) {
        for (int i = layers; i >= 1; i--) {
            float k = i / (float) layers, grow = spread * k;
            int a = (int) Easing.clamp(alpha * 255f * (1f - k) * (1f - k) * 0.6f, 0, 255);
            round(c, x - grow, y - grow, w + grow * 2, h + grow * 2, r + grow, (a << 24) | (rgb & 0xFFFFFF));
        }
    }

    /** A filled circle. */
    public static void disc(DrawContext c, float fcx, float fcy, float fr, int argb) {
        int cx = Math.round(fcx), cy = Math.round(fcy), r = Math.round(fr);
        if (r <= 0) { c.fill(cx, cy, cx + 1, cy + 1, argb); return; }
        for (int i = -r; i <= r; i++) {
            int half = (int) Math.round(Math.sqrt(Math.max(0, r * r - i * i)));
            c.fill(cx - half, cy + i, cx + half + 1, cy + i + 1, argb);
        }
    }

    /** A soft glowing dot (layered discs). */
    public static void orb(DrawContext c, float cx, float cy, float r, int rgb, float alpha) {
        for (int i = 4; i >= 1; i--) {
            float k = i / 4f;
            disc(c, cx, cy, r * (0.4f + 1.8f * k), ((int) Easing.clamp(alpha * 255f * (1f - k) * 0.5f + 6f, 0, 255) << 24) | (rgb & 0xFFFFFF));
        }
        disc(c, cx, cy, r * 0.45f, ((int) (alpha * 255f) << 24) | 0xFFFFFF & Colors.lerp(rgb, 0xFFFFFF, 0.6f));
    }

    /** A circle outline drawn as small dots. */
    public static void ring(DrawContext c, float cx, float cy, float r, float thick, int argb) {
        int n = Math.max(16, (int) (r * 3));
        int t = Math.max(1, Math.round(thick));
        for (int i = 0; i < n; i++) {
            double a = i * Math.PI * 2 / n;
            int x = (int) Math.round(cx + Math.cos(a) * r), y = (int) Math.round(cy + Math.sin(a) * r);
            c.fill(x, y, x + t, y + t, argb);
        }
    }

    /** A horizontal gradient bar between two RGB colors with a moving shimmer. */
    public static void gradientBar(DrawContext c, int x, int y, int w, int h, int rgbA, int rgbB, float shift) {
        int step = 2;
        for (int i = 0; i < w; i += step) {
            float k = (float) i / Math.max(1, w);
            float m = 0.5f + 0.5f * (float) Math.sin((k * 2f + shift) * Math.PI);
            c.fill(x + i, y, Math.min(x + w, x + i + step), y + h, 0xFF000000 | Colors.lerp(rgbA, rgbB, m));
        }
    }

    public static void text(DrawContext c, TextRenderer tr, String s, float x, float y, int argb, boolean shadow) {
        if (((argb >>> 24) & 255) < 4) return;
        c.drawText(tr, s, Math.round(x), Math.round(y), argb, shadow);
    }

    public static void textCentered(DrawContext c, TextRenderer tr, String s, float cx, float y, int argb, boolean shadow) {
        text(c, tr, s, cx - tr.getWidth(s) / 2f, y, argb, shadow);
    }

    public static boolean in(double mx, double my, float x, float y, float w, float h) {
        return mx >= x && mx < x + w && my >= y && my < y + h;
    }
}
