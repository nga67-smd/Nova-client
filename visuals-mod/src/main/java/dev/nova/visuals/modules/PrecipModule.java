package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.MathHelper;
import net.minecraft.world.Heightmap;
import net.minecraft.world.biome.Biome;

import java.util.Random;

/** Soft glowing rain streaks and drifting snowflakes around you, only where the sky is open. */
public final class PrecipModule extends Module {
    private static final int MAX = 1400;
    private static final float R = 18f, H = 26f;
    private final float[] ox = new float[MAX], oz = new float[MAX], oy = new float[MAX], sp = new float[MAX];

    private final Setting.Choice mode = add(new Setting.Choice("mode", "Mode", 0, "Automatic", "Always rain", "Always snow"));
    private final Setting.Num amount = add(new Setting.Num("amount", "Amount", 1.0f, 0.2f, 2f, 0.05f, "x"));
    private final Setting.Num size = add(new Setting.Num("size", "Size", 1.0f, 0.4f, 2.5f, 0.05f, "x"));
    private final Setting.Num wind = add(new Setting.Num("wind", "Wind", 0.25f, -1f, 1f, 0.05f, ""));
    private final Setting.Color rainColor = add(new Setting.Color("rain_color", "Rain color", 0x9CC4FF));
    private final Setting.Color snowColor = add(new Setting.Color("snow_color", "Snow color", 0xFFFFFF));
    private final Setting.Bool needStorm = add(new Setting.Bool("only_weather", "Only while it is raining", true));

    public PrecipModule() {
        super("precip", "Rain & Snow", "Nicer rain streaks and snowflakes.", Category.ENVIRONMENT, false);
        Random r = new Random(4242L);
        for (int i = 0; i < MAX; i++) { ox[i] = r.nextFloat(); oz[i] = r.nextFloat(); oy[i] = r.nextFloat(); sp[i] = 0.7f + r.nextFloat() * 0.6f; }
    }

    private static float wrap(float v, float c, float range) {
        float k = (v - c + range / 2f) % range;
        if (k < 0) k += range;
        return c - range / 2f + k;
    }

    @Override
    public void onWorld(Frame f) {
        float gradient = f.world.getRainGradient(f.tickDelta);
        float strength = needStorm.value ? gradient : 1f;
        if (strength < 0.02f) return;
        boolean snow;
        if (mode.index == 1) snow = false;
        else if (mode.index == 2) snow = true;
        else {
            BlockPos cp = BlockPos.ofFloored(f.cam);
            Biome.Precipitation pr = f.world.getBiome(cp).value().getPrecipitation(cp, f.world.getSeaLevel());
            if (pr == Biome.Precipitation.NONE && needStorm.value) return;
            snow = pr == Biome.Precipitation.SNOW;
        }
        int n = Math.min(MAX, (int) (Settings.count(snow ? 520 : 650) * amount.value * strength));
        VertexConsumer b = f.add(snow ? Gfx.GLOW : Gfx.LINE);
        float t = f.time;
        double cx = f.cam.x, cy = f.cam.y, cz = f.cam.z;
        for (int i = 0; i < n; i++) {
            float fall = snow ? 1.6f : 22f;
            float drift = wind.value * (snow ? 1.2f : 3f) * t;
            float x = wrap(ox[i] * R * 2f + drift + (snow ? 0.9f * (float) Math.sin(t * 0.8f + i) : 0f), (float) cx, R * 2f);
            float z = wrap(oz[i] * R * 2f + (snow ? 0.7f * (float) Math.cos(t * 0.7f + i * 1.7f) : 0f), (float) cz, R * 2f);
            float y = wrap(oy[i] * H - t * fall * sp[i], (float) cy, H);
            int ix = MathHelper.floor(x), iz = MathHelper.floor(z);
            if (!f.world.isChunkLoaded(ix >> 4, iz >> 4)) continue;
            if (f.world.getTopY(Heightmap.Type.MOTION_BLOCKING, ix, iz) > y) continue;            // under a roof
            float dist = (float) Math.sqrt((x - cx) * (x - cx) + (z - cz) * (z - cz));
            float fade = Math.min(1f, (R - dist) / 6f);
            if (fade <= 0f) continue;
            if (snow) {
                f.sprite(b, x, y, z, 0.07f * size.value * (0.7f + sp[i] * 0.5f), t * sp[i], snowColor.value, 0.85f * fade * Math.min(1f, strength * 1.5f));
            } else {
                float len = 0.55f * size.value * sp[i];
                f.line(b, x, y, z, x - wind.value * 0.08f, y + len, z, 0.012f * size.value, 0.004f, rainColor.value, 0.55f * fade, rainColor.value, 0f);
            }
        }
    }
}
