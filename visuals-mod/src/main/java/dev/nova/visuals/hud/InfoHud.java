package dev.nova.visuals.hud;

import dev.nova.visuals.config.ColorSpec;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.gui.Draw;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.util.math.Direction;

import java.util.ArrayList;
import java.util.List;

/** FPS, coordinates and facing in a small minimalist box. */
public final class InfoHud extends HudModule {
    private final Setting.Bool fps = add(new Setting.Bool("fps", "FPS", true));
    private final Setting.Bool coords = add(new Setting.Bool("coords", "Coordinates", true));
    private final Setting.Bool facing = add(new Setting.Bool("facing", "Facing direction", true));
    private final Setting.Bool ping = add(new Setting.Bool("ping", "Ping (servers)", false));
    private final ColorSpec color = new ColorSpec(this, 0xFFFFFF, 0);

    public InfoHud() {
        super("hud_info", "FPS & Coordinates", "Minimal FPS counter and position.", true, 0.01f, 0.02f);
    }

    private List<String[]> lines() {
        MinecraftClient mc = MinecraftClient.getInstance();
        List<String[]> out = new ArrayList<>();
        if (fps.value) out.add(new String[]{"FPS", String.valueOf(mc.getCurrentFps())});
        if (ping.value && mc.player != null && mc.getNetworkHandler() != null) {
            var e = mc.getNetworkHandler().getPlayerListEntry(mc.player.getUuid());
            if (e != null) out.add(new String[]{"Ping", e.getLatency() + " ms"});
        }
        if (coords.value && mc.player != null) {
            out.add(new String[]{"XYZ", String.format("%.1f  %.1f  %.1f", mc.player.getX(), mc.player.getY(), mc.player.getZ())});
        }
        if (facing.value && mc.player != null) {
            Direction d = mc.player.getHorizontalFacing();
            String n = d.asString();
            out.add(new String[]{"Facing", Character.toUpperCase(n.charAt(0)) + n.substring(1)});
        }
        return out;
    }

    @Override protected int width(TextRenderer tr) {
        int w = 40;
        for (String[] l : lines()) w = Math.max(w, 8 + tr.getWidth(l[0]) + 10 + tr.getWidth(l[1]) + 8);
        return w;
    }

    @Override protected int height(TextRenderer tr) { return Math.max(1, lines().size()) * 11 + 6; }

    @Override
    protected void draw(DrawContext ctx, TextRenderer tr, float dt, float alpha) {
        int y = 4, i = 0;
        for (String[] l : lines()) {
            Draw.text(ctx, tr, l[0], 6, y, Draw.rgba(color.at(i * 0.2f), alpha), true);
            Draw.text(ctx, tr, l[1], 6 + tr.getWidth(l[0]) + 10, y, Draw.fade(0xFFFFFFFF, alpha), true);
            y += 11; i++;
        }
    }
}
