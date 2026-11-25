package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import net.minecraft.client.MinecraftClient;

/** Client-side time of day: only you see it, the server is not told. */
public final class TimeModule extends Module {
    private final Setting.Choice mode = add(new Setting.Choice("mode", "Mode", 1, "Fixed time", "Always night", "Always day", "Fast cycle"));
    private final Setting.Num time = add(new Setting.Num("time", "Time", 13000f, 0f, 24000f, 100f, ""));
    private final Setting.Num cycle = add(new Setting.Num("cycle", "Cycle speed", 10f, 1f, 60f, 1f, "x"));
    private double clock = 6000;

    public TimeModule() {
        super("time", "Client Time", "Pick the time of day for yourself without touching the server.", Category.ENVIRONMENT, false);
        time.showIf(() -> mode.index == 0);
        cycle.showIf(() -> mode.index == 3);
    }

    @Override
    public void onTick(MinecraftClient mc) {
        if (mc.world == null) return;
        long t;
        switch (mode.index) {
            case 1 -> t = 18000;
            case 2 -> t = 6000;
            case 3 -> { clock = (clock + cycle.value) % 24000; t = (long) clock; }
            default -> t = (long) time.value;
        }
        mc.world.getLevelProperties().setTimeOfDay(t);
    }
}
