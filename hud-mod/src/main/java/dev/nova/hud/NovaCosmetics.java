package dev.nova.hud;

import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.client.texture.NativeImage;
import net.minecraft.client.util.SkinTextures;
import net.minecraft.util.Identifier;

import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Shows the skin and cape designed in Nova Launcher's Cosmetics tab on your own character.
 * Nova copies them to {game folder}/nova-cosmetics/ (skin.png, cape.png, model.txt) before each launch.
 */
public final class NovaCosmetics {
    private static boolean loaded;
    private static Identifier skinId, capeId;
    private static boolean slim;

    private NovaCosmetics() {}

    private static synchronized void load() {
        if (loaded) return;
        loaded = true;
        Path dir = FabricLoader.getInstance().getGameDir().resolve("nova-cosmetics");
        skinId = register(dir.resolve("skin.png"), "cosmetic_skin");
        capeId = register(dir.resolve("cape.png"), "cosmetic_cape");
        try {
            slim = "slim".equals(Files.readString(dir.resolve("model.txt")).trim());
        } catch (Exception ignored) {
            slim = false;
        }
    }

    private static Identifier register(Path file, String name) {
        if (!Files.isRegularFile(file)) return null;
        try (InputStream in = Files.newInputStream(file)) {
            NativeImage image = NativeImage.read(in);
            Identifier id = Identifier.of("nova_hud", name);
            Compat.registerTexture(id, image);
            return id;
        } catch (Exception e) {
            return null;     // a missing or broken file just means "no cosmetic"
        }
    }

    /** The local player's textures with Nova's skin and cape swapped in (the elytra uses the same picture). */
    public static SkinTextures apply(SkinTextures orig) {
        load();
        if (skinId == null && capeId == null) return orig;
        return new SkinTextures(
                skinId != null ? skinId : orig.texture(),
                skinId != null ? null : orig.textureUrl(),
                capeId != null ? capeId : orig.capeTexture(),
                capeId != null ? capeId : orig.elytraTexture(),
                skinId != null ? (slim ? SkinTextures.Model.SLIM : SkinTextures.Model.WIDE) : orig.model(),
                orig.secure());
    }
}
