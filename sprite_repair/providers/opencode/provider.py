"""OpenCode provider orchestration: endpoints, probing, verification state."""

from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from sprite_repair.providers.opencode.adapters import opencode_complete

ROOT = Path(__file__).resolve().parent.parent.parent.parent
VERIFIED_PATH = ROOT / "workspace" / "opencode_verified.json"

OPENCODE_PROVIDERS = {
    "opencode_go": {
        "name": "OpenCode Go",
        "base_default": "https://opencode.ai/zen/go/v1",
        "key_env": "OPENCODE_GO_API_KEY",
        "model_env": "AI_MODEL_OPENCODE_GO",
        "fallback_env": "AI_FALLBACK_OPENCODE_GO",
    },
    "opencode": {
        "name": "OpenCode Console",
        "base_default": "https://opencode.ai/zen/v1",
        "key_env": "OPENCODE_API_KEY",
        "model_env": "AI_MODEL_OPENCODE",
        "fallback_env": "AI_FALLBACK_OPENCODE",
    },
}

# statuses: DISCOVERED / TEXT_VERIFIED / VISION_VERIFIED / JSON_VERIFIED /
# IMPLEMENTED_NOT_LIVE_VERIFIED / REGION_UNAVAILABLE / AUTH_FAILED /
# TEMPORARILY_UNAVAILABLE / DEPRECATED


def opencode_endpoint(provider: str, env: dict[str, str]) -> tuple[str, str, str]:
    """Return (base_url, api_key, default_model) for opencode_go / opencode."""
    spec = OPENCODE_PROVIDERS.get(provider)
    if not spec:
        raise RuntimeError(f"unknown opencode provider: {provider}")
    key = env.get(spec["key_env"], "").strip()
    base = (env.get("OPENCODE_" + ("GO_" if provider == "opencode_go" else "") + "BASE_URL") or spec["base_default"]).rstrip("/")
    model = env.get(spec["model_env"], "").strip()
    if not model:
        model = "deepseek-v4-flash-vision-exp" if provider == "opencode_go" else "deepseek-v4-flash-free"
    return base, key, model


