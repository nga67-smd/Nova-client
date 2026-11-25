package dev.nova.visuals.hud;

import dev.nova.visuals.config.ColorSpec;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.gui.Draw;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import org.lwjgl.glfw.GLFW;

/** Clicks per second for both mouse buttons, counted every frame (not once per tick). */
public final class CpsHud extends HudModule {
    private final Setting.Bool both = add(new Setting.Bool("both", "Show left and right", true));
    private final ColorSpec color = new ColorSpec(this, 0xFFFFFF, 0);
    private final long[][] clicks = new long[2][64];
    private final int[] head = new int[2], size = new int[2];
    private final boolean[] was = new boolean[2];

    public CpsHud() {
        super("hud_cps", "CPS Counter", "Clicks per second.", true, 0.01f, 0.5f);
    }

    private void poll() {
        MinecraftClient mc = MinecraftClient.getInstance();
        long now = System.currentTimeMillis();
        for (int b = 0; b < 2; b++) {
            boolean down = mc.currentScreen == null && GLFW.glfwGetMouseButton(mc.getWindow().getHandle(), b) == GLFW.GLFW_PRESS;
            if (down && !was[b] && size[b] < 64) { clicks[b][(head[b] + size[b]) % 64] = now; size[b]++; }
            was[b] = down;
            while (size[b] > 0 && now - clicks[b][head[b]] > 1000) { head[b] = (head[b] + 1) % 64; size[b]--; }
        }
    }

    private String text() {
        return both.value ? size[0] + " | " + size[1] + " CPS" : size[0] + " CPS";
    }

    @Override protected int width(TextRenderer tr) { return tr.getWidth(both.value ? "00 | 00 CPS" : "00 CPS") + 12; }
    @Override protected int height(TextRenderer tr) { return 17; }

    @Override
    protected void draw(DrawContext ctx, TextRenderer tr, float dt, float alpha) {
        poll();
        Draw.text(ctx, tr, text(), 6, 4.5f, Draw.rgba(color.at(0f), alpha), true);
    }
}
