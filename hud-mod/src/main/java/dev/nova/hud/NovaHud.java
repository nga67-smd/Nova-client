package dev.nova.hud;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.entity.EquipmentSlot;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.item.ItemStack;

/** Draws the armor HUD and the optional FPS / coordinates lines. */
public final class NovaHud {
    private static final int PURPLE = 0xFFB66BFF;
    private static final EquipmentSlot[] ARMOR_SLOTS = {
            EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET};

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

        Compat.push(ctx);
        Compat.translate(ctx, x, y);
        Compat.scale(ctx, s);
        for (int i = 0; i < rows; i++) {
            ItemStack stack = player.getEquippedStack(ARMOR_SLOTS[i]);
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
        Compat.pop(ctx);
    }
}
