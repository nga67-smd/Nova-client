package dev.nova.visuals.gfx;

import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.util.math.MathHelper;
import net.minecraft.util.math.Vec3d;

/** Where a player is and which way the body faces, so shapes can be described in the player's own directions. */
public final class Pose {
    /** Player origin (feet) relative to the camera. */
    public final float ox, oy, oz;
    /** Horizontal unit vectors: the player's right and forward. */
    public final float rx, rz, fx, fz;
    public final float yawDeg;
    public final boolean sneaking, onGround;
    public final double wx, wy, wz;

    public Pose(Frame f, PlayerEntity p) { this(f, p, false); }

    /** headTurn: use the way the head faces instead of the body. */
    public Pose(Frame f, PlayerEntity p, boolean headTurn) {
        Vec3d pos = p.getLerpedPos(f.tickDelta);
        wx = pos.x; wy = pos.y; wz = pos.z;
        ox = (float) (pos.x - f.cam.x);
        oy = (float) (pos.y - f.cam.y);
        oz = (float) (pos.z - f.cam.z);
        yawDeg = headTurn ? MathHelper.lerpAngleDegrees(f.tickDelta, p.prevHeadYaw, p.headYaw)
                : MathHelper.lerpAngleDegrees(f.tickDelta, p.prevBodyYaw, p.bodyYaw);
        float y = (float) Math.toRadians(yawDeg);
        fx = -(float) Math.sin(y);
        fz = (float) Math.cos(y);
        rx = -(float) Math.cos(y);
        rz = -(float) Math.sin(y);
        sneaking = p.isSneaking();
        onGround = p.isOnGround();
    }

    /** Local (right, up, forward) to camera-relative world x. */
    public float x(float r, float fwd) { return ox + rx * r + fx * fwd; }
    public float y(float up) { return oy + up; }
    public float z(float r, float fwd) { return oz + rz * r + fz * fwd; }

    /** The same point in absolute world coordinates (for particles). */
    public double ax(float r, float fwd) { return wx + rx * r + fx * fwd; }
    public double az(float r, float fwd) { return wz + rz * r + fz * fwd; }
}
