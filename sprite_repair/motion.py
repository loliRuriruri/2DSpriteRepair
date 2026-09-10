"""Procedural Motion Engine for 2D Game Sprites.

Supports 7 procedural animation motions from a single frame:
1. breathe: Idle breathing loop with rigid head preservation
2. jump: Jump preparation squash -> launch stretch -> apex -> descent -> impact landing squash -> recover
3. hit: Knockback tilt & flash -> high-frequency damped vibration -> stagger recover
4. hover: Gentle sine-wave vertical float -> horizontal sway -> subtle tilt
5. charge: Power wind-up crouch -> progressive high-frequency rumble & vibration
6. bounce: Elastic double-bounce with exaggerated squash & stretch
7. down: Knockdown backward rotation -> ground bounce -> flat rest
"""

from __future__ import annotations

import math
from typing import Any
from PIL import Image

from sprite_repair.breathe import (
    Anatomy,
    analyze_anatomy,
    _solid_bbox,
    _warp_phase,
    _smoothstep,
    _wave,
)


def _apply_tint(img: Image.Image, r_add: int, g_add: int, b_add: int) -> Image.Image:
    """Add color tint while preserving alpha."""
    if r_add == 0 and g_add == 0 and b_add == 0:
        return img
    out = img.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 0:
                nr = min(255, max(0, r + r_add))
                ng = min(255, max(0, g + g_add))
                nb = min(255, max(0, b + b_add))
                px[x, y] = (nr, ng, nb, a)
    return out


def _affine_warp(
    frame: Image.Image,
    anat: Anatomy,
    dx: float = 0.0,
    dy: float = 0.0,
    stretch_x: float = 0.0,
    stretch_y: float = 0.0,
    tilt_deg: float = 0.0,
    anchor_y_mode: str = "foot",  # "foot", "center", "neck"
) -> Image.Image:
    """
    Apply procedural physics transform anchored around foot/center:
    - stretch_x, stretch_y: squash & stretch relative to anchor
    - dx, dy: translation
    - tilt_deg: rotation angle around anchor
    """
    box = _solid_bbox(frame)
    if not box:
        return frame.copy()

    x0, y0, x1, y1 = box
    cx = x0 + anat.axis_x
    if anchor_y_mode == "foot":
        cy = y1
    elif anchor_y_mode == "neck":
        cy = y0 + anat.rigid_row
    else:
        cy = (y0 + y1) // 2

    w, h = frame.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dst = out.load()
    src = frame.load()

    # Precalculate transform matrices
    rad = math.radians(-tilt_deg)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    sx = max(0.2, 1.0 + stretch_x)
    sy = max(0.2, 1.0 + stretch_y)

    # Inverse mapping for pixel-true nearest sampling
    for y in range(h):
        for x in range(w):
            # 1. Un-translate
            tx = x - dx - cx
            ty = y - dy - cy

            # 2. Un-rotate
            rx = tx * cos_r - ty * sin_r
            ry = tx * sin_r + ty * cos_r

            # 3. Un-scale
            ox = int(round(rx / sx + cx))
            oy = int(round(ry / sy + cy))

            if 0 <= ox < w and 0 <= oy < h:
                c = src[ox, oy]
                if c[3] > 0:
                    dst[x, y] = c

    return out


