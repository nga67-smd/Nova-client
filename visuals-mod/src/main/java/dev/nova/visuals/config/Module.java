package dev.nova.visuals.config;

import com.google.gson.JsonObject;
import dev.nova.visuals.core.Smooth;
import dev.nova.visuals.gfx.Frame;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.DrawContext;

import java.util.ArrayList;
import java.util.List;

/** A feature that can be switched on and off and has its own settings. */
public abstract class Module {
    public final String id, name, description;
    public final Category category;
    public final List<Setting> settings = new ArrayList<>();
    private boolean enabled;
    /** 0..1, animates the toggle switch in the menu. */
    public final Smooth switchAnim = new Smooth(0f, 14f);
    public final Smooth openAnim = new Smooth(0f, 12f);
    public boolean expanded;

    protected Module(String id, String name, String description, Category category, boolean defaultOn) {
        this.id = id; this.name = name; this.description = description; this.category = category;
        this.enabled = defaultOn;
        switchAnim.snap(defaultOn ? 1f : 0f);
    }

    protected <S extends Setting> S add(S s) { settings.add(s); return s; }

    public boolean enabled() { return enabled; }

    public void setEnabled(boolean on) {
        if (on == enabled) return;
        enabled = on;
        switchAnim.set(on ? 1f : 0f);
        if (on) onEnable(); else onDisable();
        Config.markDirty();
    }

    public void toggle() { setEnabled(!enabled); }

    /** Runs once per game tick while enabled. */
    public void onTick(MinecraftClient mc) {}
    /** Runs every frame while enabled, inside the world render. */
    public void onWorld(Frame f) {}
    /** Runs every frame while enabled, on the HUD layer. */
    public void onHud(DrawContext ctx, float dt) {}
    public void onEnable() {}
    public void onDisable() {}

    public JsonObject save() {
        JsonObject o = new JsonObject();
        o.addProperty("enabled", enabled);
        JsonObject s = new JsonObject();
        for (Setting x : settings) s.add(x.id, x.save());
        o.add("settings", s);
        return o;
    }

    public void load(JsonObject o) {
        if (o.has("enabled") && o.get("enabled").isJsonPrimitive()) {
            boolean on = o.get("enabled").getAsBoolean();
            if (on != enabled) {
                enabled = on;
                switchAnim.set(on ? 1f : 0f);
                if (on) onEnable(); else onDisable();
            }
        }
        if (o.has("settings") && o.get("settings").isJsonObject()) {
            JsonObject s = o.getAsJsonObject("settings");
            for (Setting x : settings) if (s.has(x.id)) {
                try {
                    x.load(s.get(x.id));
                } catch (RuntimeException ignored) {
                    // a bad value in a hand-edited file keeps the default
                }
            }
        }
    }

    private JsonObject defaults;

    /** Remembers the current values as "factory settings". */
    public void captureDefaults() { defaults = save(); }

    public void resetToDefaults() { if (defaults != null) load(defaults); }

    public boolean matches(String query) {
        if (query == null || query.isBlank()) return true;
        String q = query.toLowerCase();
        return name.toLowerCase().contains(q) || description.toLowerCase().contains(q) || category.label.toLowerCase().contains(q);
    }
}
