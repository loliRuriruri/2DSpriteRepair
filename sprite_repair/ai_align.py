"""AI vision foot/scale alignment for Sprite Repair (stdlib urllib only)."""

from __future__ import annotations

# SR_JSON_ONLY_ALIGN_V1

import base64
import json
import re
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from sprite_repair.pipeline import recompose_with_anchors
from sprite_repair.providers.opencode import (
    OPENCODE_PROVIDERS,
    list_opencode_models_merged,
    load_verification_state,
    opencode_complete,
    opencode_endpoint,
    probe_opencode_json,
    probe_opencode_text,
    probe_opencode_vision,
)

ROOT = Path(__file__).resolve().parent.parent
OPENROUTER_VISION_DEFAULT = "google/gemma-4-31b-it:free"
OPENROUTER_LIST_DEFAULT = "google/gemma-4-31b-it:free"
ENV_PATH = ROOT / ".env"
_PROMPT = """You are aligning sprite animation frames for a 2D game.
CRITICAL: Reply with ONLY one JSON object. No markdown. No reasoning. No prose.
First character must be '{' and last must be '}'. Example schema:
{"frames":[{"frame":0,"anchor_x":64,"anchor_y":120,"scale":1.0},{"frame":1,"anchor_x":66,"anchor_y":118,"scale":1.0}]}
For EACH frame image (index order given), find the character foot / ground-contact center
and a relative scale vs median character height.

Return ONLY valid JSON (no markdown, no commentary):
{"frames":[{"frame":0,"anchor_x":123,"anchor_y":200,"scale":1.0}, ...]}

Rules:
- anchor_x, anchor_y are integers in the ORIGINAL crop/raw frame pixel coordinates
  (NOT the downscaled preview). Image size for each frame is provided in the text.
- Foot anchor = center of ground contact (bottom of feet / root).
- scale is relative to median character height across frames; 1.0 = no change.
  Prefer values between 0.85 and 1.15 unless a frame is clearly wrong size.
- Include every frame index exactly once, starting at 0.
"""


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    """Parse KEY=VALUE lines from .env (no python-dotenv required)."""
    p = path or ENV_PATH
    out: dict[str, str] = {}
    if not p.is_file():
        return out
    raw_text = p.read_text(encoding="utf-8-sig")  # strip BOM
    for raw in raw_text.splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        val = val.strip().strip('"').strip("'")
        if key:
            out[key] = val
    return out




# Popular / useful order for sprite vision assist (NVIDIA Build catalog - working vision models first)
CURATED_NVIDIA = [
    "meta/llama-3.2-11b-vision-instruct",
    "meta/llama-3.2-90b-vision-instruct",
    "microsoft/phi-3-vision-128k-instruct",
    "google/gemma-3-12b-it",
    "google/gemma-3-4b-it",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "moonshotai/kimi-k3",
    "deepseek-ai/deepseek-v4-flash-0731",
    "deepseek-ai/deepseek-v4-pro-0813",
    "nvidia/llama-3.1-nemotron-70b-instruct",
]

# OpenRouter multimodal / vision models (FREE high-performance vision models prioritized)
CURATED_OPENROUTER = [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "qwen/qwen-2.5-vl-72b-instruct:free",
    "meta/llama-3.2-11b-vision-instruct:free",
    "nex-agi/nex-n2.5-pro:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "openrouter/free",
    "google/gemini-2.5-flash-lite",
    "google/gemini-2.5-flash",
    "meta/llama-3.2-11b-vision-instruct",
    "qwen/qwen-2.5-vl-72b-instruct",
    "openai/gpt-4o-mini",
    "deepseek/deepseek-v4-flash-vision-exp",
    "moonshotai/kimi-k3",
    "xiaomi/mimo-v2.5",
    "anthropic/claude-haiku-4.5",
]


