package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.core.Easing;
import net.minecraft.client.MinecraftClient;

/** Client-side weather: rain and thunder strength that only you see. */
public final class WeatherModule extends Module {
    private final Setting.Choice mode = add(new Setting.Choice("mode", "Weather", 1, "Clear", "Rain", "Thunderstorm"));
    private final Setting.Num strength = add(new Setting.Num("strength", "Strength", 0.7f, 0.1f, 1f, 0.05f, ""));
    private float rain, thunder;

    public WeatherModule() {
        super("weather", "Client Weather", "Force clear skies, rain or a thunderstorm on your screen only.", Category.ENVIRONMENT, false);
    }

    @Override
    public void onTick(MinecraftClient mc) {
        if (mc.world == null) return;
        float rt = mode.index == 0 ? 0f : strength.value, tt = mode.index == 2 ? strength.value : 0f;
        rain += (rt - rain) * 0.04f;                                           // glide towards the target, 20 times a second
        thunder += (tt - thunder) * 0.04f;
        mc.world.setRainGradient(Easing.clamp01(rain));
        mc.world.setThunderGradient(Easing.clamp01(thunder));
    }
}
