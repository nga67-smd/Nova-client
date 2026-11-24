package dev.nova.visuals.config;

import dev.nova.visuals.gfx.Frame;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.DrawContext;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Owns every module and hands out the per-tick, per-frame and HUD callbacks. */
public final class ModuleManager {
    private static final Map<String, Module> MODULES = new LinkedHashMap<>();

    private ModuleManager() {}

    public static void register(Module m) {
        m.captureDefaults();
        MODULES.put(m.id, m);
    }

    public static List<Module> all() { return new ArrayList<>(MODULES.values()); }

    public static Module get(String id) { return MODULES.get(id); }

    public static List<Module> in(Category c) {
        List<Module> out = new ArrayList<>();
        for (Module m : MODULES.values()) if (m.category == c) out.add(m);
        return out;
    }

    public static void tick(MinecraftClient mc) {
        for (Module m : MODULES.values()) if (m.enabled()) m.onTick(mc);
    }

    public static void world(Frame f) {
        for (Module m : MODULES.values()) if (m.enabled()) m.onWorld(f);
    }

    public static void hud(DrawContext ctx, float dt) {
        for (Module m : MODULES.values()) if (m.enabled()) m.onHud(ctx, dt);
    }

    public static void resetAll() {
        for (Module m : MODULES.values()) m.resetToDefaults();
        Config.markDirty();
    }
}
