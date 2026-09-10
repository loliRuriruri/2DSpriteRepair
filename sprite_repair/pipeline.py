"""
sprite_repair.pipeline
~~~~~~~~~~~~~~~~~~~~~~
Alpha-aware spritesheet extraction with expanded bbox, foot anchors,
character vs VFX separation, and Project/Frame domain models.
Conforms to Sections 7-18 of MASTER_SPEC.md.
"""

from __future__ import annotations

import base64
import math
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from sprite_repair.models import (
    Point,
    Rect,
    Anchor,
    Diagnostics,
    Layer,
    Cel,
    Frame,
    Tag,
    Slice,
    Sprite,
    Project,
)


def _alpha_mask(img: Image.Image, threshold: int) -> list[list[bool]]:
    px = img.load()
    w, h = img.size
    return [[px[x, y][3] > threshold for x in range(w)] for y in range(h)]


def _alpha_plane(img: Image.Image) -> list[list[int]]:
    px = img.load()
    w, h = img.size
    return [[px[x, y][3] for x in range(w)] for y in range(h)]


def auto_transparent_solid_background(
    img: Image.Image,
    tolerance: int = 40,
    sample_corners: bool = True,
    bg_color: tuple[int, int, int] | None = None,
    return_stats: bool = False,
) -> Image.Image | tuple[Image.Image, dict[str, Any]]:
    """Remove solid background using 4-pass chroma key & despill."""
    from sprite_repair.chromakey import remove_chroma_background_soft
    res, stats = remove_chroma_background_soft(
        img,
        chroma_key=bg_color,
        threshold=float(tolerance),
    )
    if return_stats:
        return res, stats
    return res


def _flood_component(
    mask: list[list[bool]],
    sx: int,
    sy: int,
    visited: list[list[bool]],
    x_lo: int,
    y_lo: int,
    x_hi: int,
    y_hi: int,
) -> list[tuple[int, int]]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    stack = [(sx, sy)]
    visited[sy][sx] = True
    comp = []
    while stack:
        x, y = stack.pop()
        comp.append((x, y))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if x_lo <= nx <= x_hi and y_lo <= ny <= y_hi:
                if 0 <= ny < h and 0 <= nx < w:
                    if mask[ny][nx] and not visited[ny][nx]:
                        visited[ny][nx] = True
                        stack.append((nx, ny))
    return comp


def _seed_center(seed: Rect) -> tuple[float, float]:
    return (seed.x + seed.w / 2.0, seed.y + seed.h / 2.0)


