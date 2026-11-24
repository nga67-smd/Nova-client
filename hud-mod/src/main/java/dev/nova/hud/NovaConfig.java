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

    // Info rows (shown together in one panel)
    public boolean showFps = true;
    public boolean showCoords = true;
    public boolean showPing = true;
    public boolean showCps = true;
    public boolean showDirection = false;
    public boolean showBiome = false;
    public boolean showSpeed = false;
    public boolean showClock = false;
    public boolean showMcTime = false;
    public boolean showMemory = false;
    public boolean showCombo = false;
    public boolean showReach = false;

    // Other panels
    public boolean keystrokes = true;
    public boolean potions = true;
    public boolean itemCounts = false;

    // Where each panel sits: 0 top left, 1 top right, 2 bottom left, 3 bottom right, 4 middle left, 5 middle right, 6 top centre, 7 bottom centre
    public int anchorInfo = 0, anchorKeys = 2, anchorPotions = 1, anchorItems = 5;
    public int marginX = 4, marginY = 4;

    // Look (Nova theme by default). Colors are 0xRRGGBB.
    public int accent = 0xB66BFF;
    public int background = 0x151024;
    public int textColor = 0xF0EAFF;
    public int labelColor = 0xA99BC8;
    public float bgOpacity = 0.66f;
    public float hudScale = 1.0f;
    public int radius = 3;
    public int border = 1;
    public int padding = 4;
    public int minWidth = 0;
    public boolean shadow = true;
    public boolean accentBar = true;

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
                if (c != null) {
                    c.clamp();
                    return c;
                }
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

    /** Keeps hand-edited values in a range that draws properly. */
    public void clamp() {
        bgOpacity = Math.max(0f, Math.min(1f, bgOpacity));
        hudScale = Math.max(0.5f, Math.min(2.5f, hudScale));
        radius = Math.max(0, Math.min(8, radius));
        border = Math.max(0, Math.min(4, border));
        padding = Math.max(1, Math.min(12, padding));
        minWidth = Math.max(0, Math.min(300, minWidth));
        marginX = Math.max(0, Math.min(200, marginX));
        marginY = Math.max(0, Math.min(200, marginY));
        anchorInfo = Math.floorMod(anchorInfo, 8);
        anchorKeys = Math.floorMod(anchorKeys, 8);
        anchorPotions = Math.floorMod(anchorPotions, 8);
        anchorItems = Math.floorMod(anchorItems, 8);
    }

    /** Ready-made color sets. */
    public void applyPreset(String name) {
        switch (name) {
            case "ice" -> { accent = 0x6FD3FF; background = 0x0C1824; textColor = 0xEAF8FF; labelColor = 0x8FB4C8; }
            case "sunset" -> { accent = 0xFF8A5C; background = 0x241012; textColor = 0xFFEFE6; labelColor = 0xCFA08C; }
            case "mint" -> { accent = 0x5CFFB0; background = 0x0C2018; textColor = 0xEAFFF4; labelColor = 0x8CC8AE; }
            case "mono" -> { accent = 0xFFFFFF; background = 0x101010; textColor = 0xFFFFFF; labelColor = 0xA0A0A0; }
            default -> { accent = 0xB66BFF; background = 0x151024; textColor = 0xF0EAFF; labelColor = 0xA99BC8; }
        }
    }

    public void resetViewModel() {
        vmX = vmY = vmZ = 0f;
        vmScale = 1f;
        vmRotX = vmRotY = vmRotZ = 0f;
    }
}
