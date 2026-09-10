"""Retro Pixel Art Palette Quantizer for SpriteRepair (Aseprite style).

Built-in industry standard pixel art palettes:
- pico8: 16 colors
- gameboy: 4 classic olive green colors
- sweetie16: 16 vibrant pastel colors
- db32: DawnBringer 32 colors
- edg32: Endesga 32 colors
- cga: 4 colors
"""

from __future__ import annotations

import math
from typing import Sequence
from PIL import Image

PALETTES: dict[str, list[tuple[int, int, int]]] = {
    "pico8": [
        (0, 0, 0), (29, 43, 83), (126, 37, 83), (0, 135, 81),
        (171, 82, 54), (95, 87, 79), (194, 195, 199), (255, 241, 232),
        (255, 0, 77), (255, 163, 0), (255, 236, 39), (0, 228, 54),
        (41, 173, 255), (131, 118, 156), (255, 119, 168), (255, 204, 170)
    ],
    "gameboy": [
        (15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)
    ],
    "sweetie16": [
        (26, 28, 44), (93, 39, 93), (177, 62, 83), (239, 125, 87),
        (255, 205, 117), (167, 240, 112), (56, 183, 100), (37, 113, 121),
        (41, 54, 111), (59, 93, 201), (65, 166, 246), (115, 239, 247),
        (244, 244, 244), (148, 176, 194), (86, 108, 134), (51, 60, 87)
    ],
    "db32": [
        (0, 0, 0), (34, 32, 52), (69, 40, 60), (102, 57, 49),
        (143, 86, 59), (223, 113, 38), (217, 160, 102), (238, 195, 154),
        (68, 36, 52), (123, 75, 99), (198, 110, 131), (239, 152, 159),
        (48, 52, 109), (78, 74, 178), (133, 149, 161), (109, 170, 44),
        (218, 212, 94), (179, 93, 98), (94, 62, 80), (168, 103, 130),
        (222, 176, 149), (39, 39, 68), (75, 105, 47), (82, 75, 36),
        (51, 80, 68), (103, 144, 115), (160, 205, 142), (58, 68, 102),
        (90, 105, 136), (139, 155, 180), (204, 213, 221), (240, 246, 240)
    ],
    "edg32": [
        (190, 74, 47), (215, 118, 67), (234, 212, 170), (228, 166, 114),
        (184, 111, 80), (115, 62, 57), (62, 39, 49), (162, 38, 51),
        (228, 59, 68), (247, 118, 34), (254, 174, 52), (254, 231, 97),
        (99, 199, 77), (62, 137, 72), (38, 92, 66), (25, 60, 62),
        (18, 78, 137), (44, 142, 187), (107, 192, 234), (244, 244, 244),
        (166, 182, 192), (99, 107, 116), (49, 54, 59), (34, 32, 52),
        (69, 40, 60), (102, 57, 49), (133, 149, 161), (109, 170, 44),
        (218, 212, 94), (179, 93, 98), (208, 70, 72), (210, 170, 153)
    ],
    "cga": [
        (0, 0, 0), (85, 255, 255), (255, 85, 255), (255, 255, 255)
    ],
}


def _color_dist_sq(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> int:
    """Perceptually weighted Euclidean distance squared."""
    # Weights approximately matching human eye perception (Red: 30%, Green: 59%, Blue: 11%)
    dr = c1[0] - c2[0]
    dg = c1[1] - c2[1]
    db = c1[2] - c2[2]
    return int(0.30 * dr * dr + 0.59 * dg * dg + 0.11 * db * db)


def quantize_frame_to_palette(
    img: Image.Image,
    palette_name: str = "pico8",
    dither: bool = False,
    alpha_threshold: int = 16,
) -> Image.Image:
    """
    Map an RGBA image to a target retro palette.
    Alpha channel < alpha_threshold is completely transparent.
    Alpha >= alpha_threshold gets mapped to the nearest palette color.
    """
    colors = PALETTES.get(palette_name.lower().strip())
    if not colors:
        raise ValueError(f"Unknown palette name: {palette_name}. Available: {list(PALETTES.keys())}")

    src = img.convert("RGBA")
    w, h = src.size
    px = src.load()

    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dst = out.load()

    # Cache color lookups for speed (LUT)
    cache: dict[tuple[int, int, int], tuple[int, int, int]] = {}

    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < alpha_threshold:
                continue

            key = (r, g, b)
            if key in cache:
                nr, ng, nb = cache[key]
            else:
                best_c = colors[0]
                best_d = _color_dist_sq(key, best_c)
                for c in colors[1:]:
                    d = _color_dist_sq(key, c)
                    if d < best_d:
                        best_d = d
                        best_c = c
                cache[key] = best_c
                nr, ng, nb = best_c

            dst[x, y] = (nr, ng, nb, a)

    return out


def quantize_all_frames(
    frames: Sequence[Image.Image],
    palette_name: str = "pico8",
    alpha_threshold: int = 16,
) -> list[Image.Image]:
    """Batch quantize a sequence of frames."""
    return [quantize_frame_to_palette(f, palette_name=palette_name, alpha_threshold=alpha_threshold) for f in frames]