def _dist2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _largest_components_in_seed(
    mask: list[list[bool]],
    alpha: list[list[int]],
    seed: Rect,
    expand: int,
    sheet_w: int,
    sheet_h: int,
    neighbor_seeds: list[Rect],
    solid_alpha: int = 120,
) -> tuple[Rect | None, set[tuple[int, int]]]:
    x0 = max(0, seed.x - expand)
    y0 = max(0, seed.y - expand)
    x1 = min(sheet_w - 1, seed.x + seed.w + expand - 1)
    y1 = min(sheet_h - 1, seed.y + seed.h + expand - 1)

    forbid_solid = set()
    for ns in neighbor_seeds:
        cx0 = ns.x + ns.w // 4
        cy0 = ns.y + ns.h // 4
        cx1 = ns.x + (3 * ns.w) // 4
        cy1 = ns.y + (3 * ns.h) // 4
        ix0 = max(x0, cx0)
        iy0 = max(y0, cy0)
        ix1 = min(x1, cx1)
        iy1 = min(y1, cy1)
        for y in range(iy0, iy1 + 1):
            for x in range(ix0, ix1 + 1):
                forbid_solid.add((x, y))

    visited = [[False] * sheet_w for _ in range(sheet_h)]
    components: list[list[tuple[int, int]]] = []

    def accept_pixel(p: tuple[int, int]) -> bool:
        x, y = p
        if p not in forbid_solid:
            return True
        return alpha[y][x] < solid_alpha

    for y in range(seed.y, seed.y + seed.h):
        for x in range(seed.x, seed.x + seed.w):
            if 0 <= x < sheet_w and 0 <= y < sheet_h and mask[y][x] and not visited[y][x]:
                if (x, y) in forbid_solid and alpha[y][x] >= solid_alpha:
                    continue
                comp = _flood_component(mask, x, y, visited, x0, y0, x1, y1)
                comp = [p for p in comp if accept_pixel(p)]
                if comp and any(
                    seed.x <= px < seed.x + seed.w and seed.y <= py < seed.y + seed.h
                    for px, py in comp
                ):
                    components.append(comp)

    if not components:
        visited2 = [[False] * sheet_w for _ in range(sheet_h)]
        for y in range(seed.y, seed.y + seed.h):
            for x in range(seed.x, seed.x + seed.w):
                if 0 <= x < sheet_w and 0 <= y < sheet_h and mask[y][x] and not visited2[y][x]:
                    comp = _flood_component(mask, x, y, visited2, x0, y0, x1, y1)
                    if comp:
                        components.append(comp)

    if not components:
        return None, set()

    best = max(components, key=len)
    claimed = set(best)
    my_c = _seed_center(seed)
    nb_centers = [_seed_center(ns) for ns in neighbor_seeds]

    for comp in components:
        if comp is best:
            continue
        comp_xs = [p[0] for p in comp]
        comp_ys = [p[1] for p in comp]
        c_pt = (sum(comp_xs) / len(comp), sum(comp_ys) / len(comp))
        d_my = _dist2(c_pt, my_c)
        d_nb = min((_dist2(c_pt, nc) for nc in nb_centers), default=1e9)
        touching = any(
            (px + dx, py + dy) in claimed
            for px, py in comp
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
        )
        if touching or d_my < d_nb * 1.15:
            claimed.update(comp)

    claimed = _trim_below_seed_gap(claimed, alpha, seed, solid_alpha=solid_alpha)

    xs = [p[0] for p in claimed]
    ys = [p[1] for p in claimed]
    return Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1), claimed


def _trim_below_seed_gap(
    claimed: set[tuple[int, int]],
    alpha: list[list[int]],
    seed: Rect,
    solid_alpha: int = 120,
    gap_solid_max: int = 3,
) -> set[tuple[int, int]]:
    seed_bottom = seed.y + seed.h
    below = [p for p in claimed if p[1] >= seed_bottom]
    if not below:
        return claimed
    max_y = max(p[1] for p in below)
    cut_y: int | None = None
    for y in range(seed_bottom, max_y + 1):
        row_solid = sum(1 for p in claimed if p[1] == y and alpha[p[1]][p[0]] >= solid_alpha)
        if row_solid <= gap_solid_max:
            has_solid_below = any(
                p[1] > y + 2 and alpha[p[1]][p[0]] >= solid_alpha for p in claimed
            )
            if has_solid_below:
                cut_y = y
                break
    if cut_y is not None:
        return {p for p in claimed if p[1] < cut_y}
    return claimed


def _body_mask_ignore_vfx(pixels: set[tuple[int, int]], bbox: Rect) -> set[tuple[int, int]]:
    if not pixels:
        return set()
    h = bbox.h
    lower_y = bbox.y + int(h * 0.45)
    candidates = [p for p in pixels if p[1] >= lower_y]
    if not candidates:
        return set(pixels)
    ys = [p[1] for p in candidates]
    y_hi = max(ys)
    y_band = max(lower_y, y_hi - max(3, int(h * 0.2)))
    band = [p for p in candidates if p[1] >= y_band]
    return set(band) if band else set(candidates)


def _bbox_of_pixels(pixels: set[tuple[int, int]]) -> Rect | None:
    if not pixels:
        return None
    xs = [p[0] for p in pixels]
    ys = [p[1] for p in pixels]
    return Rect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1)


