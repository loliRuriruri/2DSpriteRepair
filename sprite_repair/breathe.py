"""Anatomy-aware Deterministic Idle 'Breathe' Loop Generator for SpriteRepair.

Inspired by aldegad/sprite-gen (v2.0 Breathe layer):
- Finds neck/head bottleneck so head pixels stay 100% bit-identical
- Applies continuous vertical squash & stretch with torso expansion
- Deterministic, pixel-true integer mapping without blurring or antialiasing damage
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from PIL import Image


@dataclass
class Anatomy:
    width: int
    height: int
    axis_x: int
    rigid_row: int
    basis_rows: int
    torso_half: int
    max_half: int
    rigid_u: float


def _solid_bbox(img: Image.Image, alpha_threshold: int = 64) -> tuple[int, int, int, int] | None:
    alpha = img.split()[-1]
    mask = alpha.point(lambda p: 255 if p >= alpha_threshold else 0)
    return mask.getbbox()


def analyze_anatomy(frame: Image.Image, alpha_threshold: int = 64) -> Anatomy:
    box = _solid_bbox(frame, alpha_threshold)
    if not box:
        w, h = frame.size
        return Anatomy(w, h, w // 2, h // 3, max(1, h * 2 // 3), w // 4, w // 2, 0.67)

    x0, y0, x1, y1 = box
    width = x1 - x0
    height = y1 - y0
    px = frame.load()

    # 1. Axis X: centroid of solid pixels
    total = 0
    acc_x = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if px[x, y][3] >= alpha_threshold:
                acc_x += (x - x0)
                total += 1
    cx = acc_x // max(1, total)

    # 2. Width profile: continuous solid run passing through or closest to cx
    profile: list[int] = []
    max_half = 1
    for y in range(y0, y1):
        # find seed near cx
        seed = None
        if px[x0 + cx, y][3] >= alpha_threshold:
            seed = cx
        else:
            best_d = 999999
            for i in range(width):
                if px[x0 + i, y][3] >= alpha_threshold:
                    d = abs(i - cx)
                    if d < best_d:
                        best_d = d
                        seed = i
        if seed is None:
            profile.append(0)
            continue
        lo = seed
        while lo > 0 and px[x0 + lo - 1, y][3] >= alpha_threshold:
            lo -= 1
        hi = seed
        while hi < width - 1 and px[x0 + hi + 1, y][3] >= alpha_threshold:
            hi += 1
        run_len = hi - lo + 1
        profile.append(run_len)
        half = max(abs(hi - cx), abs(lo - cx))
        if half > max_half:
            max_half = half

    # 3. Find neck bottleneck in top 15% to 60% of height
    neck_row = int(height * 0.35)
    best_prominence = -1.0
    min_search = max(2, int(height * 0.15))
    max_search = min(height - 2, int(height * 0.60))

    for i in range(min_search, max_search):
        val = profile[i]
        if val <= 0:
            continue
        left_max = max(profile[max(0, i - int(height * 0.2)):i] or [val])
        right_max = max(profile[i + 1:min(height, i + int(height * 0.25))] or [val])
        prominence = min(left_max, right_max) - val
        if prominence > best_prominence and val < left_max * 0.92:
            best_prominence = prominence
            neck_row = i

    rigid_row = max(1, neck_row)
    rigid_u = 1.0 - (rigid_row / max(1, height - 1))
    torso_half = max(4, max_half // 2)

    return Anatomy(
        width=width,
        height=height,
        axis_x=cx,
        rigid_row=rigid_row,
        basis_rows=max(1, height - rigid_row),
        torso_half=torso_half,
        max_half=max_half,
        rigid_u=rigid_u,
    )


def _wave(t: float) -> float:
    """Primary breath waveform: smooth sine with gentle inhalation peak."""
    return 0.86 * math.sin(2.0 * math.pi * t) + 0.14 * math.sin(4.0 * math.pi * t)


def _smoothstep(a: float, b: float, x: float) -> float:
    if b <= a:
        return 1.0 if x >= b else 0.0
    u = min(1.0, max(0.0, (x - a) / (b - a)))
    return u * u * (3.0 - 2.0 * u)


def _warp_phase(
    frame: Image.Image,
    anat: Anatomy,
    depth: float,
    lag: float,
    t: float,
    depth_x: float | None = None,
) -> Image.Image:
    box = _solid_bbox(frame)
    if not box:
        return frame.copy()

    x0, y0, x1, y1 = box
    width = x1 - x0
    height = y1 - y0
    body = frame.convert("RGBA").crop(box)
    src = body.load()
    anchor_x = x0 + anat.axis_x
    baseline = y1

    ru = anat.rigid_u
    taper = 0.055
    foot = 0.28
    band = max(1.5, taper * height) / max(1, height)
    foot_top = foot * ru

    def env(u: float) -> float:
        return _smoothstep(0.0, foot_top, u) * (1.0 - _smoothstep(ru - band, ru + band, u))

    # amplitude normalization
    total_env = sum(env(j / max(1, height - 1)) for j in range(height))
    norm = anat.basis_rows / total_env if total_env > 1e-6 else 0.0
    dx_amp = depth if depth_x is None else depth_x

    def gain(u: float, d: float) -> float:
        e = env(u)
        if e <= 0.0:
            return 0.0
        return d * norm * _wave(t - lag * min(1.0, u / max(1e-6, ru))) * e

    # Vertical cumulative mapping
    heights: list[float] = []
    acc = 0.0
    for j in range(height):
        u = 1.0 - j / max(1, height - 1)
        g = gain(u, depth)
        acc += 1.0 if g == 0.0 else 1.0 / (1.0 + g)
        heights.append(acc)

    total_scaled = max(1, int(round(acc)))
    out = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    dst = out.load()
    y_cursor = baseline - total_scaled
    prev = 0

    for j in range(height):
        u = 1.0 - j / max(1, height - 1)
        cur = int(round(heights[j]))
        reps = max(0, cur - prev)
        prev = cur
        if reps == 0:
            continue

        g = gain(u, dx_amp)
        if g == 0.0:
            # Rigid head: bit-identical coordinate preservation
            row_map = [(x0 + i, i) for i in range(width)]
        else:
            # Torso: horizontal expansion/compression anchored on axis_x
            dens = [max(0.05, 1.0 + g) for _ in range(width)]
            edge = [0.0]
            for d in dens:
                edge.append(edge[-1] + d)
            origin = edge[anat.axis_x]
            lo = int(round(edge[0] - origin))
            hi = int(round(edge[width] - origin))
            row_map = []
            idx = 0
            for ox in range(lo, hi):
                while idx < width - 1 and (edge[idx + 1] - origin) <= ox:
                    idx += 1
                row_map.append((anchor_x + ox, idx))

        # Paste reps rows
        for rep in range(reps):
            dst_y = y_cursor
            y_cursor += 1
            if 0 <= dst_y < frame.height:
                for dst_x, src_x in row_map:
                    if 0 <= dst_x < frame.width and 0 <= src_x < width:
                        c = src[src_x, j]
                        if c[3] > 0:
                            dst[dst_x, dst_y] = c

    return out


def generate_breathe_loop(
    frame: Image.Image,
    num_frames: int = 12,
    depth: float = 0.05,
    lag: float = 0.08,
) -> list[Image.Image]:
    """
    Generate a seamless breathing loop of `num_frames` from a single still frame.
    Head is bit-identical; chest and body expand and compress deterministically.
    """
    num_frames = max(4, min(36, int(num_frames)))
    depth = max(0.01, min(0.15, float(depth)))
    lag = max(0.0, min(0.3, float(lag)))

    anat = analyze_anatomy(frame)
    loop: list[Image.Image] = []
    for i in range(num_frames):
        phase = i / float(num_frames)
        warped = _warp_phase(frame, anat, depth=depth, lag=lag, t=phase)
        loop.append(warped)
    return loop
