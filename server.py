#!/usr/bin/env python3
"""Sprite Repair local server — static app/ + JSON API. Port 5190."""

from __future__ import annotations

import json
import pickle
import mimetypes
import re
import shutil
import sys
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from PIL import Image

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "app"
WORK_DIR = ROOT / "workspace"
SESSIONS: dict[str, dict[str, Any]] = {}
SESSIONS_LOCK = threading.Lock()

sys.path.insert(0, str(ROOT))
from sprite_repair.pipeline import (  # noqa: E402
    process_sheet,
    recompose_with_anchors,
    frames_to_data_urls,
    expand_frame_rgba,
    tight_crop_rgba,
    apply_ownership_brush,
    estimate_grid,
)
from sprite_repair.export import export_bundle  # noqa: E402
from sprite_repair.qa import analyze_animation_qa  # noqa: E402
from sprite_repair.ai_qa import request_contact_sheet_qa, request_problem_frame_deep_analysis  # noqa: E402
from sprite_repair.project import write_project, read_project  # noqa: E402
from sprite_repair.multipart import parse_multipart  # noqa: E402
from sprite_repair.ai_align import (  # noqa: E402
    ai_config_public,
    apply_ai_align,
    list_ai_models,
    list_nvidia_models,
    request_ai_alignments,
    save_dotenv_keys,
)


import os

PORT = int(os.environ.get("PORT", 5190))

def _persist_session(sess_dir: Path, result: dict[str, Any]) -> None:
    """Save session so server restart can recover (fixes session not found)."""
    try:
        sess_dir.mkdir(parents=True, exist_ok=True)
        with (sess_dir / "session.pkl").open("wb") as f:
            pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        traceback.print_exc()


def _load_session(sid: str) -> dict[str, Any] | None:
    with SESSIONS_LOCK:
        sess = SESSIONS.get(sid)
        if sess:
            return sess
    sess_dir = WORK_DIR / sid
    pkl = sess_dir / "session.pkl"
    if not pkl.is_file():
        return None
    try:
        with pkl.open("rb") as f:
            result = pickle.load(f)
        sess = {"dir": sess_dir, "result": result}
        with SESSIONS_LOCK:
            SESSIONS[sid] = sess
        return sess
    except Exception:
        traceback.print_exc()
        return None




def _json_response(handler: BaseHTTPRequestHandler, code: int, obj: Any) -> None:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    try:
        handler.send_response(code)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        handler.wfile.write(data)
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
        pass


