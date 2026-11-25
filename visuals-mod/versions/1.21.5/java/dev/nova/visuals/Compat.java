package dev.nova.visuals;

import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.util.math.BlockPos;
import net.minecraft.world.World;
import net.minecraft.world.biome.Biome;

/** The few calls whose names differ between Minecraft versions. This is the 1.21.5 copy. */
public final class Compat {
    private Compat() {}

    public static boolean gliding(PlayerEntity p) { return p.isGliding(); }

    /** 0 = none, 1 = rain, 2 = snow at that position. */
    public static int precipitation(World w, BlockPos pos) {
        Biome.Precipitation pr = w.getBiome(pos).value().getPrecipitation(pos, w.getSeaLevel());
        return pr == Biome.Precipitation.NONE ? 0 : pr == Biome.Precipitation.SNOW ? 2 : 1;
    }
}
