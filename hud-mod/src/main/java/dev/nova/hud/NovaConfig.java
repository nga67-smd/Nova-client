package dev.nova.hud;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.fabricmc.loader.api.FabricLoader;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** Settings, saved to config/nova-hud.json. */
public final class NovaConfig {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    private static NovaConfig instance;

    // Armor HUD
    public boolean armorHud = true;
    public boolean armorLeft = true;
    public boolean armorDurability = true;
    public float armorScale = 1.0f;

    // Scoreboard sidebar
    public boolean showSidebar = true;
    public float sidebarScale = 1.0f;
    public int sidebarOffsetY = 0;

    // Info lines
    public boolean showFps = false;
    public boolean showCoords = false;

    // Held-item view model
    public boolean viewModel = false;
    public float vmX = 0f, vmY = 0f, vmZ = 0f;
    public float vmScale = 1.0f;
    public float vmRotX = 0f, vmRotY = 0f, vmRotZ = 0f;

    public static NovaConfig get() {
        if (instance == null) instance = load();
        return instance;
    }

    private static Path file() {
        return FabricLoader.getInstance().getConfigDir().resolve("nova-hud.json");
    }

    private static NovaConfig load() {
        try {
            Path f = file();
            if (Files.exists(f)) {
                NovaConfig c = GSON.fromJson(Files.readString(f), NovaConfig.class);
                if (c != null) return c;
            }
        } catch (Exception ignored) {
            // A broken file just resets to defaults.
        }
        return new NovaConfig();
    }

    public void save() {
        try {
            Files.writeString(file(), GSON.toJson(this));
        } catch (IOException ignored) {
        }
    }

    public void resetViewModel() {
        vmX = vmY = vmZ = 0f;
        vmScale = 1f;
        vmRotX = vmRotY = vmRotZ = 0f;
    }
}
