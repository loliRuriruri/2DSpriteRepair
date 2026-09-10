"""CLI entry: python -m sprite_repair sheet.png --cols 4 --rows 4 --out outdir"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import process_sheet
from .export import export_bundle


def main() -> None:
    ap = argparse.ArgumentParser(description="Sprite Repair CLI")
    ap.add_argument("sheet", type=Path, help="Input spritesheet PNG")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--duration", type=int, default=80, help="Frame duration ms")
    ap.add_argument("--pad", type=int, default=2, help="Crop pad pixels")
    ap.add_argument("--alpha", type=int, default=16, help="Alpha threshold 0-255")
    ap.add_argument("--out", type=Path, default=Path("workspace/cli_export"))
    args = ap.parse_args()

    result = process_sheet(
        args.sheet,
        cols=args.cols,
        rows=args.rows,
        alpha_threshold=args.alpha,
        pad=args.pad,
        duration_ms=args.duration,
    )
    out = export_bundle(result, args.out, write_gif=True, write_sheet=True)
    meta = {k: v for k, v in result.items() if k != "frame_images"}
    print(json.dumps({"ok": True, "out": str(out), "canvas": meta.get("canvas"), "frames": len(meta.get("frames", []))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
