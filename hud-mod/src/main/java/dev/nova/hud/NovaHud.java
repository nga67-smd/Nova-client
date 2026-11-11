package dev.nova.hud;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.item.ItemStack;

/** Draws the armor HUD and the optional FPS / coordinates lines. */
public final class NovaHud {
    private static final int PURPLE = 0xFFB66BFF;

    private NovaHud() {}

    public static void render(DrawContext ctx, RenderTickCounter tickCounter) {
        MinecraftClient mc = MinecraftClient.getInstance();
        PlayerEntity player = mc.player;
        if (player == null || mc.options.hudHidden) return;
        NovaConfig c = NovaConfig.get();
        TextRenderer font = mc.textRenderer;

        if (c.armorHud) drawArmor(ctx, mc, player, font, c);

        int y = 4;
        if (c.showFps) {
            ctx.drawTextWithShadow(font, mc.getCurrentFps() + " FPS", 4, y, PURPLE);
            y += 11;
        }
        if (c.showCoords) {
            ctx.drawTextWithShadow(font, "XYZ " + player.getBlockX() + " " + player.getBlockY() + " " + player.getBlockZ(), 4, y, PURPLE);
        }
    }

    private static void drawArmor(DrawContext ctx, MinecraftClient mc, PlayerEntity player, TextRenderer font, NovaConfig c) {
        int rowH = 20;
        int rows = 4;
        float s = c.armorScale;
        int width = ctx.getScaledWindowWidth();
        int height = ctx.getScaledWindowHeight();
        float blockH = rows * rowH * s;
        float x = c.armorLeft ? 4 : width - 4 - (c.armorDurability ? 44 : 18) * s;
        float y = (height - blockH) / 2f;

        ctx.getMatrices().push();
        ctx.getMatrices().translate(x, y, 0);
        ctx.getMatrices().scale(s, s, 1f);
        for (int i = 0; i < rows; i++) {
            // armor list is boots(0) .. helmet(3); show helmet on top
            ItemStack stack = player.getInventory().armor.get(3 - i);
            if (stack.isEmpty()) continue;
            int ry = i * rowH;
            ctx.drawItem(stack, 0, ry);
            if (c.armorDurability && stack.isDamageable()) {
                int max = stack.getMaxDamage();
                int pct = Math.max(0, (max - stack.getDamage()) * 100 / max);
                int color = pct > 50 ? 0xFF55FF55 : pct > 20 ? 0xFFFFFF55 : 0xFFFF5555;
                ctx.drawTextWithShadow(font, pct + "%", 19, ry + 4, color);
            }
        }
        ctx.getMatrices().pop();
    }
}
