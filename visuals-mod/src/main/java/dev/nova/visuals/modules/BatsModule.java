package dev.nova.visuals.modules;

import dev.nova.visuals.config.Category;
import dev.nova.visuals.config.Module;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.gfx.Frame;
import dev.nova.visuals.gfx.Gfx;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.entity.player.PlayerEntity;

/** A small flock of bats circling you, with glowing eyes. */
public final class BatsModule extends Module {
    private final Setting.Num count = add(new Setting.Num("count", "Bats", 5f, 1f, 12f, 1f, ""));
    private final Setting.Num orbit = add(new Setting.Num("orbit", "Orbit radius", 1.9f, 0.8f, 4f, 0.05f, ""));
    private final Setting.Num speed = add(new Setting.Num("speed", "Speed", 1.0f, 0.2f, 3f, 0.05f, "x"));
    private final Setting.Num size = add(new Setting.Num("size", "Size", 1.0f, 0.4f, 2.5f, 0.05f, "x"));
    private final Setting.Color eyes = add(new Setting.Color("eyes", "Eye color", 0xFF2A2A));
    private final Setting.Color body = add(new Setting.Color("body", "Body color", 0x120A14));

    public BatsModule() {
        super("bats", "Bats", "Bats flying in circles around you.", Category.COSMETICS, false);
    }

    @Override
    public void onWorld(Frame f) {
        for (PlayerEntity p : Fx.targets(f)) {
            if (p == f.player && Fx.firstPerson()) { /* still drawn: they orbit around the camera */ }
            draw(f, p);
        }
    }

    private void draw(Frame f, PlayerEntity p) {
        var pos = p.getLerpedPos(f.tickDelta);
        int n = (int) count.value;
        VertexConsumer solid = f.solid(Gfx.WHITE);
        float br = ((body.value >> 16) & 255) / 255f, bg = ((body.value >> 8) & 255) / 255f, bb = (body.value & 255) / 255f;
        float L = 0.3f * size.value;
        for (int i = 0; i < n; i++) {
            float k = i / (float) n;
            float ang = f.time * speed.value * (0.7f + 0.1f * (i % 3)) + k * 6.283f;
            float rad = orbit.value * (0.8f + 0.25f * (float) Math.sin(f.time * 0.6f + i * 2f));
            double x = pos.x + Math.cos(ang) * rad, z = pos.z + Math.sin(ang) * rad;
            double y = pos.y + 1.1 + 0.55 * Math.sin(f.time * 1.1f + i * 1.9f) + 0.3 * Math.sin(i);
            float hx = (float) -Math.sin(ang), hz = (float) Math.cos(ang);          // heading along the circle
            float sx = -hz, sz = hx;                                                // the bat's side direction
            float flapA = (float) Math.sin(f.time * 11f * speed.value + i * 1.3f);
            float tipUp = flapA * L * 0.9f;
            float cx = (float) (x - f.cam.x), cy = (float) (y - f.cam.y), cz = (float) (z - f.cam.z);
            for (int s = -1; s <= 1; s += 2) {
                float tx = cx + sx * s * L * 1.6f, ty = cy + tipUp + L * 0.15f, tz = cz + sz * s * L * 1.6f;
                float mx = cx + sx * s * L * 0.9f - hx * L * 0.55f, my = cy + tipUp * 0.45f - L * 0.1f, mz = cz + sz * s * L * 0.9f - hz * L * 0.55f;
                Gfx.tri(solid, f.m, cx + hx * L * 0.3f, cy, cz + hz * L * 0.3f, tx, ty, tz, mx, my, mz, br, bg, bb, 0.95f);
                Gfx.tri(solid, f.m, cx - hx * L * 0.35f, cy - L * 0.05f, cz - hz * L * 0.35f, mx, my, mz, cx + hx * L * 0.3f, cy, cz + hz * L * 0.3f, br, bg, bb, 0.95f);
            }
            // body and head
            f.sprite(solid, x, y, z, L * 0.28f, 0f, body.value, 0.95f);
            f.bloom(x + hx * L * 0.35f, y + L * 0.05f, z + hz * L * 0.35f, 0.025f * size.value, eyes.value, 0.95f);
        }
    }
}
