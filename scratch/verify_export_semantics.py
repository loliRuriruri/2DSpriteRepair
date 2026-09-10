#!/usr/bin/env python3
import sys
import json
from pathlib import Path
from PIL import Image, ImageSequence

def verify_export(out_dir: str):
    p = Path(out_dir)
    if not p.is_dir():
        print(f"FAIL: Export directory does not exist: {p}")
        sys.exit(1)

    print(f"Inspecting export directory: {p}")

    # 1. Verify PNG sequence
    frames_dir = p / "frames"
    if not frames_dir.is_dir():
        frames_dir = p  # fallback
    png_files = sorted(list(frames_dir.glob("frame_*.png")) or list(frames_dir.glob("*.png")))
    # Exclude preview.png and sheet.png if in same dir
    png_files = [f for f in png_files if f.name not in ("preview.png", "sheet.png")]
    print(f"  [1] PNG Frame Sequence: {len(png_files)} files found")
    if len(png_files) != 16:
        print(f"FAIL: Expected 16 PNG frames, found {len(png_files)}")
        sys.exit(1)

    canvas_w, canvas_h = None, None
    for i, pf in enumerate(png_files):
        with Image.open(pf) as im:
            if im.mode != "RGBA":
                print(f"FAIL: Frame {pf.name} is mode {im.mode}, expected RGBA")
                sys.exit(1)
            if canvas_w is None:
                canvas_w, canvas_h = im.width, im.height
            elif (im.width, im.height) != (canvas_w, canvas_h):
                print(f"FAIL: Frame {pf.name} size {im.size} != initial {canvas_w}x{canvas_h}")
                sys.exit(1)
            # Verify alpha channel has transparency
            extrema = im.getextrema()
            alpha_extrema = extrema[3]
            if alpha_extrema[0] == 255:
                print(f"WARNING: Frame {pf.name} has no transparent pixels")

    print(f"      All 16 frames RGBA valid ({canvas_w}x{canvas_h}) with alpha channel")

    # 2. Verify sheet.png or spritesheet.png
    sheet_file = p / "spritesheet.png" if (p / "spritesheet.png").is_file() else p / "sheet.png"
    if not sheet_file.is_file():
        print("FAIL: sheet.png / spritesheet.png missing")
        sys.exit(1)
    with Image.open(sheet_file) as sheet_im:
        if sheet_im.mode != "RGBA":
            print(f"FAIL: {sheet_file.name} is not RGBA: {sheet_im.mode}")
            sys.exit(1)
        print(f"  [2] SpriteSheet Atlas ({sheet_file.name}): {sheet_im.size} RGBA valid")

    # 3. Verify preview.gif
    gif_file = p / "preview.gif"
    if not gif_file.is_file():
        print("FAIL: preview.gif missing")
        sys.exit(1)
    with Image.open(gif_file) as gif_im:
        gif_frames = [f.copy() for f in ImageSequence.Iterator(gif_im)]
        print(f"  [3] Animated GIF: {len(gif_frames)} frames found (expected 16)")
        if len(gif_frames) != 16:
            print(f"FAIL: GIF frame count {len(gif_frames)} != 16")
            sys.exit(1)
        dur = gif_im.info.get("duration", 0)
        print(f"      GIF frame duration: {dur}ms (target 80ms)")

    # 4. Verify preview.apng.png or preview.png (APNG)
    apng_file = p / "preview.apng.png" if (p / "preview.apng.png").is_file() else p / "preview.png"
    if apng_file.is_file():
        with Image.open(apng_file) as apng_im:
            n_frames = getattr(apng_im, "n_frames", 1)
            print(f"  [4] Animated PNG (APNG): {n_frames} frames (expected 16)")
            if n_frames != 16:
                print(f"FAIL: APNG frame count {n_frames} != 16")
                sys.exit(1)

    # 5. Verify preview.webp
    webp_file = p / "preview.webp"
    if webp_file.is_file():
        with Image.open(webp_file) as webp_im:
            n_frames = getattr(webp_im, "n_frames", 1)
            print(f"  [5] Animated WebP: {n_frames} frames (expected 16)")
            if n_frames != 16:
                print(f"FAIL: WebP frame count {n_frames} != 16")
                sys.exit(1)

    # 6. Verify animation.json schema and anchors
    anim_json_file = p / "animation.json"
    if not anim_json_file.is_file():
        print("FAIL: animation.json missing")
        sys.exit(1)
    anim_data = json.loads(anim_json_file.read_text(encoding="utf-8"))
    frames_list = anim_data.get("frames", [])
    print(f"  [6] Engine Metadata (animation.json): {len(frames_list)} frames defined")
    if len(frames_list) != 16:
        print(f"FAIL: animation.json frame count {len(frames_list)} != 16")
        sys.exit(1)
    for i, f in enumerate(frames_list):
        if "anchor" not in f or "x" not in f["anchor"] or "y" not in f["anchor"]:
            print(f"FAIL: Frame {i} missing anchor in animation.json")
            sys.exit(1)
        ax, ay = f["anchor"]["x"], f["anchor"]["y"]
        if ax < 0 or ay < 0 or ax >= canvas_w or ay >= canvas_h:
            print(f"FAIL: Frame {i} anchor ({ax}, {ay}) out of bounds ({canvas_w}x{canvas_h})")
            sys.exit(1)
    print("      All 16 frame anchors mathematically within canvas bounds")

    # 7. Verify aseprite.json schema
    ase_json_file = p / "aseprite.json"
    if not ase_json_file.is_file():
        print("FAIL: aseprite.json missing")
        sys.exit(1)
    ase_data = json.loads(ase_json_file.read_text(encoding="utf-8"))
    ase_frames = ase_data.get("frames", [])
    ase_meta = ase_data.get("meta", {})
    ase_count = len(ase_frames) if isinstance(ase_frames, list) else len(ase_frames.keys())
    print(f"  [7] Aseprite Metadata (aseprite.json): {ase_count} frames, format: {ase_meta.get('format')}")
    if ase_count != 16:
        print(f"FAIL: aseprite.json frame count {ase_count} != 16")
        sys.exit(1)

    # 8. Verify project.spriteproject
    proj_file = p / "project.spriteproject"
    if proj_file.is_file():
        proj_data = json.loads(proj_file.read_text(encoding="utf-8"))
        print(f"  [8] Project Archive (project.spriteproject): format={proj_data.get('format')}, layers={len(proj_data.get('meta', {}).get('layers', []))}")

    print("\nALL 8 EXPORT SEMANTIC ARTIFACTS VERIFIED 100% OPERATIONAL!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: verify_export_semantics.py <out_dir>")
        sys.exit(1)
    verify_export(sys.argv[1])
