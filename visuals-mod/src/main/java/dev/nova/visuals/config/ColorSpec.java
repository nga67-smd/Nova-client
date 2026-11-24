package dev.nova.visuals.config;

import dev.nova.visuals.core.Colors;
import dev.nova.visuals.core.Time;

/** The "Color" choice most effects share: the accent, a rainbow, a gradient, a flame or your own color. */
public final class ColorSpec {
    public final Setting.Choice mode;
    public final Setting.Color custom;

    public ColorSpec(Module m, int defaultCustom, int defaultMode) {
        mode = m.add(new Setting.Choice("color_mode", "Color", defaultMode, "Accent", "Rainbow", "Gradient", "Ember", "Custom"));
        custom = m.add(new Setting.Color("color", "Custom color", defaultCustom));
        custom.showIf(() -> mode.index == 4);
    }

    /** phase 0..1 spreads colors along something (a trail, a ring); the time part animates it. */
    public int at(float phase) {
        float t = Time.time();
        return switch (mode.index) {
            case 0 -> Settings.accent();
            case 1 -> Colors.rainbow(phase * 0.5f + t * Settings.rgbSpeed());
            case 2 -> {
                float k = 0.5f + 0.5f * (float) Math.sin((phase * 2f + t * Settings.rgbSpeed() * 4f) * Math.PI);
                yield Colors.lerp(Settings.accent(), Settings.accent2(), k);
            }
            case 3 -> Colors.lerp(0xFF2A00, 0xFFC040, 0.5f + 0.5f * (float) Math.sin(phase * 5f + t * 2.3f));
            default -> custom.value;
        };
    }
}
