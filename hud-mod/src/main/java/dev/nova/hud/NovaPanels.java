package dev.nova.hud;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.entity.effect.StatusEffectInstance;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.entity.player.PlayerInventory;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import net.minecraft.item.Items;
import net.minecraft.text.Text;

import java.time.LocalTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

/** The Nova-styled panels: info rows, keystrokes, potion effects and item counts. */
public final class NovaPanels {
    private NovaPanels() {}

    /** One thing to draw. Sizes are in unscaled pixels. */
    public abstract static class Block {
        public int w, h;
        public abstract void draw(DrawContext ctx, int x, int y);
    }

    // ---- colors
    public static int opaque(int rgb) { return 0xFF000000 | (rgb & 0xFFFFFF); }

    public static int alpha(int rgb, float a) {
        return ((int) (Math.max(0f, Math.min(1f, a)) * 255) << 24) | (rgb & 0xFFFFFF);
    }

    // ---- shapes
    public static void roundRect(DrawContext ctx, int x, int y, int w, int h, int r, int color) {
        r = Math.max(0, Math.min(r, Math.min(w, h) / 2));
        if (r == 0) {
            ctx.fill(x, y, x + w, y + h, color);
            return;
        }
        ctx.fill(x, y + r, x + w, y + h - r, color);
        for (int i = 0; i < r; i++) {
            double dy = r - i - 0.5;
            int inset = r - (int) Math.floor(Math.sqrt(Math.max(0, r * r - dy * dy)));
            ctx.fill(x + inset, y + i, x + w - inset, y + i + 1, color);
            ctx.fill(x + inset, y + h - 1 - i, x + w - inset, y + h - i, color);
        }
    }

    /** Panel background, thin accent border and optional accent bar on the left. */
    public static void frame(DrawContext ctx, NovaConfig c, int x, int y, int w, int h) {
        roundRect(ctx, x, y, w, h, c.radius, alpha(c.background, c.bgOpacity));
        int r = Math.min(c.radius, Math.min(w, h) / 2), b = c.border, line = opaque(c.accent);
        if (b > 0) {
            ctx.fill(x + r, y, x + w - r, y + b, line);
            ctx.fill(x + r, y + h - b, x + w - r, y + h, line);
            ctx.fill(x, y + r, x + b, y + h - r, line);
            ctx.fill(x + w - b, y + r, x + w, y + h - r, line);
        }
        if (c.accentBar) {
            ctx.fill(x + Math.max(b, 0), y + r, x + Math.max(b, 0) + 2, y + h - r, line);
        }
    }

    private static void text(DrawContext ctx, NovaConfig c, TextRenderer f, String s, int x, int y, int rgb) {
        ctx.drawText(f, s, x, y, opaque(rgb), c.shadow);
    }

