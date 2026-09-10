"""4-Pass Soft-Alpha Chroma Key & Despill Engine for SpriteRepair.

Inspired by aldegad/sprite-gen (v1.13 4-pass chain):
1. Key distance hard cut
2. Chebyshev distance frontier growth
3. Soft-alpha unmix: Observed = (1-k)*Subject + k*Key  =>  Coverage = 1-k, despilled RGB + partial alpha
4. Trapped-spill despill: cleans up key reflections/spill without punching pinholes
"""

from __future__ import annotations

import math
from typing import Any
from PIL import Image


def color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Euclidean distance between two RGB colors."""
    dr = c1[0] - c2[0]
    dg = c1[1] - c2[1]
    db = c1[2] - c2[2]
    return math.sqrt(dr * dr + dg * dg + db * db)


def _key_channel_split(chroma_key: tuple[int, int, int]) -> tuple[list[int], list[int]]:
    """Determine which channels the chroma key saturates and which it leaves dark."""
    keyed_channels = [i for i, val in enumerate(chroma_key) if val >= 180]
    unkeyed_channels = [i for i, val in enumerate(chroma_key) if val < 80]
    if not keyed_channels or not unkeyed_channels:
        # Fallback for custom solid backgrounds (e.g. gray, pastel)
        max_v = max(chroma_key)
        min_v = min(chroma_key)
        if max_v - min_v > 30:
            keyed_channels = [i for i, val in enumerate(chroma_key) if val >= max_v - 20]
            unkeyed_channels = [i for i, val in enumerate(chroma_key) if val <= min_v + 20]
        else:
            return [], []
    return keyed_channels, unkeyed_channels


def key_tint_score(color: tuple[int, int, int], chroma_key: tuple[int, int, int]) -> float:
    """Calculate tint score towards the chroma key: positive means biased towards the key color."""
    keyed_channels, unkeyed_channels = _key_channel_split(chroma_key)
    if not keyed_channels or not unkeyed_channels:
        # Generic distance-based tint score
        dist = color_distance(color, chroma_key)
        return max(0.0, 100.0 - dist)
    keyed_avg = sum(color[i] for i in keyed_channels) / len(keyed_channels)
    unkeyed_avg = sum(color[i] for i in unkeyed_channels) / len(unkeyed_channels)
    return keyed_avg - unkeyed_avg


def despill_color(
    color: tuple[int, int, int],
    chroma_key: tuple[int, int, int],
    key_tint: float,
    tint: float,
) -> tuple[float, tuple[int, int, int]]:
    """Estimate the key fraction k = tint / key_tint, recovering subject coverage (1-k) and despilled RGB."""
    if key_tint <= 0:
        return 1.0, color
    k = max(0.0, min(tint / key_tint, 1.0))
    coverage = 1.0 - k
    if coverage <= 0.001:
        return 0.0, (0, 0, 0)
    despilled = tuple(
        min(255, max(0, int(round((color[i] - k * chroma_key[i]) / coverage))))
        for i in range(3)
    )
    return coverage, (despilled[0], despilled[1], despilled[2])


def unmix_key_blend(
    color: tuple[int, int, int],
    alpha: int,
    chroma_key: tuple[int, int, int],
    key_tint: float,
    tint: float,
) -> tuple[int, int, int, int]:
    """Separate a key/subject blend pixel into despilled RGB + partial alpha."""
    coverage, despilled = despill_color(color, chroma_key, key_tint, tint)
    out_alpha = min(255, max(0, int(round(alpha * coverage))))
    if out_alpha <= 0:
        return (0, 0, 0, 0)
    return (despilled[0], despilled[1], despilled[2], out_alpha)


def detect_chroma_key(img: Image.Image, tolerance: float = 40.0) -> tuple[int, int, int] | None:
    """Detect solid chroma background from image 4 corners."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    corners = [
        px[0, 0][:3],
        px[w - 1, 0][:3],
        px[0, h - 1][:3],
        px[w - 1, h - 1][:3],
    ]
    c0 = corners[0]
    # Check similarity with other corners
    matches = [c for c in corners if color_distance(c, c0) <= tolerance]
    if len(matches) >= 2:
        return c0
    return None


