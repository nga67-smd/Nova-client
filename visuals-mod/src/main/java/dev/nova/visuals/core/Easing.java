package dev.nova.visuals.core;

/** Easing functions. Input and output are 0..1 (outBack/outElastic overshoot a little). */
public final class Easing {
    private Easing() {}

    public static float clamp(float v, float lo, float hi) { return v < lo ? lo : Math.min(v, hi); }
    public static float clamp01(float v) { return clamp(v, 0f, 1f); }
    public static float lerp(float a, float b, float t) { return a + (b - a) * t; }
    public static float smoothstep(float t) { t = clamp01(t); return t * t * (3f - 2f * t); }

    public static float inQuad(float t) { return t * t; }
    public static float outQuad(float t) { return 1f - (1f - t) * (1f - t); }
    public static float inOutQuad(float t) { return t < 0.5f ? 2f * t * t : 1f - (float) Math.pow(-2f * t + 2f, 2) / 2f; }
    public static float outCubic(float t) { return 1f - (float) Math.pow(1f - t, 3); }
    public static float inOutCubic(float t) { return t < 0.5f ? 4f * t * t * t : 1f - (float) Math.pow(-2f * t + 2f, 3) / 2f; }
    public static float outExpo(float t) { return t >= 1f ? 1f : 1f - (float) Math.pow(2, -10f * t); }
    public static float outBack(float t) {
        float c1 = 1.70158f, c3 = c1 + 1f;
        return 1f + c3 * (float) Math.pow(t - 1f, 3) + c1 * (float) Math.pow(t - 1f, 2);
    }
    public static float outElastic(float t) {
        if (t <= 0f) return 0f;
        if (t >= 1f) return 1f;
        return (float) (Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * (2 * Math.PI / 3)) + 1);
    }
}
