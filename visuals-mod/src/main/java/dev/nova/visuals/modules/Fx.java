package dev.nova.visuals.modules;

import dev.nova.visuals.config.Settings;
import dev.nova.visuals.gfx.Frame;
import net.minecraft.entity.Entity;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.util.math.Vec3d;

/** Small helpers shared by the effect modules. */
final class Fx {
    private Fx() {}

    static Vec3d at(Entity e, float td) { return e.getLerpedPos(td); }

    /** The players cosmetics are drawn on: you, and (if allowed) everyone you can see. */
    static Iterable<PlayerEntity> targets(Frame f) {
        java.util.List<PlayerEntity> out = new java.util.ArrayList<>(1);
        out.add(f.player);
        if (Settings.others()) {
            for (PlayerEntity p : f.world.getPlayers()) {
                if (p != f.player && !p.isInvisible() && !p.isSpectator() && p.squaredDistanceTo(f.player) < 48 * 48) out.add(p);
            }
        }
        return out;
    }

    static boolean firstPerson() {
        return net.minecraft.client.MinecraftClient.getInstance().options.getPerspective().isFirstPerson();
    }

    static float rand(float lo, float hi) { return lo + (float) Math.random() * (hi - lo); }
}
