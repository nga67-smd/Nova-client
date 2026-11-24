package dev.nova.hud;

import net.fabricmc.fabric.api.event.player.AttackEntityCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.entity.Entity;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.util.ActionResult;
import net.minecraft.util.math.Box;
import net.minecraft.util.math.Vec3d;
import org.lwjgl.glfw.GLFW;

import java.util.ArrayDeque;

/** Things the HUD needs to watch over time: clicks per second, combo, reach and speed. */
public final class NovaStats {
    private static final ArrayDeque<Long> LEFT = new ArrayDeque<>();
    private static final ArrayDeque<Long> RIGHT = new ArrayDeque<>();
    private static boolean leftDown, rightDown;

    private static int combo;
    private static long lastHit;
    private static double reach = -1;
    private static long reachAt;

    private static Vec3d lastPos;
    private static double speed;

    private NovaStats() {}

    public static void init() {
        AttackEntityCallback.EVENT.register((player, world, hand, entity, hit) -> {
            if (world.isClient) onAttack(player, entity);
            return ActionResult.PASS;
        });
    }

    private static void onAttack(PlayerEntity player, Entity target) {
        long now = System.currentTimeMillis();
        combo = (now - lastHit < 2500) ? combo + 1 : 1;
        lastHit = now;
        Box b = target.getBoundingBox();
        Vec3d e = player.getEyePos();
        double dx = Math.max(Math.max(b.minX - e.x, 0), e.x - b.maxX);
        double dy = Math.max(Math.max(b.minY - e.y, 0), e.y - b.maxY);
        double dz = Math.max(Math.max(b.minZ - e.z, 0), e.z - b.maxZ);
        reach = Math.sqrt(dx * dx + dy * dy + dz * dz);
        reachAt = now;
    }

    /** Once per game tick. */
    public static void tick(MinecraftClient mc) {
        PlayerEntity p = mc.player;
        if (p == null) {
            lastPos = null;
            return;
        }
        Vec3d pos = p.getPos();
        if (lastPos != null) {
            double dx = pos.x - lastPos.x, dz = pos.z - lastPos.z;
            speed = speed * 0.6 + Math.sqrt(dx * dx + dz * dz) * 20 * 0.4;      // smoothed blocks per second
        }
        lastPos = pos;
        if (p.hurtTime > 0) combo = 0;                                           // getting hit ends your combo
        if (combo > 0 && System.currentTimeMillis() - lastHit > 2500) combo = 0;
    }

    /** Once per drawn frame: counts mouse clicks. */
    public static void frame(MinecraftClient mc) {
        long window = mc.getWindow().getHandle();
        long now = System.currentTimeMillis();
        boolean l = GLFW.glfwGetMouseButton(window, GLFW.GLFW_MOUSE_BUTTON_LEFT) == GLFW.GLFW_PRESS;
        boolean r = GLFW.glfwGetMouseButton(window, GLFW.GLFW_MOUSE_BUTTON_RIGHT) == GLFW.GLFW_PRESS;
        if (l && !leftDown) LEFT.addLast(now);
        if (r && !rightDown) RIGHT.addLast(now);
        leftDown = l;
        rightDown = r;
        while (!LEFT.isEmpty() && now - LEFT.peekFirst() > 1000) LEFT.pollFirst();
        while (!RIGHT.isEmpty() && now - RIGHT.peekFirst() > 1000) RIGHT.pollFirst();
    }

    public static int leftCps() { return LEFT.size(); }
    public static int rightCps() { return RIGHT.size(); }
    public static boolean leftDown() { return leftDown; }
    public static boolean rightDown() { return rightDown; }
    public static int combo() { return combo; }
    public static double speed() { return speed; }

    /** Distance of your last hit, or -1 when there wasn't one in the last 5 seconds. */
    public static double reach() {
        return (reach >= 0 && System.currentTimeMillis() - reachAt < 5000) ? reach : -1;
    }
}
