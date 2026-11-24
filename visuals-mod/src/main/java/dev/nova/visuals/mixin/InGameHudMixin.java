package dev.nova.visuals.mixin;

import net.minecraft.client.gui.hud.InGameHud;
import org.spongepowered.asm.mixin.Mixin;

/** Placeholder target so the mixin config always has a valid class; the crosshair hook is added with the HUD. */
@Mixin(InGameHud.class)
public class InGameHudMixin {
}
