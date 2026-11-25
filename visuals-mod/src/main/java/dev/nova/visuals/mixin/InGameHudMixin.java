package dev.nova.visuals.mixin;

import dev.nova.visuals.hud.CrosshairModule;
import net.minecraft.client.gui.hud.InGameHud;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Skips the vanilla crosshair while the custom one is on. If the target ever changes, the mixin is skipped instead of crashing. */
@Mixin(InGameHud.class)
public class InGameHudMixin {
    @Inject(method = "renderCrosshair", at = @At("HEAD"), cancellable = true, require = 0)
    private void nova_visuals$crosshair(CallbackInfo ci) {
        if (CrosshairModule.replacingVanilla()) ci.cancel();
    }
}
