package dev.nova.visuals;

import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.util.math.BlockPos;
import net.minecraft.world.World;
import net.minecraft.world.biome.Biome;

/** The few calls whose names differ between Minecraft versions. This is the 1.21.3 copy. */
public final class Compat {
    private Compat() {}

    public static boolean gliding(PlayerEntity p) { return p.isGliding(); }

    /** 0 = none, 1 = rain, 2 = snow at that position. */
    public static int precipitation(World w, BlockPos pos) {
        Biome.Precipitation pr = w.getBiome(pos).value().getPrecipitation(pos, w.getSeaLevel());
        return pr == Biome.Precipitation.NONE ? 0 : pr == Biome.Precipitation.SNOW ? 2 : 1;
    }

    public static float tickDelta(net.fabricmc.fabric.api.client.rendering.v1.WorldRenderContext ctx) {
        return ctx.tickCounter().getTickDelta(false);
    }

    public static float bodyYaw(PlayerEntity p, float td) {
        return net.minecraft.util.math.MathHelper.lerpAngleDegrees(td, p.prevBodyYaw, p.bodyYaw);
    }

    public static float headYaw(PlayerEntity p, float td) {
        return net.minecraft.util.math.MathHelper.lerpAngleDegrees(td, p.prevHeadYaw, p.headYaw);
    }

    public static void push(net.minecraft.client.gui.DrawContext c) { c.getMatrices().push(); }
    public static void pop(net.minecraft.client.gui.DrawContext c) { c.getMatrices().pop(); }
    public static void translate(net.minecraft.client.gui.DrawContext c, float x, float y) { c.getMatrices().translate(x, y, 0f); }
    public static void scale(net.minecraft.client.gui.DrawContext c, float s) { c.getMatrices().scale(s, s, 1f); }
}
