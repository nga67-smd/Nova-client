package dev.nova.visuals.hud;

import dev.nova.visuals.config.ColorSpec;
import dev.nova.visuals.config.Setting;
import dev.nova.visuals.core.Colors;
import dev.nova.visuals.core.Smooth;
import dev.nova.visuals.gui.Draw;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.option.KeyBinding;
import org.lwjgl.glfw.GLFW;

/** WASD, space and the mouse buttons; each key glows and fades smoothly as it is pressed. */
public final class KeystrokesHud extends HudModule {
    private static final int K = 22, GAP = 2;
    private final Setting.Bool mouse = add(new Setting.Bool("mouse", "Mouse buttons", true));
    private final Setting.Bool space = add(new Setting.Bool("space", "Space bar", true));
    private final ColorSpec color = new ColorSpec(this, 0xB66BFF, 0);
    private final Smooth[] anim = new Smooth[7];

    public KeystrokesHud() {
        super("hud_keys", "Keystrokes", "Animated WASD, space and mouse display.", true, 0.01f, 0.62f);
        for (int i = 0; i < anim.length; i++) anim[i] = new Smooth(0f, 18f);
    }

    @Override protected boolean usesBackground() { return false; }
    @Override protected int width(TextRenderer tr) { return K * 3 + GAP * 2; }
    @Override protected int height(TextRenderer tr) { return K * 2 + GAP + (space.value ? K / 2 + GAP : 0) + (mouse.value ? K + GAP : 0); }

    private boolean down(KeyBinding k) {
        return MinecraftClient.getInstance().currentScreen == null && k.isPressed();
    }

    @Override
    protected void draw(DrawContext ctx, TextRenderer tr, float dt, float alpha) {
        MinecraftClient mc = MinecraftClient.getInstance();
        var o = mc.options;
        boolean noScreen = mc.currentScreen == null;
        boolean lmb = noScreen && GLFW.glfwGetMouseButton(mc.getWindow().getHandle(), GLFW.GLFW_MOUSE_BUTTON_LEFT) == GLFW.GLFW_PRESS;
        boolean rmb = noScreen && GLFW.glfwGetMouseButton(mc.getWindow().getHandle(), GLFW.GLFW_MOUSE_BUTTON_RIGHT) == GLFW.GLFW_PRESS;
        key(ctx, tr, 0, K + GAP, 0, K, K, "W", down(o.forwardKey), 0, dt, alpha);
        key(ctx, tr, 1, 0, K + GAP, K, K, "A", down(o.leftKey), 1, dt, alpha);
        key(ctx, tr, 2, K + GAP, K + GAP, K, K, "S", down(o.backKey), 2, dt, alpha);
        key(ctx, tr, 3, (K + GAP) * 2, K + GAP, K, K, "D", down(o.rightKey), 3, dt, alpha);
        int y = (K + GAP) * 2;
        if (mouse.value) {
            int w = (K * 3 + GAP * 2 - GAP) / 2;
            key(ctx, tr, 4, 0, y, w, K, "LMB", lmb, 4, dt, alpha);
            key(ctx, tr, 5, w + GAP, y, w, K, "RMB", rmb, 5, dt, alpha);
            y += K + GAP;
        }
        if (space.value) {
            key(ctx, tr, 6, 0, y, K * 3 + GAP * 2, K / 2, "", down(o.jumpKey), 6, dt, alpha);
        }
    }

    private void key(DrawContext ctx, TextRenderer tr, int idx, int x, int y, int w, int h, String label, boolean pressed, int phase, float dt, float alpha) {
        Smooth a = anim[idx];
        a.set(pressed ? 1f : 0f);
        float k = a.update(dt);
        int c = color.at(phase * 0.15f);
        int base = ((int) (alpha * 255 * (0.42f + 0.1f * k)) << 24) | Colors.lerp(0x0B0B12, c, 0.55f * k);
        float grow = k * 1.2f;
        if (k > 0.02f) Draw.glow(ctx, x, y, w, h, 4, c, alpha * k * 0.9f, 3, 4);
        Draw.round(ctx, x - grow * 0.3f, y - grow * 0.3f, w + grow * 0.6f, h + grow * 0.6f, 4, base);
        if (!label.isEmpty()) {
            int tc = Colors.lerp(0xC8C8D2, 0xFFFFFF, k);
            Draw.text(ctx, tr, label, x + (w - tr.getWidth(label)) / 2f, y + (h - 8) / 2f + 0.5f, Draw.fade(0xFF000000 | tc, alpha), k > 0.5f);
        } else {
            int bw = w - 16;
            Draw.round(ctx, x + 8, y + h / 2f - 1, bw, 2, 1, Draw.fade(0xFF000000 | Colors.lerp(0x8A8A96, 0xFFFFFF, k), alpha));
        }
    }
}
