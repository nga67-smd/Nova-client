package dev.nova.hud;

import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.gui.screen.Screen;
import net.minecraft.client.gui.widget.ButtonWidget;
import net.minecraft.client.gui.widget.SliderWidget;
import net.minecraft.text.Text;
import org.lwjgl.glfw.GLFW;

import java.util.function.BooleanSupplier;
import java.util.function.Consumer;
import java.util.function.DoubleConsumer;

/** The settings menu opened with Right Shift. */
public class NovaHudScreen extends Screen {
    private final Screen parent;

    public NovaHudScreen(Screen parent) {
        super(Text.literal("Nova HUD"));
        this.parent = parent;
    }

    @Override
    protected void init() {
        NovaConfig c = NovaConfig.get();
        int colW = 150, gap = 10, step = 24;
        int left = width / 2 - colW - gap / 2;
        int right = width / 2 + gap / 2;
        int ly = 36, ry = 36;

        // Left column: HUD elements
        addDrawableChild(toggle(left, ly, colW, "Armor HUD", () -> c.armorHud, v -> c.armorHud = v)); ly += step;
        addDrawableChild(toggle(left, ly, colW, "Armor side: left", () -> c.armorLeft, v -> c.armorLeft = v)); ly += step;
        addDrawableChild(toggle(left, ly, colW, "Armor durability", () -> c.armorDurability, v -> c.armorDurability = v)); ly += step;
        addDrawableChild(new Slider(left, ly, colW, "Armor size", 0.5, 2.0, c.armorScale, v -> c.armorScale = (float) v)); ly += step;
        addDrawableChild(toggle(left, ly, colW, "Sidebar", () -> c.showSidebar, v -> c.showSidebar = v)); ly += step;
        addDrawableChild(new Slider(left, ly, colW, "Sidebar size", 0.4, 1.5, c.sidebarScale, v -> c.sidebarScale = (float) v)); ly += step;
        addDrawableChild(new Slider(left, ly, colW, "Sidebar height", -100, 100, c.sidebarOffsetY, v -> c.sidebarOffsetY = (int) Math.round(v))); ly += step;
        addDrawableChild(toggle(left, ly, colW, "FPS", () -> c.showFps, v -> c.showFps = v)); ly += step;
        addDrawableChild(toggle(left, ly, colW, "Coordinates", () -> c.showCoords, v -> c.showCoords = v));

        // Right column: view model
        addDrawableChild(toggle(right, ry, colW, "View model", () -> c.viewModel, v -> c.viewModel = v)); ry += step;
        addDrawableChild(new Slider(right, ry, colW, "Move X", -1.0, 1.0, c.vmX, v -> c.vmX = (float) v)); ry += step;
        addDrawableChild(new Slider(right, ry, colW, "Move Y", -1.0, 1.0, c.vmY, v -> c.vmY = (float) v)); ry += step;
        addDrawableChild(new Slider(right, ry, colW, "Move Z", -1.0, 1.0, c.vmZ, v -> c.vmZ = (float) v)); ry += step;
        addDrawableChild(new Slider(right, ry, colW, "Size", 0.3, 1.5, c.vmScale, v -> c.vmScale = (float) v)); ry += step;
        addDrawableChild(new Slider(right, ry, colW, "Rotate X", -90, 90, c.vmRotX, v -> c.vmRotX = (float) v)); ry += step;
        addDrawableChild(new Slider(right, ry, colW, "Rotate Y", -90, 90, c.vmRotY, v -> c.vmRotY = (float) v)); ry += step;
        addDrawableChild(new Slider(right, ry, colW, "Rotate Z", -90, 90, c.vmRotZ, v -> c.vmRotZ = (float) v)); ry += step;
        addDrawableChild(ButtonWidget.builder(Text.literal("Reset view model"), b -> {
            c.resetViewModel();
            clearAndInit();
        }).dimensions(right, ry, colW, 20).build());

        addDrawableChild(ButtonWidget.builder(Text.literal("Done"), b -> close())
                .dimensions(width / 2 - 100, height - 28, 200, 20).build());
    }

    private ButtonWidget toggle(int x, int y, int w, String label, BooleanSupplier get, Consumer<Boolean> set) {
        return ButtonWidget.builder(text(label, get.getAsBoolean()), b -> {
            boolean now = !get.getAsBoolean();
            set.accept(now);
            b.setMessage(text(label, now));
        }).dimensions(x, y, w, 20).build();
    }

    private static Text text(String label, boolean on) {
        return Text.literal(label + ": " + (on ? "ON" : "OFF"));
    }

    @Override
    public void render(DrawContext ctx, int mouseX, int mouseY, float delta) {
        super.render(ctx, mouseX, mouseY, delta);
        ctx.drawCenteredTextWithShadow(textRenderer, title, width / 2, 14, 0xFFB66BFF);
    }

    @Override
    public boolean keyPressed(int keyCode, int scanCode, int modifiers) {
        if (keyCode == NovaHudClient.menuKeyCode() || keyCode == GLFW.GLFW_KEY_RIGHT_SHIFT) {
            close();
            return true;
        }
        return super.keyPressed(keyCode, scanCode, modifiers);
    }

    @Override
    public void close() {
        NovaConfig.get().save();
        if (client != null) client.setScreen(parent);
    }

    @Override
    public boolean shouldPause() {
        return false;
    }

    private static class Slider extends SliderWidget {
        private final String label;
        private final double min, max;
        private final DoubleConsumer setter;

        Slider(int x, int y, int w, String label, double min, double max, double current, DoubleConsumer setter) {
            super(x, y, w, 20, Text.empty(), (current - min) / (max - min));
            this.label = label;
            this.min = min;
            this.max = max;
            this.setter = setter;
            updateMessage();
        }

        @Override
        protected void updateMessage() {
            if (label == null) return; // super() calls this before the fields exist
            double v = min + value * (max - min);
            setMessage(Text.literal(label + ": " + String.format("%.2f", v)));
        }

        @Override
        protected void applyValue() {
            setter.accept(min + value * (max - min));
        }
    }
}