def generate_motion_sequence(
    frame: Image.Image,
    motion_type: str = "breathe",
    num_frames: int = 12,
    intensity: float = 1.0,
    options: dict[str, Any] | None = None,
) -> tuple[list[Image.Image], dict[str, Any]]:
    """
    Generate procedural animation frames from a single frame.
    Returns (frames, metadata).
    """
    opts = options or {}
    intensity = max(0.2, min(3.0, float(intensity)))
    anat = analyze_anatomy(frame)
    box = _solid_bbox(frame) or (0, 0, frame.width, frame.height)
    char_h = box[3] - box[1]

    frames: list[Image.Image] = []
    mtype = (motion_type or "breathe").lower().strip()

    if mtype == "breathe":
        num_frames = max(4, min(36, int(num_frames or 12)))
        depth = 0.05 * intensity
        lag = 0.08
        for i in range(num_frames):
            phase = i / float(num_frames)
            img = _warp_phase(frame, anat, depth=depth, lag=lag, t=phase)
            frames.append(img)

    elif mtype == "jump":
        num_frames = max(8, min(36, int(num_frames or 14)))
        jump_h = max(10.0, char_h * 0.22 * intensity)

        for i in range(num_frames):
            t = i / float(num_frames)
            if t < 0.15:
                # Anticipation / Crouch
                p = t / 0.15
                sy = -0.16 * math.sin(math.pi * p) * intensity
                sx = 0.12 * math.sin(math.pi * p) * intensity
                dy = 0.0
            elif t < 0.48:
                # Ascent Launch
                u = (t - 0.15) / 0.33
                dy = -jump_h * math.sin(math.pi * 0.5 * u)
                sy = 0.20 * (1.0 - u * 0.7) * intensity
                sx = -0.10 * (1.0 - u * 0.7) * intensity
            elif t < 0.72:
                # Descent
                u = (t - 0.48) / 0.24
                dy = -jump_h * math.cos(math.pi * 0.5 * u)
                sy = 0.14 * u * intensity
                sx = -0.08 * u * intensity
            elif t < 0.88:
                # Impact Landing Squash
                u = (t - 0.72) / 0.16
                dy = 0.0
                sy = -0.24 * math.sin(math.pi * u) * intensity
                sx = 0.18 * math.sin(math.pi * u) * intensity
            else:
                # Recover
                u = (t - 0.88) / 0.12
                dy = 0.0
                sy = 0.06 * (1.0 - u) * intensity
                sx = -0.04 * (1.0 - u) * intensity

            img = _affine_warp(frame, anat, dx=0, dy=dy, stretch_x=sx, stretch_y=sy, anchor_y_mode="foot")
            frames.append(img)

    elif mtype == "hit":
        num_frames = max(6, min(24, int(num_frames or 10)))
        knock_dist = max(6.0, char_h * 0.08 * intensity)

        for i in range(num_frames):
            t = i / float(num_frames)
            if t < 0.22:
                # Knockback impact
                u = t / 0.22
                dx = -knock_dist * (1.0 - u)
                dy = -2.0 * math.sin(math.pi * u) * intensity
                tilt = -8.0 * (1.0 - u) * intensity
                # Flash tint on frame 0 & 1
                r_tint, g_tint, b_tint = (120, 40, 40) if i <= 1 else (0, 0, 0)
            elif t < 0.75:
                # Damped vibration
                u = (t - 0.22) / 0.53
                decay = math.exp(-3.5 * u)
                dx = 5.0 * math.sin(2.0 * math.pi * 5.0 * u) * decay * intensity
                dy = 0.0
                tilt = 2.0 * math.sin(2.0 * math.pi * 3.0 * u) * decay * intensity
                r_tint, g_tint, b_tint = 0, 0, 0
            else:
                # Recover
                u = (t - 0.75) / 0.25
                dx = -1.0 * (1.0 - u)
                dy = 0.0
                tilt = 0.0
                r_tint, g_tint, b_tint = 0, 0, 0

            img = _affine_warp(frame, anat, dx=dx, dy=dy, tilt_deg=tilt, anchor_y_mode="foot")
            if r_tint > 0:
                img = _apply_tint(img, r_tint, g_tint, b_tint)
            frames.append(img)

    elif mtype == "hover":
        num_frames = max(8, min(36, int(num_frames or 16)))
        float_amp = max(4.0, char_h * 0.07 * intensity)
        sway_amp = max(2.0, char_h * 0.03 * intensity)

        for i in range(num_frames):
            t = i / float(num_frames)
            dy = -float_amp * math.sin(2.0 * math.pi * t)
            dx = sway_amp * math.sin(2.0 * math.pi * t - math.pi * 0.5)
            tilt = 3.0 * math.cos(2.0 * math.pi * t) * intensity
            sy = 0.03 * math.sin(2.0 * math.pi * t) * intensity
            sx = -0.02 * math.sin(2.0 * math.pi * t) * intensity

            img = _affine_warp(frame, anat, dx=dx, dy=dy, stretch_x=sx, stretch_y=sy, tilt_deg=tilt, anchor_y_mode="center")
            frames.append(img)

    elif mtype == "charge":
        num_frames = max(8, min(36, int(num_frames or 14)))

        for i in range(num_frames):
            t = i / float(num_frames)
            # Increasing crouch
            sy = -0.16 * t * intensity
            sx = 0.12 * t * intensity
            # Increasing high-frequency rumble
            freq = 3.0 + 8.0 * t
            shake = 3.0 * t * math.sin(2.0 * math.pi * freq * t) * intensity
            img = _affine_warp(frame, anat, dx=shake, dy=0, stretch_x=sx, stretch_y=sy, anchor_y_mode="foot")
            # Energy flash at end
            if i >= num_frames - 2:
                img = _apply_tint(img, 70, 70, 100)
            frames.append(img)

    elif mtype == "bounce":
        num_frames = max(8, min(36, int(num_frames or 16)))
        h1 = max(5.0, char_h * 0.10 * intensity)
        h2 = max(10.0, char_h * 0.18 * intensity)

        for i in range(num_frames):
            t = i / float(num_frames)
            if t < 0.44:
                # Bounce 1 (Small)
                u = t / 0.44
                dy = -h1 * math.sin(math.pi * u)
                sy = 0.10 * (0.5 - abs(u - 0.5)) * intensity
                sx = -0.06 * (0.5 - abs(u - 0.5)) * intensity
            elif t < 0.88:
                # Bounce 2 (Big)
                u = (t - 0.44) / 0.44
                dy = -h2 * math.sin(math.pi * u)
                sy = 0.16 * (0.5 - abs(u - 0.5)) * intensity
                sx = -0.10 * (0.5 - abs(u - 0.5)) * intensity
            else:
                # Land settle
                u = (t - 0.88) / 0.12
                dy = 0.0
                sy = -0.10 * math.sin(math.pi * u) * intensity
                sx = 0.08 * math.sin(math.pi * u) * intensity

            img = _affine_warp(frame, anat, dx=0, dy=dy, stretch_x=sx, stretch_y=sy, anchor_y_mode="foot")
            frames.append(img)

    elif mtype == "down":
        num_frames = max(6, min(24, int(num_frames or 10)))

        for i in range(num_frames):
            t = i / float(num_frames)
            if t < 0.55:
                # Fall backward with rotation
                u = t / 0.55
                tilt = -75.0 * (u ** 1.5) * intensity
                dx = -12.0 * u * intensity
                dy = (char_h * 0.20) * (u ** 2)
                sy = -0.15 * u * intensity
                sx = 0.10 * u * intensity
            elif t < 0.78:
                # Floor hit rebound bounce
                u = (t - 0.55) / 0.23
                tilt = -75.0 * intensity
                dx = -12.0 * intensity
                dy = (char_h * 0.20) - (4.0 * math.sin(math.pi * u))
                sy = -0.22 * intensity
                sx = 0.18 * intensity
            else:
                # Stay flat on ground
                tilt = -75.0 * intensity
                dx = -12.0 * intensity
                dy = char_h * 0.20
                sy = -0.20 * intensity
                sx = 0.15 * intensity

            img = _affine_warp(frame, anat, dx=dx, dy=dy, stretch_x=sx, stretch_y=sy, tilt_deg=tilt, anchor_y_mode="foot")
            frames.append(img)

    else:
        raise ValueError(f"Unknown motion_type: {motion_type}")

    info = {
        "motion_type": mtype,
        "num_frames": len(frames),
        "intensity": intensity,
        "rigid_row": anat.rigid_row,
        "rigid_u": anat.rigid_u,
    }
    return frames, info
