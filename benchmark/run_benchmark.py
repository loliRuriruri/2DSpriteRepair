"""Real-world GPT 4x4 spritesheet benchmark runner (Part A).

Runs the full SpriteRepair pipeline (grid seed -> expanded bbox -> character/
VFX split -> foot anchor -> global canvas -> export bundle) over the corpus in
benchmark/corpus/, records automatic metrics, verifies every export format by
re-decoding, and generates before/after artifacts + a human-review page.

Usage:
    .venv/Scripts/python.exe benchmark/run_benchmark.py [--limit N] [--fixture gpt_sheet_001]

Outputs:
    benchmark/auto_results.json
    benchmark/out/<fixture_id>/...        (export bundles)
    benchmark/before_after/<fixture_id>_after.png
    benchmark/preview/<fixture_id>_frames.png
    benchmark/review.html                 (human ground-truth form)
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import warnings
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", category=DeprecationWarning)

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "benchmark"
CORPUS = BENCH / "corpus"
OUT = BENCH / "out"
BEFORE_AFTER = BENCH / "before_after"
PREVIEW = BENCH / "preview"
FAILURES = BENCH / "failures"

import sys
sys.path.insert(0, str(ROOT))

from sprite_repair.pipeline import process_sheet  # noqa: E402
from sprite_repair.export import export_bundle  # noqa: E402


FRAME_STATUSES = [
    "PASS",
    "ANCHOR_FIX",
    "MASK_FIX",
    "CROP_FIX",
    "OWNERSHIP_FIX",
    "SCALE_FIX",
    "PALETTE_FIX",
    "VFX_CLIPPED",
    "NEIGHBOR_CONTAMINATION",
    "REPROCESS_REQUIRED",
]

DIFFICULTY_TAGS = [
    "large_vfx",
    "neighbor_overflow",
    "low_contrast",
    "shadow_below_feet",
    "hair_below_waist",
    "cape",
    "weapon_crosses_cell",
    "character_translation",
    "jump",
    "extreme_pose",
    "color_shift",
    "scale_drift",
    "irregular_grid",
    "non_divisible_sheet_size",
]

REQUIRED_DIVERSITY = [
    "short sword", "great sword", "spear", "bow", "projectile",
    "hand-to-hand", "fire", "ice", "lightning/beam", "large explosion",
    "long hair", "cape/coat/skirt", "ground shadow", "VFX below feet",
    "jump", "dash", "spin", "large silhouette change",
    "transparent BG", "imperfect/solid BG",
]


def _alpha_bbox(img: Image.Image, threshold: int = 12):
    mask = img.getchannel("A").point(lambda a: 255 if a > threshold else 0)
    return mask.getbbox()


def _border_touch_ratio(img: Image.Image, threshold: int = 64, margin: int = 1) -> float:
    """Fraction of opaque content pixels touching the crop border (VFX clip hint)."""
    w, h = img.size
    if w <= 2 or h <= 2:
        return 0.0
    a = img.getchannel("A")
    border_px = []
    border_px.extend(a.crop((0, 0, w, margin)).getdata())
    border_px.extend(a.crop((0, h - margin, w, h)).getdata())
    border_px.extend(a.crop((0, 0, margin, h)).getdata())
    border_px.extend(a.crop((w - margin, 0, w, h)).getdata())
    touching = sum(1 for v in border_px if v > threshold)
    total = sum(1 for v in a.getdata() if v > threshold)
    if total == 0:
        return 0.0
    return touching / float(total)


def _neighbor_overlap_ratio(rect: dict[str, int], seed: dict[str, int]) -> float:
    """Fraction of crop rect lying outside its own seed cell (neighbor steal hint)."""
    rx, ry, rw, rh = rect["x"], rect["y"], rect["w"], rect["h"]
    sx, sy, sw, sh = seed["x"], seed["y"], seed["w"], seed["h"]
    ix0, iy0 = max(rx, sx), max(ry, sy)
    ix1, iy1 = min(rx + rw, sx + sw), min(ry + rh, sy + sh)
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    area = max(1, rw * rh)
    return 1.0 - inter / float(area)


def _mean_rgb(img: Image.Image) -> tuple[float, float, float]:
    """Mean RGB of opaque pixels (robust color-shift signature)."""
    rgb = img.convert("RGB")
    a = img.getchannel("A")
    n = 0
    sr = sg = sb = 0
    for (r, g, b), av in zip(rgb.getdata(), a.getdata()):
        if av <= 32:
            continue
        sr += r
        sg += g
        sb += b
        n += 1
    if n == 0:
        return (0.0, 0.0, 0.0)
    return (sr / n, sg / n, sb / n)


def _rgb_dist(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def compose_canvas_preview(result: dict[str, Any]) -> Image.Image:
    """Reproduce the global canvas composite from composed frames."""
    canvas = result["canvas"]
    w, h = int(canvas["w"]), int(canvas["h"])
    sheet = Image.new("RGBA", (w, h), (40, 44, 56, 255))
    for img, meta in zip(result["frame_images"], result["frames"]):
        off = meta.get("offset") or {"x": 0, "y": 0}
        sheet.paste(img, (int(off["x"]), int(off["y"])), img)
    return sheet


def frames_contact_sheet(images: list[Image.Image], labels: bool = True) -> Image.Image:
    n = len(images)
    if n == 0:
        return Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    cols = 4
    rows = (n + cols - 1) // cols
    cell_w = max(img.width for img in images) + 4
    cell_h = max(img.height for img in images) + 4
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (24, 26, 32, 255))
    draw = ImageDraw.Draw(sheet)
    for i, img in enumerate(images):
        r, c = divmod(i, cols)
        sheet.paste(img, (c * cell_w + 2, r * cell_h + 2), img)
        if labels:
            draw.text((c * cell_w + 4, r * cell_h + 4), str(i), fill=(255, 220, 80, 255))
    return sheet


def run_one(fixture: dict[str, Any]) -> dict[str, Any]:
    fid = fixture["fixture_id"]
    sheet_path = CORPUS / (fid + ".png")
    out_dir = OUT / fid
    t0 = time.time()
    try:
        result = process_sheet(sheet_path, cols=4, rows=4)
    except Exception as e:  # noqa: BLE001
        return {"fixture_id": fid, "pipeline_error": str(e), "pipeline_ok": False}
    t_process = round(time.time() - t0, 2)

    raw_frames = result["raw_frames"]
    frames = result["frames"]
    n = len(raw_frames)
    non_empty = [i for i, m in enumerate(raw_frames) if not m.get("empty")]

    # --- frame detection ---
    frame_detection_ok = (n == 16) and (len(non_empty) == 16)

    # --- anchor spread (composed canvas coords) ---
    anchors = [m.get("anchor") or {"x": 0, "y": 0} for m in frames if not m.get("empty")]
    xs = [a["x"] for a in anchors]
    ys = [a["y"] for a in anchors]
    def _stats(vals: list[float]) -> dict[str, float]:
        if not vals:
            return {"median": 0.0, "stdev": 0.0, "max_dev": 0.0}
        vals_s = sorted(vals)
        med = vals_s[len(vals_s) // 2]
        var = sum((v - med) ** 2 for v in vals) / len(vals)
        return {
            "median": round(med, 2),
            "stdev": round(var ** 0.5, 2),
            "max_dev": round(max(abs(v - med) for v in vals), 2),
        }
    anchor_stats = {"x": _stats(xs), "y": _stats(ys)}
    anchor_y_gt3 = sum(1 for v in ys if abs(v - anchor_stats["y"]["median"]) > 3.0)

    # --- scale drift ---
    char_heights = []
    for m in raw_frames:
        cb = m.get("character_bbox") or {}
        ch = cb.get("h")
        if ch:
            char_heights.append(float(ch))
    scale_drift_frames: list[int] = []
    scale_stats: dict[str, float] = {}
    if char_heights:
        med_h = sorted(char_heights)[len(char_heights) // 2]
        for i, m in enumerate(raw_frames):
            cb = m.get("character_bbox") or {}
            ch = cb.get("h")
            if ch and med_h > 0 and abs(ch - med_h) / med_h > 0.10:
                scale_drift_frames.append(i)
        scale_stats = {
            "median_char_h": round(med_h, 2),
            "min": round(min(char_heights), 2),
            "max": round(max(char_heights), 2),
            "p90_ratio": round(sorted(abs(h - med_h) / med_h for h in char_heights)[int(len(char_heights) * 0.9)] if len(char_heights) > 1 else 0, 4),
        }

    # --- palette drift (mean RGB distance vs frame median) ---
    means = [_mean_rgb(img) for img in result["raw_frame_images"]]
    med = tuple(sorted(c[i] for c in means)[len(means) // 2] for i in range(3))
    pal_dists = [_rgb_dist(m, med) for m in means]
    palette_drift_frames = [i for i, d in enumerate(pal_dists) if d > 24.0]
    palette_max_dist = round(max(pal_dists), 2) if pal_dists else 0.0

    # --- neighbor contamination / border clipping hints ---
    neighbor_flags: list[int] = []
    clip_flags: list[int] = []
    for m, img in zip(raw_frames, result["raw_frame_images"]):
        i = int(m.get("frame", 0))
        if m.get("empty"):
            continue
        rect = m.get("rect") or {}
        seed = m.get("seed") or {}
        if rect and seed and _neighbor_overlap_ratio(rect, seed) > 0.30:
            neighbor_flags.append(i)
        if _border_touch_ratio(img) > 0.10:
            clip_flags.append(i)

    # --- anchor lands at character bottom rate (proxy for foot-anchor correctness) ---
    anchor_bottom_hits = 0
    anchor_bottom_total = 0
    for m in raw_frames:
        if m.get("empty"):
            continue
        cb = m.get("character_bbox") or {}
        anc = m.get("anchor") or {}
        if cb and anc:
            anchor_bottom_total += 1
            bottom = cb.get("y", 0) + cb.get("h", 0)
            if abs(int(anc.get("y", 0)) - bottom) <= 2:
                anchor_bottom_hits += 1
    anchor_bottom_rate = round(anchor_bottom_hits / float(anchor_bottom_total), 3) if anchor_bottom_total else None

    # --- export + verification ---
    export_ok = False
    export_report: dict[str, Any] = {}
    try:
        t2 = time.time()
        export_bundle(result, out_dir)
        t_export = round(time.time() - t2, 2)
        export_report = verify_export(out_dir, n)
        export_ok = bool(export_report.get("ok"))
    except Exception as e:  # noqa: BLE001
        t_export = -1.0
        export_report = {"error": str(e)}

    # --- artifacts ---
    try:
        after = compose_canvas_preview(result)
        after.save(BEFORE_AFTER / f"{fid}_after.png")
    except Exception as e:  # noqa: BLE001
        export_report["artifact_error"] = str(e)
    try:
        cs = frames_contact_sheet(result["raw_frame_images"])
        cs.save(PREVIEW / f"{fid}_frames.png")
    except Exception as e:  # noqa: BLE001
        pass

    raw_frame_meta = {}
    for m, img in zip(raw_frames, result["raw_frame_images"]):
        raw_frame_meta[str(m.get("frame", 0))] = {
            "anchor": m.get("anchor"),
            "size": {"w": img.width, "h": img.height},
            "character_bbox": m.get("character_bbox"),
            "empty": bool(m.get("empty")),
        }

    return {
        "fixture_id": fid,
        "pipeline_ok": True,
        "source_file": fixture.get("source_file"),
        "sheet_size": result["sheet_size"],
        "chroma": bool(result.get("chroma_stats")),
        "t_process_s": t_process,
        "t_export_s": t_export,
        "frames_total": n,
        "frames_nonempty": len(non_empty),
        "frame_detection_ok": frame_detection_ok,
        "anchor_stats": anchor_stats,
        "anchor_y_gt3": anchor_y_gt3,
        "scale_drift_frames": scale_drift_frames,
        "scale_stats": scale_stats,
        "palette_drift_frames": palette_drift_frames,
        "palette_max_dist": palette_max_dist,
        "neighbor_flags": neighbor_flags,
        "clip_flags": clip_flags,
        "anchor_bottom_rate": anchor_bottom_rate,
        "export_ok": export_ok,
        "export_report": export_report,
        "canvas": result["canvas"],
        "raw_frame_meta": raw_frame_meta,
    }


def verify_export(out_dir: Path, expected_frames: int) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    ok = True

    def _ck(name: str, cond: bool, detail: Any = None) -> None:
        nonlocal ok
        checks[name] = {"ok": bool(cond), "detail": detail}
        if not cond:
            ok = False

    # PNG sequence
    pngs = sorted((out_dir / "frames").glob("*.png")) if (out_dir / "frames").is_dir() else []
    _ck("png_count", len(pngs) == expected_frames, len(pngs))
    alpha_ok = True
    for p in pngs:
        try:
            im = Image.open(p)
            if im.mode not in ("RGBA", "LA", "P"):
                alpha_ok = False
        except Exception:  # noqa: BLE001
            alpha_ok = False
    _ck("png_alpha", alpha_ok)

    # GIF
    gif = out_dir / "preview.gif"
    if gif.is_file():
        try:
            im = Image.open(gif)
            _ck("gif_frames", im.n_frames == expected_frames, im.n_frames)
        except Exception as e:  # noqa: BLE001
            _ck("gif_frames", False, str(e))
    else:
        _ck("gif_frames", False, "missing")

    # APNG
    apng = out_dir / "preview.apng.png"
    if apng.is_file():
        try:
            im = Image.open(apng)
            _ck("apng_frames", im.n_frames == expected_frames, im.n_frames)
        except Exception as e:  # noqa: BLE001
            _ck("apng_frames", False, str(e))
    else:
        _ck("apng_frames", False, "missing")

    # WebP
    webp = out_dir / "preview.webp"
    if webp.is_file():
        try:
            im = Image.open(webp)
            _ck("webp_frames", im.n_frames == expected_frames, im.n_frames)
        except Exception as e:  # noqa: BLE001
            _ck("webp_frames", False, str(e))
    else:
        _ck("webp_frames", False, "missing")

    # Spritesheet + manifest (packed atlas)
    sheet = out_dir / "spritesheet.png"
    manifest = out_dir / "manifest.json"
    if sheet.is_file() and manifest.is_file():
        try:
            im = Image.open(sheet)
            m = json.loads(manifest.read_text(encoding="utf-8"))
            fcount = len(m.get("frames") or {})
            _ck("atlas", im.size[0] > 0 and fcount == expected_frames, {"size": im.size, "frames": fcount})
        except Exception as e:  # noqa: BLE001
            _ck("atlas", False, str(e))
    else:
        _ck("atlas", False, "missing")

    # animation.json
    anim = out_dir / "animation.json"
    if anim.is_file():
        try:
            a = json.loads(anim.read_text(encoding="utf-8"))
            f = a.get("frames") or []
            _ck("json_frames", len(f) == expected_frames, len(f))
            _ck("json_canvas", bool(a.get("canvas") and a["canvas"].get("w")), a.get("canvas"))
            _ck("json_anchors", all("anchor" in x for x in f))
        except Exception as e:  # noqa: BLE001
            _ck("json_frames", False, str(e))
    else:
        _ck("json_frames", False, "missing")

    checks["ok"] = ok
    return checks


def build_review_html(auto_results: list[dict[str, Any]], corpus_meta: list[dict[str, Any]]) -> str:
    fixtures = []
    for r in auto_results:
        m = next((x for x in corpus_meta if x["fixture_id"] == r["fixture_id"]), {})
        fixtures.append((r, m))

    rows = []
    for r, m in fixtures:
        fid = r["fixture_id"]
        hint = ""
        if not r.get("pipeline_ok"):
            hint = f'<div class="err">PIPELINE ERROR: {r.get("pipeline_error", "")}</div>'
        auto_hints = []
        if r.get("frame_detection_ok") is False:
            auto_hints.append(f"검출 {r.get('frames_nonempty')}/{r.get('frames_total')}")
        if r.get("scale_drift_frames"):
            auto_hints.append(f"스케일 드리프트 프레임: {[x + 1 for x in r['scale_drift_frames']]}")
        if r.get("palette_drift_frames"):
            auto_hints.append(f"팔레트 드리프트 프레임: {[x + 1 for x in r['palette_drift_frames']]}")
        if r.get("neighbor_flags"):
            auto_hints.append(f"이웃 침범 의심: {[x + 1 for x in r['neighbor_flags']]}")
        if r.get("clip_flags"):
            auto_hints.append(f"가장자리 잘림 의심: {[x + 1 for x in r['clip_flags']]}")
        if r.get("anchor_y_gt3"):
            auto_hints.append(f"앵커Y 편차>3px: {r.get('anchor_y_gt3')}프레임")
        if r.get("anchor_bottom_rate") is not None:
            auto_hints.append(f"앵커=발바닥 정확률: {int(r['anchor_bottom_rate'] * 100)}%")
        hints_html = '<div class="hints">자동 측정 힌트: ' + ("; ".join(auto_hints) if auto_hints else "이상 없음") + "</div>"

        frame_selects = []
        for i in range(16):
            opts = "\n".join(
                f'<option value="{s}"{" selected" if s == "PASS" else ""}>{s}</option>' for s in FRAME_STATUSES
            )
            gt = f"""
              <span class="gt" style="display:none">
                GT anchor x <input type="number" id="gtx_{fid}_{i}" size="4"> y <input type="number" id="gty_{fid}_{i}" size="4">
              </span>"""
            frame_selects.append(
                f'<div class="frow"><label>#{i + 1:02d}</label><select id="st_{fid}_{i}">{opts}</select>{gt}</div>'
            )

        tag_boxes = "\n".join(
            f'<label class="tag"><input type="checkbox" class="tagcb" data-fid="{fid}" value="{t}"> {t}</label>'
            for t in DIFFICULTY_TAGS
        )

        rows.append(f"""
        <details class="fixture" id="fx_{fid}">
          <summary>
            <b>{fid}</b> · {m.get("source_file", "")} · {m.get("width")}x{m.get("height")} ·
            그리드 검출 v={m.get("detected_grid", {}).get("vlines")} h={m.get("detected_grid", {}).get("hlines")} ·
            bg={m.get("background_type", "?")} · <span id="sum_{fid}" class="sum">미검수</span>
          </summary>
          {hint}
          {hints_html}
          <div class="imgrow">
            <figure><img src="corpus/{fid}.png" loading="lazy"><figcaption>BEFORE (원본 GPT 시트)</figcaption></figure>
            <figure><img src="before_after/{fid}_after.png" loading="lazy"><figcaption>AFTER (SpriteRepair 캔버스)</figcaption></figure>
            <figure><img src="preview/{fid}_frames.png" loading="lazy"><figcaption>RAW 프레임 (크롭 결과)</figcaption></figure>
          </div>
          <div class="meta">
            prompt_class <input type="text" id="pc_{fid}" placeholder="예: sword_attack, fireball, jump...">
            manual_minutes <input type="number" id="mm_{fid}" min="0" step="0.5" style="width:80px" placeholder="수동작업 분">
            sheet_status
            <select id="ss_{fid}">
              <option value="PENDING">PENDING</option>
              <option value="PASS">PASS</option>
              <option value="FAIL">FAIL</option>
            </select>
            <button type="button" onclick="allPass('{fid}')">전체 PASS</button>
          </div>
          <div class="tags">{tag_boxes}</div>
          <div class="frames">{''.join(frame_selects)}</div>
        </details>""")

    return """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><title>SpriteRepair GPT 4x4 Benchmark Review</title>