def load_verification_state() -> dict[str, Any]:
    if VERIFIED_PATH.is_file():
        try:
            return json.loads(VERIFIED_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_verification_state(state: dict[str, Any]) -> None:
    VERIFIED_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERIFIED_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _set_capability(model: str, capability: str, *, ok: bool, error: str | None = None, protocol: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge a probe result into the model verification state.

    Capabilities are monotonic flags; the displayed status is derived so a
    later weaker probe can never demote an earlier stronger one.
    """
    state = load_verification_state()
    entry = state.get(model) or {}
    entry.setdefault("text_ok", False)
    entry.setdefault("json_ok", False)
    entry.setdefault("vision_ok", False)
    if capability == "text":
        entry["text_ok"] = bool(entry.get("text_ok") or ok)
    elif capability == "json":
        entry["json_ok"] = bool(entry.get("json_ok") or ok)
    elif capability == "vision":
        entry["vision_ok"] = bool(entry.get("vision_ok") or ok)
    entry["verified_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if error:
        entry["error"] = str(error)[:400]
    elif "error" in entry:
        entry.pop("error", None)
    if protocol:
        entry["protocol"] = protocol
    if extra:
        for k, v in extra.items():
            if k != "status":
                entry[k] = v
    if entry.get("vision_ok"):
        entry["status"] = "VISION_VERIFIED"
    elif entry.get("json_ok"):
        entry["status"] = "JSON_VERIFIED"
    elif entry.get("text_ok"):
        entry["status"] = "TEXT_VERIFIED"
    else:
        entry["status"] = "UNVERIFIED"
    state[model] = entry
    save_verification_state(state)
    return entry


def _set_status(model: str, status: str, *, error: str | None = None, protocol: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Legacy status setter — kept for explicit failure statuses only."""
    if status in ("VISION_VERIFIED", "JSON_VERIFIED", "TEXT_VERIFIED", "UNVERIFIED"):
        capability = {"VISION_VERIFIED": "vision", "JSON_VERIFIED": "json", "TEXT_VERIFIED": "text", "UNVERIFIED": "text"}[status]
        return _set_capability(model, capability, ok=(status != "UNVERIFIED"), error=error, protocol=protocol, extra=extra)
    state = load_verification_state()
    entry = state.get(model) or {}
    entry["status"] = status
    entry["verified_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if error:
        entry["error"] = str(error)[:400]
    elif "error" in entry:
        entry.pop("error", None)
    if protocol:
        entry["protocol"] = protocol
    if extra:
        entry.update(extra)
    state[model] = entry
    save_verification_state(state)
    return entry


def _probe_sheet_image() -> Image.Image:
    """4 labeled frames; frame 3 character shifted 8px down-right."""
    cell = 96
    cols, rows = 4, 1
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (20, 24, 32, 255))
    draw = ImageDraw.Draw(sheet)
    for i in range(4):
        x0 = i * cell
        # character: 24x32 box standing on baseline y=76 (in-cell coords)
        shift = 8 if i == 3 else 0
        draw.rectangle(
            (x0 + 36 + shift, 32 + shift, x0 + 36 + 24 + shift, 32 + 52 + shift),
            fill=(230, 90, 120, 255),
        )
        draw.rectangle(
            (x0 + 36 + shift, 78 + shift, x0 + 36 + 24 + shift, 86 + shift),
            fill=(90, 60, 50, 255),
        )
        draw.text((x0 + 4, 4), str(i + 1), fill=(255, 220, 80, 255))
    return sheet


_VISION_PROBE_PROMPT = """This is a 4-frame sprite animation contact sheet labeled 1..4.
CRITICAL: Return JSON only. No markdown. No prose. First char '{', last '}'.
Exactly one frame has an inconsistent foot/root anchor (its character sits
8 pixels off the shared ground baseline compared to the other frames).
Return: {"problem_frames":[<frame number>]}
Frame numbering is 1-based (labels on the image)."""


# The shifted frame is index 3 (0-based) = label 4 (1-based, as drawn on the sheet).
_EXPECTED_PROBLEM_LABEL = 4


def probe_opencode_vision(
    provider: str,
    model: str,
    env: dict[str, str] | None = None,
    *,
    timeout: float = 90.0,
) -> dict[str, Any]:
    """Send the 4-frame probe sheet; VISION_VERIFIED only on schema match."""
    env = env if env is not None else {}
    base_url, api_key, _ = opencode_endpoint(provider, env)
    sheet = _probe_sheet_image()
    buf = BytesIO()
    sheet.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _VISION_PROBE_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }
    ]
    t0 = time.time()
    try:
        text = opencode_complete(
            base_url=base_url, api_key=api_key, model=model,
            messages=messages, timeout=timeout,
        )
        latency = round(time.time() - t0, 2)
    except RuntimeError as e:
        msg = str(e)
        if "HTTP 401" in msg or "HTTP 403" in msg:
            return {"ok": False, "status": "AUTH_FAILED", "error": msg, "model": model, "provider": provider}
        if "HTTP 429" in msg or "unavailable" in msg.lower() or "HTTP 500" in msg:
            return {"ok": False, "status": "TEMPORARILY_UNAVAILABLE", "error": msg, "model": model, "provider": provider}
        _set_status(model, "UNVERIFIED", error=msg, extra={"vision_probe_error": True})
        return {"ok": False, "status": "UNVERIFIED", "error": msg, "model": model, "provider": provider}

    # schema validation: find {"problem_frames": [...]}
    parsed: dict[str, Any] | None = None
    blobs = re.findall(r"\{[^{}]*\}", text)
    for blob in sorted(blobs, key=len, reverse=True):
        try:
            obj = json.loads(blob)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, dict) and "problem_frames" in obj:
            parsed = obj
            break
    if not parsed:
        try:
            parsed = json.loads(text)
        except Exception:  # noqa: BLE001
            parsed = None

    pf = (parsed or {}).get("problem_frames")
    hit = isinstance(pf, list) and any(int(x) == _EXPECTED_PROBLEM_LABEL for x in pf)
    if hit:
        _set_capability(model, "vision", ok=True, protocol="chat", extra={"latency_s": latency, "problem_frames": pf})
        status = "VISION_VERIFIED"
    else:
        _set_capability(model, "json", ok=True, protocol="chat", extra={"latency_s": latency, "problem_frames": pf})
        status = "JSON_VERIFIED"
    return {
        "ok": hit,
        "status": status,
        "model": model,
        "provider": provider,
        "problem_frames": pf,
        "expected": [_EXPECTED_PROBLEM_LABEL],
        "latency_s": latency,
        "raw": text[:300],
    }


