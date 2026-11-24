package dev.nova.hud;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.entity.EquipmentSlot;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.item.ItemStack;

/** Draws the armor HUD and the Nova panels. */
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
        NovaStats.frame(mc);

        if (c.armorHud) drawArmor(ctx, mc, player, font, c);

        // Build the panels, then stack the ones that share a corner.
        java.util.List<NovaPanels.Block>[] groups = new java.util.List[8];
        for (int i = 0; i < 8; i++) groups[i] = new java.util.ArrayList<>();
        add(groups, c.anchorInfo, NovaPanels.info(mc, player, c));
        if (c.keystrokes) add(groups, c.anchorKeys, NovaPanels.keystrokes(mc, c));
        if (c.potions) add(groups, c.anchorPotions, NovaPanels.potions(mc, player, c));
        if (c.itemCounts) add(groups, c.anchorItems, NovaPanels.items(mc, player, c));

        int sw = ctx.getScaledWindowWidth(), sh = ctx.getScaledWindowHeight();
        float s = c.hudScale;
        for (int a = 0; a < 8; a++) {
            java.util.List<NovaPanels.Block> list = groups[a];
            if (list.isEmpty()) continue;
            int gw = 0, gh = 0, gap = 3;
            for (NovaPanels.Block b : list) {
                gw = Math.max(gw, b.w);
                gh += b.h + gap;
            }
            gh -= gap;
            boolean right = a == 1 || a == 3 || a == 5;
            boolean centre = a == 6 || a == 7;
            float x = centre ? (sw - gw * s) / 2f : right ? sw - c.marginX - gw * s : c.marginX;
            float y = (a == 2 || a == 3 || a == 7) ? sh - c.marginY - gh * s : (a == 4 || a == 5) ? (sh - gh * s) / 2f : c.marginY;

            Compat.push(ctx);
            Compat.translate(ctx, x, y);
            Compat.scale(ctx, s);
            int cy = 0;
            for (NovaPanels.Block b : list) {
                b.draw(ctx, (right ? gw - b.w : centre ? (gw - b.w) / 2 : 0), cy);
                cy += b.h + gap;
            }
            Compat.pop(ctx);
        }
    }

    private static void add(java.util.List<NovaPanels.Block>[] groups, int anchor, NovaPanels.Block b) {
        if (b != null) groups[Math.floorMod(anchor, 8)].add(b);
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
