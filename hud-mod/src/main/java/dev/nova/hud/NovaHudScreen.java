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

    private static int page = 0;
    private static final String[] PAGES = {"Info", "Panels", "Look", "Armor", "Hand"};
    private static final String[] POSITIONS = {"Top left", "Top right", "Bottom left", "Bottom right", "Middle left", "Middle right", "Top centre", "Bottom centre"};

    @Override
    protected void init() {
        colorLabels.clear();
        NovaConfig c = NovaConfig.get();
        int colW = 150, gap = 10, step = 24;
        int left = width / 2 - colW - gap / 2;
        int right = width / 2 + gap / 2;
        int ly = 52, ry = 52;

        // Tabs
        int tabW = 62, tx = width / 2 - (PAGES.length * (tabW + 4) - 4) / 2;
        for (int i = 0; i < PAGES.length; i++) {
            final int n = i;
            ButtonWidget t = ButtonWidget.builder(Text.literal(PAGES[i]), b -> {
                page = n;
                clearAndInit();
            }).dimensions(tx + i * (tabW + 4), 28, tabW, 18).build();
            t.active = i != page;
            addDrawableChild(t);
        }

        switch (page) {
            case 0 -> { // Info rows
                addDrawableChild(toggle(left, ly, colW, "FPS", () -> c.showFps, v -> c.showFps = v)); ly += step;
                addDrawableChild(toggle(left, ly, colW, "Ping", () -> c.showPing, v -> c.showPing = v)); ly += step;
                addDrawableChild(toggle(left, ly, colW, "CPS", () -> c.showCps, v -> c.showCps = v)); ly += step;
                addDrawableChild(toggle(left, ly, colW, "Coordinates", () -> c.showCoords, v -> c.showCoords = v)); ly += step;
                addDrawableChild(toggle(left, ly, colW, "Facing", () -> c.showDirection, v -> c.showDirection = v)); ly += step;
                addDrawableChild(toggle(left, ly, colW, "Biome", () -> c.showBiome, v -> c.showBiome = v)); ly += step;
                addDrawableChild(toggle(right, ry, colW, "Speed", () -> c.showSpeed, v -> c.showSpeed = v)); ry += step;
                addDrawableChild(toggle(right, ry, colW, "Real clock", () -> c.showClock, v -> c.showClock = v)); ry += step;
                addDrawableChild(toggle(right, ry, colW, "Game time", () -> c.showMcTime, v -> c.showMcTime = v)); ry += step;
                addDrawableChild(toggle(right, ry, colW, "Memory", () -> c.showMemory, v -> c.showMemory = v)); ry += step;
                addDrawableChild(toggle(right, ry, colW, "Combo", () -> c.showCombo, v -> c.showCombo = v)); ry += step;
                addDrawableChild(toggle(right, ry, colW, "Reach", () -> c.showReach, v -> c.showReach = v)); ry += step;
                addDrawableChild(cycle(width / 2 - 75, Math.max(ly, ry) + 4, 150, "Info panel", () -> c.anchorInfo, v -> c.anchorInfo = v));
            }
            case 1 -> { // Other panels
                addDrawableChild(toggle(left, ly, colW, "Keystrokes", () -> c.keystrokes, v -> c.keystrokes = v));
                addDrawableChild(cycle(right, ly, colW, "Keys at", () -> c.anchorKeys, v -> c.anchorKeys = v)); ly += step;
                addDrawableChild(toggle(left, ly, colW, "Potion effects", () -> c.potions, v -> c.potions = v));
                addDrawableChild(cycle(right, ly, colW, "Potions at", () -> c.anchorPotions, v -> c.anchorPotions = v)); ly += step;
                addDrawableChild(toggle(left, ly, colW, "Item counts", () -> c.itemCounts, v -> c.itemCounts = v));
                addDrawableChild(cycle(right, ly, colW, "Items at", () -> c.anchorItems, v -> c.anchorItems = v)); ly += step;
                addDrawableChild(new Slider(left, ly, colW, "Edge gap X", 0, 100, c.marginX, v -> c.marginX = (int) Math.round(v)));
                addDrawableChild(new Slider(right, ly, colW, "Edge gap Y", 0, 100, c.marginY, v -> c.marginY = (int) Math.round(v)));
            }
            case 2 -> { // Look
                addDrawableChild(colorField(left, ly, colW, "Accent", c.accent, v -> c.accent = v)); ly += step;
                addDrawableChild(colorField(left, ly, colW, "Background", c.background, v -> c.background = v)); ly += step;
                addDrawableChild(colorField(left, ly, colW, "Text", c.textColor, v -> c.textColor = v)); ly += step;
                addDrawableChild(colorField(left, ly, colW, "Labels", c.labelColor, v -> c.labelColor = v)); ly += step;
                String[][] presets = {{"Nova", "nova"}, {"Ice", "ice"}, {"Sunset", "sunset"}, {"Mint", "mint"}, {"Mono", "mono"}};
                int pw = (colW - 4) / 2;
                for (int i = 0; i < presets.length; i++) {
                    final String key = presets[i][1];
                    addDrawableChild(ButtonWidget.builder(Text.literal(presets[i][0]), b -> {
                        c.applyPreset(key);
                        clearAndInit();
                    }).dimensions(left + (i % 2) * (pw + 4), ly + (i / 2) * 22, pw, 18).build());
                }
                addDrawableChild(new Slider(right, ry, colW, "Opacity", 0, 1, c.bgOpacity, v -> c.bgOpacity = (float) v)); ry += step;
                addDrawableChild(new Slider(right, ry, colW, "Size", 0.5, 2.5, c.hudScale, v -> c.hudScale = (float) v)); ry += step;
                addDrawableChild(new Slider(right, ry, colW, "Width (min)", 0, 200, c.minWidth, v -> c.minWidth = (int) Math.round(v))); ry += step;
                addDrawableChild(new Slider(right, ry, colW, "Corners", 0, 8, c.radius, v -> c.radius = (int) Math.round(v))); ry += step;
                addDrawableChild(new Slider(right, ry, colW, "Border", 0, 4, c.border, v -> c.border = (int) Math.round(v))); ry += step;
                addDrawableChild(new Slider(right, ry, colW, "Padding", 1, 12, c.padding, v -> c.padding = (int) Math.round(v))); ry += step;
                addDrawableChild(toggle(right, ry, 73, "Shadow", () -> c.shadow, v -> c.shadow = v));
                addDrawableChild(toggle(right + 77, ry, 73, "Bar", () -> c.accentBar, v -> c.accentBar = v));
            }
            case 3 -> { // Armor and sidebar
                addDrawableChild(toggle(left, ly, colW, "Armor HUD", () -> c.armorHud, v -> c.armorHud = v)); ly += step;
                addDrawableChild(toggle(left, ly, colW, "Armor side: left", () -> c.armorLeft, v -> c.armorLeft = v)); ly += step;
                addDrawableChild(toggle(left, ly, colW, "Armor durability", () -> c.armorDurability, v -> c.armorDurability = v)); ly += step;
                addDrawableChild(new Slider(left, ly, colW, "Armor size", 0.5, 2.0, c.armorScale, v -> c.armorScale = (float) v));
                addDrawableChild(toggle(right, ry, colW, "Sidebar", () -> c.showSidebar, v -> c.showSidebar = v)); ry += step;
                addDrawableChild(new Slider(right, ry, colW, "Sidebar size", 0.4, 1.5, c.sidebarScale, v -> c.sidebarScale = (float) v)); ry += step;
                addDrawableChild(new Slider(right, ry, colW, "Sidebar height", -100, 100, c.sidebarOffsetY, v -> c.sidebarOffsetY = (int) Math.round(v)));
            }
            default -> { // Held item
                addDrawableChild(toggle(left, ly, colW, "View model", () -> c.viewModel, v -> c.viewModel = v)); ly += step;
                addDrawableChild(new Slider(left, ly, colW, "Move X", -1.0, 1.0, c.vmX, v -> c.vmX = (float) v)); ly += step;
                addDrawableChild(new Slider(left, ly, colW, "Move Y", -1.0, 1.0, c.vmY, v -> c.vmY = (float) v)); ly += step;
                addDrawableChild(new Slider(left, ly, colW, "Move Z", -1.0, 1.0, c.vmZ, v -> c.vmZ = (float) v)); ly += step;
                addDrawableChild(new Slider(right, ry, colW, "Size", 0.3, 1.5, c.vmScale, v -> c.vmScale = (float) v)); ry += step;
                addDrawableChild(new Slider(right, ry, colW, "Rotate X", -90, 90, c.vmRotX, v -> c.vmRotX = (float) v)); ry += step;
                addDrawableChild(new Slider(right, ry, colW, "Rotate Y", -90, 90, c.vmRotY, v -> c.vmRotY = (float) v)); ry += step;
                addDrawableChild(new Slider(right, ry, colW, "Rotate Z", -90, 90, c.vmRotZ, v -> c.vmRotZ = (float) v)); ry += step;
                addDrawableChild(ButtonWidget.builder(Text.literal("Reset view model"), b -> {
                    c.resetViewModel();
                    clearAndInit();
                }).dimensions(left, ly, colW, 20).build());
            }
        }

        addDrawableChild(ButtonWidget.builder(Text.literal("Done"), b -> close())
                .dimensions(width / 2 - 100, height - 28, 200, 20).build());
    }

    private ButtonWidget cycle(int x, int y, int w, String label, java.util.function.IntSupplier get, java.util.function.IntConsumer set) {
        return ButtonWidget.builder(Text.literal(label + ": " + POSITIONS[Math.floorMod(get.getAsInt(), 8)]), b -> {
            int now = (get.getAsInt() + 1) % 8;
            set.accept(now);
            b.setMessage(Text.literal(label + ": " + POSITIONS[now]));
        }).dimensions(x, y, w, 20).build();
    }

    /** A box where a color is typed as #RRGGBB; it applies as soon as it is a complete color. */
    private net.minecraft.client.gui.widget.TextFieldWidget colorField(int x, int y, int w, String label, int current, java.util.function.IntConsumer set) {
        net.minecraft.client.gui.widget.TextFieldWidget f = new net.minecraft.client.gui.widget.TextFieldWidget(textRenderer, x + 70, y, w - 70, 20, Text.literal(label));
        f.setMaxLength(7);
        f.setText(String.format("#%06X", current & 0xFFFFFF));
        f.setChangedListener(t -> {
            String h = t.startsWith("#") ? t.substring(1) : t;
            if (h.length() == 6) {
                try {
                    set.accept(Integer.parseInt(h, 16));
                } catch (NumberFormatException ignored) {
                    // not a color yet
                }
            }
        });
        colorLabels.add(new Object[]{label, x, y});
        return f;
    }

    private final java.util.List<Object[]> colorLabels = new java.util.ArrayList<>();

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
        ctx.drawCenteredTextWithShadow(textRenderer, title, width / 2, 12, 0xFFB66BFF);
        for (Object[] l : colorLabels) ctx.drawTextWithShadow(textRenderer, (String) l[0], (int) l[1], (int) l[2] + 6, 0xFFCFC4EA);
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
