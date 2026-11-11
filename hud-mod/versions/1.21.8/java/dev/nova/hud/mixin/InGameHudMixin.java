package dev.nova.hud.mixin;

import dev.nova.hud.Compat;
import dev.nova.hud.NovaConfig;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.hud.InGameHud;
import net.minecraft.scoreboard.ScoreboardObjective;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Lets the sidebar (scoreboard) be hidden, resized and moved. */
@Mixin(InGameHud.class)
public class InGameHudMixin {
    @Unique
    private boolean novaPushed;

    @Inject(method = "renderScoreboardSidebar(Lnet/minecraft/client/gui/DrawContext;Lnet/minecraft/scoreboard/ScoreboardObjective;)V", at = @At("HEAD"), cancellable = true)
    private void nova$sidebarBefore(DrawContext context, ScoreboardObjective objective, CallbackInfo ci) {
        NovaConfig c = NovaConfig.get();
        if (!c.showSidebar) {
            ci.cancel();
            return;
        }
        float s = c.sidebarScale;
        if (s != 1.0f || c.sidebarOffsetY != 0) {
            // Scale around the right edge, vertically centred, where the sidebar sits.
            float px = context.getScaledWindowWidth();
            float py = context.getScaledWindowHeight() / 2f;
            Compat.push(context);
            Compat.translate(context, px, py + c.sidebarOffsetY);
            Compat.scale(context, s);
            Compat.translate(context, -px, -py);
            novaPushed = true;
        }
    }

    @Inject(method = "renderScoreboardSidebar(Lnet/minecraft/client/gui/DrawContext;Lnet/minecraft/scoreboard/ScoreboardObjective;)V", at = @At("RETURN"))
    private void nova$sidebarAfter(DrawContext context, ScoreboardObjective objective, CallbackInfo ci) {
        if (novaPushed) {
            Compat.pop(context);
            novaPushed = false;
        }
    }
}