_TEXT_PROBE_PROMPT = "Reply with exactly: OK"


def probe_opencode_text(
    provider: str,
    model: str,
    env: dict[str, str] | None = None,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    env = env if env is not None else {}
    base_url, api_key, _ = opencode_endpoint(provider, env)
    t0 = time.time()
    try:
        text = opencode_complete(
            base_url=base_url, api_key=api_key, model=model,
            messages=[{"role": "user", "content": _TEXT_PROBE_PROMPT}],
            timeout=timeout, json_mode=False,
        )
        latency = round(time.time() - t0, 2)
        ok = bool(text.strip())
        _set_capability(model, "text", ok=ok, protocol="chat", extra={"latency_s": latency})
        return {"ok": ok, "status": "TEXT_VERIFIED" if ok else "UNVERIFIED", "model": model, "provider": provider, "latency_s": latency, "raw": text[:200]}
    except RuntimeError as e:
        msg = str(e)
        if "HTTP 401" in msg or "HTTP 403" in msg:
            status = "AUTH_FAILED"
        elif "HTTP 429" in msg or "unavailable" in msg.lower() or "HTTP 500" in msg:
            status = "TEMPORARILY_UNAVAILABLE"
        else:
            status = "UNVERIFIED"
        _set_status(model, status, error=msg)
        return {"ok": False, "status": status, "error": msg, "model": model, "provider": provider}


_JSON_PROBE_PROMPT = 'Return JSON only: {"ok": true}'


def probe_opencode_json(
    provider: str,
    model: str,
    env: dict[str, str] | None = None,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    env = env if env is not None else {}
    base_url, api_key, _ = opencode_endpoint(provider, env)
    t0 = time.time()
    try:
        text = opencode_complete(
            base_url=base_url, api_key=api_key, model=model,
            messages=[{"role": "user", "content": _JSON_PROBE_PROMPT}],
            timeout=timeout,
        )
        latency = round(time.time() - t0, 2)
        blobs = re.findall(r"\{[^{}]*\}", text)
        ok = False
        for blob in blobs:
            try:
                if json.loads(blob).get("ok") is True:
                    ok = True
                    break
            except Exception:  # noqa: BLE001
                continue
        _set_capability(model, "json", ok=ok, protocol="chat", extra={"latency_s": latency})
        return {"ok": ok, "status": "JSON_VERIFIED" if ok else "UNVERIFIED", "model": model, "provider": provider, "latency_s": latency, "raw": text[:200]}
    except RuntimeError as e:
        msg = str(e)
        if "HTTP 401" in msg or "HTTP 403" in msg:
            status = "AUTH_FAILED"
        elif "HTTP 429" in msg or "unavailable" in msg.lower() or "HTTP 500" in msg:
            status = "TEMPORARILY_UNAVAILABLE"
        else:
            status = "UNVERIFIED"
        _set_status(model, status, error=msg)
        return {"ok": False, "status": status, "error": msg, "model": model, "provider": provider}
