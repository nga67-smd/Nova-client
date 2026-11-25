package dev.nova.visuals.core;

/** Color helpers. Colors are 0xRRGGBB ints unless a method says otherwise. */
public final class Colors {
    private Colors() {}

    public static int r(int c) { return (c >> 16) & 255; }
    public static int g(int c) { return (c >> 8) & 255; }
    public static int b(int c) { return c & 255; }
    public static int rgb(int r, int g, int b) { return ((r & 255) << 16) | ((g & 255) << 8) | (b & 255); }
    public static int argb(int rgb, float alpha) { return ((int) (Easing.clamp01(alpha) * 255f) << 24) | (rgb & 0xFFFFFF); }
    public static int opaque(int rgb) { return 0xFF000000 | (rgb & 0xFFFFFF); }

    public static int lerp(int a, int b, float t) {
        t = Easing.clamp01(t);
        return rgb(Math.round(r(a) + (r(b) - r(a)) * t), Math.round(g(a) + (g(b) - g(a)) * t), Math.round(b(a) + (b(b) - b(a)) * t));
    }

    public static int hsv(float h, float s, float v) {
        h = h - (float) Math.floor(h);
        float c = v * s, x = c * (1f - Math.abs((h * 6f) % 2f - 1f)), m = v - c;
        float r, g, b;
        int sector = (int) (h * 6f);
        switch (sector) {
            case 0 -> { r = c; g = x; b = 0; }
            case 1 -> { r = x; g = c; b = 0; }
            case 2 -> { r = 0; g = c; b = x; }
            case 3 -> { r = 0; g = x; b = c; }
            case 4 -> { r = x; g = 0; b = c; }
            default -> { r = c; g = 0; b = x; }
        }
        return rgb(Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255));
    }

    /** Hue, saturation and value (each 0..1) of a color. */
    public static float[] toHsv(int c) {
        float r = r(c) / 255f, g = g(c) / 255f, b = b(c) / 255f;
        float max = Math.max(r, Math.max(g, b)), min = Math.min(r, Math.min(g, b)), d = max - min, h;
        if (d == 0) h = 0;
        else if (max == r) h = ((g - b) / d % 6f) / 6f;
        else if (max == g) h = ((b - r) / d + 2f) / 6f;
        else h = ((r - g) / d + 4f) / 6f;
        if (h < 0) h += 1f;
        return new float[]{h, max == 0 ? 0 : d / max, max};
    }

    public static int rainbow(float t) { return hsv(t, 0.75f, 1f); }

    /** Parses #RRGGBB (the # is optional). Returns -1 when it isn't a complete color. */
    public static int parseHex(String s) {
        if (s == null) return -1;
        String h = s.startsWith("#") ? s.substring(1) : s;
        if (h.length() != 6) return -1;
        try {
            return Integer.parseInt(h, 16);
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    public static String hex(int c) { return String.format("#%06X", c & 0xFFFFFF); }
}
