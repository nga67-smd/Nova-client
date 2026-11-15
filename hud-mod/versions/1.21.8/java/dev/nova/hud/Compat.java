package dev.nova.hud;

import net.minecraft.client.MinecraftClient;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.texture.NativeImage;
import net.minecraft.client.texture.NativeImageBackedTexture;
import net.minecraft.util.Identifier;

/** Matrix operations on a DrawContext; the type of its matrix stack differs between Minecraft versions. */
public final class Compat {
    private Compat() {}

    public static void push(DrawContext ctx) { ctx.getMatrices().pushMatrix(); }

    public static void translate(DrawContext ctx, float x, float y) { ctx.getMatrices().translate(x, y); }

    public static void scale(DrawContext ctx, float s) { ctx.getMatrices().scale(s, s); }

    public static void pop(DrawContext ctx) { ctx.getMatrices().popMatrix(); }

    /** Registers a picture as a game texture; the texture constructor differs between Minecraft versions. */
    public static void registerTexture(Identifier id, NativeImage img) {
        MinecraftClient.getInstance().getTextureManager().registerTexture(id, new NativeImageBackedTexture(() -> id.toString(), img));
    }
}
