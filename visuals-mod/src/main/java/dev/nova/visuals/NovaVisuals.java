package dev.nova.visuals;

import dev.nova.visuals.config.Config;
import dev.nova.visuals.config.ModuleManager;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.fx.ParticleEngine;
import dev.nova.visuals.fx.RingPool;
import dev.nova.visuals.fx.WorldFx;
import dev.nova.visuals.core.Time;
import dev.nova.visuals.gui.ClickGui;
import dev.nova.visuals.hud.CinematicBarsModule;
import dev.nova.visuals.hud.CpsHud;
import dev.nova.visuals.hud.CrosshairModule;
import dev.nova.visuals.hud.InfoHud;
import dev.nova.visuals.hud.KeystrokesHud;
import dev.nova.visuals.hud.PotionHud;
import dev.nova.visuals.hud.ScreenOverlayModule;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.client.util.InputUtil;
import org.lwjgl.glfw.GLFW;
import dev.nova.visuals.modules.AuroraModule;
import dev.nova.visuals.modules.StarFieldModule;
import dev.nova.visuals.modules.SunMoonModule;
import dev.nova.visuals.modules.SkyboxModule;
import dev.nova.visuals.modules.TimeModule;
import dev.nova.visuals.modules.WeatherModule;
import dev.nova.visuals.modules.PrecipModule;
import dev.nova.visuals.modules.AtmosphereModule;
import dev.nova.visuals.modules.WingsModule;
import dev.nova.visuals.modules.HaloModule;
import dev.nova.visuals.modules.HornsModule;
import dev.nova.visuals.modules.MagicCircleModule;
import dev.nova.visuals.modules.BatsModule;
import dev.nova.visuals.modules.AuraModule;
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
    public static KeyBinding menuKey;

    @Override
    public void onInitializeClient() {
        ModuleManager.register(new Settings());
        ModuleManager.register(new TrailModule());
        ModuleManager.register(new RingsModule());
        ModuleManager.register(hitFx = new HitFxModule());
        ModuleManager.register(new StarsModule());
        ModuleManager.register(new AuroraModule());
        ModuleManager.register(new StarFieldModule());
        ModuleManager.register(new SunMoonModule());
        ModuleManager.register(new SkyboxModule());
        ModuleManager.register(new TimeModule());
        ModuleManager.register(new WeatherModule());
        ModuleManager.register(new PrecipModule());
        ModuleManager.register(new AtmosphereModule());
        ModuleManager.register(new WingsModule());
        ModuleManager.register(new HaloModule());
        ModuleManager.register(new HornsModule());
        ModuleManager.register(new MagicCircleModule());
        ModuleManager.register(new BatsModule());
        ModuleManager.register(new AuraModule());
        ModuleManager.register(new ScreenOverlayModule());
        ModuleManager.register(new CinematicBarsModule());
        ModuleManager.register(new InfoHud());
        ModuleManager.register(new KeystrokesHud());
        ModuleManager.register(new CpsHud());
        ModuleManager.register(new PotionHud());
        ModuleManager.register(new CrosshairModule());
        Config.load();

        menuKey = KeyBindingHelper.registerKeyBinding(new KeyBinding("key.nova_visuals.menu", InputUtil.Type.KEYSYM, GLFW.GLFW_KEY_RIGHT_SHIFT, "key.categories.nova_visuals"));
        HudRenderCallback.EVENT.register((ctx, tickCounter) -> {
            Time.frame();
            ModuleManager.hud(ctx, Time.dt());
        });

        WorldFx.init();
        ClientTickEvents.END_CLIENT_TICK.register(mc -> {
            while (menuKey.wasPressed()) {
                if (mc.currentScreen == null) mc.setScreen(new ClickGui());
            }
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
