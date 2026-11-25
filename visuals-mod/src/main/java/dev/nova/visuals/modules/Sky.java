package dev.nova.visuals.modules;

import dev.nova.visuals.core.Easing;
import dev.nova.visuals.gfx.Frame;
import net.minecraft.client.world.ClientWorld;

/** Sky helpers shared by the environment modules. */
final class Sky {
    private Sky() {}

    /** 0 in daylight, 1 at night (smooth through dusk and dawn). 0 in dimensions without a sky. */
    static float night(ClientWorld w, float td) {
        if (!w.getDimension().hasSkyLight()) return 0f;
        float sun = (float) Math.cos(w.getSkyAngle(td) * 2 * Math.PI);          // +1 noon, -1 midnight
        return Easing.smoothstep((0.12f - sun) / 0.4f);
    }

    static float clear(ClientWorld w, float td) { return 1f - 0.85f * w.getRainGradient(td); }

    /** Rotates a direction the way the sky turns during the day (same as the vanilla sky). */
    static float[] rotate(float x, float y, float z, float skyAngle) {
        double th = skyAngle * 2 * Math.PI, c = Math.cos(th), s = Math.sin(th);
        float y1 = (float) (y * c - z * s), z1 = (float) (y * s + z * c);
        return new float[]{-z1, y1, x};                                          // then a quarter turn about the vertical axis
    }

    /** Direction of the sun (the moon is the opposite). */
    static float[] sun(ClientWorld w, float td) { return rotate(0f, 1f, 0f, w.getSkyAngle(td)); }

    static boolean hasSky(Frame f) { return f.world.getDimension().hasSkyLight(); }
}
