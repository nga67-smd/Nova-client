package dev.nova.visuals.config;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.fabricmc.loader.api.FabricLoader;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

/** Saves and loads settings as JSON, plus presets, import and export. */
public final class Config {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static boolean dirty;
    private static long lastSave;
    /** Things that aren't modules (the HUD layout) keep their JSON here. */
    private static JsonObject extras = new JsonObject();

    private Config() {}

    private static Path dir() { return FabricLoader.getInstance().getConfigDir(); }
    private static Path file() { return dir().resolve("nova-visuals.json"); }
    private static Path presetDir() { return dir().resolve("nova-visuals-presets"); }

    public static void markDirty() { dirty = true; }

    public static JsonObject extra(String key) {
        if (!extras.has(key) || !extras.get(key).isJsonObject()) extras.add(key, new JsonObject());
        return extras.getAsJsonObject(key);
    }

    /** Called often; writes the file at most every few seconds and only when something changed. */
    public static void autosave() {
        long now = System.currentTimeMillis();
        if (dirty && now - lastSave > 3000) saveNow();
    }

    public static void saveNow() {
        dirty = false;
        lastSave = System.currentTimeMillis();
        try {
            Files.createDirectories(dir());
            Files.writeString(file(), GSON.toJson(snapshot()));
        } catch (IOException ignored) {
            // a read-only config folder just means settings aren't kept
        }
    }

    public static void load() {
        try {
            if (Files.exists(file())) apply(JsonParser.parseString(Files.readString(file())).getAsJsonObject(), false);
        } catch (Exception ignored) {
            // a broken file means defaults
        }
    }

    // ---- JSON of everything
    public static JsonObject snapshot() {
        JsonObject root = new JsonObject();
        root.addProperty("format", 1);
        JsonObject mods = new JsonObject();
        for (Module m : ModuleManager.all()) mods.add(m.id, m.save());
        root.add("modules", mods);
        root.add("extras", extras);
        return root;
    }

    /** reset: start from factory settings first, so a preset only has to name what it changes. */
    public static void apply(JsonObject root, boolean reset) {
        if (reset) for (Module m : ModuleManager.all()) m.resetToDefaults();
        if (root.has("modules") && root.get("modules").isJsonObject()) {
            JsonObject mods = root.getAsJsonObject("modules");
            for (Module m : ModuleManager.all()) {
                if (mods.has(m.id) && mods.get(m.id).isJsonObject()) m.load(mods.getAsJsonObject(m.id));
            }
        }
        if (root.has("extras") && root.get("extras").isJsonObject()) extras = root.getAsJsonObject("extras");
        markDirty();
    }

    // ---- import / export (the clipboard)
    public static String export() { return GSON.toJson(snapshot()); }

    /** Returns null when it worked, otherwise a short reason. */
    public static String importFrom(String text) {
        try {
            JsonObject o = JsonParser.parseString(text == null ? "" : text.trim()).getAsJsonObject();
            if (!o.has("modules")) return "That isn't a Nova Visuals config.";
            apply(o, true);
            return null;
        } catch (RuntimeException e) {
            return "That isn't a Nova Visuals config.";
        }
    }

    // ---- presets
    public static List<String> userPresets() {
        List<String> out = new ArrayList<>();
        try (Stream<Path> s = Files.isDirectory(presetDir()) ? Files.list(presetDir()) : Stream.empty()) {
            s.filter(p -> p.getFileName().toString().endsWith(".json")).forEach(p -> {
                String n = p.getFileName().toString();
                out.add(n.substring(0, n.length() - 5));
            });
        } catch (IOException ignored) {
            // no presets
        }
        java.util.Collections.sort(out, String.CASE_INSENSITIVE_ORDER);
        return out;
    }

    private static String safe(String name) {
        String n = name == null ? "" : name.replaceAll("[^\\p{L}\\p{N} _-]", "").trim();
        return n.length() > 32 ? n.substring(0, 32) : n;
    }

    public static boolean savePreset(String name) {
        String n = safe(name);
        if (n.isEmpty()) return false;
        try {
            Files.createDirectories(presetDir());
            Files.writeString(presetDir().resolve(n + ".json"), GSON.toJson(snapshot()));
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    public static boolean loadPreset(String name) {
        try {
            Path p = presetDir().resolve(safe(name) + ".json");
            if (!Files.exists(p)) return false;
            apply(JsonParser.parseString(Files.readString(p)).getAsJsonObject(), true);
            return true;
        } catch (IOException | RuntimeException e) {
            return false;
        }
    }

    public static boolean deletePreset(String name) {
        try {
            return Files.deleteIfExists(presetDir().resolve(safe(name) + ".json"));
        } catch (IOException e) {
            return false;
        }
    }
}