<style>
body { background:#16181d; color:#e6e6e6; font-family:Segoe UI, sans-serif; margin:16px; }
h1 { font-size:20px; }
.bar { position:sticky; top:0; background:#20232a; padding:10px; border-radius:8px; margin-bottom:12px; display:flex; gap:8px; align-items:center; z-index:10; }
button { background:#2f6fed; color:#fff; border:0; padding:6px 12px; border-radius:6px; cursor:pointer; }
details.fixture { background:#20232a; border-radius:8px; margin-bottom:10px; padding:10px; }
summary { cursor:pointer; font-size:15px; }
.imgrow { display:flex; gap:10px; flex-wrap:wrap; margin:8px 0; }
.imgrow img { max-height:260px; max-width:340px; border:1px solid #333; border-radius:4px; }
figure { margin:0; text-align:center; font-size:12px; color:#9aa3b2; }
.frames { display:grid; grid-template-columns:repeat(4, 1fr); gap:4px; margin-top:8px; }
.frow { display:flex; gap:6px; align-items:center; font-size:12px; }
.frow select { flex:1; background:#2b2f38; color:#e6e6e6; border:1px solid #3a3f4a; border-radius:4px; padding:2px; }
.frow select:has(option[value="ANCHOR_FIX"]:checked), .frow select[data-fix="1"] { background:#4a3520; }
.meta { display:flex; gap:8px; align-items:center; margin-top:8px; flex-wrap:wrap; }
.meta input, .meta select { background:#2b2f38; color:#e6e6e6; border:1px solid #3a3f4a; border-radius:4px; padding:4px; }
.hints { color:#d9a441; font-size:12px; margin-top:6px; }
.err { color:#e05c5c; font-size:12px; margin-top:6px; }
.tag { font-size:12px; margin-right:8px; display:inline-block; }
.sum { font-size:12px; }
.sum.ok { color:#5cd27a; } .sum.fail { color:#e05c5c; }
.gt { font-size:11px; color:#9aa3b2; }
</style></head><body>
<h1>SpriteRepair — Real-World GPT 4x4 Benchmark Human Review</h1>
<p style="font-size:13px;color:#9aa3b2">
  각 시트의 BEFORE/AFTER를 눈으로 확인하고 프레임별 상태를 선택하세요.
  <b>ANCHOR_FIX</b> 선택 시 GT 앵커 x/y(프레임 로컬 좌표)를 입력하면 앵커 오차 px 통계가 계산됩니다.
  manual_minutes에는 같은 시트를 수동 작업(split→crop→foot align→VFX repair→preview→export)했을 때 걸리는 시간을 입력하세요.
  완료 후 <b>저장(JSON 다운로드)</b>로 review_results.json을 내보내고 benchmark 폴더에 넣으세요.
</p>
<div class="bar">
  <button onclick="saveJson()">저장 (review_results.json 다운로드)</button>
  <button onclick="document.getElementById('loadfile').click()">이전 검수 불러오기</button>
  <input type="file" id="loadfile" accept=".json" style="display:none" onchange="loadJson(event)">
  <span id="progress" style="font-size:13px"></span>
</div>
""" + "\n".join(rows) + """
<script>
const FIDS = """ + json.dumps([r["fixture_id"] for r in auto_results]) + """;
const AUTO = """ + json.dumps(auto_results, ensure_ascii=False) + """;
function allPass(fid) {
  for (let i = 0; i < 16; i++) {
    const el = document.getElementById("st_" + fid + "_" + i);
    if (el) el.value = "PASS";
  }
  updateSum(fid);
}
function updateSum(fid) {
  let fixes = 0;
  for (let i = 0; i < 16; i++) {
    const el = document.getElementById("st_" + fid + "_" + i);
    if (el && el.value !== "PASS") fixes++;
  }
  const ss = document.getElementById("ss_" + fid);
  const el = document.getElementById("sum_" + fid);
  if (!el) return;
  if (ss && ss.value === "PASS" && fixes === 0) { el.textContent = "PASS"; el.className = "sum ok"; }
  else if (ss && ss.value === "FAIL") { el.textContent = "FAIL"; el.className = "sum fail"; }
  else if (fixes > 0) { el.textContent = fixes + " 프레임 수정 필요"; el.className = "sum fail"; }
  else { el.textContent = "검수 중"; el.className = "sum"; }
}
document.addEventListener("change", (e) => {
  if (e.target && e.target.id && e.target.id.startsWith("st_")) {
    const [_, fid, i] = e.target.id.split("_");
    const gtx = document.getElementById("gtx_" + fid + "_" + i);
    const gty = document.getElementById("gty_" + fid + "_" + i);
    const wrap = (gtx && gtx.parentElement);
    if (wrap) wrap.style.display = e.target.value === "ANCHOR_FIX" ? "" : "none";
    e.target.dataset.fix = e.target.value === "PASS" ? "0" : "1";
    updateSum(fid);
  } else if (e.target && e.target.id && e.target.id.startsWith("ss_")) {
    updateSum(e.target.id.split("_")[1]);
  }
});
function collect() {
  const out = { reviewed_at: new Date().toISOString(), fixtures: {} };
  for (const fid of FIDS) {
    const frames = {};
    for (let i = 0; i < 16; i++) {
      const st = document.getElementById("st_" + fid + "_" + i);
      const gtx = document.getElementById("gtx_" + fid + "_" + i);
      const gty = document.getElementById("gty_" + fid + "_" + i);
      frames[String(i)] = {
        status: st ? st.value : "PASS",
        gt_anchor_x: gtx && gtx.value !== "" ? Number(gtx.value) : null,
        gt_anchor_y: gty && gty.value !== "" ? Number(gty.value) : null,
      };
    }
    const tags = [];
    document.querySelectorAll('.tagcb[data-fid="' + fid + '"]:checked').forEach((c) => tags.push(c.value));
    out.fixtures[fid] = {
      prompt_class: (document.getElementById("pc_" + fid) || {}).value || "",
      difficulty_tags: tags,
      manual_minutes: (document.getElementById("mm_" + fid) || {}).value ? Number(document.getElementById("mm_" + fid).value) : null,
      sheet_status: (document.getElementById("ss_" + fid) || {}).value || "PENDING",
      frames: frames,
    };
  }
  return out;
}
function saveJson() {
  const data = collect();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "review_results.json";
  a.click();
  updateProgress();
}
function loadJson(ev) {
  const f = ev.target.files[0];
  if (!f) return;
  const rd = new FileReader();
  rd.onload = () => {
    try {
      const data = JSON.parse(rd.result);
      for (const fid of FIDS) {
        const fx = (data.fixtures || {})[fid];
        if (!fx) continue;
        if (fx.prompt_class != null) document.getElementById("pc_" + fid).value = fx.prompt_class;
        if (fx.manual_minutes != null) document.getElementById("mm_" + fid).value = fx.manual_minutes;
        if (fx.sheet_status != null) document.getElementById("ss_" + fid).value = fx.sheet_status;
        (fx.difficulty_tags || []).forEach((t) => {
          const cb = document.querySelector('.tagcb[data-fid="' + fid + '"][value="' + t + '"]');
          if (cb) cb.checked = true;
        });
        for (let i = 0; i < 16; i++) {
          const fr = (fx.frames || {})[String(i)];
          if (!fr) continue;
          const st = document.getElementById("st_" + fid + "_" + i);
          if (st && fr.status) st.value = fr.status;
          if (fr.gt_anchor_x != null) document.getElementById("gtx_" + fid + "_" + i).value = fr.gt_anchor_x;
          if (fr.gt_anchor_y != null) document.getElementById("gty_" + fid + "_" + i).value = fr.gt_anchor_y;
          const gtx = document.getElementById("gtx_" + fid + "_" + i);
          const wrap = gtx && gtx.parentElement;
          if (wrap && st) wrap.style.display = st.value === "ANCHOR_FIX" ? "" : "none";
        }
        updateSum(fid);
      }
      updateProgress();
    } catch (e) { alert("불러오기 실패: " + e.message); }
  };
  rd.readAsText(f);
}
function updateProgress() {
  let done = 0;
  for (const fid of FIDS) {
    const ss = document.getElementById("ss_" + fid);
    if (ss && ss.value !== "PENDING") done++;
  }
  document.getElementById("progress").textContent = "검수 완료: " + done + " / " + FIDS.length;
}
updateProgress();
</script>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--fixture", default="")
    args = parser.parse_args()

    meta_path = CORPUS / "metadata.json"
    if not meta_path.is_file():
        raise SystemExit("corpus metadata missing — run the corpus collector first")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    selected = meta
    if args.fixture:
        selected = [m for m in meta if m["fixture_id"] == args.fixture]
    if args.limit:
        selected = selected[: args.limit]

    for d in (OUT, BEFORE_AFTER, PREVIEW, FAILURES):
        d.mkdir(parents=True, exist_ok=True)

    results = []
    for i, m in enumerate(selected, 1):
        fid = m["fixture_id"]
        print(f"[{i}/{len(selected)}] {fid} ...", flush=True)
        r = run_one(m)
        results.append(r)
        print("   ", "OK" if r.get("pipeline_ok") else "PIPELINE ERROR",
              "| export:", "OK" if r.get("export_ok") else "FAIL",
              "| t_process:", r.get("t_process_s"), "s", flush=True)

    out_json = BENCH / "auto_results.json"
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nauto_results.json -> {out_json}")

    review_html = build_review_html(results, selected)
    (BENCH / "review.html").write_text(review_html, encoding="utf-8")
    print("review.html generated")


if __name__ == "__main__":
    main()
