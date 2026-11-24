package dev.nova.visuals;

import dev.nova.visuals.config.Config;
import dev.nova.visuals.config.ModuleManager;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.fx.ParticleEngine;
import dev.nova.visuals.fx.RingPool;
import dev.nova.visuals.fx.WorldFx;
import dev.nova.visuals.modules.HitFxModule;
import dev.nova.visuals.modules.RingsModule;
import dev.nova.visuals.modules.StarsModule;
import dev.nova.visuals.modules.TrailModule;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.event.player.AttackEntityCallback;
import net.minecraft.util.ActionResult;

public class NovaVisuals implements ClientModInitializer {
    public static HitFxModule hitFx;

    @Override
    public void onInitializeClient() {
        ModuleManager.register(new Settings());
        ModuleManager.register(new TrailModule());
        ModuleManager.register(new RingsModule());
        ModuleManager.register(hitFx = new HitFxModule());
        ModuleManager.register(new StarsModule());
        Config.load();

        WorldFx.init();
        ClientTickEvents.END_CLIENT_TICK.register(mc -> {
            if (mc.world == null) {
                ParticleEngine.clear();
                RingPool.clear();
                return;
            }
            ModuleManager.tick(mc);
        });
        AttackEntityCallback.EVENT.register((player, world, hand, entity, hit) -> {
            if (world.isClient && hitFx.enabled()) hitFx.hit(entity);
            return ActionResult.PASS;
        });
    }
}
