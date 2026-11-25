package dev.nova.visuals.config;

import com.google.gson.JsonObject;

/** Ready-made looks. Each one starts from factory settings and only names what it changes. */
public final class Presets {
    public static final String[] NAMES = {"Gothic", "Aurora Night", "Neon", "Minimal", "Cinematic"};

    private Presets() {}

    public static void apply(String name) {
        Config.apply(build(name), true);
    }

    private static final class B {
        final JsonObject modules = new JsonObject();

        B on(String id, Object... kv) { return put(id, true, kv); }
        B off(String id) { return put(id, false); }

        B put(String id, boolean enabled, Object... kv) {
            JsonObject m = new JsonObject(), s = new JsonObject();
            for (int i = 0; i + 1 < kv.length; i += 2) {
                String k = (String) kv[i];
                Object v = kv[i + 1];
                if (v instanceof Number n) s.addProperty(k, n);
                else if (v instanceof Boolean b) s.addProperty(k, b);
                else s.addProperty(k, String.valueOf(v));
            }
            m.addProperty("enabled", enabled);
            m.add("settings", s);
            modules.add(id, m);
            return this;
        }

        JsonObject done() {
            JsonObject root = new JsonObject();
            root.addProperty("format", 1);
            root.add("modules", modules);
            return root;
        }
    }

    private static JsonObject build(String name) {
        B b = new B();
        switch (name) {
            case "Gothic" -> b
                    .put("settings", true, "accent", "#C01030", "accent2", "#7A1FA2", "accent_mode", "Breathing", "bloom", 1.2f)
                    .on("trail", "color_mode", "Ember")
                    .on("wings", "style", "Devil", "size", 1.1f)
                    .on("horns", "style", "Devil")
                    .on("circle", "radius", 1.7f)
                    .on("bats", "count", 5)
                    .on("aura", "style", "Infernal embers")
                    .on("skybox", "style", "Gothic mist")
                    .on("sunmoon", "blood", true)
                    .on("starfield")
                    .on("time", "mode", "Always night")
                    .on("weather", "mode", "Thunderstorm", "strength", 0.5f)
                    .on("precip")
                    .on("atmosphere", "style", "Embers")
                    .on("overlay", "grade", "Blood", "tint_amount", 0.1f, "vignette", 0.6f, "vignette_color", "#2A0008");
            case "Aurora Night" -> b
                    .put("settings", true, "accent", "#3DFF9B", "accent2", "#8A5CFF", "accent_mode", "Breathing")
                    .on("aurora", "palette", "Classic green", "intensity", 1.1f)
                    .on("starfield", "density", 1.4f)
                    .on("sunmoon")
                    .on("skybox", "style", "Nebula")
                    .on("time", "mode", "Always night")
                    .on("atmosphere", "style", "Fireflies")
                    .on("overlay", "grade", "Cold", "tint_amount", 0.08f);
            case "Neon" -> b
                    .put("settings", true, "accent_mode", "Rainbow", "bloom", 1.6f, "bloom_size", 1.3f)
                    .on("trail", "color_mode", "Rainbow", "width", 0.18f)
                    .on("rings", "color_mode", "Rainbow")
                    .on("hit_fx", "color_mode", "Rainbow")
                    .on("stars", "color_mode", "Rainbow")
                    .on("halo", "style", "Runes", "color_mode", "Rainbow")
                    .on("atmosphere", "style", "Sparkles")
                    .on("skybox", "style", "Rainbow");
            case "Minimal" -> b
                    .off("trail").off("rings").off("hit_fx").off("stars");
            case "Cinematic" -> b
                    .put("settings", true, "bloom", 0.8f)
                    .on("cine_bars")
                    .on("skybox", "style", "Twilight")
                    .on("sunmoon", "glow", 1.4f)
                    .on("time", "mode", "Fixed time", "time", 12700)
                    .on("overlay", "grade", "Dusk", "tint_amount", 0.1f, "vignette", 0.5f)
                    .off("rings").off("hit_fx").off("stars");
            default -> { }
        }
        return b.done();
    }
}
