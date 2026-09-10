"""Animation QA: anchor jitter + body scale drift + palette consistency warnings."""
from __future__ import annotations

import math
from typing import Any
from PIL import Image


def compute_frame_color_histogram(img: Image.Image, bins: int = 4) -> list[float]:
    """Compute normalized RGB histogram for opaque/semi-opaque pixels (alpha > 16)."""
    rgba = img.convert("RGBA")
    data = rgba.getdata()
    total_bins = bins * bins * bins
    hist = [0.0] * total_bins
    count = 0

    bin_size = 256 // bins
    for r, g, b, a in data:
        if a <= 16:
            continue
        ri = min(bins - 1, r // bin_size)
        gi = min(bins - 1, g // bin_size)
        bi = min(bins - 1, b // bin_size)
        idx = (ri * bins + gi) * bins + bi
        hist[idx] += 1.0
        count += 1

    if count > 0:
        for i in range(total_bins):
            hist[i] /= count
    return hist


def histogram_distance(h1: list[float], h2: list[float]) -> float:
    """Compute Euclidean distance between two normalized histograms [0.0, ~1.414]."""
    if len(h1) != len(h2) or not h1:
        return 0.0
    sum_sq = sum((a - b) ** 2 for a, b in zip(h1, h2))
    return math.sqrt(sum_sq)


def check_palette_consistency(
    images: list[Image.Image],
    threshold: float = 0.28,
) -> list[dict[str, Any]]:
    """Compare cross-frame color distributions and flag anomalous palette drift."""
    warnings: list[dict[str, Any]] = []
    if len(images) < 2:
        return warnings

    hists = [compute_frame_color_histogram(img) for img in images]
    # Filter empty frames (no pixels)
    valid_indices = [i for i, h in enumerate(hists) if any(v > 0 for v in h)]
    if len(valid_indices) < 2:
        return warnings

    # Compute average histogram across valid frames
    dim = len(hists[0])
    avg_hist = [0.0] * dim
    for idx in valid_indices:
        for d in range(dim):
            avg_hist[d] += hists[idx][d]
    for d in range(dim):
        avg_hist[d] /= len(valid_indices)

    for idx in valid_indices:
        dist = histogram_distance(hists[idx], avg_hist)
        if dist >= threshold:
            pct = round(dist * 100.0, 1)
            warnings.append({
                "frame": idx,
                "type": "palette_drift",
                "message": f"Frame color palette drift ({pct}%) vs sequence average",
                "palette_drift": round(dist, 3),
            })
    return warnings


def analyze_animation_qa(
    frames: list[dict[str, Any]],
    images: list[Image.Image] | None = None,
) -> dict[str, Any]:
    """Compare consecutive frame anchors, character scale (height & width), and palette consistency."""
    warnings: list[dict[str, Any]] = []
    if len(frames) < 2:
        return {"ok": True, "warnings": [], "summary": "need >=2 frames"}

    anchors = []
    heights = []
    widths = []
    for f in frames:
        a = f.get("anchor") or {}
        anchors.append((int(a.get("x", 0)), int(a.get("y", 0))))
        cb = f.get("character_bbox") or {}
        if cb.get("h"):
            heights.append(float(cb["h"]))
        else:
            sz = f.get("size") or {}
            heights.append(float(sz.get("h") or 0))
        if cb.get("w"):
            widths.append(float(cb["w"]))
        else:
            sz = f.get("size") or {}
            widths.append(float(sz.get("w") or 0))

    # 1. Anchor jitter on consecutive frames
    for i in range(1, len(anchors)):
        dx = anchors[i][0] - anchors[i - 1][0]
        dy = anchors[i][1] - anchors[i - 1][1]
        sa = frames[i].get("source_anchor") or frames[i].get("anchor") or {}
        sb = frames[i - 1].get("source_anchor") or frames[i - 1].get("anchor") or {}
        if frames[i].get("source_anchor") is not None:
            dx = int(sa.get("x", 0)) - int(sb.get("x", 0))
            dy = int(sa.get("y", 0)) - int(sb.get("y", 0))
        if abs(dx) >= 3 or abs(dy) >= 3:
            warnings.append({
                "frame": frames[i].get("frame", i),
                "type": "jitter",
                "message": f"Possible jitter vs prev: X {dx:+d}px Y {dy:+d}px",
                "body_shift": {"x": dx, "y": dy},
            })

    # 2. Scale vs median height
    valid_h = [h for h in heights if h > 0]
    med_h = sorted(valid_h)[len(valid_h) // 2] if valid_h else 0.0
    if valid_h and med_h > 0:
        for i, h in enumerate(heights):
            if h <= 0:
                continue
            pct = (h - med_h) / med_h * 100.0
            if abs(pct) >= 8.0:
                warnings.append({
                    "frame": frames[i].get("frame", i),
                    "type": "scale",
                    "message": f"Body height {pct:+.1f}% vs median — possible generation inconsistency",
                    "body_height_pct": round(pct, 2),
                })

    # 3. Scale vs median width
    valid_w = [w for w in widths if w > 0]
    med_w = sorted(valid_w)[len(valid_w) // 2] if valid_w else 0.0
    if valid_w and med_w > 0:
        for i, w in enumerate(widths):
            if w <= 0:
                continue
            pct = (w - med_w) / med_w * 100.0
            if abs(pct) >= 15.0:
                warnings.append({
                    "frame": frames[i].get("frame", i),
                    "type": "scale_width",
                    "message": f"Body width {pct:+.1f}% vs median ({round(w,1)}px vs {round(med_w,1)}px)",
                    "body_width_pct": round(pct, 2),
                })

    # 4. Aspect ratio distortion
    if valid_h and valid_w and med_h > 0 and med_w > 0:
        med_ratio = med_w / med_h
        for i in range(len(frames)):
            h = heights[i]
            w = widths[i]
            if h <= 0 or w <= 0:
                continue
            ratio = w / h
            diff_ratio_pct = (ratio - med_ratio) / med_ratio * 100.0
            if abs(diff_ratio_pct) >= 20.0:
                warnings.append({
                    "frame": frames[i].get("frame", i),
                    "type": "aspect_ratio",
                    "message": f"Aspect ratio drift {diff_ratio_pct:+.1f}% vs median",
                    "aspect_ratio_drift_pct": round(diff_ratio_pct, 2),
                })

    # 5. Palette consistency QA if images available
    if images and len(images) == len(frames):
        palette_warnings = check_palette_consistency(images)
        warnings.extend(palette_warnings)

    return {
        "ok": True,
        "warnings": warnings,
        "summary": f"{len(warnings)} QA warnings" if warnings else "QA clean",
        "median_body_height": med_h if valid_h else None,
        "median_body_width": med_w if valid_w else None,
    }
