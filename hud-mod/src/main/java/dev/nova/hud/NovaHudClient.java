package dev.nova.hud;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.option.KeyBinding;
import net.minecraft.client.util.InputUtil;
import org.lwjgl.glfw.GLFW;

public class NovaHudClient implements ClientModInitializer {
    private static KeyBinding menuKey;

    @Override
    public void onInitializeClient() {
        // Right Shift opens the menu (not Left Shift). Rebindable under Controls -> Nova HUD.
        menuKey = KeyBindingHelper.registerKeyBinding(new KeyBinding(
                "key.nova_hud.menu", InputUtil.Type.KEYSYM, GLFW.GLFW_KEY_RIGHT_SHIFT, "key.categories.nova_hud"));

        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            while (menuKey.wasPressed()) {
                if (client.currentScreen == null) client.setScreen(new NovaHudScreen(null));
            }
        });

        HudRenderCallback.EVENT.register(NovaHud::render);
    }

    public static int menuKeyCode() {
        return InputUtil.fromTranslationKey(menuKey.getBoundKeyTranslationKey()).getCode();
    }
}
