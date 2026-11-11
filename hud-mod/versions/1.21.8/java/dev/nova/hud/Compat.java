package dev.nova.hud;

import net.minecraft.client.gui.DrawContext;

/** Matrix operations on a DrawContext; the type of its matrix stack differs between Minecraft versions. */
public final class Compat {
    private Compat() {}

    public static void push(DrawContext ctx) { ctx.getMatrices().pushMatrix(); }

    public static void translate(DrawContext ctx, float x, float y) { ctx.getMatrices().translate(x, y); }

    public static void scale(DrawContext ctx, float s) { ctx.getMatrices().scale(s, s); }

    public static void pop(DrawContext ctx) { ctx.getMatrices().popMatrix(); }
}
