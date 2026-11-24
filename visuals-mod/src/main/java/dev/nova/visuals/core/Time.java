package dev.nova.visuals.core;

/** Frame timing. Every animation multiplies by dt(), so speed is the same at 30 or 300 FPS. */
public final class Time {
    private static long last = System.nanoTime();
    private static float dt = 1f / 60f;
    private static float time;

    private Time() {}

    /** Call at the start of every render pass; calling it twice in the same frame is harmless. */
    public static void frame() {
        long now = System.nanoTime();
        if (now - last < 1_000_000L) return;
        dt = Math.min(0.1f, (now - last) / 1_000_000_000f);
        time += dt;
        last = now;
    }

    public static float dt() { return dt; }

    /** Seconds since start (wraps rarely; float precision is fine for animation). */
    public static float time() { return time; }
}
