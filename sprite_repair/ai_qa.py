"""Contact-sheet AI QA with disk cache, JSON schema validation, and selective 2nd pass."""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from sprite_repair.ai_align import load_dotenv, _provider_endpoint, _chat_completions, _extract_json, ai_config_public, assert_model_supports_vision

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".ai-cache"


def _cache_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", errors="replace"))
        h.update(b"\0")
    return h.hexdigest()


def _cache_get(key: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cache_set(key: str, obj: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_ai_qa_schema(parsed: Any, total_frames: int) -> dict[str, Any]:
    """Strict JSON schema validator for AI QA responses."""
    if not isinstance(parsed, dict):
        raise ValueError(f"AI QA output must be a JSON dictionary, got {type(parsed).__name__}")
    raw_problems = parsed.get("problem_frames", [])
    if not isinstance(raw_problems, list):
        raise ValueError(f"'problem_frames' must be a list, got {type(raw_problems).__name__}")
    problem_frames: list[int] = []
    for p in raw_problems:
        try:
            pi = int(p)
            if 0 <= pi < total_frames and pi not in problem_frames:
                problem_frames.append(pi)
        except (TypeError, ValueError):
            continue

    raw_notes = parsed.get("notes", [])
    if not isinstance(raw_notes, list):
        raw_notes = []
    notes: list[dict[str, Any]] = []
    for n in raw_notes:
        if isinstance(n, dict):
            try:
                fi = int(n.get("frame", -1))
                issue = str(n.get("issue") or n.get("note") or "Needs human review")
                notes.append({"frame": fi, "issue": issue})
            except (TypeError, ValueError):
                pass
    return {"problem_frames": problem_frames, "notes": notes}


def build_contact_sheet(
    images: list[Image.Image],
    anchors: list[dict[str, int]] | None = None,
    cell: int = 128,
    cols: int | None = None,
) -> Image.Image:
    n = len(images)
    if n == 0:
        return Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
    if cols is None:
        cols = max(1, int(n ** 0.5 + 0.999))
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (20, 24, 32, 255))
    draw = ImageDraw.Draw(sheet)
    for i, img in enumerate(images):
        r, c = i // cols, i % cols
        thumb = img.convert("RGBA").copy()
        thumb.thumbnail((cell - 8, cell - 8), Image.Resampling.NEAREST)
        x0 = c * cell + (cell - thumb.width) // 2
        y0 = r * cell + (cell - thumb.height) // 2
        sheet.paste(thumb, (x0, y0), thumb)
        # frame number
        draw.text((c * cell + 4, r * cell + 2), str(i), fill=(255, 220, 80, 255))
        if anchors and i < len(anchors):
            ax = anchors[i].get("x", 0)
            ay = anchors[i].get("y", 0)
            # map anchor from original to thumb approx
            sx = thumb.width / max(1, img.width)
            sy = thumb.height / max(1, img.height)
            px = x0 + int(ax * sx)
            py = y0 + int(ay * sy)
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), outline=(255, 70, 90, 255), width=2)
    return sheet


_QA_PROMPT = """You are QA for a sprite animation contact sheet.
Each cell is numbered. Red dots are foot/root anchors.
Return ONLY JSON:
{"problem_frames":[6,7,8],"notes":[{"frame":6,"issue":"anchor too high"},{"frame":7,"issue":"VFX ownership unclear"}]}
List only frames that need human review (bad foot anchor, neighbor bleed, clipped VFX, obvious jitter).
If all look fine: {"problem_frames":[],"notes":[]}
"""