def remove_chroma_background_soft(
    image: Image.Image,
    chroma_key: tuple[int, int, int] | None = None,
    threshold: float = 64.0,
    fringe_threshold: float = 110.0,
    fringe_delta: float = 15.0,
    *,
    unmix_reach: int = 4,
    spill_max_fraction: float = 0.015,
) -> tuple[Image.Image, dict[str, Any]]:
    """
    Remove solid / chroma background using 4-pass soft-alpha unmix & trapped-spill despill.
    Preserves antialiased hair, silhouettes, and fine edges with real partial alpha.
    """
    rgba = image.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()

    if chroma_key is None:
        chroma_key = detect_chroma_key(rgba, tolerance=threshold)
        if chroma_key is None:
            # Check if there is already alpha transparency
            has_alpha = False
            for y in range(0, h, max(1, h // 20)):
                for x in range(0, w, max(1, w // 20)):
                    if px[x, y][3] < 240:
                        has_alpha = True
                        break
                if has_alpha:
                    break
            if has_alpha:
                return rgba, {"modified": False, "reason": "already_transparent"}
            # Default to top-left corner
            chroma_key = px[0, 0][:3]

    kr, kg, kb = chroma_key
    key_tint = key_tint_score(chroma_key, chroma_key)
    if key_tint <= 0:
        key_tint = 100.0

    # Classification buffers
    KEYED = 0
    SUBJECT = 1
    BLEND_IN_BAND = 2
    BLEND_OUT_OF_BAND = 3

    classes = [bytearray(w) for _ in range(h)]
    depths = [bytearray([255] * w) for _ in range(h)]
    out_img = rgba.copy()
    out_px = out_img.load()

    keyed_count = 0
    frontier: list[tuple[int, int]] = []

    # Pass 1: Classification & Hard Key Cut
    for y in range(h):
        row_class = classes[y]
        row_depth = depths[y]
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                row_class[x] = KEYED
                row_depth[x] = 0
                out_px[x, y] = (0, 0, 0, 0)
                frontier.append((x, y))
                keyed_count += 1
                continue

            dist = color_distance((r, g, b), chroma_key)
            if dist <= threshold:
                row_class[x] = KEYED
                row_depth[x] = 0
                out_px[x, y] = (0, 0, 0, 0)
                frontier.append((x, y))
                keyed_count += 1
            else:
                tint = key_tint_score((r, g, b), chroma_key)
                if tint < fringe_delta:
                    row_class[x] = SUBJECT
                elif dist <= fringe_threshold:
                    row_class[x] = BLEND_IN_BAND
                else:
                    row_class[x] = BLEND_OUT_OF_BAND

    if keyed_count == 0:
        return rgba, {"modified": False, "keyed_count": 0}

    # Pass 2: Chebyshev 8-way Distance Growth from Keyed Border
    current_frontier = frontier
    for depth in range(1, unmix_reach + 1):
        next_frontier: list[tuple[int, int]] = []
        for fx, fy in current_frontier:
            for dy in (-1, 0, 1):
                ny = fy + dy
                if 0 <= ny < h:
                    row_depth = depths[ny]
                    for dx in (-1, 0, 1):
                        nx = fx + dx
                        if 0 <= nx < w:
                            if row_depth[nx] == 255:
                                row_depth[nx] = depth
                                next_frontier.append((nx, ny))
        current_frontier = next_frontier
        if not current_frontier:
            break

    # Pass 3: Soft-Alpha Unmix on Edge Band
    unmixed_count = 0
    for y in range(h):
        row_class = classes[y]
        row_depth = depths[y]
        for x in range(w):
            d = row_depth[x]
            if 0 < d <= unmix_reach:
                cls = row_class[x]
                if (cls == BLEND_IN_BAND and d <= 2) or cls == BLEND_OUT_OF_BAND:
                    r, g, b, a = out_px[x, y]
                    if a > 0:
                        tint = key_tint_score((r, g, b), chroma_key)
                        if tint > 0:
                            nr, ng, nb, na = unmix_key_blend((r, g, b), a, chroma_key, key_tint, tint)
                            out_px[x, y] = (nr, ng, nb, na)
                            unmixed_count += 1

    # Pass 4: Trapped-Spill Despill (interior reflection/tint without cutting alpha)
    despilled_count = 0
    if spill_max_fraction > 0:
        subject_count = (w * h) - keyed_count
        spill_cluster_limit = max(16, int(round(subject_count * spill_max_fraction)))
        candidates: set[tuple[int, int]] = set()

        for y in range(h):
            row_depth = depths[y]
            for x in range(w):
                r, g, b, a = out_px[x, y]
                if a > 0 and row_depth[x] > unmix_reach:
                    tint = key_tint_score((r, g, b), chroma_key)
                    if tint >= fringe_delta:
                        candidates.add((x, y))

        visited: set[tuple[int, int]] = set()
        for pt in list(candidates):
            if pt in visited:
                continue
            cluster = [pt]
            visited.add(pt)
            stack = [pt]
            while stack:
                cx, cy = stack.pop()
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        neighbor = (cx + dx, cy + dy)
                        if neighbor in candidates and neighbor not in visited:
                            visited.add(neighbor)
                            cluster.append(neighbor)
                            stack.append(neighbor)

            if len(cluster) <= spill_cluster_limit:
                for cx, cy in cluster:
                    r, g, b, a = out_px[cx, cy]
                    tint = key_tint_score((r, g, b), chroma_key)
                    _, despilled = despill_color((r, g, b), chroma_key, key_tint, tint)
                    out_px[cx, cy] = (despilled[0], despilled[1], despilled[2], a)
                    despilled_count += 1

    stats = {
        "modified": True,
        "chroma_key": chroma_key,
        "keyed_pixels": keyed_count,
        "unmixed_pixels": unmixed_count,
        "despilled_pixels": despilled_count,
    }
    return out_img, stats
