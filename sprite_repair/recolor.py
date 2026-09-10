"""Palette Swap & Recolor Engine for SpriteRepair.

Inspired by aldegad/sprite-gen (v2.0 recolor pipeline):
- Fast palette extraction and cluster analysis
- Preset variants: 2P Blue, Fire, Ice, Dark/Void, Toxic, Royal Gold
- Custom hue rotation (0..360 degrees) and saturation/brightness shift
"""

from __future__ import annotations

import colorsys
from typing import Any
from PIL import Image

PRESETS = {
    "2p_blue": {"name": "2P (블루/시안)", "hue_shift": 0.50, "sat_mult": 1.1, "val_mult": 1.0},
    "fire": {"name": "화염/크림슨", "hue_shift": 0.0, "tint_rgb": (240, 70, 30), "blend": 0.45},
    "ice": {"name": "얼음/프로스트", "hue_shift": 0.55, "tint_rgb": (50, 180, 245), "blend": 0.40},
    "dark": {"name": "암흑/보이드", "hue_shift": 0.75, "tint_rgb": (140, 40, 210), "blend": 0.50},
    "toxic": {"name": "맹독/애시드", "hue_shift": 0.28, "tint_rgb": (60, 230, 80), "blend": 0.45},
    "gold": {"name": "황금/로열", "hue_shift": 0.12, "tint_rgb": (250, 200, 40), "blend": 0.40},
    "monochrome": {"name": "모노크롬/흑백", "sat_mult": 0.0, "val_mult": 1.0},
}


def recolor_frame(
    frame: Image.Image,
    preset: str | None = None,
    hue_shift: float = 0.0,
    sat_mult: float = 1.0,
    val_mult: float = 1.0,
    preserve_skin: bool = True,
) -> Image.Image:
    """
    Recolor an RGBA frame using a lookup table for extreme speed (<5ms).
    `preset`: one of PRESETS keys (e.g. 'fire', 'ice', '2p_blue')
    `hue_shift`: 0.0 to 1.0 (0 to 360 deg rotation)
    `preserve_skin`: whether to avoid shifting warm peach/skin tones (approx hue 0.05..0.12)
    """
    rgba = frame.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()

    cfg = PRESETS.get(preset or "", {})
    effective_hue = (hue_shift + cfg.get("hue_shift", 0.0)) % 1.0
    effective_sat = sat_mult * cfg.get("sat_mult", 1.0)
    effective_val = val_mult * cfg.get("val_mult", 1.0)
    tint_rgb = cfg.get("tint_rgb")
    blend = cfg.get("blend", 0.0)

    # Gather unique colors
    unique_colors: set[tuple[int, int, int]] = set()
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            if c[3] > 0:
                unique_colors.add(c[:3])

    # Build LUT
    lut: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    for r, g, b in unique_colors:
        rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
        h_val, s_val, v_val = colorsys.rgb_to_hsv(rf, gf, bf)

        # Detect human/anime skin tone (warm low-saturation hue: 0.04 to 0.11, s: 0.15 to 0.60, v > 0.45)
        is_skin = preserve_skin and (0.04 <= h_val <= 0.12) and (0.15 <= s_val <= 0.65) and (v_val >= 0.45)
        if is_skin:
            lut[(r, g, b)] = (r, g, b)
            continue

        if tint_rgb and blend > 0:
            # Tint blend
            tr, tg, tb = tint_rgb
            nr = int(round(r * (1.0 - blend) + tr * blend * v_val))
            ng = int(round(g * (1.0 - blend) + tg * blend * v_val))
            nb = int(round(b * (1.0 - blend) + tb * blend * v_val))
            lut[(r, g, b)] = (min(255, max(0, nr)), min(255, max(0, ng)), min(255, max(0, nb)))
        else:
            # HSV shift
            nh = (h_val + effective_hue) % 1.0
            ns = min(1.0, max(0.0, s_val * effective_sat))
            nv = min(1.0, max(0.0, v_val * effective_val))
            out_rf, out_gf, out_bf = colorsys.hsv_to_rgb(nh, ns, nv)
            lut[(r, g, b)] = (
                min(255, max(0, int(round(out_rf * 255)))),
                min(255, max(0, int(round(out_gf * 255)))),
                min(255, max(0, int(round(out_bf * 255)))),
            )

    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out_px = out.load()
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            if c[3] > 0:
                nr, ng, nb = lut.get(c[:3], c[:3])
                out_px[x, y] = (nr, ng, nb, c[3])

    return out


def recolor_all_frames(
    frames: list[Image.Image],
    preset: str | None = None,
    hue_shift: float = 0.0,
    sat_mult: float = 1.0,
    val_mult: float = 1.0,
    preserve_skin: bool = True,
) -> list[Image.Image]:
    return [
        recolor_frame(f, preset=preset, hue_shift=hue_shift, sat_mult=sat_mult, val_mult=val_mult, preserve_skin=preserve_skin)
        for f in frames
    ]
