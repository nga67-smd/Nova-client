package dev.nova.visuals.fx;

import dev.nova.visuals.config.Config;
import dev.nova.visuals.config.ModuleManager;
import dev.nova.visuals.config.Settings;
import dev.nova.visuals.core.Time;
import dev.nova.visuals.gfx.Frame;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderContext;
import net.fabricmc.fabric.api.client.rendering.v1.WorldRenderEvents;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.client.util.BufferAllocator;
import org.joml.Matrix4f;

/** Hooks the world render, runs every enabled effect, draws it all, and leaves the render state as it found it. */
public final class WorldFx {
    private static VertexConsumerProvider.Immediate imm;
    private static BufferAllocator allocator;

    private WorldFx() {}

    public static void init() {
        WorldRenderEvents.AFTER_TRANSLUCENT.register(WorldFx::render);
    }

    private static void render(WorldRenderContext ctx) {
        MinecraftClient mc = MinecraftClient.getInstance();
        if (mc.world == null || mc.player == null) return;
        Time.frame();
        if (imm == null) {
            allocator = new BufferAllocator(1 << 20);
            imm = VertexConsumerProvider.immediate(allocator);
        }
        float dt = Time.dt();
        Matrix4f m = new Matrix4f(ctx.matrixStack().peek().getPositionMatrix());
        var cam = ctx.camera();
        Frame f = new Frame(mc.world, mc.player, m, cam.getPos(), cam.getYaw(), cam.getPitch(),
                dev.nova.visuals.Compat.tickDelta(ctx), dt, Time.time(), imm);
        try {
            ParticleEngine.update(dt);
            RingPool.update(dt);
            ModuleManager.world(f);
            RingPool.render(f);
            ParticleEngine.render(f, Settings.bloom(), Settings.bloomSize());
        } finally {
            f.flush();                       // the layers set up and tear down their own blend/depth state
        }
        Config.autosave();
    }
}