def _split_character_effect(
    claimed: set[tuple[int, int]],
    alpha: list[list[int]],
    crop_bbox: Rect,
    solid_alpha: int = 120,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]], Rect | None, Rect | None]:
    if not claimed:
        return set(), set(), None, None
    solid = {pt for pt in claimed if alpha[pt[1]][pt[0]] >= solid_alpha}
    body_src = solid if len(solid) >= max(12, len(claimed) // 20) else set(claimed)
    character = _body_mask_ignore_vfx(body_src, crop_bbox) if body_src else set()
    if not character:
        character = set(body_src) if body_src else set(claimed)
    effect = claimed - character
    return character, effect, _bbox_of_pixels(character), _bbox_of_pixels(effect)


def estimate_foot_anchor(body_pixels: set[tuple[int, int]], bbox: Rect) -> Point:
    if not body_pixels:
        return Point(bbox.x + bbox.w // 2, bbox.y + bbox.h)
    ys = [p[1] for p in body_pixels]
    y_max = max(ys)
    y_min = min(ys)
    band = max(2, int((y_max - y_min + 1) * 0.18))
    band_y0 = y_max - band + 1
    bottom = [p for p in body_pixels if p[1] >= band_y0] or list(body_pixels)
    xs = sorted(p[0] for p in bottom)
    return Point(xs[len(xs) // 2], y_max)


def _crop_rgba_masked(img: Image.Image, rect: Rect, claimed_pixels: set[tuple[int, int]], pad: int = 0) -> tuple[Image.Image, Rect]:
    x0 = max(0, rect.x - pad)
    y0 = max(0, rect.y - pad)
    x1 = min(img.width, rect.x + rect.w + pad)
    y1 = min(img.height, rect.y + rect.h + pad)
    cropped = img.crop((x0, y0, x1, y1)).convert("RGBA")
    c_px = cropped.load()
    cw, ch = cropped.size
    for cy in range(ch):
        for cx in range(cw):
            gx = x0 + cx
            gy = y0 + cy
            if (gx, gy) not in claimed_pixels:
                c_px[cx, cy] = (0, 0, 0, 0)
    return cropped, Rect(x0, y0, x1 - x0, y1 - y0)


def _crop_rgba(img: Image.Image, rect: Rect, pad: int = 0) -> tuple[Image.Image, Rect]:
    x0 = max(0, rect.x - pad)
    y0 = max(0, rect.y - pad)
    x1 = min(img.width, rect.x + rect.w + pad)
    y1 = min(img.height, rect.y + rect.h + pad)
    return img.crop((x0, y0, x1, y1)), Rect(x0, y0, x1 - x0, y1 - y0)


def _rect_to_local(rect: Rect | None, origin: Rect) -> dict[str, int] | None:
    if rect is None:
        return None
    return {
        "x": int(rect.x - origin.x),
        "y": int(rect.y - origin.y),
        "w": int(rect.w),
        "h": int(rect.h),
    }


def _qa_frame(seed: Rect, combined: Rect, character_bbox: Rect | None, effect_bbox: Rect | None) -> list[str]:
    warnings: list[str] = []
    if combined is None:
        return warnings
    overflow_l = max(0, seed.x - combined.x)
    overflow_t = max(0, seed.y - combined.y)
    overflow_r = max(0, (combined.x + combined.w) - (seed.x + seed.w))
    overflow_b = max(0, (combined.y + combined.h) - (seed.y + seed.h))
    if overflow_l + overflow_r + overflow_t + overflow_b > 0:
        warnings.append(f"overflow L{overflow_l}/R{overflow_r}/T{overflow_t}/B{overflow_b}px past seed")
    if effect_bbox and character_bbox and effect_bbox.w > character_bbox.w * 1.35:
        warnings.append("wide VFX vs character")
    return warnings


def estimate_grid(sheet: Image.Image, alpha_threshold: int = 12, max_n: int = 12) -> tuple[int, int]:
    w, h = sheet.size
    alpha = sheet.split()[-1]
    px = alpha.load()
    col_density = [sum(1 for y in range(h) if px[x, y] > alpha_threshold) for x in range(w)]
    row_density = [sum(1 for x in range(w) if px[x, y] > alpha_threshold) for y in range(h)]

    def best_split(density: list[int], length: int) -> int:
        best_n = 4
        best_score = -1.0
        for n in range(2, max_n + 1):
            step = length / n
            valleys = []
            for i in range(1, n):
                cut = int(i * step)
                r = max(2, int(step * 0.08))
                lo = max(0, cut - r)
                hi = min(length, cut + r + 1)
                valleys.append(min(density[lo:hi]) if lo < hi else 0)
            avg_valley = sum(valleys) / len(valleys) if valleys else 0
            score = 1.0 / (avg_valley + 1.0)
            if score > best_score:
                best_score = score
                best_n = n
        return best_n

    return best_split(col_density, w), best_split(row_density, h)


def tight_crop_rgba(img: Image.Image, anchor: dict[str, int], alpha_threshold: int = 12, margin: int = 0) -> tuple[Image.Image, dict[str, int]]:
    alpha = img.split()[-1]
    bbox = alpha.getbbox()
    if not bbox:
        return img.copy(), dict(anchor)
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - margin)
    y0 = max(0, y0 - margin)
    x1 = min(img.width, x1 + margin)
    y1 = min(img.height, y1 + margin)
    cropped = img.crop((x0, y0, x1, y1))
    new_anchor = {"x": anchor.get("x", 0) - x0, "y": anchor.get("y", 0) - y0}
    return cropped, new_anchor


def expand_frame_rgba(img: Image.Image, anchor: dict[str, int], left: int = 0, top: int = 0, right: int = 0, bottom: int = 0) -> tuple[Image.Image, dict[str, int]]:
    nw = img.width + left + right
    nh = img.height + top + bottom
    res = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
    res.paste(img, (left, top), img)
    new_anchor = {"x": anchor.get("x", 0) + left, "y": anchor.get("y", 0) + top}
    return res, new_anchor


def apply_ownership_brush(
    frame: Image.Image,
    base: Image.Image,
    *,
    mode: str,
    strokes: list[dict[str, Any]],
    brush: int = 6,
    sheet: Image.Image | None = None,
    crop_rect: dict[str, int] | None = None,
) -> Image.Image:
    out = frame.copy()
    f_px = out.load()
    b_px = base.load()
    w, h = out.size

    for st in strokes:
        cx = int(st.get("x", 0))
        cy = int(st.get("y", 0))
        r = brush
        x0 = max(0, cx - r)
        y0 = max(0, cy - r)
        x1 = min(w, cx + r + 1)
        y1 = min(h, cy + r + 1)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    if mode in ("erase", "exclude"):
                        f_px[x, y] = (0, 0, 0, 0)
                    elif mode in ("include", "restore"):
                        f_px[x, y] = b_px[x, y]
    return out


def _img_to_data_url(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def frames_to_data_urls(images: list[Image.Image]) -> list[str]:
    return [_img_to_data_url(im) for im in images]


def compose_on_canvas(
    frame_images: list[Image.Image],
    frames_meta: list[dict[str, Any]],
    pad: int = 0,
) -> tuple[dict[str, int], list[dict[str, Any]], list[Image.Image]]:
    if not frame_images:
        return {"w": 1, "h": 1, "anchor_x": 0, "anchor_y": 0}, [], []

    max_left = max_right = max_up = max_down = 0
    for img, meta in zip(frame_images, frames_meta):
        ax = int(meta["anchor"]["x"])
        ay = int(meta["anchor"]["y"])
        max_left = max(max_left, ax)
        max_right = max(max_right, img.width - ax)
        max_up = max(max_up, ay)
        max_down = max(max_down, img.height - ay)

    safety = 4
    max_left += pad + safety
    max_right += pad + safety
    max_up += pad + safety
    max_down += pad + safety
    cw = max(1, max_left + max_right)
    ch = max(1, max_up + max_down)
    canvas_anchor = Point(max_left, max_up)

    composed_images: list[Image.Image] = []
    composed_meta: list[dict[str, Any]] = []
    for img, meta in zip(frame_images, frames_meta):
        ax = int(meta["anchor"]["x"])
        ay = int(meta["anchor"]["y"])
        ox = canvas_anchor.x - ax
        oy = canvas_anchor.y - ay
        canvas_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        canvas_img.paste(img, (ox, oy), img)
        composed_images.append(canvas_img)
        composed_meta.append(
            {
                "frame": meta["frame"],
                "empty": meta.get("empty", False),
                "rect": {"x": 0, "y": 0, "w": cw, "h": ch},
                "anchor": {"x": canvas_anchor.x, "y": canvas_anchor.y},
                "offset": {"x": ox, "y": oy},
                "duration": meta.get("duration", 80),
                "source_rect": meta.get("rect"),
                "source_anchor": meta.get("anchor"),
                "seed": meta.get("seed"),
                "nominal_rect": meta.get("nominal_rect") or meta.get("seed"),
                "content_rect": meta.get("content_rect") or meta.get("rect"),
                "character_bbox": meta.get("character_bbox"),
                "effect_bbox": meta.get("effect_bbox"),
                "combined_bbox": meta.get("combined_bbox"),
                "qa_warnings": meta.get("qa_warnings") or [],
                "size": {"w": cw, "h": ch},
            }
        )
    return {"w": cw, "h": ch, "anchor_x": canvas_anchor.x, "anchor_y": canvas_anchor.y}, composed_meta, composed_images


def recompose_with_anchors(
    raw_frame_images: list[Image.Image],
    raw_frames: list[dict[str, Any]],
    anchor_overrides: list[dict[str, int]] | None = None,
    duration_ms: int | None = None,
    pad: int = 0,
) -> dict[str, Any]:
    metas = []
    for i, meta in enumerate(raw_frames):
        m = dict(meta)
        if anchor_overrides and i < len(anchor_overrides) and anchor_overrides[i] is not None:
            ov = anchor_overrides[i]
            if "x" in ov and "y" in ov:
                m["anchor"] = {"x": int(ov["x"]), "y": int(ov["y"])}
            elif "x" in ov:
                m["anchor"] = {"x": int(ov["x"]), "y": int(m["anchor"]["y"])}
            elif "y" in ov:
                m["anchor"] = {"x": int(m["anchor"]["x"]), "y": int(ov["y"])}
        if duration_ms is not None:
            m["duration"] = duration_ms
        metas.append(m)
    canvas, composed_meta, composed_images = compose_on_canvas(raw_frame_images, metas, pad=pad)

    proj_sprite = Sprite(
        width=int(canvas["w"]),
        height=int(canvas["h"]),
        anchor=Point(int(canvas["anchor_x"]), int(canvas["anchor_y"])),
    )
    proj_frames = [Frame.from_dict(m) for m in composed_meta]
    proj = Project(
        name="Recomposed",
        version="2.0",
        sprite=proj_sprite,
        frames=proj_frames,
    )

    return {
        "canvas": canvas,
        "frames": composed_meta,
        "frame_images": composed_images,
        "raw_frames": metas,
        "raw_frame_images": raw_frame_images,
        "project": proj,
        "project_dict": proj.to_dict(),
    }


def process_sheet(
    sheet_path: str | Path | Image.Image,
    cols: int = 4,
    rows: int = 4,
    alpha_threshold: int = 12,
    pad: int = 4,
    duration_ms: int = 80,
    expand_ratio: float = 0.35,
    auto_chromakey: bool = True,
    chromakey_color: tuple[int, int, int] | None = None,
) -> dict[str, Any]:
    if isinstance(sheet_path, Image.Image):
        sheet = sheet_path.convert("RGBA")
        source_name = "upload.png"
    else:
        sheet = Image.open(sheet_path).convert("RGBA")
        source_name = Path(sheet_path).name

    chroma_stats = None
    if auto_chromakey:
        sheet, chroma_stats = auto_transparent_solid_background(
            sheet, bg_color=chromakey_color, return_stats=True
        )

    sw, sh = sheet.size
    cell_w = sw // cols
    cell_h = sh // rows
    expand = int(max(cell_w, cell_h) * expand_ratio)

    seeds: list[Rect] = []
    for r in range(rows):
        for c in range(cols):
            x = c * cell_w
            y = r * cell_h
            w = (sw - x) if c == cols - 1 else cell_w
            h = (sh - y) if r == rows - 1 else cell_h
            seeds.append(Rect(x, y, w, h))

    mask = _alpha_mask(sheet, alpha_threshold)
    alpha = _alpha_plane(sheet)

    frames_meta: list[dict[str, Any]] = []
    frame_images: list[Image.Image] = []

    for i, seed in enumerate(seeds):
        neighbors = [s for j, s in enumerate(seeds) if j != i]
        crop_bbox, pix = _largest_components_in_seed(
            mask, alpha, seed, expand, sw, sh, neighbors
        )
        if crop_bbox is None or not pix:
            empty = Image.new("RGBA", (max(1, cell_w // 4), max(1, cell_h // 4)), (0, 0, 0, 0))
            frame_images.append(empty)
            frames_meta.append(
                {
                    "frame": i,
                    "empty": True,
                    "rect": {"x": seed.x, "y": seed.y, "w": seed.w, "h": seed.h},
                    "anchor": {"x": empty.width // 2, "y": empty.height},
                    "offset": {"x": 0, "y": 0},
                    "duration": duration_ms,
                    "seed": asdict(seed),
                }
            )
            continue

        character_px, effect_px, char_bbox_s, effect_bbox_s = _split_character_effect(
            pix, alpha, crop_bbox
        )
        body_for_anchor = character_px if character_px else pix
        body_bbox = char_bbox_s if char_bbox_s is not None else crop_bbox

        anchor_sheet = estimate_foot_anchor(body_for_anchor, body_bbox)
        crop_img, crop_rect = _crop_rgba_masked(sheet, crop_bbox, pix, pad=pad)

        ax = max(0, min(crop_img.width - 1, anchor_sheet.x - crop_rect.x))
        ay = max(0, min(crop_img.height - 1, anchor_sheet.y - crop_rect.y))

        combined_local = {
            "x": 0,
            "y": 0,
            "w": crop_img.width,
            "h": crop_img.height,
        }
        character_bbox = _rect_to_local(char_bbox_s, crop_rect)
        effect_bbox = _rect_to_local(effect_bbox_s, crop_rect)
        qa = _qa_frame(seed, crop_bbox, char_bbox_s, effect_bbox_s)

        frame_images.append(crop_img)
        frames_meta.append(
            {
                "frame": i,
                "empty": False,
                "rect": asdict(crop_rect),
                "nominal_rect": asdict(seed),
                "content_rect": asdict(crop_bbox),
                "character_bbox": character_bbox,
                "effect_bbox": effect_bbox,
                "combined_bbox": combined_local,
                "anchor": {"x": ax, "y": ay},
                "offset": {"x": 0, "y": 0},
                "duration": duration_ms,
                "seed": asdict(seed),
                "size": {"w": crop_img.width, "h": crop_img.height},
                "qa_warnings": qa,
            }
        )

    canvas, composed_meta, composed_images = compose_on_canvas(frame_images, frames_meta, pad=0)

    proj_sprite = Sprite(
        width=int(canvas["w"]),
        height=int(canvas["h"]),
        anchor=Point(int(canvas["anchor_x"]), int(canvas["anchor_y"])),
    )
    proj_layers = [
        Layer(id="layer_character", name="Character", type="character"),
        Layer(id="layer_vfx", name="VFX", type="vfx"),
    ]
    proj_frames = []
    for m in composed_meta:
        f = Frame.from_dict(m)
        f.cels = [
            Cel(layer_id="layer_character", frame_id=f.index, x=f.offset.x, y=f.offset.y),
            Cel(layer_id="layer_vfx", frame_id=f.index, x=f.offset.x, y=f.offset.y),
        ]
        proj_frames.append(f)

    proj_tags = [
        Tag(name="Main", from_frame=0, to_frame=max(0, len(composed_meta) - 1), direction="forward")
    ]
    proj = Project(
        name=Path(source_name).stem if source_name else "Untitled",
        version="2.0",
        sprite=proj_sprite,
        layers=proj_layers,
        frames=proj_frames,
        tags=proj_tags,
    )

    return {
        "source": source_name,
        "sheet_size": {"w": sw, "h": sh},
        "grid": {"cols": cols, "rows": rows, "cell_w": cell_w, "cell_h": cell_h},
        "alpha_threshold": alpha_threshold,
        "pad": pad,
        "expand_ratio": expand_ratio,
        "canvas": canvas,
        "frames": composed_meta,
        "frame_images": composed_images,
        "raw_frame_images": frame_images,
        "raw_frames": frames_meta,
        "chroma_stats": chroma_stats,
        "project": proj,
        "project_dict": proj.to_dict(),
    }
