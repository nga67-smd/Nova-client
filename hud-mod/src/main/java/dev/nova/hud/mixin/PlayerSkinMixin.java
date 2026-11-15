package dev.nova.hud.mixin;

import dev.nova.hud.NovaCosmetics;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.network.AbstractClientPlayerEntity;
import net.minecraft.client.util.SkinTextures;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Swaps in the Nova cosmetics skin and cape, for your own player only. */
@Mixin(AbstractClientPlayerEntity.class)
public class PlayerSkinMixin {
    @Inject(method = "getSkinTextures", at = @At("RETURN"), cancellable = true)
    private void nova$cosmetics(CallbackInfoReturnable<SkinTextures> cir) {
        if ((Object) this != MinecraftClient.getInstance().player) return;
        cir.setReturnValue(NovaCosmetics.apply(cir.getReturnValue()));
    }
}
