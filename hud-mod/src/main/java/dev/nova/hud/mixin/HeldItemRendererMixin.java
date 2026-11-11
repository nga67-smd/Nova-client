package dev.nova.hud.mixin;

import dev.nova.hud.NovaConfig;
import net.minecraft.client.network.AbstractClientPlayerEntity;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.client.render.item.HeldItemRenderer;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.item.ItemStack;
import net.minecraft.util.Hand;
import net.minecraft.util.math.RotationAxis;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Moves, resizes and tilts the item/hand you hold in first person. */
@Mixin(HeldItemRenderer.class)
public class HeldItemRendererMixin {
    @Inject(method = "renderFirstPersonItem", at = @At("HEAD"))
    private void nova$viewModel(AbstractClientPlayerEntity player, float tickDelta, float pitch, Hand hand,
                                float swingProgress, ItemStack item, float equipProgress, MatrixStack matrices,
                                VertexConsumerProvider vertexConsumers, int light, CallbackInfo ci) {
        NovaConfig c = NovaConfig.get();
        if (!c.viewModel) return;
        matrices.translate(c.vmX, c.vmY, c.vmZ);
        matrices.scale(c.vmScale, c.vmScale, c.vmScale);
        matrices.multiply(RotationAxis.POSITIVE_X.rotationDegrees(c.vmRotX));
        matrices.multiply(RotationAxis.POSITIVE_Y.rotationDegrees(c.vmRotY));
        matrices.multiply(RotationAxis.POSITIVE_Z.rotationDegrees(c.vmRotZ));
    }
}