def _heuristic_qa_fallback(raw_images: list[Image.Image], raw_frames: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic offline fallback QA when live API keys are not provided."""
    problems: list[int] = []
    notes: list[dict[str, Any]] = []

    for i, f in enumerate(raw_frames):
        a = f.get("anchor") or {}
        ax, ay = int(a.get("x", 0)), int(a.get("y", 0))
        img = raw_images[i] if i < len(raw_images) else None
        if img:
            # Check if anchor is on or outside image boundary
            if ax <= 2 or ax >= img.width - 2 or ay <= 2 or ay >= img.height - 2:
                problems.append(i)
                notes.append({"frame": i, "issue": f"Anchor near border ({ax}, {ay})"})
        # Check warnings recorded during extraction
        warns = f.get("qa_warnings") or []
        for w in warns:
            if i not in problems:
                problems.append(i)
            notes.append({"frame": i, "issue": str(w)})

    return {"problem_frames": sorted(list(set(problems))), "notes": notes}


def request_contact_sheet_qa(
    raw_images: list[Image.Image],
    raw_frames: list[dict[str, Any]],
    *,
    provider: str | None = None,
    model: str | None = None,
    env: dict[str, str] | None = None,
    force_fallback: bool = False,
) -> dict[str, Any]:
    env = env if env is not None else load_dotenv()
    cfg = ai_config_public(env)
    prov = (provider or cfg["default_provider"]).strip().lower()

    anchors = [dict(f.get("anchor") or {"x": 0, "y": 0}) for f in raw_frames]
    sheet = build_contact_sheet(raw_images, anchors)
    buf = BytesIO()
    sheet.save(buf, format="PNG")
    png = buf.getvalue()
    b64 = __import__("base64").b64encode(png).decode("ascii")

    # Offline / No-key fallback guard
    has_key = bool(env.get("NVIDIA_API_KEY") if prov == "nvidia" else env.get("OPENROUTER_API_KEY"))
    if force_fallback or not has_key:
        fb = _heuristic_qa_fallback(raw_images, raw_frames)
        return {
            "ok": True,
            "cached": False,
            "fallback": True,
            "provider": prov,
            "model": model or "local-heuristic",
            "problem_frames": fb["problem_frames"],
            "notes": fb["notes"],
            "contact_sheet_png_sha256": hashlib.sha256(png).hexdigest(),
        }

    try:
        base_url, api_key, default_model = _provider_endpoint(prov, env)
        use_model = (model or default_model).strip()
        assert_model_supports_vision(prov, use_model, env)

        key = _cache_key("contact-qa-v2", use_model, hashlib.sha256(png).hexdigest(), _QA_PROMPT)
        cached = _cache_get(key)
        if cached:
            cached["cached"] = True
            return cached

        content = [
            {"type": "text", "text": _QA_PROMPT + f"\nTotal frames: {len(raw_images)}"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
        text = _chat_completions(
            base_url=base_url,
            api_key=api_key,
            model=use_model,
            messages=[{"role": "user", "content": content}],
            provider=prov,
            timeout=10.0,
        )
        parsed = _extract_json(text)
        validated = validate_ai_qa_schema(parsed, total_frames=len(raw_images))

        out = {
            "ok": True,
            "cached": False,
            "provider": prov,
            "model": use_model,
            "problem_frames": validated["problem_frames"],
            "notes": validated["notes"],
            "contact_sheet_png_sha256": hashlib.sha256(png).hexdigest(),
        }
        _cache_set(key, out)
        return out
    except Exception as exc:
        fb = _heuristic_qa_fallback(raw_images, raw_frames)
        return {
            "ok": True,
            "cached": False,
            "fallback": True,
            "fallback_reason": str(exc),
            "provider": prov,
            "model": model or "local-heuristic",
            "problem_frames": fb["problem_frames"],
            "notes": fb["notes"],
            "contact_sheet_png_sha256": hashlib.sha256(png).hexdigest(),
        }


_DEEP_ANALYSIS_PROMPT = """You are analyzing high-resolution problem frames from a sprite animation.
For each problem frame, return precise diagnostic information and suggested anchor offset delta.
Return ONLY JSON in this schema:
{
  "diagnostics": [
    {
      "frame": 6,
      "issue_type": "anchor_drift",
      "suggested_dx": 0,
      "suggested_dy": -4,
      "suggested_pad": 4,
      "recommendation": "Nudge foot anchor 4px up to match ground plane"
    }
  ]
}
"""


def request_problem_frame_deep_analysis(
    raw_images: list[Image.Image],
    raw_frames: list[dict[str, Any]],
    problem_frames: list[int],
    *,
    provider: str | None = None,
    model: str | None = None,
    env: dict[str, str] | None = None,
    force_fallback: bool = False,
) -> dict[str, Any]:
    """Selective 2nd pass: high-resolution inspection of only flagged problem frames."""
    if not problem_frames:
        return {"ok": True, "diagnostics": []}

    env = env if env is not None else load_dotenv()
    cfg = ai_config_public(env)
    prov = (provider or cfg["default_provider"]).strip().lower()

    has_key = bool(env.get("NVIDIA_API_KEY") if prov == "nvidia" else env.get("OPENROUTER_API_KEY"))
    if force_fallback or not has_key:
        # Heuristic 2nd pass
        diagnostics = []
        for pf in problem_frames:
            if 0 <= pf < len(raw_frames):
                f = raw_frames[pf]
                a = f.get("anchor") or {"x": 0, "y": 0}
                diagnostics.append({
                    "frame": pf,
                    "issue_type": "anchor_drift" if a.get("y", 0) <= 2 else "bleed_artifact",
                    "suggested_dx": 0,
                    "suggested_dy": -2 if a.get("y", 0) <= 2 else 0,
                    "suggested_pad": 4,
                    "recommendation": f"Inspect frame {pf} anchor ({a.get('x')}, {a.get('y')}) and verify boundary padding",
                })
        return {"ok": True, "fallback": True, "diagnostics": diagnostics}

    try:
        base_url, api_key, default_model = _provider_endpoint(prov, env)
        use_model = (model or default_model).strip()
        assert_model_supports_vision(prov, use_model, env)

        selected_imgs = [raw_images[i] for i in problem_frames if 0 <= i < len(raw_images)]
        selected_anchors = [dict(raw_frames[i].get("anchor") or {"x": 0, "y": 0}) for i in problem_frames if 0 <= i < len(raw_frames)]
        strip = build_contact_sheet(selected_imgs, selected_anchors, cell=192, cols=len(selected_imgs))

        buf = BytesIO()
        strip.save(buf, format="PNG")
        png = buf.getvalue()
        b64 = __import__("base64").b64encode(png).decode("ascii")

        key = _cache_key("deep-qa-v1", use_model, hashlib.sha256(png).hexdigest(), str(problem_frames))
        cached = _cache_get(key)
        if cached:
            cached["cached"] = True
            return cached

        content = [
            {"type": "text", "text": _DEEP_ANALYSIS_PROMPT + f"\nProblem frame indices: {problem_frames}"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
        text = _chat_completions(
            base_url=base_url,
            api_key=api_key,
            model=use_model,
            messages=[{"role": "user", "content": content}],
            provider=prov,
            timeout=10.0,
        )
        parsed = _extract_json(text)
        diag = parsed.get("diagnostics") if isinstance(parsed, dict) else []
        out = {
            "ok": True,
            "cached": False,
            "provider": prov,
            "model": use_model,
            "diagnostics": diag or [],
        }
        _cache_set(key, out)
        return out
    except Exception as exc:
        diagnostics = []
        for pf in problem_frames:
            if 0 <= pf < len(raw_frames):
                f = raw_frames[pf]
                a = f.get("anchor") or {"x": 0, "y": 0}
                diagnostics.append({
                    "frame": pf,
                    "issue_type": "anchor_drift" if a.get("y", 0) <= 2 else "bleed_artifact",
                    "suggested_dx": 0,
                    "suggested_dy": -2 if a.get("y", 0) <= 2 else 0,
                    "suggested_pad": 4,
                    "recommendation": f"Inspect frame {pf} anchor ({a.get('x')}, {a.get('y')}) and verify boundary padding",
                })
        return {"ok": True, "fallback": True, "fallback_reason": str(exc), "diagnostics": diagnostics}