    // ---- info panel
    public static Block info(MinecraftClient mc, PlayerEntity p, NovaConfig c) {
        List<String[]> rows = new ArrayList<>();
        if (c.showFps) rows.add(new String[]{"FPS", String.valueOf(mc.getCurrentFps())});
        if (c.showPing) rows.add(new String[]{"Ping", ping(mc, p) + " ms"});
        if (c.showCps) rows.add(new String[]{"CPS", NovaStats.leftCps() + " | " + NovaStats.rightCps()});
        if (c.showCoords) rows.add(new String[]{"XYZ", p.getBlockX() + " " + p.getBlockY() + " " + p.getBlockZ()});
        if (c.showDirection) rows.add(new String[]{"Facing", direction(p)});
        if (c.showBiome) rows.add(new String[]{"Biome", biome(mc, p)});
        if (c.showSpeed) rows.add(new String[]{"Speed", String.format("%.1f b/s", NovaStats.speed())});
        if (c.showClock) rows.add(new String[]{"Time", LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm"))});
        if (c.showMcTime) rows.add(new String[]{"Day", mcTime(mc)});
        if (c.showMemory) rows.add(new String[]{"RAM", memory()});
        if (c.showCombo) rows.add(new String[]{"Combo", String.valueOf(NovaStats.combo())});
        if (c.showReach) {
            double r = NovaStats.reach();
            rows.add(new String[]{"Reach", r < 0 ? "-" : String.format("%.2f", r)});
        }
        if (rows.isEmpty()) return null;

        TextRenderer f = mc.textRenderer;
        int pad = c.padding, bar = c.accentBar ? 4 : 0;
        int inner = 0;
        for (String[] r : rows) inner = Math.max(inner, f.getWidth(r[0]) + 10 + f.getWidth(r[1]));
        int width = Math.max(c.minWidth, inner + pad * 2 + bar);
        int rowH = 11;
        Block b = new Block() {
            @Override
            public void draw(DrawContext ctx, int x, int y) {
                frame(ctx, c, x, y, w, h);
                int ty = y + pad;
                for (String[] r : rows) {
                    text(ctx, c, f, r[0], x + pad + bar, ty, c.labelColor);
                    text(ctx, c, f, r[1], x + w - pad - f.getWidth(r[1]), ty, c.textColor);
                    ty += rowH;
                }
            }
        };
        b.w = width;
        b.h = rows.size() * rowH - 2 + pad * 2;
        return b;
    }

    private static int ping(MinecraftClient mc, PlayerEntity p) {
        if (mc.getNetworkHandler() == null) return 0;
        var e = mc.getNetworkHandler().getPlayerListEntry(p.getUuid());
        return e == null ? 0 : e.getLatency();
    }

    private static String direction(PlayerEntity p) {
        String d = p.getHorizontalFacing().asString();
        return Character.toUpperCase(d.charAt(0)) + d.substring(1);
    }

    private static String biome(MinecraftClient mc, PlayerEntity p) {
        if (mc.world == null) return "-";
        return mc.world.getBiome(p.getBlockPos()).getKey().map(k -> {
            String s = k.getValue().getPath().replace('_', ' ');
            return Character.toUpperCase(s.charAt(0)) + s.substring(1);
        }).orElse("-");
    }

    private static String mcTime(MinecraftClient mc) {
        if (mc.world == null) return "-";
        long t = mc.world.getTimeOfDay() % 24000L;
        long hours = (t / 1000 + 6) % 24, minutes = (t % 1000) * 60 / 1000;
        return String.format("%02d:%02d", hours, minutes);
    }

    private static String memory() {
        Runtime rt = Runtime.getRuntime();
        long used = (rt.totalMemory() - rt.freeMemory()) >> 20, max = rt.maxMemory() >> 20;
        return used + "/" + max + " MB";
    }

    // ---- keystrokes
    public static Block keystrokes(MinecraftClient mc, NovaConfig c) {
        int k = 20, g = 2;
        Block b = new Block() {
            @Override
            public void draw(DrawContext ctx, int x, int y) {
                var o = mc.options;
                key(ctx, c, mc, x + k + g, y, k, k, "W", o.forwardKey.isPressed());
                key(ctx, c, mc, x, y + k + g, k, k, "A", o.leftKey.isPressed());
                key(ctx, c, mc, x + k + g, y + k + g, k, k, "S", o.backKey.isPressed());
                key(ctx, c, mc, x + (k + g) * 2, y + k + g, k, k, "D", o.rightKey.isPressed());
                int half = (w - g) / 2;
                key(ctx, c, mc, x, y + (k + g) * 2, half, k, "LMB " + NovaStats.leftCps(), NovaStats.leftDown());
                key(ctx, c, mc, x + half + g, y + (k + g) * 2, w - half - g, k, "RMB " + NovaStats.rightCps(), NovaStats.rightDown());
                key(ctx, c, mc, x, y + (k + g) * 3, w, 12, "", o.jumpKey.isPressed());
            }
        };
        b.w = k * 3 + g * 2;
        b.h = (k + g) * 3 + 12;
        return b;
    }

    private static void key(DrawContext ctx, NovaConfig c, MinecraftClient mc, int x, int y, int w, int h, String label, boolean down) {
        roundRect(ctx, x, y, w, h, Math.min(c.radius, 4), down ? alpha(c.accent, 0.85f) : alpha(c.background, c.bgOpacity));
        int line = opaque(c.accent);
        if (c.border > 0 && !down) {
            ctx.fill(x + 1, y, x + w - 1, y + 1, line);
            ctx.fill(x + 1, y + h - 1, x + w - 1, y + h, line);
        }
        TextRenderer f = mc.textRenderer;
        if (label.isEmpty()) {                                    // the space bar is just a bar
            ctx.fill(x + w / 2 - 6, y + h / 2 - 1, x + w / 2 + 6, y + h / 2 + 1, down ? opaque(c.background) : line);
            return;
        }
        text(ctx, c, f, label, x + (w - f.getWidth(label)) / 2, y + (h - 8) / 2, down ? c.background : c.textColor);
    }

    // ---- potion effects
    public static Block potions(MinecraftClient mc, PlayerEntity p, NovaConfig c) {
        var effects = new ArrayList<>(p.getStatusEffects());
        if (effects.isEmpty()) return null;
        TextRenderer f = mc.textRenderer;
        List<String[]> rows = new ArrayList<>();
        List<Boolean> good = new ArrayList<>();
        int inner = 0;
        for (StatusEffectInstance e : effects) {
            String name = Text.translatable(e.getTranslationKey()).getString() + (e.getAmplifier() > 0 ? " " + roman(e.getAmplifier() + 1) : "");
            String time = e.isInfinite() ? "inf" : String.format("%d:%02d", e.getDuration() / 1200, (e.getDuration() / 20) % 60);
            rows.add(new String[]{name, time});
            good.add(e.getEffectType().value().isBeneficial());
            inner = Math.max(inner, f.getWidth(name) + 10 + f.getWidth(time));
        }
        int pad = c.padding, bar = c.accentBar ? 4 : 0;
        Block b = new Block() {
            @Override
            public void draw(DrawContext ctx, int x, int y) {
                frame(ctx, c, x, y, w, h);
                int ty = y + pad;
                for (int i = 0; i < rows.size(); i++) {
                    String[] r = rows.get(i);
                    text(ctx, c, f, r[0], x + pad + bar, ty, good.get(i) ? c.textColor : 0xFF6B6B);
                    text(ctx, c, f, r[1], x + w - pad - f.getWidth(r[1]), ty, c.labelColor);
                    ty += 11;
                }
            }
        };
        b.w = Math.max(c.minWidth, inner + pad * 2 + bar);
        b.h = rows.size() * 11 - 2 + pad * 2;
        return b;
    }

    private static String roman(int n) {
        String[] r = {"", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"};
        return n < r.length ? r[n] : String.valueOf(n);
    }

    // ---- item counts
    public static Block items(MinecraftClient mc, PlayerEntity p, NovaConfig c) {
        Item[] watched = {Items.TOTEM_OF_UNDYING, Items.GOLDEN_APPLE, Items.ENDER_PEARL, Items.END_CRYSTAL, Items.ARROW};
        List<ItemStack> shown = new ArrayList<>();
        List<Integer> counts = new ArrayList<>();
        PlayerInventory inv = p.getInventory();
        for (Item it : watched) {
            int n = 0;
            for (int i = 0; i < inv.size(); i++) {
                ItemStack s = inv.getStack(i);
                if (s.isOf(it) || (it == Items.GOLDEN_APPLE && s.isOf(Items.ENCHANTED_GOLDEN_APPLE))) n += s.getCount();
            }
            if (n > 0) {
                shown.add(new ItemStack(it));
                counts.add(n);
            }
        }
        if (shown.isEmpty()) return null;
        TextRenderer f = mc.textRenderer;
        int pad = c.padding, bar = c.accentBar ? 4 : 0, inner = 0;
        for (int n : counts) inner = Math.max(inner, 20 + f.getWidth("x" + n));
        Block b = new Block() {
            @Override
            public void draw(DrawContext ctx, int x, int y) {
                frame(ctx, c, x, y, w, h);
                int ty = y + pad;
                for (int i = 0; i < shown.size(); i++) {
                    ctx.drawItem(shown.get(i), x + pad + bar, ty);
                    text(ctx, c, f, "x" + counts.get(i), x + pad + bar + 20, ty + 4, c.textColor);
                    ty += 18;
                }
            }
        };
        b.w = Math.max(c.minWidth, inner + pad * 2 + bar);
        b.h = shown.size() * 18 - 2 + pad * 2;
        return b;
    }
}
