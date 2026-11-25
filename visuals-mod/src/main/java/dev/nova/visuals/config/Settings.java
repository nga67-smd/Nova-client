package dev.nova.visuals.config;

import dev.nova.visuals.core.Colors;
import dev.nova.visuals.core.Time;

/** Global options: quality, accent colors and the shared glow ("bloom") strength. Always on. */
public final class Settings extends Module {
    private static Settings instance;

    public final Setting.Choice quality = add(new Setting.Choice("quality", "Quality", 2, "Low", "Medium", "High", "Ultra"));
    public final Setting.Color accent = add(new Setting.Color("accent", "Accent color", 0xB66BFF));
    public final Setting.Color accent2 = add(new Setting.Color("accent2", "Second accent", 0x4DD7FF));
    public final Setting.Choice accentMode = add(new Setting.Choice("accent_mode", "Accent animation", 1, "Static", "Breathing", "Rainbow"));
    public final Setting.Num rgbSpeed = add(new Setting.Num("rgb_speed", "Color speed", 0.15f, 0.02f, 1.0f, 0.01f, "x"));
    public final Setting.Num bloom = add(new Setting.Num("bloom", "Bloom strength", 1.0f, 0f, 2.5f, 0.05f, "x"));
    public final Setting.Num bloomSize = add(new Setting.Num("bloom_size", "Bloom size", 1.0f, 0.5f, 2.5f, 0.05f, "x"));
    public final Setting.Bool others = add(new Setting.Bool("others", "Show cosmetics on other players (only you see it)", false));
    public final Setting.Bool menuBlur = add(new Setting.Bool("menu_blur", "Blur behind the menu", true));
    public final Setting.Num menuSpeed = add(new Setting.Num("menu_speed", "Menu animation speed", 1.0f, 0.4f, 2.5f, 0.05f, "x"));

    public Settings() {
        super("settings", "General", "Quality, colors and glow used by every effect.", Category.SETTINGS, true);
        instance = this;
    }

    public static Settings get() { return instance; }

    @Override public void setEnabled(boolean on) { /* always on */ }

    // ---- shared look
    public static int accent() {
        Settings s = instance;
        return switch (s.accentMode.index) {
            case 1 -> Colors.lerp(s.accent.value, s.accent2.value, 0.5f + 0.5f * (float) Math.sin(Time.time() * s.rgbSpeed.value * 3f));
            case 2 -> Colors.rainbow(Time.time() * s.rgbSpeed.value);
            default -> s.accent.value;
        };
    }

    public static int accent2() { return instance.accent2.value; }
    public static float rgbSpeed() { return instance.rgbSpeed.value; }
    public static float bloom() { return instance.bloom.value; }
    public static float bloomSize() { return instance.bloomSize.value; }
    public static boolean others() { return instance.others.value; }

    // ---- quality
    /** How many particles / segments compared with High. */
    public static float count() { return new float[]{0.35f, 0.65f, 1.0f, 1.6f}[instance.quality.index]; }
    public static int count(int n) { return Math.max(1, Math.round(n * count())); }
    /** Roundness of circles. */
    public static int segments() { return new int[]{20, 32, 48, 72}[instance.quality.index]; }
    /** Extra glow layers drawn per bright sprite. */
    public static int glowLayers() { return new int[]{1, 2, 2, 3}[instance.quality.index]; }
}