def _dedupe(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in seq:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _is_visionish(model_id: str, meta: dict[str, Any] | None = None) -> bool:
    low = model_id.lower()
    vision_keys = (
        "vision", "vl-", "vl_", "-vl", "vlm", "image", "omni", "gemini",
        "gpt-4o", "gpt-5", "claude", "kimi-k3", "gemma-3", "gemma-4",
        "mimo", "qwen", "minimax", "phi-3-vision", "phi-4", "nex-n2.5-pro",
        "openrouter/free", "dots-3", "inkling", "llama-3.2-11b-vision",
        "llama-3.2-90b-vision", "fuyu", "kosmos", "neva", "nano-omni"
    )
    if any(k in low for k in vision_keys):
        return True
    if meta:
        arch = meta.get("architecture") or {}
        mods = arch.get("input_modalities") or []
        if isinstance(mods, list) and any("image" in str(x).lower() for x in mods):
            return True
        modality = str(arch.get("modality") or "").lower()
        if "image" in modality:
            return True
    return False


def list_nvidia_models(env: dict[str, str] | None = None) -> dict[str, Any]:
    """Scan NVIDIA /v1/models; curated popular order + DeepSeek/Kimi/vision first."""
    env = env if env is not None else load_dotenv()
    key = env.get("NVIDIA_API_KEY", "").strip()
    base = (env.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1").rstrip("/")
    default = (env.get("AI_MODEL_NVIDIA") or "meta/llama-3.2-11b-vision-instruct").strip()
    scanned: list[str] = []
    error = None
    if not key:
        return {
            "ok": False,
            "provider": "nvidia",
            "error": "NVIDIA_API_KEY not configured in .env",
            "default": default,
            "curated": list(CURATED_NVIDIA),
            "models": list(CURATED_NVIDIA),
            "scanned_count": 0,
        }
    try:
        url = f"{base}/models"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for row in data.get("data") or []:
            mid = row.get("id") if isinstance(row, dict) else None
            if isinstance(mid, str) and mid:
                scanned.append(mid)
        scanned = sorted(set(scanned))
    except Exception as e:
        error = str(e)
        scanned = []

    prefer = [m for m in CURATED_NVIDIA if (not scanned or m in scanned)]
    if default and default not in prefer:
        prefer = [default] + prefer
    extras = []
    for m in scanned:
        low = m.lower()
        if any(k in low for k in ("deepseek", "kimi", "moonshot", "vision", "vl-", "vl_", "gemma-3", "phi-3-vision", "nemotron")):
            if m not in prefer:
                extras.append(m)
    models = _dedupe(prefer + extras)
    # Drop known broken-for-many-accounts k2.6 if present after k3 (keep in list but after working ones)
    return {
        "ok": error is None,
        "provider": "nvidia",
        "error": error,
        "default": default if (not scanned or default in scanned or default in CURATED_NVIDIA) else (prefer[0] if prefer else default),
        "curated": list(CURATED_NVIDIA),
        "models": models,
        "scanned_count": len(scanned),
        "sort": "build-nvidia-popular",
        "note": "kimi-k3 needs reasoning_effort on NVIDIA; some catalog ids 404 for free-tier accounts",
    }


def list_openrouter_models(env: dict[str, str] | None = None) -> dict[str, Any]:
    """OpenRouter models: free first, then cheapest; default Nemotron free."""
    env = env if env is not None else load_dotenv()
    key = env.get("OPENROUTER_API_KEY", "").strip()
    base = (env.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
    default = (env.get("AI_MODEL_OPENROUTER") or OPENROUTER_VISION_DEFAULT).strip()
    error = None
    rows_out: list[dict[str, Any]] = []
    if not key:
        return {
            "ok": False,
            "provider": "openrouter",
            "error": "OPENROUTER_API_KEY not configured in .env",
            "default": default,
            "curated": list(CURATED_OPENROUTER),
            "models": list(CURATED_OPENROUTER),
            "scanned_count": 0,
            "sort": "free-then-price",
        }
    try:
        url = f"{base}/models?sort=pricing-low-to-high"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
                "HTTP-Referer": "http://127.0.0.1:5190/",
                "X-Title": "SpriteRepair",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for row in data.get("data") or []:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                rows_out.append(row)
    except Exception as e:
        error = str(e)
        rows_out = []

    def _price(row: dict[str, Any]) -> float:
        pricing = row.get("pricing") or {}
        try:
            prompt = float(pricing.get("prompt") or 0)
            completion = float(pricing.get("completion") or 0)
            return prompt + completion
        except Exception:
            return 1e9

    def _is_free(row: dict[str, Any]) -> bool:
        mid = str(row.get("id") or "")
        if mid.endswith(":free") or ":free" in mid:
            return True
        return _price(row) <= 0.0

    # Prefer curated order for free/cheap anchors, then API price order
    by_id = {r["id"]: r for r in rows_out}
    free_ids = [r["id"] for r in rows_out if _is_free(r)]
    paid = [r for r in rows_out if not _is_free(r)]
    paid.sort(key=lambda r: (_price(r), 0 if "deepseek" in r["id"].lower() else 1, r["id"]))

    # Free vision models first (Curated free vision -> Discovered free vision)
    free_vision_spine = [
        m for m in CURATED_OPENROUTER
        if (m in by_id or m.endswith(":free")) and (_is_free(by_id.get(m, {})) or ":free" in m) and _is_visionish(m, by_id.get(m))
    ]
    other_free_vision = [
        m for m in free_ids
        if _is_visionish(m, by_id.get(m)) and m not in free_vision_spine
    ]
    # Then curated paid vision models (e.g. Gemini 2.5 Flash Lite, GPT-4o-mini, etc.)
    curated_paid = [m for m in CURATED_OPENROUTER if m not in free_vision_spine]

    spine = []
    if default and default in by_id:
        spine.append(default)
    for m in free_vision_spine + other_free_vision + curated_paid:
        if m not in spine:
            spine.append(m)

    extra_free = [m for m in free_ids if m not in spine]
    extra_paid = [r["id"] for r in paid if r["id"] not in spine]
    models = _dedupe(spine + extra_free + extra_paid)
    vision_models = [m for m in models if _is_visionish(m, by_id.get(m))]

    # Default: user default if it supports vision, otherwise top free vision model
    vision_default = default if (default in vision_models) else (vision_models[0] if vision_models else OPENROUTER_VISION_DEFAULT)

    models_meta = []
    for mid in models:
        row = by_id.get(mid) or {}
        pricing = row.get("pricing") or {}
        price = None
        try:
            pp = float(pricing.get("prompt") or 0)
            if pp > 0:
                price = f"${pp * 1e6:g}/1M"
            elif mid.endswith(":free") or ":free" in mid:
                price = "무료"
        except Exception:  # noqa: BLE001
            price = None
        desc = None
        try:
            from sprite_repair.providers.opencode.registry import MODEL_DESC_KO
            desc = MODEL_DESC_KO.get(mid)
        except Exception:  # noqa: BLE001
            desc = None
        models_meta.append({
            "id": mid,
            "vision": _is_visionish(mid, row if row else None),
            "free": mid.endswith(":free") or ":free" in mid or (_price(row) <= 0 if row else mid.endswith(":free")),
            "price": price,
            "desc": desc,
        })

    if "vision_models" not in locals():
        vision_models = [m for m in models if _is_visionish(m, by_id.get(m) if "by_id" in locals() else None)]
        vision_default = next((m for m in (OPENROUTER_VISION_DEFAULT, *vision_models) if m in vision_models or m == OPENROUTER_VISION_DEFAULT), OPENROUTER_VISION_DEFAULT)
        if vision_default not in vision_models and vision_models:
            vision_default = vision_models[0]
        models_meta = [{"id": m, "vision": m in vision_models, "free": m.endswith(":free") or ":free" in m} for m in models]
    return {
        "ok": error is None,
        "provider": "openrouter",
        "error": error,
        "default": default,
        "vision_default": vision_default,
        "curated": list(CURATED_OPENROUTER),
        "models": models,
        "vision_models": vision_models,
        "models_meta": models_meta,
        "scanned_count": len(rows_out),
        "sort": "free-then-price",
        "note": "AI 정렬/시트QA는 vision 모델만. 텍스트 전용 free(Nemotron 등)는 이미지 404.",
    }


def list_ollama_models(env: dict[str, str] | None = None) -> dict[str, Any]:
    """List installed models in local Ollama instance (127.0.0.1:11434)."""
    env = env if env is not None else load_dotenv()
    base_url = (env.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
    url = f"{base_url}/api/tags"
    req = urllib.request.Request(url, headers={"User-Agent": "SpriteRepair/0.1"})
    models: list[str] = []
    models_meta: list[dict[str, Any]] = []
    vision_models: list[str] = []

    try:
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for m in data.get("models", []):
                name = m.get("name", "")
                if not name:
                    continue
                models.append(name)
                details = m.get("details", {}) or {}
                families = details.get("families", []) or []
                param_size = details.get("parameter_size", "")
                is_vision = any(
                    x in name.lower() for x in ["vl", "vision", "llava", "cpm", "paligemma", "qwen3.5", "qwen3-vl"]
                ) or any("clip" in str(f).lower() or "vision" in str(f).lower() for f in families)

                models_meta.append({
                    "id": name,
                    "name": name + (" 📷 [비전]" if is_vision else ""),
                    "free": True,
                    "local": True,
                    "vision": is_vision,
                    "param_size": param_size,
                    "pricing": {"prompt": "0", "completion": "0"},
                })
                if is_vision:
                    vision_models.append(name)
    except Exception:
        manifest_dir = Path.home() / ".ollama" / "models" / "manifests"
        if manifest_dir.is_dir():
            for f in manifest_dir.rglob("*"):
                if f.is_file():
                    parts = f.relative_to(manifest_dir).parts
                    if len(parts) >= 3:
                        if parts[1] == "library":
                            m_name = f"{parts[2]}:{parts[3]}" if len(parts) > 3 else parts[2]
                        else:
                            m_name = f"{parts[1]}/{parts[2]}:{parts[3]}" if len(parts) > 3 else f"{parts[1]}/{parts[2]}"
                        if m_name not in models:
                            models.append(m_name)
                            is_v = any(x in m_name.lower() for x in ["vl", "vision", "llava", "cpm", "qwen3.5", "qwen3-vl"])
                            models_meta.append({
                                "id": m_name,
                                "name": m_name + (" 📷 [비전]" if is_v else "") + " (오프라인)",
                                "free": True,
                                "local": True,
                                "vision": is_v,
                                "pricing": {"prompt": "0", "completion": "0"},
                            })
                            if is_v:
                                vision_models.append(m_name)

    vision_models.sort(key=lambda x: (0 if "qwen3-vl" in x.lower() else (1 if "-vl" in x.lower() or "vl-" in x.lower() or "vision" in x.lower() else (2 if "qwen3.5" in x.lower() else 3))))
    default_vision = vision_models[0] if vision_models else (models[0] if models else "huihui_ai/qwen3-vl-abliterated:8b-instruct")

    return {
        "ok": True,
        "provider": "ollama",
        "models": models,
        "vision_models": vision_models if vision_models else models,
        "models_meta": models_meta,
        "vision_default": default_vision,
        "default": default_vision,
        "curated": vision_models if vision_models else models,
        "is_local": True,
    }


def list_opencode_models(provider: str, env: dict[str, str] | None = None) -> dict[str, Any]:
    """OpenCode Go / Console: dynamic /models discovery merged with registry."""
    env = env if env is not None else load_dotenv()
    base_url, _, _ = opencode_endpoint(provider, env)
    return list_opencode_models_merged(provider, env, base_url=base_url, verified=load_verification_state())


def list_ai_models(provider: str | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env if env is not None else load_dotenv()
    cfg = ai_config_public(env)
    prov = (provider or cfg.get("default_provider") or "ollama").strip().lower()
    if prov in OPENCODE_PROVIDERS:
        return list_opencode_models(prov, env)
    if prov == "ollama":
        return list_ollama_models(env)
    if prov == "openrouter":
        return list_openrouter_models(env)
    return list_nvidia_models(env)



def mask_secret(s: str | None) -> str:
    if not s:
        return "(empty)"
    return "****"



def save_dotenv_keys(
    *,
    nvidia_key: str | None = None,
    openrouter_key: str | None = None,
    opencode_go_key: str | None = None,
    opencode_key: str | None = None,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    model_openrouter: str | None = None,
    model_nvidia: str | None = None,
    model_ollama: str | None = None,
    model_opencode_go: str | None = None,
    model_opencode: str | None = None,
    ollama_base_url: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Update .env keys without echoing secrets. Empty string means leave unchanged."""
    p = path or ENV_PATH
    env = load_dotenv(p)
    if nvidia_key is not None and nvidia_key.strip():
        env["NVIDIA_API_KEY"] = nvidia_key.strip()
    if openrouter_key is not None and openrouter_key.strip():
        env["OPENROUTER_API_KEY"] = openrouter_key.strip()
    if opencode_go_key is not None and opencode_go_key.strip():
        env["OPENCODE_GO_API_KEY"] = opencode_go_key.strip()
    if opencode_key is not None and opencode_key.strip():
        env["OPENCODE_API_KEY"] = opencode_key.strip()
    if ai_provider:
        prov = ai_provider.strip().lower()
        if prov in ("nvidia", "openrouter", "ollama", "opencode_go", "opencode", "disabled"):
            env["AI_PROVIDER"] = prov
            if ai_model and ai_model.strip():
                if prov == "openrouter":
                    env["AI_MODEL_OPENROUTER"] = ai_model.strip()
                elif prov == "nvidia":
                    env["AI_MODEL_NVIDIA"] = ai_model.strip()
                elif prov == "ollama":
                    env["AI_MODEL_OLLAMA"] = ai_model.strip()
                elif prov == "opencode_go":
                    env["AI_MODEL_OPENCODE_GO"] = ai_model.strip()
                elif prov == "opencode":
                    env["AI_MODEL_OPENCODE"] = ai_model.strip()
    if model_openrouter is not None and model_openrouter.strip():
        env["AI_MODEL_OPENROUTER"] = model_openrouter.strip()
    if model_nvidia is not None and model_nvidia.strip():
        env["AI_MODEL_NVIDIA"] = model_nvidia.strip()
    if model_ollama is not None and model_ollama.strip():
        env["AI_MODEL_OLLAMA"] = model_ollama.strip()
    if model_opencode_go is not None and model_opencode_go.strip():
        env["AI_MODEL_OPENCODE_GO"] = model_opencode_go.strip()
    if model_opencode is not None and model_opencode.strip():
        env["AI_MODEL_OPENCODE"] = model_opencode.strip()
    if ollama_base_url is not None and ollama_base_url.strip():
        env["OLLAMA_BASE_URL"] = ollama_base_url.strip()
    # preserve known order
    order = [
        "AI_PROVIDER",
        "AI_MODEL_OLLAMA",
        "OLLAMA_BASE_URL",
        "OPENCODE_GO_API_KEY",
        "AI_MODEL_OPENCODE_GO",
        "AI_FALLBACK_OPENCODE_GO",
        "OPENCODE_API_KEY",
        "AI_MODEL_OPENCODE",
        "AI_FALLBACK_OPENCODE",
        "NVIDIA_API_KEY",
        "OPENROUTER_API_KEY",
        "AI_MODEL_OPENROUTER",
        "AI_MODEL_NVIDIA",
        "NVIDIA_BASE_URL",
        "OPENROUTER_BASE_URL",
    ]
    lines: list[str] = []
    seen = set()
    for k in order:
        if k in env:
            lines.append(f"{k}={env[k]}")
            seen.add(k)
    for k, v in env.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    p.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
    return ai_config_public(load_dotenv(p))


def ai_config_public(env: dict[str, str] | None = None) -> dict[str, Any]:
    env = env if env is not None else load_dotenv()
    nvidia_ok = bool(env.get("NVIDIA_API_KEY", "").strip())
    openrouter_ok = bool(env.get("OPENROUTER_API_KEY", "").strip())
    opencode_go_ok = bool(env.get("OPENCODE_GO_API_KEY", "").strip())
    opencode_ok = bool(env.get("OPENCODE_API_KEY", "").strip())
    ollama_online = False
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "SpriteRepair/0.1"})
        with urllib.request.urlopen(req, timeout=0.8) as r:
            if r.status == 200:
                ollama_online = True
    except Exception:
        ollama_online = False

    saved_prov = (env.get("AI_PROVIDER") or "").strip().lower()
    if saved_prov in ("ollama", "openrouter", "nvidia", "opencode_go", "opencode", "disabled"):
        default_provider = saved_prov
    else:
        default_provider = "ollama" if ollama_online else ("opencode_go" if opencode_go_ok else ("nvidia" if nvidia_ok else "openrouter"))

    models = {
        "ollama": (env.get("AI_MODEL_OLLAMA") or "huihui_ai/qwen3-vl-abliterated:8b-instruct").strip(),
        "openrouter": (env.get("AI_MODEL_OPENROUTER") or OPENROUTER_VISION_DEFAULT).strip(),
        "nvidia": (env.get("AI_MODEL_NVIDIA") or "meta/llama-3.2-11b-vision-instruct").strip(),
        "opencode_go": (env.get("AI_MODEL_OPENCODE_GO") or "deepseek-v4-flash-vision-exp").strip(),
        "opencode": (env.get("AI_MODEL_OPENCODE") or "deepseek-v4-flash-free").strip(),
    }
    def _hint(key: str) -> str:
        v = env.get(key, "").strip()
        if not v:
            return ""
        if len(v) <= 8:
            return "****"
        return v[:4] + "…" + v[-4:]

    return {
        "ok": True,
        "providers": {
            "ollama": True,
            "nvidia": nvidia_ok,
            "openrouter": openrouter_ok,
            "opencode_go": opencode_go_ok,
            "opencode": opencode_ok,
            "disabled": True,
        },
        "ollama_online": ollama_online,
        "key_hints": {
            "ollama": "Local (API 키 불필요)",
            "nvidia": _hint("NVIDIA_API_KEY"),
            "openrouter": _hint("OPENROUTER_API_KEY"),
            "opencode_go": _hint("OPENCODE_GO_API_KEY"),
            "opencode": _hint("OPENCODE_API_KEY"),
        },
        "default_provider": default_provider,
        "default_model": models.get(default_provider, models["ollama"]),
        "models": models,
    }



def _nn_upscale_for_ai(img: Image.Image, min_side: int = 512, factor: int = 8) -> Image.Image:
    """Nearest-neighbor enlarge tiny pixel art for vision models; keep sharp pixels."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    if max(w, h) >= min_side:
        return rgba
    scale = max(2, int(factor))
    while max(w * scale, h * scale) > 2048 and scale > 2:
        scale -= 1
    return rgba.resize((w * scale, h * scale), Image.Resampling.NEAREST)

def _downscale_png_b64(img: Image.Image, max_side: int = 384) -> tuple[str, int, int, float]:
    """Return (base64 png, orig_w, orig_h, scale_factor preview/original)."""
    rgba = img.convert("RGBA")
    ow, oh = rgba.size
    factor = 1.0
    if max(ow, oh) > max_side:
        factor = max_side / float(max(ow, oh))
        nw = max(1, int(round(ow * factor)))
        nh = max(1, int(round(oh * factor)))
        rgba = rgba.resize((nw, nh), Image.Resampling.LANCZOS)
    buf = BytesIO()
    rgba.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return b64, ow, oh, factor


def _provider_endpoint(provider: str, env: dict[str, str]) -> tuple[str, str, str]:
    """Return (base_url, api_key, default_model). Never log the key."""
    p = provider.strip().lower()
    if p in OPENCODE_PROVIDERS:
        return opencode_endpoint(p, env)
    if p == "nvidia":
        key = env.get("NVIDIA_API_KEY", "").strip()
        base = (env.get("NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1").rstrip("/")
        model = (env.get("AI_MODEL_NVIDIA") or "meta/llama-3.2-11b-vision-instruct").strip()
        if not key:
            raise RuntimeError("NVIDIA_API_KEY not configured in .env")
        return base, key, model
    if p == "openrouter":
        key = env.get("OPENROUTER_API_KEY", "").strip()
        base = (env.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").rstrip("/")
        model = (env.get("AI_MODEL_OPENROUTER") or "nvidia/nemotron-3-ultra-550b-a55b:free").strip()
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY not configured in .env")
    if p == "ollama":
        base = (env.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434/v1").rstrip("/")
        model = (env.get("AI_MODEL_OLLAMA") or "huihui_ai/qwen3-vl-abliterated:8b-instruct").strip()
        return base, "ollama", model
    raise RuntimeError(f"unknown provider: {provider}")


def _chat_completions(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    provider: str,
    timeout: float = 120.0,
) -> str:
    # OpenCode Go / Console: dispatch to dialect adapters (chat / responses /
    # messages) with protocol fallback.
    if provider in OPENCODE_PROVIDERS:
        return opencode_complete(
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=messages,
            timeout=timeout,
        )
    url = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    # Ask for JSON when provider supports it (ignore if model rejects — caller retries).
    if provider in ("openrouter", "nvidia", "ollama"):
        payload["response_format"] = {"type": "json_object"}
    # NVIDIA Kimi K3 (and similar) require reasoning_effort
    low = model.lower()
    if "kimi-k3" in low or (provider == "nvidia" and "kimi" in low):
        payload["temperature"] = 1.0
        payload["reasoning_effort"] = "low"
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "http://127.0.0.1:5190/"
        headers["X-Title"] = "SpriteRepair"
    import time
    max_attempts = 2 if provider == "ollama" else 1
    raw = ""
    for attempt in range(max_attempts):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                break
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")[:800]
            # If Ollama backend was restarting or switching models, retry once
            if attempt < max_attempts - 1 and provider == "ollama" and (
                e.code == 500 or "forcibly closed" in err_body or "wsarecv" in err_body
            ):
                time.sleep(1.5)
                continue

            # Never include Authorization / secrets
            if (
                e.code == 400
                and "response_format" in payload
                and ("response_format" in err_body.lower() or "json_object" in err_body.lower() or "invalid" in err_body.lower())
            ):
                payload.pop("response_format", None)
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        raw = resp.read().decode("utf-8")
                        break
                except urllib.error.HTTPError as e2:
                    err_body2 = e2.read().decode("utf-8", errors="replace")[:800]
                    raise RuntimeError(f"AI HTTP {e2.code}: {err_body2}") from None
            else:
                if provider == "ollama" and ("forcibly closed" in err_body or "wsarecv" in err_body):
                    raise RuntimeError(
                        f"Ollama 로컬 백엔드(llama-server) 중단이 발생했습니다.\n"
                        f"대형 모델({model})의 비전 부하 때문일 수 있으니, 상단에서 빠르고 안정적인 'huihui_ai/qwen3-vl-abliterated:8b-instruct'(약 3초 완료) 모델로 변경해 보세요."
                    ) from None
                raise RuntimeError(f"AI HTTP {e.code}: {err_body}") from None
        except TimeoutError as e:
            raise RuntimeError(
                f"AI 응답 시간 초과({int(timeout)}초). 비전 모델/프레임 수를 줄이거나 잠시 후 다시 시도하세요."
            ) from None
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", e)
            # nested timeout
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise RuntimeError(
                    f"AI 응답 시간 초과({int(timeout)}초). 비전 모델/프레임 수를 줄이거나 잠시 후 다시 시도하세요."
                ) from None
            if attempt < max_attempts - 1 and provider == "ollama":
                time.sleep(1.5)
                continue
            if provider == "ollama" and ("10054" in str(reason) or "forcibly closed" in str(reason)):
                raise RuntimeError(
                    f"Ollama 로컬 백엔드(llama-server) 연결이 끊어졌습니다.\n"
                    f"가볍고 빠른 비전 전용 모델인 'huihui_ai/qwen3-vl-abliterated:8b-instruct'(약 3초 완료) 모델로 다시 시도해 보세요."
                ) from None
            raise RuntimeError(f"AI network error: {reason}") from None
        except OSError as e:
            if attempt < max_attempts - 1 and provider == "ollama":
                time.sleep(1.5)
                continue
            if provider == "ollama" and ("10054" in str(e) or "forcibly closed" in str(e)):
                raise RuntimeError(
                    f"Ollama 로컬 백엔드(llama-server) 연결이 끊어졌습니다.\n"
                    f"가볍고 빠른 비전 전용 모델인 'huihui_ai/qwen3-vl-abliterated:8b-instruct'(약 3초 완료) 모델로 다시 시도해 보세요."
                ) from None
            raise RuntimeError(f"AI network/OS error: {e}") from None
    data = json.loads(raw)
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError("AI response missing message: %s" % (str(data)[:400],)) from e
    return _message_text(msg)


def _message_text(msg):
    """Pull usable text; content may be null on reasoning/vision models."""
    if not isinstance(msg, dict):
        raise RuntimeError("AI message not an object: %s" % (str(msg)[:300],))
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str) and part.strip():
                parts.append(part)
            elif isinstance(part, dict):
                t = part.get("text") or part.get("content")
                if isinstance(t, str) and t.strip():
                    parts.append(t)
        if parts:
            return "\n".join(parts)
    for key in ("reasoning_content", "reasoning", "refusal"):
        alt = msg.get(key)
        if isinstance(alt, str) and alt.strip():
            return alt
    raise RuntimeError(
        "AI returned empty content (content=null). "
        "Try another vision model (gemini / kimi). keys=%s preview=%s"
        % (list(msg.keys())[:12], str(msg)[:280])
    )


def _strip_md_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"```(?:json|JSON)?\s*", "", text)
    text = re.sub(r"```", "", text)
    return text.strip()


def _balanced_blobs(s: str, open_ch: str, close_ch: str) -> list[str]:
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        if s[i] != open_ch:
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        start = i
        j = i
        while j < n:
            ch = s[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                j += 1
                continue
            if ch == '"':
                in_str = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    out.append(s[start : j + 1])
                    i = j + 1
                    break
            j += 1
        else:
            break
    return out


def _loads_loose_json(s: str) -> Any:
    s2 = re.sub(r",\s*([}\]])", r"\1", s.strip())
    return json.loads(s2)


def _user_facing_ai_error(kind: str, preview: str | None = None, limit: int = 120) -> str:
    base = {
        "no_json": "모델이 JSON이 아닌 설명을 반환했습니다. Gemini Flash Lite로 바꿔 보세요.",
        "parse": "모델 JSON 파싱에 실패했습니다. Gemini Flash Lite로 바꿔 보세요.",
        "empty": "모델이 빈 응답을 반환했습니다. Gemini Flash Lite로 바꿔 보세요.",
        "schema": "모델 JSON에 frames[]가 없습니다. Gemini Flash Lite로 바꿔 보세요.",
    }.get(kind, "AI 정렬에 실패했습니다. Gemini Flash Lite로 바꿔 보세요.")
    if not preview:
        return base
    snip = re.sub(r"\s+", " ", preview).strip()
    if len(snip) > limit:
        snip = snip[: limit - 1] + "…"
    return f"{base} ({snip})"


def _extract_json(text: str | None) -> dict[str, Any]:
    """Parse model text: strip fences; take largest {...} or [...]."""
    if text is None or not str(text).strip():
        raise RuntimeError(_user_facing_ai_error("empty"))
    text = _strip_md_fences(str(text))
    blobs = _balanced_blobs(text, "{", "}") + _balanced_blobs(text, "[", "]")
    blobs.sort(key=len, reverse=True)
    if not blobs:
        raise RuntimeError(_user_facing_ai_error("no_json", text))
    last_err: Exception | None = None
    fallback: list[dict[str, Any]] = []
    for blob in blobs:
        try:
            obj = _loads_loose_json(blob)
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
        if isinstance(obj, dict):
            if "frames" in obj:
                return obj
            fallback.append(obj)
        elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
            if "anchor_x" in obj[0] or "frame" in obj[0]:
                return {"frames": obj}
    if fallback:
        return fallback[0]
    if last_err is not None:
        raise RuntimeError(_user_facing_ai_error("parse", text)) from None
    raise RuntimeError(_user_facing_ai_error("no_json", text))


_REPAIR_JSON_PROMPT = (
    "JSON only. No other text. No markdown.\n"
    'Example: {"frames":[{"frame":0,"anchor_x":64,"anchor_y":120,"scale":1.0}]}\n'
    "Bad reply snippet:\n{snippet}\n"
)


def _repair_align_json_once(
    *,
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    bad_text: str,
    n_frames: int,
) -> str:
    snip = re.sub(r"\s+", " ", (bad_text or "")[:350]).strip()
    prompt = _REPAIR_JSON_PROMPT.format(snippet=snip) + f"N={n_frames} (frames 0..{n_frames-1})."
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": [{"type": "text", "text": prompt}]}
    ]
    return _chat_completions(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=messages,
    )


def _parse_align_response(
    text: str,
    *,
    n_frames: int,
    provider: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    allow_repair: bool = True,
) -> dict[str, Any]:
    try:
        parsed = _extract_json(text)
        frames = parsed.get("frames")
        if not isinstance(frames, list) or not frames:
            raise RuntimeError(_user_facing_ai_error("schema", text))
        return parsed
    except RuntimeError as err:
        if not allow_repair or not provider or not base_url or not api_key or not model:
            raise
        try:
            fixed = _repair_align_json_once(
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                model=model,
                bad_text=text,
                n_frames=n_frames,
            )
            parsed = _extract_json(fixed)
            frames = parsed.get("frames")
            if not isinstance(frames, list) or not frames:
                raise RuntimeError(_user_facing_ai_error("schema", fixed))
            return parsed
        except Exception:
            raise err from None


def _resize_about_anchor(img: Image.Image, anchor: dict[str, int], scale: float) -> tuple[Image.Image, dict[str, int]]:
    """Resize image by scale, keeping anchor point meaning in new pixel space."""
    if abs(scale - 1.0) < 1e-3:
        return img, {"x": int(anchor["x"]), "y": int(anchor["y"])}
    scale = max(0.25, min(4.0, float(scale)))
    w, h = img.size
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    ax = int(round(int(anchor["x"]) * scale))
    ay = int(round(int(anchor["y"]) * scale))
    ax = max(0, min(nw - 1, ax))
    ay = max(0, min(nh - 1, ay))
    return resized, {"x": ax, "y": ay}



def assert_model_supports_vision(provider: str, model: str, env: dict[str, str] | None = None) -> None:
    """Raise clear error if model cannot take images (OpenRouter routing 404)."""
    prov = (provider or "").strip().lower()
    mid = (model or "").strip()
    if not mid:
        return
    if prov in OPENCODE_PROVIDERS:
        from sprite_repair.providers.opencode.registry import get_registry_entry

        entry = get_registry_entry(mid)
        if entry:
            mods = [str(m).lower() for m in (entry.get("modalities") or [])]
            if all(m == "text" for m in mods):
                raise RuntimeError(
                    f"모델 '{mid}' 은(는) 텍스트 전용입니다 (registry modalities=text). "
                    f"비전 후보: deepseek-v4-flash-vision-exp, kimi-k3, qwen3.8-flash, mimo-v2.5, glm-5.3-flash"
                )
            if any(m == "unchecked" for m in mods):
                pass
        # UNKNOWN modality models are allowed; capability is confirmed by
        # the runtime vision probe, never by name heuristics.
        verified = load_verification_state()
        v = verified.get(mid) or {}
        if v.get("vision_ok"):
            return
        if (v.get("text_ok") or v.get("json_ok") or v.get("status") in ("TEXT_VERIFIED", "JSON_VERIFIED")) and not v.get("vision_ok"):
            raise RuntimeError(
                f"모델 '{mid}' 은(는) 텍스트 검증만 통과했습니다. "
                f"Vision probe로 이미지 입력을 확인하거나 비전 후보를 선택하세요."
            )
        return
    # Known text-only free traps
    text_only_hints = (
        "nemotron-3-ultra",
        "nemotron-3.5-lightning",
        "nemotron-3-super",
        "deepseek-v4-flash-0731",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "laguna",
        "ling-3.0-flash-fin",
    )
    # Allow if explicitly vision
    if any(k in mid.lower() for k in ("vision", "vl", "gpt-4o", "gemini", "kimi", "claude", "gemma", "nex", "openrouter/free", "nano-omni", "qwen", "phi-3-vision", "phi-4", "llama-3.2")):
        if "deepseek-v4-flash-0731" in mid or (mid.endswith("deepseek-v4-flash") and "vision" not in mid) or ("deepseek-v4-pro" in mid and "vision" not in mid):
            pass  # fall through check
        else:
            return
    if prov == "openrouter":
        # quick reject known text-only
        low = mid.lower()
        if any(h in low for h in text_only_hints) and "vision" not in low:
            raise RuntimeError(
                f"모델 '{mid}' 은(는) 이미지를 지원하지 않습니다 (텍스트 전용). "
                f"AI 정렬에는 비전 모델(예: {OPENROUTER_VISION_DEFAULT}, meta/llama-3.2-11b-vision-instruct, google/gemini-2.5-flash-lite 등)을 선택하세요."
            )
        # If we have catalog meta from a fresh list — optional soft check via name
        if not _is_visionish(mid, None) and (":free" in mid or any(h in low for h in ("nemotron", "deepseek-v4-flash", "deepseek-v4-pro"))):
            if "vision" not in low and "gemini" not in low and "kimi" not in low and "gpt-4o" not in low and "claude" not in low and "gemma" not in low and "mimo" not in low and "qwen" not in low and "nex" not in low:
                raise RuntimeError(
                    f"모델 '{mid}' 은(는) 이미지 입력을 지원하지 않을 수 있습니다. "
                    f"비전 모델(예: {OPENROUTER_VISION_DEFAULT}, meta/llama-3.2-11b-vision-instruct, google/gemini-2.5-flash-lite 등)을 고르세요."
                )



_CONTACT_ALIGN_PROMPT = """You are aligning sprite animation frames on a NUMBERED contact sheet.
CRITICAL: Reply with ONLY one JSON object. No markdown. No reasoning. No prose.
First character must be '{' and last must be '}'. Example schema:
{"frames":[{"frame":0,"anchor_x":64,"anchor_y":120,"scale":1.0},{"frame":1,"anchor_x":66,"anchor_y":118,"scale":1.0}]}
CRITICAL: Reply with ONLY a single JSON object. No prose, no markdown fences, no analysis.
Each cell is labeled with its frame index (top-left yellow number).
For EACH frame, find the character foot / ground-contact center (root).
Return ONLY JSON:
{"frames":[{"frame":0,"anchor_x":12,"anchor_y":40,"scale":1.0}, ...]}

Rules:
- anchor_x/anchor_y are in ORIGINAL frame pixel coordinates (see sizes below), NOT contact-sheet pixels.
- Foot anchor = center of ground contact (bottom of feet / root).
- scale = relative to median character height across frames (1.0 = same size; use ~0.9-1.1 only if clearly different).
- Include every frame index from 0..N-1.
- Empty / no-character cells: put anchor at bottom-center of that original frame.
"""


def _build_align_contact_sheet(
    images: list[Image.Image],
    *,
    cell: int = 192,
) -> tuple[Image.Image, int, int]:
    """Labeled contact sheet for single-image vision APIs (NVIDIA limit = 1 image)."""
    from PIL import ImageDraw

    n = len(images)
    if n <= 0:
        return Image.new("RGBA", (cell, cell), (0, 0, 0, 0)), 1, 1
    cols = max(1, int(n ** 0.5 + 0.999))
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (20, 24, 32, 255))
    draw = ImageDraw.Draw(sheet)
    for i, img in enumerate(images):
        r, c = divmod(i, cols)
        thumb = img.convert("RGBA").copy()
        # nearest upscale tiny art then fit
        vision = _nn_upscale_for_ai(thumb)
        vision.thumbnail((cell - 10, cell - 10), Image.Resampling.NEAREST)
        x0 = c * cell + (cell - vision.width) // 2
        y0 = r * cell + (cell - vision.height) // 2
        sheet.paste(vision, (x0, y0), vision)
        draw.text((c * cell + 4, r * cell + 2), str(i), fill=(255, 220, 80, 255))
    return sheet, cols, cell


def _request_ai_alignments_contact(
    raw_frame_images: list[Image.Image],
    *,
    provider: str,
    model: str,
    env: dict[str, str],
    max_side: int = 1024,
) -> list[dict[str, Any]]:
    """Single contact-sheet image — required for NVIDIA (max 1 image / prompt)."""
    base_url, api_key, _ = _provider_endpoint(provider, env)
    sheet, cols, cell = _build_align_contact_sheet(raw_frame_images, cell=192)
    # downscale sheet if huge
    b64, _, _, _ = _downscale_png_b64(sheet, max_side=max_side)
    size_lines = []
    for i, img in enumerate(raw_frame_images):
        ow, oh = img.size
        size_lines.append(f"frame {i}: original_size={ow}x{oh}, sheet_cell={cell}px, grid_cols={cols}")
    content = [
        {
            "type": "text",
            "text": _CONTACT_ALIGN_PROMPT
            + f"\nTotal frames: {len(raw_frame_images)}\nCell size: {cell}px, cols: {cols}\n"
            + "Frame sizes:\n"
            + "\n".join(size_lines),
        },
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ]
    text = _chat_completions(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=[{"role": "user", "content": content}],
        provider=provider,
        timeout=90.0,
    )
    try:
        parsed = _parse_align_response(
            text,
            n_frames=len(raw_frame_images),
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            model=model,
        )
    except RuntimeError as e:
        msg = str(e)
        # Reasoning models (deepseek-flash etc.) occasionally return
        # reasoning-only content; a single re-request is cheap and reliable.
        if "did not return JSON" in msg or "empty content" in msg or "missing frames" in msg:
            import time as _time

            _time.sleep(1.0)
            text = _chat_completions(
                base_url=base_url,
                api_key=api_key,
                model=model,
                messages=[{"role": "user", "content": content}],
                provider=provider,
                timeout=90.0,
            )
            parsed = _parse_align_response(
                text,
                n_frames=len(raw_frame_images),
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                model=model,
            )
        else:
            raise
    frames = parsed.get("frames")
    if not isinstance(frames, list) or not frames:
        raise RuntimeError(_user_facing_ai_error("schema"))
    by_idx: dict[int, dict[str, Any]] = {}
    for item in frames:
        if not isinstance(item, dict):
            continue
        fi = int(item.get("frame", len(by_idx)))
        ax = int(round(float(item.get("anchor_x", item.get("x", 0)))))
        ay = int(round(float(item.get("anchor_y", item.get("y", 0)))))
        sc = float(item.get("scale", 1.0))
        by_idx[fi] = {"frame": fi, "anchor_x": ax, "anchor_y": ay, "scale": sc}
    out: list[dict[str, Any]] = []
    for i, img in enumerate(raw_frame_images):
        if i in by_idx:
            row = by_idx[i]
        else:
            row = {
                "frame": i,
                "anchor_x": img.width // 2,
                "anchor_y": max(0, img.height - 1),
                "scale": 1.0,
            }
        ax = max(0, min(img.width - 1, int(row["anchor_x"])))
        ay = max(0, min(img.height - 1, int(row["anchor_y"])))
        sc = float(row.get("scale", 1.0))
        if sc <= 0:
            sc = 1.0
        out.append({"frame": i, "anchor_x": ax, "anchor_y": ay, "scale": sc})
    return out


def request_ai_alignments(
    raw_frame_images: list[Image.Image],
    *,
    provider: str | None = None,
    model: str | None = None,
    env: dict[str, str] | None = None,
    max_side: int = 384,
) -> list[dict[str, Any]]:
    """Call vision model; return list of {frame, anchor_x, anchor_y, scale} in raw coords.

    Provider-level fallback chain (Section 27): if the primary model fails
    with rate-limit/auth/network errors and AI_FALLBACK_<PROVIDER> is set,
    retry with each fallback model in order.
    """
    env = env if env is not None else load_dotenv()
    cfg = ai_config_public(env)
    prov = (provider or cfg["default_provider"]).strip().lower()
    base_url, api_key, default_model = _provider_endpoint(prov, env)
    use_model = (model or default_model or "").strip()
    if not use_model:
        raise RuntimeError("AI model id is empty — pick a vision model in the UI")

    fallback_key = None
    if prov in OPENCODE_PROVIDERS:
        fallback_key = OPENCODE_PROVIDERS[prov]["fallback_env"]
    fallbacks = [m.strip() for m in (env.get(fallback_key, "") if fallback_key else "").split(",") if m.strip()] if fallback_key else []
    chain = [use_model] + [m for m in fallbacks if m != use_model]

    last_err: Exception | None = None
    for mid in chain:
        try:
            return _request_ai_alignments_once(
                raw_frame_images,
                provider=prov,
                model=mid,
                env=env,
                base_url=base_url,
                api_key=api_key,
                default_model=default_model,
                max_side=max_side,
            )
        except RuntimeError as e:
            msg = str(e)
            retryable = (
                "HTTP 429" in msg
                or "HTTP 401" in msg
                or "HTTP 403" in msg
                or "timeout" in msg.lower()
                or "timed out" in msg.lower()
                or "network" in msg.lower()
            )
            if not retryable or mid == chain[-1]:
                raise
            last_err = e
    if last_err is not None:
        raise last_err
    raise RuntimeError("AI align failed with empty fallback chain")


def _request_ai_alignments_once(
    raw_frame_images: list[Image.Image],
    *,
    provider: str,
    model: str,
    env: dict[str, str],
    base_url: str,
    api_key: str,
    default_model: str,
    max_side: int = 384,
) -> list[dict[str, Any]]:
    """Single-model alignment attempt (no provider-level fallback)."""
    prov = provider.strip().lower()
    use_model = (model or default_model or "").strip()
    if not use_model:
        raise RuntimeError("AI model id is empty — pick a vision model in the UI")
    assert_model_supports_vision(prov, use_model, env)

    # NVIDIA and Ollama work best with contact-sheet batches (JSON compliance & local VRAM speed).
    # OpenCode models also use the labeled single-sheet path (most reliable across dialects).
    if prov in ("nvidia", "ollama", "opencode_go", "opencode") or len(raw_frame_images) > 24:
        batch = 4
        contact_side = 1024 if prov in ("opencode_go", "opencode") else max_side
        if len(raw_frame_images) <= batch:
            return _request_ai_alignments_contact(
                raw_frame_images, provider=prov, model=use_model, env=env, max_side=contact_side
            )
        out: list[dict[str, Any]] = []
        for start in range(0, len(raw_frame_images), batch):
            chunk = raw_frame_images[start : start + batch]
            part = _request_ai_alignments_contact(
                chunk, provider=prov, model=use_model, env=env, max_side=contact_side
            )
            for row in part:
                row = dict(row)
                row["frame"] = int(row.get("frame", 0)) + start
                out.append(row)
        # ensure full coverage
        by = {int(r["frame"]): r for r in out}
        fixed = []
        for i, img in enumerate(raw_frame_images):
            if i in by:
                fixed.append(by[i])
            else:
                fixed.append(
                    {
                        "frame": i,
                        "anchor_x": img.width // 2,
                        "anchor_y": max(0, img.height - 1),
                        "scale": 1.0,
                    }
                )
        return fixed

    content: list[dict[str, Any]] = [{"type": "text", "text": _PROMPT}]
    size_lines: list[str] = []
    for i, img in enumerate(raw_frame_images):
        ow, oh = img.size
        vision_img = _nn_upscale_for_ai(img)
        nn_sx = vision_img.size[0] / float(ow) if ow else 1.0
        b64, _, _, prev_factor = _downscale_png_b64(vision_img, max_side=max_side)
        size_lines.append(
            f"frame {i}: original_size={ow}x{oh}, nn_upscale={nn_sx:.3f}, "
            f"preview_max_side={max_side}, preview_vs_nn={prev_factor:.6f}. "
            f"Return anchor_x/anchor_y in ORIGINAL {ow}x{oh} pixels (divide vision coords by nn_upscale)."
        )
        content.append({"type": "text", "text": f"Frame {i} (original {ow}x{oh}, nn_upscale={nn_sx:.3f}):"})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )
    content.insert(1, {"type": "text", "text": "Frame sizes:\n" + "\n".join(size_lines)})

    messages = [
        {
            "role": "user",
            "content": content,
        }
    ]
    try:
        text = _chat_completions(
            base_url=base_url,
            api_key=api_key,
            model=use_model,
            messages=messages,
            provider=prov,
            timeout=180.0,
        )
        parsed = _parse_align_response(
        text,
        n_frames=len(raw_frame_images),
        provider=prov,
        base_url=base_url,
        api_key=api_key,
        model=use_model,
    )
        frames = parsed.get("frames")
        if not isinstance(frames, list) or not frames:
            raise RuntimeError(_user_facing_ai_error("schema"))
    except RuntimeError as e:
        msg = str(e)
        if (
            "At most 1 image" in msg
            or "at most 1 image" in msg.lower()
            or "only 1 image" in msg.lower()
            or "single image" in msg.lower()
        ):
            return _request_ai_alignments_contact(
                raw_frame_images, provider=prov, model=use_model, env=env
            )
        # Non-JSON / empty content: one retry via contact sheet (often more reliable)
        if "did not return JSON" in msg or "empty content" in msg or "missing frames" in msg:
            try:
                return _request_ai_alignments_contact(
                    raw_frame_images, provider=prov, model=use_model, env=env
                )
            except Exception:
                raise e from None
        raise
    # Normalize / fill gaps
    by_idx: dict[int, dict[str, Any]] = {}
    for item in frames:
        if not isinstance(item, dict):
            continue
        fi = int(item.get("frame", len(by_idx)))
        ax = int(round(float(item.get("anchor_x", item.get("x", 0)))))
        ay = int(round(float(item.get("anchor_y", item.get("y", 0)))))
        sc = float(item.get("scale", 1.0))
        by_idx[fi] = {"frame": fi, "anchor_x": ax, "anchor_y": ay, "scale": sc}
    out: list[dict[str, Any]] = []
    for i, img in enumerate(raw_frame_images):
        if i in by_idx:
            row = by_idx[i]
        else:
            # fallback: bottom-center
            row = {
                "frame": i,
                "anchor_x": img.width // 2,
                "anchor_y": max(0, img.height - 1),
                "scale": 1.0,
            }
        ax = max(0, min(img.width - 1, int(row["anchor_x"])))
        ay = max(0, min(img.height - 1, int(row["anchor_y"])))
        sc = float(row.get("scale", 1.0))
        if sc <= 0:
            sc = 1.0
        out.append({"frame": i, "anchor_x": ax, "anchor_y": ay, "scale": sc})
    return out


def apply_ai_align(
    raw_frame_images: list[Image.Image],
    raw_frames: list[dict[str, Any]],
    alignments: list[dict[str, Any]],
    *,
    duration_ms: int | None = None,
    pad: int = 0,
    apply_scale: bool = True,
) -> dict[str, Any]:
    """Update anchors (and optional scale) then recompose."""
    new_images: list[Image.Image] = []
    overrides: list[dict[str, int]] = []
    metas = [dict(m) for m in raw_frames]

    for i, img in enumerate(raw_frame_images):
        al = alignments[i] if i < len(alignments) else None
        if al is None:
            new_images.append(img)
            overrides.append({"x": int(metas[i]["anchor"]["x"]), "y": int(metas[i]["anchor"]["y"])})
            continue
        anchor = {"x": int(al["anchor_x"]), "y": int(al["anchor_y"])}
        scale = float(al.get("scale", 1.0))
        if apply_scale and abs(scale - 1.0) >= 1e-3:
            img2, anchor2 = _resize_about_anchor(img, anchor, scale)
            new_images.append(img2)
            overrides.append(anchor2)
            metas[i]["size"] = {"w": img2.width, "h": img2.height}
            metas[i]["ai_scale"] = scale
        else:
            new_images.append(img)
            overrides.append(anchor)
            metas[i]["ai_scale"] = 1.0
        metas[i]["anchor"] = dict(overrides[-1])

    updated = recompose_with_anchors(
        new_images,
        metas,
        anchor_overrides=overrides,
        duration_ms=duration_ms,
        pad=pad,
    )
    updated["ai_alignments"] = alignments
    return updated