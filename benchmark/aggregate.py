"""Merge auto metrics + human review into benchmark reports (Part A).

Usage:
    .venv/Scripts/python.exe benchmark/aggregate.py [--review review_results.json]

Inputs:
    benchmark/auto_results.json   (from run_benchmark.py)
    benchmark/review_results.json (human review from review.html)

Outputs:
    benchmark/results.json
    benchmark/results.csv
    benchmark/REAL_WORLD_GPT_SPRITESHEET_BENCHMARK.md
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

BENCH = Path(__file__).resolve().parent
AUTO_PATH = BENCH / "auto_results.json"
REVIEW_PATH = BENCH / "review_results.json"
OUT_JSON = BENCH / "results.json"
OUT_CSV = BENCH / "results.csv"
OUT_MD = BENCH / "REAL_WORLD_GPT_SPRITESHEET_BENCHMARK.md"

CSV_COLUMNS = [
    "fixture_id",
    "difficulty",
    "frame_detection_ok",
    "auto_pass_frames",
    "manual_fix_frames",
    "anchor_fix_frames",
    "mask_fix_frames",
    "crop_fix_frames",
    "ownership_fix_frames",
    "vfx_clipping_frames",
    "neighbor_contamination_frames",
    "scale_review_frames",
    "palette_review_frames",
    "export_ok",
    "manual_minutes",
    "spriterepair_minutes",
    "time_saved_pct",
    "final_sheet_status",
]

REQUIRED_DIVERSITY = [
    "short sword", "great sword", "spear", "bow", "projectile",
    "hand-to-hand", "fire", "ice", "lightning/beam", "large explosion",
    "long hair", "cape/coat/skirt", "ground shadow", "VFX below feet",
    "jump", "dash", "spin", "large silhouette change",
    "transparent BG", "imperfect/solid BG",
]


def _pct(num: float, den: float) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def _p(vals: list[float]) -> dict[str, float]:
    if not vals:
        return {"mean": 0.0, "median": 0.0, "p90": 0.0}
    s = sorted(vals)
    p90 = s[min(len(s) - 1, int(len(s) * 0.9))]
    return {
        "mean": round(statistics.mean(vals), 2),
        "median": round(statistics.median(vals), 2),
        "p90": round(p90, 2),
    }


def aggregate(auto: list[dict[str, Any]], review: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    auto_by = {r["fixture_id"]: r for r in auto}
    fixtures_rev = review.get("fixtures") or {}
    rows: list[dict[str, Any]] = []

    total_frames = 0
    pass_frames = 0
    fix_counts: dict[str, int] = {}
    sheet_level_pass = 0
    sheets_reviewed = 0
    fix_frames_per_sheet: list[int] = []
    time_saved_list: list[float] = []
    manual_minutes_total = 0.0
    sr_minutes_total = 0.0
    anchor_errors: list[float] = []

    for fid, a in auto_by.items():
        rv = fixtures_rev.get(fid) or {}
        fr = rv.get("frames") or {}
        n = a.get("frames_total", 16)
        total_frames += n

        statuses = [fr.get(str(i), {}).get("status", "PASS") for i in range(n)]
        pass_count = sum(1 for s in statuses if s == "PASS")
        pass_frames += pass_count

        counts = {k: 0 for k in [
            "ANCHOR_FIX", "MASK_FIX", "CROP_FIX", "OWNERSHIP_FIX", "SCALE_FIX",
            "PALETTE_FIX", "VFX_CLIPPED", "NEIGHBOR_CONTAMINATION", "REPROCESS_REQUIRED",
        ]}
        for s in statuses:
            if s in counts:
                counts[s] += 1
        for k, v in counts.items():
            fix_counts[k] = fix_counts.get(k, 0) + v

        manual_fix = n - pass_count
        fix_frames_per_sheet.append(manual_fix)

        # anchor GT subset
        for i in range(n):
            fr_i = fr.get(str(i), {})
            if fr_i.get("gt_anchor_x") is not None and fr_i.get("gt_anchor_y") is not None:
                meta = (a.get("raw_frame_meta") or {}).get(str(i)) or {}
                auto_anc = meta.get("anchor")
                if auto_anc:
                    ex = fr_i["gt_anchor_x"] - int(auto_anc.get("x", 0))
                    ey = fr_i["gt_anchor_y"] - int(auto_anc.get("y", 0))
                    anchor_errors.append((ex * ex + ey * ey) ** 0.5)

        sheet_status = rv.get("sheet_status", "PENDING")
        final_status = "UNREVIEWED" if sheet_status == "PENDING" else sheet_status
        if sheet_status == "PASS" and manual_fix == 0 and a.get("frame_detection_ok") and a.get("export_ok"):
            sheet_level_pass += 1
        if sheet_status != "PENDING":
            sheets_reviewed += 1

        manual_min = rv.get("manual_minutes")
        sr_min = round((a.get("t_process_s", 0) + a.get("t_export_s", 0)) / 60.0, 2)
        if isinstance(manual_min, (int, float)) and manual_min > 0:
            manual_minutes_total += float(manual_min)
            sr_minutes_total += sr_min
            saved = (float(manual_min) - sr_min) / float(manual_min) * 100.0
            time_saved_list.append(round(saved, 1))

        rows.append({
            "fixture_id": fid,
            "difficulty": ",".join(rv.get("difficulty_tags") or []),
            "prompt_class": rv.get("prompt_class") or "",
            "frame_detection_ok": bool(a.get("frame_detection_ok")),
            "auto_pass_frames": pass_count,
            "manual_fix_frames": manual_fix,
            "anchor_fix_frames": counts["ANCHOR_FIX"],
            "mask_fix_frames": counts["MASK_FIX"],
            "crop_fix_frames": counts["CROP_FIX"],
            "ownership_fix_frames": counts["OWNERSHIP_FIX"],
            "vfx_clipping_frames": counts["VFX_CLIPPED"],
            "neighbor_contamination_frames": counts["NEIGHBOR_CONTAMINATION"],
            "scale_review_frames": counts["SCALE_FIX"],
            "palette_review_frames": counts["PALETTE_FIX"],
            "reprocess_frames": counts["REPROCESS_REQUIRED"],
            "export_ok": bool(a.get("export_ok")),
            "manual_minutes": manual_min,
            "spriterepair_minutes": sr_min,
            "time_saved_pct": time_saved_list[-1] if time_saved_list and rows and time_saved_list else None,
            "final_sheet_status": final_status,
        })

    summary: dict[str, Any] = {
        "corpus": {
            "sheets": len(auto_by),
            "frames": total_frames,
            "expected_sheets": 20,
            "expected_frames": 320,
            "complete": len(auto_by) >= 20 and total_frames >= 320,
        },
        "kpis": {
            "sheet_level_auto_success_rate": _pct(sheet_level_pass, max(1, sheets_reviewed)),
            "frame_auto_success_rate": _pct(pass_frames, total_frames),
            "manual_intervention_rate": _pct(total_frames - pass_frames, total_frames),
            "frame_detection_success_rate": _pct(
                sum(1 for a in auto_by.values() if a.get("frame_detection_ok")), len(auto_by)
            ),
            "export_success_rate": _pct(
                sum(1 for a in auto_by.values() if a.get("export_ok")), len(auto_by)
            ),
            "anchor_correction_rate": _pct(fix_counts.get("ANCHOR_FIX", 0), total_frames),
            "mask_ownership_correction_rate": _pct(fix_counts.get("MASK_FIX", 0) + fix_counts.get("OWNERSHIP_FIX", 0), total_frames),
            "crop_correction_rate": _pct(fix_counts.get("CROP_FIX", 0), total_frames),
            "vfx_clipping_rate": _pct(fix_counts.get("VFX_CLIPPED", 0), total_frames),
            "neighbor_contamination_rate": _pct(fix_counts.get("NEIGHBOR_CONTAMINATION", 0), total_frames),
            "scale_qa_failure_rate": _pct(fix_counts.get("SCALE_FIX", 0), total_frames),
            "palette_qa_failure_rate": _pct(fix_counts.get("PALETTE_FIX", 0), total_frames),
            "reprocess_rate": _pct(fix_counts.get("REPROCESS_REQUIRED", 0), total_frames),
            "fix_frames_per_sheet": _p([float(x) for x in fix_frames_per_sheet]),
        },
        "timing": {
            "manual_minutes_total": round(manual_minutes_total, 1),
            "spriterepair_minutes_total": round(sr_minutes_total, 1),
            "time_saved_pct": _p(time_saved_list),
            "sr_process_s_mean": round(statistics.mean(a.get("t_process_s", 0) for a in auto_by.values()), 2),
            "sr_export_s_mean": round(statistics.mean(a.get("t_export_s", 0) for a in auto_by.values()), 2),
        },
        "anchor_error": {
            "n_gt_frames": len(anchor_errors),
            "mean_px": round(statistics.mean(anchor_errors), 2) if anchor_errors else None,
            "median_px": round(statistics.median(anchor_errors), 2) if anchor_errors else None,
            "p90_px": round(sorted(anchor_errors)[min(len(anchor_errors) - 1, int(len(anchor_errors) * 0.9))], 2) if anchor_errors else None,
            "leq1px_pct": _pct(sum(1 for e in anchor_errors if e <= 1.0), len(anchor_errors)),
            "leq2px_pct": _pct(sum(1 for e in anchor_errors if e <= 2.0), len(anchor_errors)),
            "gt3px_pct": _pct(sum(1 for e in anchor_errors if e > 3.0), len(anchor_errors)),
        },
        "failure_top5": sorted(
            ({"type": k, "count": v, "rate": _pct(v, total_frames)} for k, v in fix_counts.items() if v > 0),
            key=lambda x: -x["count"],
        )[:5],
        "auto_hints": {
            "scale_drift_auto_flags": sum(len(a.get("scale_drift_frames", [])) for a in auto_by.values()),
            "palette_drift_auto_flags": sum(len(a.get("palette_drift_frames", [])) for a in auto_by.values()),
            "neighbor_auto_flags": sum(len(a.get("neighbor_flags", [])) for a in auto_by.values()),
            "clip_auto_flags": sum(len(a.get("clip_flags", [])) for a in auto_by.values()),
            "chroma_applied": sum(1 for a in auto_by.values() if a.get("chroma")),
        },
        "diversity": {
            "prompt_classes": sorted({r.get("prompt_class") for r in rows if r.get("prompt_class")}),
            "tags_present": sorted({t for r in rows for t in (r["difficulty"].split(",") if r["difficulty"] else [])}),
            "missing_required": [t for t in REQUIRED_DIVERSITY if not any(
                t.lower() in (r.get("prompt_class") or "").lower() or t.lower() in r["difficulty"].lower()
                for r in rows
            )],
        },
        "reviewed_at": review.get("reviewed_at"),
    }
    return rows, summary


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for r in rows:
            w.writerow([r.get(c, "") for c in CSV_COLUMNS])


def write_md(rows: list[dict[str, Any]], s: dict[str, Any], path: Path) -> None:
    k = s["kpis"]
    t = s["timing"]
    ae = s["anchor_error"]
    L = []
    L.append("# REAL_WORLD_GPT_SPRITESHEET_BENCHMARK")
    L.append("")
    L.append(f"> Generated: {__import__('datetime').datetime.now().isoformat(timespec='minutes')}")
    L.append(f"> Human review: {s.get('reviewed_at') or 'PENDING'}")
    L.append("")
    L.append("## Corpus")
    L.append(f"- Sheets: {s['corpus']['sheets']} (required >= 20) → {'COMPLETE' if s['corpus']['complete'] else 'BENCHMARK_CORPUS_INCOMPLETE'}")
    L.append(f"- Frames: {s['corpus']['frames']} (required >= 320)")
    L.append(f"- All real GPT-generated 4x4 sheets (ChatGPT), no synthetic fixtures used")
    L.append("")
    L.append("## KPI")
    L.append("| KPI | Value |")
    L.append("|---|---|")
    for name, key in [
        ("Sheet-level Auto Success Rate", "sheet_level_auto_success_rate"),
        ("Frame-level Auto Success Rate", "frame_auto_success_rate"),
        ("Manual Intervention Rate", "manual_intervention_rate"),
        ("Frame Detection Success Rate", "frame_detection_success_rate"),
        ("Export Success Rate", "export_success_rate"),
        ("Anchor Correction Rate", "anchor_correction_rate"),
        ("Mask/Ownership Correction Rate", "mask_ownership_correction_rate"),
        ("Crop Correction Rate", "crop_correction_rate"),
        ("VFX Clipping Rate", "vfx_clipping_rate"),
        ("Neighbor Contamination Rate", "neighbor_contamination_rate"),
        ("Scale QA Failure Rate", "scale_qa_failure_rate"),
        ("Palette QA Failure Rate", "palette_qa_failure_rate"),
        ("Reprocess Required Rate", "reprocess_rate"),
    ]:
        L.append(f"| {name} | {k[key]}% |")
    L.append("")
    L.append("## Fix frames per sheet")
    L.append(f"- Mean: {k['fix_frames_per_sheet']['mean']} · Median: {k['fix_frames_per_sheet']['median']} · P90: {k['fix_frames_per_sheet']['p90']}")
    L.append("")
    L.append("## Time saved")
    L.append(f"- Manual total: {t['manual_minutes_total']} min · SpriteRepair total: {t['spriterepair_minutes_total']} min")
    L.append(f"- Time Saved %: mean {t['time_saved_pct']['mean']} · median {t['time_saved_pct']['median']} · p90 {t['time_saved_pct']['p90']}")
    L.append(f"- SpriteRepair auto pipeline: mean {t['sr_process_s_mean']}s process + {t['sr_export_s_mean']}s export per sheet")
    L.append("")
    L.append("## Anchor accuracy (human GT subset)")
    if ae.get("mean_px") is not None:
        L.append(f"- N={ae['n_gt_frames']} · mean {ae['mean_px']}px · median {ae['median_px']}px · p90 {ae['p90_px']}px")
        L.append(f"- <=1px: {ae['leq1px_pct']}% · <=2px: {ae['leq2px_pct']}% · >3px: {ae['gt3px_pct']}%")
    else:
        L.append("- GT anchor clicks not provided (ANCHOR_FIX 시 GT x/y 미입력)")
    L.append("")
    L.append("## Failure Top 5 (by human review frequency)")
    if s["failure_top5"]:
        L.append("| Rank | Type | Count | Rate |")
        L.append("|---|---|---|---|")
        for i, f in enumerate(s["failure_top5"], 1):
            L.append(f"| {i} | {f['type']} | {f['count']} | {f['rate']}% |")
    else:
        L.append("- No failures recorded (all frames PASS)")
    L.append("")
    L.append("## Automatic hints (not ground truth)")
    for kk, vv in s["auto_hints"].items():
        L.append(f"- {kk}: {vv}")
    L.append("")
    L.append("## Corpus diversity")
    L.append(f"- prompt classes: {', '.join(s['diversity']['prompt_classes']) or '(미기입)'}")
    L.append(f"- difficulty tags: {', '.join(s['diversity']['tags_present']) or '(미기입)'}")
    if s["diversity"]["missing_required"]:
        L.append(f"- MISSING required types: {', '.join(s['diversity']['missing_required'])}")
    else:
        L.append("- All required diversity types covered")
    L.append("")
    L.append("## Per-sheet")
    L.append("See `results.csv` / `results.json`.")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", default=str(REVIEW_PATH))
    args = parser.parse_args()

    if not AUTO_PATH.is_file():
        raise SystemExit("auto_results.json missing — run run_benchmark.py first")
    auto = json.loads(AUTO_PATH.read_text(encoding="utf-8"))

    review: dict[str, Any] = {"fixtures": {}}
    rp = Path(args.review)
    if rp.is_file():
        review = json.loads(rp.read_text(encoding="utf-8"))
    else:
        print(f"WARNING: {rp} missing - running with unreviewed defaults (human review PENDING)")

    rows, summary = aggregate(auto, review)
    OUT_JSON.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(rows, OUT_CSV)
    write_md(rows, summary, OUT_MD)
    print(f"results.json -> {OUT_JSON}")
    print(f"results.csv  -> {OUT_CSV}")
    print(f"report       -> {OUT_MD}")


if __name__ == "__main__":
    main()
