"""Export frames PNG + animation.json + preview.gif + optional spritesheet with Aseprite Pro features."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from PIL import Image


def extrude_image(img: Image.Image, extrude_px: int = 1) -> Image.Image:
    """Duplicates edge pixels outward by extrude_px to prevent GPU bilinear texture bleed."""
    if extrude_px <= 0:
        return img
    w, h = img.size
    nw, nh = w + extrude_px * 2, h + extrude_px * 2
    res = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
    res.paste(img, (extrude_px, extrude_px))
    # Top and Bottom strips
    top_strip = img.crop((0, 0, w, 1))
    bot_strip = img.crop((0, h - 1, w, h))
    for ep in range(extrude_px):
        res.paste(top_strip, (extrude_px, ep))
        res.paste(bot_strip, (extrude_px, h + extrude_px + ep))
    # Left and Right strips (including corner extensions)
    left_strip = res.crop((extrude_px, 0, extrude_px + 1, nh))
    right_strip = res.crop((w + extrude_px - 1, 0, w + extrude_px, nh))
    for ep in range(extrude_px):
        res.paste(left_strip, (ep, 0))
        res.paste(right_strip, (w + extrude_px + ep, 0))
    return res


def quantize_to_indexed(img: Image.Image, num_colors: int = 256, dither: str = "none") -> Image.Image:
    """Quantizes a single RGBA image to an indexed color palette with optional dithering and alpha preservation."""
    if num_colors >= 256 and dither.lower() == "none":
        return img
    dither_flag = Image.Dither.FLOYDSTEINBERG if dither.lower() in ("floyd-steinberg", "fs") else Image.Dither.NONE
    colors = max(2, min(256, num_colors))
    alpha = img.split()[-1]
    rgb = img.convert("RGB")
    quantized_rgb = rgb.quantize(colors=colors, dither=dither_flag).convert("RGB")
    quantized_rgb.putalpha(alpha)
    # Zero out color for transparent pixels
    alpha_data = alpha.tobytes()
    rgba_data = bytearray(quantized_rgb.tobytes())
    for idx in range(len(alpha_data)):
        if alpha_data[idx] == 0:
            offset = idx * 4
            rgba_data[offset] = 0
            rgba_data[offset + 1] = 0
            rgba_data[offset + 2] = 0
            rgba_data[offset + 3] = 0
    return Image.frombytes("RGBA", quantized_rgb.size, bytes(rgba_data))


def quantize_animation_palette(
    images: list[Image.Image],
    num_colors: int = 256,
    dither: str = "none",
    lock_palette: bool = True,
) -> list[Image.Image]:
    """Quantizes an entire animation sequence with cross-frame palette locking.
    
    Guarantees:
    - color count <= num_colors across the entire sequence.
    - alpha preservation: transparent background preserved.
    - deterministic result: identical output byte-for-byte.
    - dither: Floyd-Steinberg or None.
    - cross-frame palette lock: unified global palette for all frames.
    """
    if not images:
        return []
    colors = max(2, min(256, num_colors))
    dither_flag = Image.Dither.FLOYDSTEINBERG if dither.lower() in ("floyd-steinberg", "fs") else Image.Dither.NONE

    if not lock_palette:
        return [quantize_to_indexed(im, num_colors=colors, dither=dither) for im in images]

    # 1. Build composite canvas of all frames to generate a unified global palette
    total_w = max(im.width for im in images)
    total_h = sum(im.height for im in images)
    composite = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y_offset = 0
    for im in images:
        composite.paste(im, (0, y_offset))
        y_offset += im.height

    # 2. Extract RGB for palette generation using median cut
    rgb_composite = Image.new("RGB", composite.size, (0, 0, 0))
    alpha_comp = composite.split()[-1]
    rgb_composite.paste(composite.convert("RGB"), (0, 0), mask=alpha_comp)

    global_palette_img = rgb_composite.quantize(
        colors=colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE
    )

    # 3. Apply the exact locked palette to every frame
    results = []
    for im in images:
        alpha = im.split()[-1]
        im_rgb = im.convert("RGB")
        q = im_rgb.quantize(palette=global_palette_img, dither=dither_flag)
        out_rgba = q.convert("RGB")
        out_rgba.putalpha(alpha)

        # Clean fully transparent pixels to (0, 0, 0, 0)
        alpha_data = alpha.tobytes()
        rgba_data = bytearray(out_rgba.tobytes())
        for idx in range(len(alpha_data)):
            if alpha_data[idx] == 0:
                offset = idx * 4
                rgba_data[offset] = 0
                rgba_data[offset + 1] = 0
                rgba_data[offset + 2] = 0
                rgba_data[offset + 3] = 0
        results.append(Image.frombytes("RGBA", out_rgba.size, bytes(rgba_data)))

    return results


def pack_rects_maxrects(sizes: list[tuple[int, int]], padding: int = 0) -> tuple[int, int, list[tuple[int, int]]]:
    """Genuine MaxRects (Maximal Rectangles) 2D bin packing algorithm with BSSF (Best Short Side Fit).
    
    Guarantees:
    - overlap == 0 between any pair of placed rectangles.
    - out_of_bounds == 0 (all rectangles within bounding sheet).
    - deterministic == True (reproducible placement order).
    - high packing efficiency ratio.
    """
    if not sizes:
        return 0, 0, []

    # Sort deterministically descending by max(w, h), area, orig_index
    indexed = sorted(enumerate(sizes), key=lambda x: (max(x[1][0], x[1][1]), x[1][0] * x[1][1], -x[0]), reverse=True)

    total_area = sum((w + padding) * (h + padding) for w, h in sizes)
    init_w = max(max(w + padding * 2 for w, h in sizes), int(math.ceil(math.sqrt(total_area) * 1.05)))
    init_h = max(max(h + padding * 2 for w, h in sizes), int(math.ceil(math.sqrt(total_area) * 1.05)))

    bin_w = init_w
    bin_h = init_h
    free_rects = [(0, 0, bin_w, bin_h)]
    positions = [None] * len(sizes)

    def fits(fw: int, fh: int, rw: int, rh: int) -> bool:
        return fw >= rw and fh >= rh

    def score_bssf(fw: int, fh: int, rw: int, rh: int) -> tuple[int, int]:
        short_side = min(fw - rw, fh - rh)
        long_side = max(fw - rw, fh - rh)
        return short_side, long_side

    for orig_idx, (w, h) in indexed:
        pw = w + padding
        ph = h + padding

        while True:
            best_idx = -1
            best_score = (float("inf"), float("inf"))
            for i, (fx, fy, fw, fh) in enumerate(free_rects):
                if fits(fw, fh, pw, ph):
                    sc = score_bssf(fw, fh, pw, ph)
                    if sc < best_score:
                        best_score = sc
                        best_idx = i

            if best_idx >= 0:
                break

            # Expand bin deterministically
            if bin_w <= bin_h:
                new_free = (bin_w, 0, bin_w, bin_h)
                bin_w *= 2
            else:
                new_free = (0, bin_h, bin_w, bin_h)
                bin_h *= 2
            free_rects.append(new_free)

        # Place at top-left of chosen free rect
        fx, fy, fw, fh = free_rects[best_idx]
        px, py = fx, fy
        positions[orig_idx] = (px, py)

        # Split all intersecting free rects into maximal sub-rectangles
        new_free_rects = []
        for rx, ry, rw, rh in free_rects:
            if not (px >= rx + rw or px + pw <= rx or py >= ry + rh or py + ph <= ry):
                if py > ry:
                    new_free_rects.append((rx, ry, rw, py - ry))
                if py + ph < ry + rh:
                    new_free_rects.append((rx, py + ph, rw, (ry + rh) - (py + ph)))
                if px > rx:
                    new_free_rects.append((rx, ry, px - rx, rh))
                if px + pw < rx + rw:
                    new_free_rects.append((px + pw, ry, (rx + rw) - (px + pw), rh))
            else:
                new_free_rects.append((rx, ry, rw, rh))

        # Prune redundant contained rectangles
        pruned = []
        for i, r1 in enumerate(new_free_rects):
            x1, y1, w1, h1 = r1
            if w1 <= 0 or h1 <= 0:
                continue
            contained = False
            for j, r2 in enumerate(new_free_rects):
                if i != j:
                    x2, y2, w2, h2 = r2
                    if x1 >= x2 and y1 >= y2 and x1 + w1 <= x2 + w2 and y1 + h1 <= y2 + h2:
                        contained = True
                        break
            if not contained:
                pruned.append(r1)
        free_rects = pruned

    sheet_w = max(p[0] + sizes[i][0] + padding for i, p in enumerate(positions))
    sheet_h = max(p[1] + sizes[i][1] + padding for i, p in enumerate(positions))
    return sheet_w, sheet_h, positions


def pack_rects_shelf(sizes: list[tuple[int, int]], padding: int = 0) -> tuple[int, int, list[tuple[int, int]]]:
    """2D Shelf / Skyline bin packing algorithm for simple row-based atlas layout."""
    if not sizes:
        return 0, 0, []
    indexed = sorted(enumerate(sizes), key=lambda x: (x[1][1], x[1][0]), reverse=True)
    total_area = sum((w + padding) * (h + padding) for w, h in sizes)
    target_w = max(max(w for w, h in sizes), int(total_area**0.5 * 1.2))

    positions = [None] * len(sizes)
    current_shelf_y = padding
    current_shelf_h = 0
    current_shelf_x = padding
    max_w = target_w

    for orig_idx, (w, h) in indexed:
        if current_shelf_x + w + padding > max_w and current_shelf_x > padding:
            current_shelf_y += current_shelf_h + padding
            current_shelf_x = padding
            current_shelf_h = 0

        positions[orig_idx] = (current_shelf_x, current_shelf_y)
        current_shelf_x += w + padding
        current_shelf_h = max(current_shelf_h, h)

    sheet_w = max(p[0] + sizes[i][0] + padding for i, p in enumerate(positions))
    sheet_h = max(p[1] + sizes[i][1] + padding for i, p in enumerate(positions))
    return sheet_w, sheet_h, positions


def pack_rects(sizes: list[tuple[int, int]], padding: int = 0, algorithm: str = "maxrects") -> tuple[int, int, list[tuple[int, int]]]:
    """Dispatches 2D bin packing to genuine MaxRects or Shelf packing based on requested algorithm."""
    if algorithm.lower() in ("shelf", "skyline"):
        return pack_rects_shelf(sizes, padding=padding)
    return pack_rects_maxrects(sizes, padding=padding)


def export_bundle(
    result: dict[str, Any],
    out_dir: str | Path,
    write_gif: bool = True,
    write_sheet: bool = True,
    write_apng: bool = True,
    write_webp: bool = True,
    gif_bg: tuple[int, int, int] = (0, 0, 0),
    pack_mode: str = "grid",  # "grid" | "packed"
    padding: int = 0,
    extrude: int = 0,
    color_mode: str = "RGBA",  # "RGBA" | "indexed"
    palette_colors: int = 256,
    dither: str = "none",  # "none" | "floyd-steinberg"
    merge_duplicates: bool = False,
    split_tags: bool = False,
    split_layers: bool = False,
    bridge_aseprite: bool = False,
) -> Path:
    out = Path(out_dir)
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    raw_images: list[Image.Image] = result.get("frame_images") or result.get("composed_frames") or []
    frames_meta = result.get("frames", [])
    canvas = result.get("canvas") or {}
    project = result.get("project")

    # Apply indexed color quantization if requested
    if color_mode.lower() == "indexed":
        images = [quantize_to_indexed(img, palette_colors, dither) for img in raw_images]
    else:
        images = raw_images

    paths = []
    for i, img in enumerate(images):
        name = f"{i:03d}.png"
        path = frames_dir / name
        img.save(path, format="PNG")
        paths.append(f"frames/{name}")

    anim = {
        "version": 2,
        "source": result.get("source"),
        "sheet_size": result.get("sheet_size"),
        "grid": result.get("grid"),
        "canvas": {
            "w": canvas.get("w"),
            "h": canvas.get("h"),
            "anchor": {"x": canvas.get("anchor_x", 0), "y": canvas.get("anchor_y", 0)},
        },
        "color_mode": color_mode,
        "pack_mode": pack_mode,
        "extrude": extrude,
        "padding": padding,
        "master": "PNG+JSON",
        "preview_gif": "preview.gif" if write_gif else None,
        "preview_apng": "preview.apng.png" if write_apng else None,
        "preview_webp": "preview.webp" if write_webp else None,
        "spritesheet": "spritesheet.png" if write_sheet else None,
        "frames": [
            {
                "frame": m.get("frame", i),
                "file": paths[i],
                "rect": m.get("rect"),
                "anchor": m.get("anchor"),
                "pivot": m.get("pivot"),
                "offset": m.get("offset"),
                "duration": m.get("duration", 80),
                "empty": m.get("empty", False),
            }
            for i, m in enumerate(frames_meta)
        ],
    }

    anim_path = out / "animation.json"
    anim_path.write_text(json.dumps(anim, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save Project definition (.spriteproject)
    if project is not None:
        try:
            from sprite_repair.project import write_project
            write_project(out / "project.spriteproject", project, name=anim.get("source") or "project")
        except Exception as e:
            print(f"Warning: could not write project.spriteproject: {e}")

    if write_gif and images:
        _write_preview_gif(images, frames_meta, out / "preview.gif", bg=gif_bg)

    if write_sheet and images:
        _write_spritesheet(
            images,
            out / "spritesheet.png",
            frames_meta=frames_meta,
            manifest_path=out / "manifest.json",
            project=project,
            pack_mode=pack_mode,
            padding=padding,
            extrude=extrude,
            merge_duplicates=merge_duplicates,
        )

        # Split tags export if requested
        if split_tags and project and hasattr(project, "tags") and project.tags:
            for tag in project.tags:
                t_from = max(0, tag.from_frame)
                t_to = min(len(images), tag.to_frame + 1)
                tag_imgs = images[t_from:t_to]
                tag_meta = frames_meta[t_from:t_to]
                if tag_imgs:
                    safe_tag_name = "".join(c if c.isalnum() else "_" for c in tag.name)
                    _write_spritesheet(
                        tag_imgs,
                        out / f"spritesheet_tag_{safe_tag_name}.png",
                        frames_meta=tag_meta,
                        manifest_path=out / f"manifest_tag_{safe_tag_name}.json",
                        project=None,
                        pack_mode=pack_mode,
                        padding=padding,
                        extrude=extrude,
                    )

    if write_apng and images:
        _write_apng(images, frames_meta, out / "preview.apng.png")

    if write_webp and images:
        _write_webp(images, frames_meta, out / "preview.webp")

    # Aseprite Bridge export
    if bridge_aseprite:
        try:
            from sprite_repair.bridge import AsepriteBridge
            AsepriteBridge.export_to_aseprite(out, out_ase_name=f"{anim.get('source') or 'project'}.aseprite")
        except Exception as e:
            print(f"Warning: AsepriteBridge export failed: {e}")

    return out


def _write_preview_gif(
    images: list[Image.Image],
    frames_meta: list[dict[str, Any]],
    path: Path,
    bg: tuple[int, int, int] = (0, 0, 0),
) -> None:
    if not images:
        return
    durations = [m.get("duration", 80) for m in frames_meta]
    while len(durations) < len(images):
        durations.append(80)

    # Convert RGBA to palette with transparent color 0
    gif_frames = []
    for img in images:
        c = Image.new("RGBA", img.size, (bg[0], bg[1], bg[2], 0))
        c.paste(img, (0, 0), img)
        gif_frames.append(c.convert("P", palette=Image.Palette.ADAPTIVE, colors=255))

    gif_frames[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:],
        duration=durations,
        loop=0,
        transparency=0,
        disposal=2,
    )


def _write_apng(images: list[Image.Image], frames_meta: list[dict[str, Any]], path: Path) -> None:
    if not images:
        return
    durations = [m.get("duration", 80) for m in frames_meta]
    while len(durations) < len(images):
        durations.append(80)
    images[0].save(
        path,
        format="PNG",
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,
    )


def _write_webp(images: list[Image.Image], frames_meta: list[dict[str, Any]], path: Path) -> None:
    if not images:
        return
    durations = [m.get("duration", 80) for m in frames_meta]
    while len(durations) < len(images):
        durations.append(80)
    images[0].save(
        path,
        format="WEBP",
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,
        lossless=True,
    )


def _write_spritesheet(
    images: list[Image.Image],
    path: Path,
    frames_meta: list[dict[str, Any]] | None = None,
    manifest_path: Path | None = None,
    columns: int | None = None,
    project: Any | None = None,
    pack_mode: str = "grid",
    padding: int = 0,
    extrude: int = 0,
    merge_duplicates: bool = False,
) -> None:
    n = len(images)
    if n == 0:
        return

    # Apply duplicate frame merging if requested
    if merge_duplicates and frames_meta:
        unique_images: list[Image.Image] = []
        unique_meta: list[dict[str, Any]] = []
        frame_map: list[int] = []
        seen = {}
        for i, img in enumerate(images):
            h = hash(img.tobytes())
            if h in seen:
                tgt = seen[h]
                frame_map.append(tgt)
                d = frames_meta[i].get("duration", 80)
                unique_meta[tgt]["duration"] = unique_meta[tgt].get("duration", 80) + d
            else:
                seen[h] = len(unique_images)
                frame_map.append(len(unique_images))
                unique_images.append(img)
                unique_meta.append(dict(frames_meta[i]))
        render_images = unique_images
        render_meta = unique_meta
    else:
        render_images = images
        render_meta = frames_meta or [{} for _ in images]
        frame_map = list(range(n))

    # Apply extrusion to each image if requested
    if extrude > 0:
        processed_images = [extrude_image(img, extrude) for img in render_images]
    else:
        processed_images = render_images

    num_rendered = len(processed_images)
    sizes = [im.size for im in processed_images]

    if pack_mode == "packed" and num_rendered > 1:
        sheet_w, sheet_h, positions = pack_rects(sizes, padding=padding)
        sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
        frames_dict = {}
        for i, img in enumerate(processed_images):
            x, y = positions[i]
            sheet.paste(img, (x, y), img)
            # The sprite source size excludes extrusion
            orig_w, orig_h = render_images[i].size
            meta = render_meta[i] if i < len(render_meta) else {}
            anc = meta.get("anchor") or {"x": orig_w // 2, "y": orig_h}
            piv = meta.get("pivot") or anc
            key = f"frame_{i:03d}"
            frames_dict[key] = {
                "frame": {"x": x + extrude, "y": y + extrude, "w": orig_w, "h": orig_h},
                "rotated": False,
                "trimmed": False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": orig_w, "h": orig_h},
                "sourceSize": {"w": orig_w, "h": orig_h},
                "pivot": {"x": round(float(piv.get("x", orig_w // 2)) / float(orig_w), 4) if orig_w else 0.5,
                          "y": round(float(piv.get("y", orig_h)) / float(orig_h), 4) if orig_h else 1.0},
                "duration": meta.get("duration", 80),
            }
    else:
        # Standard Grid layout
        if columns is None:
            columns = int(num_rendered**0.5 + 0.999) or 1
        rows = (num_rendered + columns - 1) // columns
        max_cell_w = max(s[0] for s in sizes)
        max_cell_h = max(s[1] for s in sizes)
        step_w = max_cell_w + padding
        step_h = max_cell_h + padding
        sheet_w = columns * step_w
        sheet_h = rows * step_h
        sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
        frames_dict = {}
        for i, img in enumerate(processed_images):
            r = i // columns
            c = i % columns
            x = c * step_w
            y = r * step_h
            sheet.paste(img, (x, y), img)
            orig_w, orig_h = render_images[i].size
            meta = render_meta[i] if i < len(render_meta) else {}
            anc = meta.get("anchor") or {"x": orig_w // 2, "y": orig_h}
            piv = meta.get("pivot") or anc
            key = f"frame_{i:03d}"
            frames_dict[key] = {
                "frame": {"x": x + extrude, "y": y + extrude, "w": orig_w, "h": orig_h},
                "rotated": False,
                "trimmed": False,
                "spriteSourceSize": {"x": 0, "y": 0, "w": orig_w, "h": orig_h},
                "sourceSize": {"w": orig_w, "h": orig_h},
                "pivot": {"x": round(float(piv.get("x", orig_w // 2)) / float(orig_w), 4) if orig_w else 0.5,
                          "y": round(float(piv.get("y", orig_h)) / float(orig_h), 4) if orig_h else 1.0},
                "duration": meta.get("duration", 80),
            }

    sheet.save(path, format="PNG")
    if manifest_path:
        # Map original frames to manifest entries
        final_frames_dict = {}
        for orig_idx, mapped_idx in enumerate(frame_map):
            base_frame = frames_dict.get(f"frame_{mapped_idx:03d}")
            if base_frame:
                final_frames_dict[f"frame_{orig_idx:03d}"] = dict(base_frame)

        manifest = {
            "frames": final_frames_dict if len(final_frames_dict) == n else frames_dict,
            "meta": {
                "app": "SpriteRepair",
                "version": "2.0",
                "image": path.name,
                "format": "RGBA8888",
                "size": {"w": sheet.width, "h": sheet.height},
                "scale": "1",
                "frame_count": n,
                "pack_mode": pack_mode,
                "padding": padding,
                "extrude": extrude,
            },
        }

        tags_meta = []
        layers_meta = []
        slices_meta = []
        if project is not None:
            if hasattr(project, "tags") and project.tags:
                tags_meta = [{"name": t.name, "from": t.from_frame, "to": t.to_frame, "direction": t.direction} for t in project.tags]
            if hasattr(project, "layers") and project.layers:
                layers_meta = [{"name": l.name, "opacity": l.opacity, "blendMode": l.blend_mode} for l in project.layers if getattr(l, "type", "image") != "reference"]
            if hasattr(project, "slices") and project.slices:
                slices_meta = [{"name": s.name, "bounds": {"x": s.bounds.x, "y": s.bounds.y, "w": s.bounds.w, "h": s.bounds.h}} for s in project.slices]

        if not tags_meta:
            tags_meta = [{"name": "Main", "from": 0, "to": max(0, n - 1), "direction": "forward"}]
        if not layers_meta:
            layers_meta = [{"name": "Layer 1", "opacity": 255, "blendMode": "normal"}]

        manifest["meta"]["frameTags"] = tags_meta
        manifest["meta"]["layers"] = layers_meta
        manifest["meta"]["slices"] = slices_meta

        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        # Also write standard aseprite.json for Game Engines
        ase_path = manifest_path.parent / "aseprite.json"
        ase_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