def _read_multipart(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    ctype = handler.headers.get("Content-Type", "")
    length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(length)
    return parse_multipart(ctype, body)


def _save_preview_frames(sess_dir: Path, result: dict[str, Any]) -> tuple[list[str], list[str]]:
    raw_dir = sess_dir / "raw"
    composed_dir = sess_dir / "composed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    composed_dir.mkdir(parents=True, exist_ok=True)
    raw_urls: list[str] = []
    composed_urls: list[str] = []
    sid = sess_dir.name
    for i, img in enumerate(result["raw_frame_images"]):
        name = f"{i:03d}.png"
        img.save(raw_dir / name, format="PNG")
        raw_urls.append(f"/workspace/{sid}/raw/{name}")
    for i, img in enumerate(result["frame_images"]):
        name = f"{i:03d}.png"
        img.save(composed_dir / name, format="PNG")
        composed_urls.append(f"/workspace/{sid}/composed/{name}")
    return raw_urls, composed_urls


def _session_payload(sid: str, result: dict[str, Any], sess_dir: Path) -> dict[str, Any]:
    # Save PNG previews under workspace and return URL paths (avoid huge data-URL JSON).
    raw_urls, composed_urls = _save_preview_frames(sess_dir, result)
    # Strip non-JSON-friendly keys from frame meta copies
    raw_frames = result.get("raw_frames") or []
    composed_frames = result.get("frames") or []
    return {
        "ok": True,
        "session_id": sid,
        "source": result.get("source"),
        "sheet_size": result.get("sheet_size"),
        "grid": result.get("grid"),
        "canvas": result.get("canvas"),
        "frames": raw_frames,
        "composed_frames": composed_frames,
        "frame_urls": raw_urls,
        "composed_urls": composed_urls,
        "project": result.get("project_dict") or (result["project"].to_dict() if hasattr(result.get("project"), "to_dict") else None),
    }


SAMPLE_PAYLOAD_CACHE: dict[str, Any] | None = None

def _get_sample_payload() -> dict[str, Any]:
    global SAMPLE_PAYLOAD_CACHE
    if SAMPLE_PAYLOAD_CACHE is not None:
        return SAMPLE_PAYLOAD_CACHE
    sample_path = ROOT / "samples" / "attack_4x4_real.png"
    if not sample_path.is_file():
        return {"ok": False, "error": "sample not found"}
    sid = "sample_attack_4x4"
    sess_dir = WORK_DIR / sid
    sess_dir.mkdir(parents=True, exist_ok=True)
    
    # Fast-path: Check if already persisted and has preview frames
    loaded = _load_session(sid)
    if loaded and "result" in loaded:
        res = loaded["result"]
        if (sess_dir / "composed" / "000.png").is_file() and (sess_dir / "raw" / "000.png").is_file():
            raw_urls = [f"/workspace/{sid}/raw/{i:03d}.png" for i in range(len(res["raw_frames"]))]
            comp_urls = [f"/workspace/{sid}/composed/{i:03d}.png" for i in range(len(res.get("frames", [])))]
            SAMPLE_PAYLOAD_CACHE = {
                "ok": True,
                "session_id": sid,
                "source": res.get("source"),
                "sheet_size": res.get("sheet_size"),
                "grid": res.get("grid"),
                "canvas": res.get("canvas"),
                "frames": res.get("raw_frames") or [],
                "composed_frames": res.get("frames") or [],
                "frame_urls": raw_urls,
                "composed_urls": comp_urls,
                "project": res.get("project_dict") or (res["project"].to_dict() if hasattr(res.get("project"), "to_dict") else None),
            }
            return SAMPLE_PAYLOAD_CACHE

    shutil.copy2(sample_path, sess_dir / "attack_4x4_real.png")
    result = process_sheet(
        sample_path,
        cols=4,
        rows=4,
        alpha_threshold=12,
        pad=4,
        expand_ratio=1.15,
        duration_ms=80,
    )
    sheet_img = Image.open(sample_path).convert("RGBA")
    result["sheet"] = sheet_img
    result["mask_bases"] = [im.copy() for im in result["raw_frame_images"]]
    with SESSIONS_LOCK:
        SESSIONS[sid] = {"dir": sess_dir, "result": result}
    _persist_session(sess_dir, result)
    SAMPLE_PAYLOAD_CACHE = _session_payload(sid, result, sess_dir)
    return SAMPLE_PAYLOAD_CACHE


class Handler(BaseHTTPRequestHandler):
    server_version = "SpriteRepair/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query or "")
            if "sample" in qs or "demo" in qs:
                payload = _get_sample_payload()
                html = (APP_DIR / "index.html").read_text(encoding="utf-8")
                injected = f"<script>window.__INITIAL_SESSION__ = {json.dumps(payload, ensure_ascii=False)};</script>\n  <script src=\"/app.js\"></script>"
                html = html.replace('<script src="/app.js"></script>', injected)
                data = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            return self._serve_file(APP_DIR / "index.html")
        if path.startswith("/app/"):
            return self._serve_file(APP_DIR / path[len("/app/") :])
        # allow direct /app.js style
        candidate = (APP_DIR / path.lstrip("/")).resolve()
        try:
            candidate.relative_to(APP_DIR.resolve())
            if candidate.is_file():
                return self._serve_file(candidate)
        except ValueError:
            pass
        if path.startswith("/workspace/"):
            rel = path[len("/workspace/") :]
            return self._serve_file(WORK_DIR / rel)
        if path.startswith("/samples/"):
            rel = path[len("/samples/") :]
            return self._serve_file(ROOT / "samples" / rel)
        if path == "/api/health":
            return _json_response(self, 200, {"ok": True, "port": PORT})
        if path == "/api/ai-config":
            return _json_response(self, 200, ai_config_public())
        if path == "/api/ai-models":
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query or "")
            prov = (qs.get("provider") or [None])[0]
            return _json_response(self, 200, list_ai_models(prov))
        if path == "/api/load-sample":
            return _json_response(self, 200, _get_sample_payload())
        if path == "/api/aseprite-bridge/status":
            from sprite_repair.bridge import AsepriteBridge
            return _json_response(self, 200, AsepriteBridge.detect())
        _json_response(self, 404, {"ok": False, "error": "not found"})

    def _serve_file(self, path: Path) -> None:
        path = path.resolve()
        try:
            # stay under ROOT
            path.relative_to(ROOT.resolve())
        except ValueError:
            _json_response(self, 403, {"ok": False, "error": "forbidden"})
            return
        if not path.is_file():
            _json_response(self, 404, {"ok": False, "error": f"missing {path.name}"})
            return
        data = path.read_bytes()
        ctype, _ = mimetypes.guess_type(str(path))
        if path.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif path.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif path.suffix == ".html":
            ctype = "text/html; charset=utf-8"
        elif path.suffix == ".json":
            ctype = "application/json; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/process":
                return self._api_process()
            if parsed.path == "/api/recompose":
                return self._api_recompose()
            if parsed.path == "/api/export":
                return self._api_export()
            if parsed.path == "/api/ai-align":
                return self._api_ai_align()
            if parsed.path == "/api/crop-frame":
                return self._api_crop_frame()
            if parsed.path == "/api/mask-stroke":
                return self._api_mask_stroke()
            if parsed.path == "/api/ai-keys":
                return self._api_ai_keys()
            if parsed.path == "/api/ai-qa":
                return self._api_ai_qa()
            if parsed.path == "/api/ai-qa-deep":
                return self._api_ai_qa_deep()
            if parsed.path == "/api/save-project":
                return self._api_save_project()
            if parsed.path == "/api/anim-qa":
                return self._api_anim_qa()
            if parsed.path == "/api/aseprite-bridge/export":
                return self._api_aseprite_bridge_export()
            if parsed.path == "/api/ai-set-model":
                return self._api_ai_set_model()
            if parsed.path == "/api/ai-probe":
                return self._api_ai_probe()
            if parsed.path == "/api/ai-verified":
                return self._api_ai_verified()
            _json_response(self, 404, {"ok": False, "error": "unknown api"})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"ok": False, "error": str(e)})

    def _api_process(self) -> None:
        fields = _read_multipart(self)
        if "file" not in fields or not isinstance(fields["file"], dict):
            return _json_response(self, 400, {"ok": False, "error": "file required"})
        cols = int(fields.get("cols", 4))
        rows = int(fields.get("rows", 4))
        auto_grid = str(fields.get("auto_grid", "")).lower() in ("1", "true", "yes", "on")
        duration = int(fields.get("duration", 80))
        pad = int(fields.get("pad", 4))
        expand_ratio = float(fields.get("expand_ratio", 1.15))
        alpha = int(fields.get("alpha", 16))

        WORK_DIR.mkdir(parents=True, exist_ok=True)
        sid = uuid.uuid4().hex[:12]
        sess_dir = WORK_DIR / sid
        sess_dir.mkdir(parents=True, exist_ok=True)
        raw_name = fields["file"]["filename"] or "sheet.png"
        raw_name = re.sub(r"[^\w.\-]+", "_", raw_name) or "sheet.png"
        sheet_path = sess_dir / raw_name
        sheet_path.write_bytes(fields["file"]["data"])

        if auto_grid or cols <= 0 or rows <= 0:
            m = re.search(r"(\d+)\s*[xX]\s*(\d+)", sheet_path.name)
            if m:
                cols, rows = int(m.group(1)), int(m.group(2))
            else:
                from PIL import Image as _Image
                _im = _Image.open(sheet_path).convert("RGBA")
                cols, rows = estimate_grid(_im, alpha_threshold=alpha)
        result = process_sheet(
            sheet_path,
            cols=cols,
            rows=rows,
            alpha_threshold=alpha,
            pad=pad,
            expand_ratio=expand_ratio,
            duration_ms=duration,
        )
        sheet_img = Image.open(sheet_path).convert("RGBA")
        result["sheet"] = sheet_img
        result["mask_bases"] = [im.copy() for im in result["raw_frame_images"]]
        with SESSIONS_LOCK:
            SESSIONS[sid] = {"dir": sess_dir, "result": result}
        _persist_session(sess_dir, result)

        _json_response(self, 200, _session_payload(sid, result, sess_dir))

    def _parse_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _api_recompose(self) -> None:
        body = self._parse_json_body()
        sid = body.get("session_id")
        sess = _load_session(sid) if sid else None
        if not sess:
            return _json_response(self, 404, {"ok": False, "error": "session not found — re-process (server may have restarted; run process again)"})
        result = sess["result"]
        anchors = body.get("anchors")  # list of {x,y} in crop space
        duration = body.get("duration")
        pad = int(body.get("pad", 0))
        updated = recompose_with_anchors(
            result["raw_frame_images"],
            result["raw_frames"],
            anchor_overrides=anchors,
            duration_ms=int(duration) if duration is not None else None,
            pad=pad,
        )
        # merge back
        result = dict(result)
        result.update(updated)
        with SESSIONS_LOCK:
            SESSIONS[sid]["result"] = result
        _persist_session(Path(sess["dir"]), result)
        _json_response(self, 200, _session_payload(sid, result, Path(sess["dir"])))

    def _api_ai_align(self) -> None:
        body = self._parse_json_body()
        sid = body.get("session_id")
        sess = _load_session(sid) if sid else None
        if not sess:
            return _json_response(self, 404, {"ok": False, "error": "session not found — re-process (server may have restarted; run process again)"})
        result = sess["result"]
        provider = body.get("provider")
        model = body.get("model")
        duration = body.get("duration")
        pad = int(body.get("pad", 0))
        apply_scale = bool(body.get("apply_scale", True))
        alignments = request_ai_alignments(
            result["raw_frame_images"],
            provider=provider,
            model=model,
        )
        updated = apply_ai_align(
            result["raw_frame_images"],
            result["raw_frames"],
            alignments,
            duration_ms=int(duration) if duration is not None else None,
            pad=pad,
            apply_scale=apply_scale,
        )
        result = dict(result)
        result.update(updated)
        with SESSIONS_LOCK:
            SESSIONS[sid]["result"] = result
        cfg = ai_config_public()
        use_provider = (provider or cfg["default_provider"])
        use_model = model or cfg["models"].get(use_provider, cfg["default_model"])
        payload = _session_payload(sid, result, Path(sess["dir"]))
        payload["ai_alignments"] = alignments
        payload["ai_provider"] = use_provider
        payload["ai_model"] = use_model
        _json_response(self, 200, payload)



    def _api_mask_stroke(self) -> None:
        body = self._parse_json_body()
        sid = body.get("session_id")
        sess = _load_session(sid) if sid else None
        if not sess:
            return _json_response(self, 404, {"ok": False, "error": "session not found — re-process (server may have restarted; run process again)"})
        result = dict(sess["result"])
        idx = int(body.get("frame", 0))
        mode = (body.get("mode") or "exclude").strip().lower()
        brush = int(body.get("brush", 6))
        strokes = body.get("strokes") or []
        imgs = list(result["raw_frame_images"])
        metas = [dict(m) for m in result["raw_frames"]]
        if idx < 0 or idx >= len(imgs):
            return _json_response(self, 400, {"ok": False, "error": "frame out of range"})
        bases = list(result.get("mask_bases") or [im.copy() for im in imgs])
        while len(bases) < len(imgs):
            bases.append(imgs[len(bases)].copy())
        sheet = result.get("sheet")
        crop_rect = metas[idx].get("rect") or metas[idx].get("content_rect") or {}
        try:
            new_img = apply_ownership_brush(
                imgs[idx],
                bases[idx],
                mode=mode,
                strokes=strokes,
                brush=brush,
                sheet=sheet,
                crop_rect=crop_rect,
            )
        except Exception as e:
            return _json_response(self, 400, {"ok": False, "error": str(e)})
        imgs[idx] = new_img
        metas[idx]["size"] = {"w": new_img.width, "h": new_img.height}
        duration = body.get("duration")
        updated = recompose_with_anchors(
            imgs,
            metas,
            anchor_overrides=[m.get("anchor") for m in metas],
            duration_ms=int(duration) if duration is not None else None,
            pad=int(body.get("pad", 0)),
        )
        result.update(updated)
        result["raw_frame_images"] = imgs
        result["raw_frames"] = metas
        result["mask_bases"] = bases
        with SESSIONS_LOCK:
            SESSIONS[sid]["result"] = result
        _persist_session(Path(sess["dir"]), result)
        _json_response(self, 200, _session_payload(sid, result, Path(sess["dir"])))

    def _api_crop_frame(self) -> None:
        """Expand/trim one raw frame (or tight/safe). Keeps session non-destructive via new pixels."""
        body = self._parse_json_body()
        sid = body.get("session_id")
        sess = _load_session(sid) if sid else None
        if not sess:
            return _json_response(self, 404, {"ok": False, "error": "session not found — re-process (server may have restarted; run process again)"})
        result = dict(sess["result"])
        idx = int(body.get("frame", 0))
        imgs = list(result["raw_frame_images"])
        metas = [dict(m) for m in result["raw_frames"]]
        if idx < 0 or idx >= len(imgs):
            return _json_response(self, 400, {"ok": False, "error": "frame out of range"})
        img = imgs[idx]
        anchor = dict(metas[idx].get("anchor") or {"x": 0, "y": 0})
        mode = (body.get("mode") or "pad").strip().lower()
        try:
            if mode == "tight":
                margin = int(body.get("margin", 0))
                new_img, new_anchor = tight_crop_rgba(img, anchor, margin=margin)
            elif mode == "safe":
                n = int(body.get("amount", 5))
                new_img, new_anchor = expand_frame_rgba(img, anchor, left=n, top=n, right=n, bottom=n)
            else:
                new_img, new_anchor = expand_frame_rgba(
                    img,
                    anchor,
                    left=int(body.get("left", 0)),
                    top=int(body.get("top", 0)),
                    right=int(body.get("right", 0)),
                    bottom=int(body.get("bottom", 0)),
                )
        except Exception as e:
            return _json_response(self, 400, {"ok": False, "error": str(e)})
        imgs[idx] = new_img
        bases = list(result.get("mask_bases") or [im.copy() for im in imgs])
        while len(bases) < len(imgs):
            bases.append(imgs[len(bases)].copy())
        bases[idx] = new_img.copy()
        result["mask_bases"] = bases
        metas[idx]["anchor"] = new_anchor
        metas[idx]["size"] = {"w": new_img.width, "h": new_img.height}
        metas[idx]["rect"] = {
            "x": int((metas[idx].get("rect") or {}).get("x", 0)),
            "y": int((metas[idx].get("rect") or {}).get("y", 0)),
            "w": new_img.width,
            "h": new_img.height,
        }
        duration = body.get("duration")
        updated = recompose_with_anchors(
            imgs,
            metas,
            anchor_overrides=[m["anchor"] for m in metas],
            duration_ms=int(duration) if duration is not None else None,
            pad=int(body.get("pad", 0)),
        )
        result.update(updated)
        result["raw_frame_images"] = imgs
        result["raw_frames"] = metas
        with SESSIONS_LOCK:
            SESSIONS[sid]["result"] = result
        _persist_session(Path(sess["dir"]), result)
        _json_response(self, 200, _session_payload(sid, result, Path(sess["dir"])))



    def _api_ai_keys(self) -> None:
        body = self._parse_json_body()
        try:
            cfg = save_dotenv_keys(
                nvidia_key=body.get("nvidia_key"),
                openrouter_key=body.get("openrouter_key"),
                ai_provider=body.get("provider"),
            )
        except Exception as e:
            return _json_response(self, 400, {"ok": False, "error": str(e)})
        _json_response(self, 200, {"ok": True, "config": cfg, "message": "keys saved to .env (not logged)"})

    def _api_ai_qa(self) -> None:
        body = self._parse_json_body()
        sid = body.get("session_id")
        sess = _load_session(sid) if sid else None
        if not sess:
            return _json_response(self, 404, {"ok": False, "error": "session not found — re-process"})
        result = sess["result"]
        try:
            qa = request_contact_sheet_qa(
                result["raw_frame_images"],
                result["raw_frames"],
                provider=body.get("provider"),
                model=body.get("model"),
            )
        except Exception as e:
            return _json_response(self, 500, {"ok": False, "error": str(e)})
        # merge notes into frame qa_warnings lightly
        notes_by = {}
        for n in qa.get("notes") or []:
            if isinstance(n, dict) and "frame" in n:
                notes_by.setdefault(int(n["frame"]), []).append(str(n.get("issue") or n))
        metas = [dict(m) for m in result["raw_frames"]]
        for m in metas:
            fi = int(m.get("frame", 0))
            if fi in notes_by:
                w = list(m.get("qa_warnings") or [])
                for issue in notes_by[fi]:
                    msg = f"AI QA: {issue}"
                    if msg not in w:
                        w.append(msg)
                m["qa_warnings"] = w
        result = dict(result)
        result["raw_frames"] = metas
        result["ai_sheet_qa"] = qa
        # recompose to refresh composed meta
        updated = recompose_with_anchors(
            result["raw_frame_images"],
            metas,
            anchor_overrides=[m.get("anchor") for m in metas],
            duration_ms=int(body["duration"]) if body.get("duration") is not None else None,
        )
        result.update(updated)
        with SESSIONS_LOCK:
            SESSIONS[sid]["result"] = result
        _persist_session(Path(sess["dir"]), result)
        payload = _session_payload(sid, result, Path(sess["dir"]))
        payload["ai_sheet_qa"] = qa
        _json_response(self, 200, payload)

    def _api_anim_qa(self) -> None:
        body = self._parse_json_body()
        sid = body.get("session_id")
        sess = _load_session(sid) if sid else None
        if not sess:
            return _json_response(self, 404, {"ok": False, "error": "session not found — re-process"})
        result = sess["result"]
        qa = analyze_animation_qa(list(result.get("raw_frames") or []), images=result.get("raw_frame_images"))
        _json_response(self, 200, {"ok": True, "anim_qa": qa})

    def _api_ai_qa_deep(self) -> None:
        body = self._parse_json_body()
        sid = body.get("session_id")
        sess = _load_session(sid) if sid else None
        if not sess:
            return _json_response(self, 404, {"ok": False, "error": "session not found — re-process"})
        result = sess["result"]
        problem_frames = body.get("problem_frames") or []
        try:
            diag = request_problem_frame_deep_analysis(
                result["raw_frame_images"],
                result["raw_frames"],
                problem_frames,
                provider=body.get("provider"),
                model=body.get("model"),
            )
            _json_response(self, 200, diag)
        except Exception as e:
            _json_response(self, 500, {"ok": False, "error": str(e)})

    def _api_save_project(self) -> None:
        body = self._parse_json_body()
        sid = body.get("session_id")
        sess = _load_session(sid) if sid else None
        if not sess:
            return _json_response(self, 404, {"ok": False, "error": "session not found — re-process"})
        name = re.sub(r"[^\w.\-]+", "_", body.get("name") or "project") or "project"
        out = Path(sess["dir"]) / f"{name}.spriteproject"
        # apply latest anchors if provided
        result = dict(sess["result"])
        anchors = body.get("anchors")
        if anchors:
            updated = recompose_with_anchors(
                result["raw_frame_images"],
                result["raw_frames"],
                anchor_overrides=anchors,
                duration_ms=int(body["duration"]) if body.get("duration") is not None else None,
            )
            result.update(updated)
            with SESSIONS_LOCK:
                SESSIONS[sid]["result"] = result
            _persist_session(Path(sess["dir"]), result)
        frames_input = body.get("frames")
        if frames_input and isinstance(frames_input, list):
            metas = [dict(m) for m in (result.get("raw_frames") or [])]
            for i, fi in enumerate(frames_input):
                if i < len(metas) and isinstance(fi, dict):
                    if "anchor" in fi and fi["anchor"]: metas[i]["anchor"] = fi["anchor"]
                    if "pivot" in fi: metas[i]["pivot"] = fi["pivot"]
                    if "linked_cel_id" in fi: metas[i]["linked_cel_id"] = fi["linked_cel_id"]
                    if "mask_strokes" in fi: metas[i]["mask_strokes"] = fi["mask_strokes"]
                    if "duration" in fi: metas[i]["duration"] = fi["duration"]
                    if "duration_ms" in fi: metas[i]["duration_ms"] = fi["duration_ms"]
                    if "rect" in fi and fi["rect"]: metas[i]["rect"] = fi["rect"]
                    if "crop" in fi and fi["crop"]: metas[i]["content_rect"] = fi["crop"]
            result["raw_frames"] = metas
            result["frames"] = metas
        if body.get("layers"):
            result.setdefault("meta", {})["layers"] = body["layers"]
        if body.get("tags"):
            result.setdefault("meta", {})["tags"] = body["tags"]
        if body.get("canvas"):
            result["canvas"] = body["canvas"]
        write_project(out, result, name=name)
        _json_response(self, 200, {
            "ok": True,
            "path": str(out),
            "download": f"/workspace/{sid}/{name}.spriteproject",
            "project_url": f"/workspace/{sid}/{name}.spriteproject",
        })

    def _api_export(self) -> None:
        body = self._parse_json_body()
        sid = body.get("session_id")
        sess = _load_session(sid) if sid else None
        if not sess:
            return _json_response(self, 404, {"ok": False, "error": "session not found — re-process (server may have restarted; run process again)"})
        result = sess["result"]
        anchors = body.get("anchors")
        duration = body.get("duration")
        if anchors is not None:
            updated = recompose_with_anchors(
                result["raw_frame_images"],
                result["raw_frames"],
                anchor_overrides=anchors,
                duration_ms=int(duration) if duration is not None else None,
                pad=int(body.get("pad", 0)),
            )
            result = dict(result)
            result.update(updated)
            with SESSIONS_LOCK:
                SESSIONS[sid]["result"] = result

        export_name = body.get("name") or "export"
        export_name = re.sub(r"[^\w.\-]+", "_", export_name) or "export"
        out_dir = Path(sess["dir"]) / export_name
        export_bundle(
            result,
            out_dir,
            write_gif=True,
            write_sheet=True,
            write_apng=True,
            write_webp=True,
            pack_mode=body.get("pack_mode", "grid"),
            padding=int(body.get("padding", 0)),
            extrude=int(body.get("extrude", 0)),
            color_mode=body.get("color_mode", "RGBA"),
            palette_colors=int(body.get("palette_colors", 256)),
            dither=body.get("dither", "none"),
            merge_duplicates=bool(body.get("merge_duplicates", False)),
            split_tags=bool(body.get("split_tags", False)),
            bridge_aseprite=bool(body.get("bridge_aseprite", False)),
        )
        try:
            write_project(out_dir / "project.spriteproject", result, name=export_name)
        except Exception:
            traceback.print_exc()

        # Also zip for easy download
        zip_base = Path(sess["dir"]) / export_name
        zip_path = shutil.make_archive(str(zip_base), "zip", root_dir=out_dir)

        payload = {
            "ok": True,
            "session_id": sid,
            "out_dir": str(out_dir),
            "zip": str(zip_path),
            "download_zip": f"/workspace/{sid}/{export_name}.zip",
            "download_sheet": f"/workspace/{sid}/{export_name}/spritesheet.png",
            "download_json": f"/workspace/{sid}/{export_name}/animation.json",
            "download_aseprite": f"/workspace/{sid}/{export_name}/aseprite.json",
            "download_gif": f"/workspace/{sid}/{export_name}/preview.gif",
            "download_apng": f"/workspace/{sid}/{export_name}/preview.apng.png",
            "download_webp": f"/workspace/{sid}/{export_name}/preview.webp",
            "download_project": f"/workspace/{sid}/{export_name}/project.spriteproject",
            "canvas": result.get("canvas"),
            "frame_count": len(result.get("frames", [])),
        }
        if (out_dir / "import_to_aseprite.lua").exists():
            payload["download_bridge_lua"] = f"/workspace/{sid}/{export_name}/import_to_aseprite.lua"

        _json_response(self, 200, payload)

    def _api_aseprite_bridge_export(self) -> None:
        body = self._parse_json_body()
        sid = body.get("session_id")
        sess = _load_session(sid) if sid else None
        if not sess:
            return _json_response(self, 404, {"ok": False, "error": "session not found"})
        from sprite_repair.bridge import AsepriteBridge
        export_name = body.get("name") or "export"
        out_dir = Path(sess["dir"]) / export_name
        if not out_dir.is_dir():
            export_bundle(sess["result"], out_dir)
        res = AsepriteBridge.export_to_aseprite(out_dir, exe_path=body.get("exe_path"))
        _json_response(self, 200, res)

    def _api_ai_keys(self) -> None:
        body = self._parse_json_body()
        try:
            cfg = save_dotenv_keys(
                nvidia_key=body.get("nvidia_key"),
                openrouter_key=body.get("openrouter_key"),
                opencode_go_key=body.get("opencode_go_key"),
                opencode_key=body.get("opencode_key"),
                ai_provider=body.get("provider"),
            )
        except Exception as e:
            return _json_response(self, 400, {"ok": False, "error": str(e)})
        _json_response(self, 200, {"ok": True, "config": cfg, "message": "keys saved to .env (not logged)"})

    def _api_ai_set_model(self) -> None:
        body = self._parse_json_body()
        provider = (body.get("provider") or "").strip().lower()
        model = (body.get("model") or "").strip()
        if not provider or not model:
            return _json_response(self, 400, {"ok": False, "error": "provider and model are required"})
        try:
            cfg = save_dotenv_keys(
                ai_provider=provider,
                ai_model=model,
                model_openrouter=model if provider == "openrouter" else None,
                model_nvidia=model if provider == "nvidia" else None,
                model_ollama=model if provider == "ollama" else None,
                model_opencode_go=model if provider == "opencode_go" else None,
                model_opencode=model if provider == "opencode" else None,
            )
        except Exception as e:
            return _json_response(self, 400, {"ok": False, "error": str(e)})
        _json_response(self, 200, {"ok": True, "config": cfg})

    def _api_ai_probe(self) -> None:
        from sprite_repair.providers.opencode import (
            probe_opencode_json,
            probe_opencode_text,
            probe_opencode_vision,
        )
        from sprite_repair.ai_align import load_dotenv, opencode_endpoint

        body = self._parse_json_body()
        provider = (body.get("provider") or "").strip().lower()
        model = (body.get("model") or "").strip()
        kind = (body.get("kind") or "vision").strip().lower()
        if not provider or not model:
            return _json_response(self, 400, {"ok": False, "error": "provider and model are required"})
        try:
            opencode_endpoint(provider, load_dotenv())
        except Exception as e:
            return _json_response(self, 400, {"ok": False, "error": str(e)})
        env = load_dotenv()
        try:
            if kind == "vision":
                res = probe_opencode_vision(provider, model, env)
            elif kind == "text":
                res = probe_opencode_text(provider, model, env)
            elif kind == "json":
                res = probe_opencode_json(provider, model, env)
            else:
                return _json_response(self, 400, {"ok": False, "error": "kind must be vision|text|json"})
        except Exception as e:
            return _json_response(self, 500, {"ok": False, "error": str(e)})
        _json_response(self, 200, res)

    def _api_ai_verified(self) -> None:
        from sprite_repair.providers.opencode import load_verification_state

        state = load_verification_state()
        pub = {}
        for mid, entry in state.items():
            pub[mid] = {
                "status": entry.get("status"),
                "verified_at": entry.get("verified_at"),
                "protocol": entry.get("protocol"),
                "latency_s": entry.get("latency_s"),
            }
        _json_response(self, 200, {"ok": True, "verified": pub})


def main() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    host = "127.0.0.1"
    port = int(os.environ.get("PORT", 5190))
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    httpd = None
    for p in (port, port + 1, port + 2):
        try:
            httpd = ThreadingHTTPServer((host, p), Handler)
            port = p
            break
        except OSError:
            continue
    if not httpd:
        httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"SpriteRepair UI: http://{host}:{port}/")
    print(f"Root: {ROOT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
