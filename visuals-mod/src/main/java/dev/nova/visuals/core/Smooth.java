package dev.nova.visuals.core;

import java.util.HashMap;
import java.util.Map;

/** A number that glides toward a target. The glide uses dt, so it looks the same at any frame rate. */
public final class Smooth {
    private float value, target;
    private float speed;

    public Smooth(float start, float speed) { this.value = start; this.target = start; this.speed = speed; }

    public void set(float t) { target = t; }
    public void snap(float v) { value = v; target = v; }
    public float target() { return target; }
    public float get() { return value; }

    public float update(float dt) {
        value += (target - value) * (1f - (float) Math.exp(-speed * dt));
        if (Math.abs(target - value) < 0.0005f) value = target;
        return value;
    }

    /** Animations keyed by name, for interface elements that come and go. */
    public static final class Pool {
        private final Map<Object, Smooth> map = new HashMap<>();
        private final float speed;

        public Pool(float speed) { this.speed = speed; }

        public float to(Object key, float target, float dt) {
            Smooth s = map.computeIfAbsent(key, k -> new Smooth(target, speed));
            s.set(target);
            return s.update(dt);
        }

        public float to(Object key, float target, float dt, float startAt) {
            Smooth s = map.computeIfAbsent(key, k -> new Smooth(startAt, speed));
            s.set(target);
            return s.update(dt);
        }
    }
}
