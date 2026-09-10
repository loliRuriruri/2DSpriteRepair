"""OpenCode model bootstrap registry.

The registry is only a bootstrap / fallback catalog. Runtime discovery via
``GET {base}/models`` is the source of truth for availability. Modalities
marked UNKNOWN must be resolved by a live vision probe, never by name
heuristics alone.
"""

from __future__ import annotations

from typing import Any

# Protocol values: "chat" (OpenAI chat/completions), "responses" (OpenAI
# responses), "messages" (Anthropic-style messages), "unknown".
# Modalities: subset of {"text","image","audio","video","pdf"} or {"UNKNOWN"}.

# --- Section 17: DeepSeek models (OpenCode Go IDs) -------------------------
# Prices: official Go $/1M input tokens (off-peak where applicable). Snapshot
# 2026-09-10; indicative only.
_DEEPSEEK = {
    "deepseek-flash": {                       # Display: DeepSeek V4.1 Flash
        "display": "DeepSeek V4.1 Flash",
        "protocol": "chat",
        "modalities": ["text"],
        "role": "cheap_text",
        "free": False,
        "price": "$0.15/1M",
        "desc_ko": "저가 텍스트 추론/리포트용 (비수기 기준)",
        "note": "Go model id is 'deepseek-flash' (not deepseek-v4.1-flash)",
    },
    "deepseek-v4-pro": {
        "display": "DeepSeek V4 Pro",
        "protocol": "chat",
        "modalities": ["text"],
        "role": "quality_text",
        "free": False,
        "price": "$0.66/1M",
        "desc_ko": "고품질 텍스트/추론 (비수기 기준, 피크 $1.32)",
    },
    "deepseek-v4-flash": {
        "display": "DeepSeek V4 Flash",
        "protocol": "chat",
        "modalities": ["text"],
        "role": "batch_text",
        "free": False,
        "price": "$0.15/1M",
        "desc_ko": "초저가 배치 텍스트 (비수기 기준)",
    },
    "deepseek-v4-flash-vision-exp": {
        "display": "DeepSeek V4 Flash Vision Exp",
        "protocol": "chat",
        "modalities": ["text", "image"],
        "role": "cheap_vision",
        "free": False,
        "price": "$0.15/1M",
        "desc_ko": "저가 비전 QA 우선 후보 · SpriteRepair 기본 추천",
        "recommended": True,
    },
}

# --- Section 18: Muse Spark contributor models ------------------------------
_MUSE = {
    "muse-spark-1.3-contributor": {
        "display": "Muse Spark 1.3 Contributor",
        "protocol": "responses",
        "modalities": ["text"],
        "role": "cheap_text",
        "free": False,
        "contributor": True,
        "training_allowed": True,
        "region_limited": True,
        "price": "$0.10/1M",
        "desc_ko": "초저가 텍스트 (학습사용 동의·지역제한 조건)",
        "note": "Prompts/completions may be used for future Meta model training",
    },
    "muse-spark-1.2-contributor": {
        "display": "Muse Spark 1.2 Contributor",
        "protocol": "responses",
        "modalities": ["text"],
        "role": "cheap_text",
        "free": False,
        "contributor": True,
        "training_allowed": True,
        "region_limited": True,
        "price": "$0.10/1M",
        "desc_ko": "초저가 텍스트 (학습사용 동의·지역제한 조건)",
    },
}

# --- Section 19: Vision candidates (public info only; probe to confirm) -----
_VISION = {
    "deepseek-v4-flash-vision-exp": _DEEPSEEK["deepseek-v4-flash-vision-exp"],
    "kimi-k3": {
        "display": "Kimi K3",
        "protocol": "chat",
        "modalities": ["text", "image", "video"],
        "role": "quality_judge",
        "free": False,
        "price": "$3.00/1M",
        "desc_ko": "고품질 판정 · 긴 컨텍스트",
        "recommended": True,
    },
    "qwen3.8-flash": {
        "display": "Qwen3.8 Flash",
        "protocol": "messages",
        "modalities": ["text", "image", "video"],
        "role": "fast_vision",
        "free": False,
        "price": "$0.15/1M",
        "desc_ko": "빠른 비전 대안",
        "recommended": True,
    },
    "mimo-v2.5": {
        "display": "MiMo-V2.5",
        "protocol": "chat",
        "modalities": ["text", "image", "audio", "video"],
        "role": "fallback_vision",
        "free": False,
        "price": "$0.14/1M",
        "desc_ko": "폴백 · 초저가 비전",
        "recommended": True,
    },
    "glm-5.3-flash": {
        "display": "GLM-5.3-Flash",
        "protocol": "chat",
        "modalities": ["text", "image", "video", "pdf"],
        "role": "secondary_vision",
        "free": False,
        "price": "$0.15/1M",
        "desc_ko": "보조 비전",
        "recommended": True,
    },
}

# --- Section 20: full Go bootstrap registry ---------------------------------
# Protocols follow the official Go endpoint table (docs/go, 2026-09-10).
_GO_EXTRA = {
    "grok-4.6": {"display": "Grok 4.6", "protocol": "responses", "modalities": ["UNKNOWN"], "price": "$2.00/1M", "desc_ko": "인기 · xAI 대형 모델"},
    "glm-5.3": {"display": "GLM-5.3", "protocol": "chat", "modalities": ["UNKNOWN"], "price": "$1.40/1M"},
    "glm-5.2": {"display": "GLM-5.2", "protocol": "chat", "modalities": ["UNKNOWN"], "price": "$1.40/1M"},
    "glm-5.1": {"display": "GLM-5.1", "protocol": "chat", "modalities": ["UNKNOWN"], "price": "$1.40/1M"},
    "gpt-5.6-luna": {"display": "GPT 5.6 Luna", "protocol": "responses", "modalities": ["text", "image"], "price": "$0.20/1M", "desc_ko": "인기 · OpenAI 대형"},
    "kimi-k2.7-code": {"display": "Kimi K2.7 Code", "protocol": "chat", "modalities": ["text"], "price": "$0.95/1M", "desc_ko": "코딩 특화"},
    "kimi-k2.6": {"display": "Kimi K2.6", "protocol": "chat", "modalities": ["text"], "price": "$0.95/1M"},
    "longcat-2.0": {"display": "LongCat-2.0", "protocol": "chat", "modalities": ["text"], "price": "$0.30/1M"},
    "mimo-v2.5-pro": {"display": "MiMo-V2.5-Pro", "protocol": "chat", "modalities": ["text", "image"], "price": "$0.44/1M"},
    "minimax-m3": {"display": "MiniMax M3", "protocol": "messages", "modalities": ["text"], "price": "$0.30/1M"},
    "minimax-m2.7": {"display": "MiniMax M2.7", "protocol": "messages", "modalities": ["text"], "price": "$0.30/1M"},
    "minimax-m2.5": {"display": "MiniMax M2.5", "protocol": "messages", "modalities": ["text"], "price": "$0.30/1M"},
    "qwen3.8-max": {"display": "Qwen3.8 Max", "protocol": "messages", "modalities": ["text", "image"], "price": "$2.00/1M"},
    "qwen3.7-max": {"display": "Qwen3.7 Max", "protocol": "messages", "modalities": ["UNKNOWN"]},
    "qwen3.7-plus": {"display": "Qwen3.7 Plus", "protocol": "messages", "modalities": ["UNKNOWN"]},
    "qwen3.6-plus": {"display": "Qwen3.6 Plus", "protocol": "messages", "modalities": ["UNKNOWN"]},
    "hy4-preview": {"display": "Hy4 preview", "protocol": "chat", "modalities": ["UNKNOWN"], "price": "$0.83/1M"},
    "hy3": {"display": "Hy3", "protocol": "chat", "modalities": ["UNKNOWN"], "price": "$0.14/1M"},
    "hy3-preview": {"display": "Hy3 preview", "protocol": "chat", "modalities": ["UNKNOWN"], "desc_ko": "Hy3 프리뷰"},
    "omen-alpha": {"display": "Omen Alpha", "protocol": "chat", "modalities": ["UNKNOWN"], "desc_ko": "인기 신규모델"},
    "glm-5": {"display": "GLM-5", "protocol": "chat", "modalities": ["UNKNOWN"], "desc_ko": "지푸 GLM 대형"},
    "grok-4.5": {"display": "Grok 4.5", "protocol": "chat", "modalities": ["UNKNOWN"], "desc_ko": "xAI 이전 세대"},
    "kimi-k2.5": {"display": "Kimi K2.5", "protocol": "chat", "modalities": ["UNKNOWN"], "desc_ko": "문샷 이전 세대"},
    "mimo-v2-omni": {"display": "MiMo-V2-Omni", "protocol": "chat", "modalities": ["UNKNOWN"], "desc_ko": "샤오미 옴니"},
    "mimo-v2-pro": {"display": "MiMo-V2-Pro", "protocol": "chat", "modalities": ["UNKNOWN"], "desc_ko": "샤오미 프로"},
    "qwen3.5-plus": {"display": "Qwen3.5 Plus", "protocol": "chat", "modalities": ["UNKNOWN"], "desc_ko": "알리바바 이전 세대"},
}

# Family fallback descriptions for discovered ids without registry entries
# (mostly Console claude/gemini/gpt families).
FAMILY_DESC = [
    ("claude-", "Anthropic Claude (Console 경유)"),
    ("gemini-", "Google Gemini (Console 경유)"),
    ("gpt-", "OpenAI GPT (Console 경유)"),
    ("grok-", "xAI Grok (Console 경유)"),
    ("kimi-", "Moonshot Kimi (경유)"),
    ("qwen", "Alibaba Qwen (경유)"),
    ("glm-", "지푸 GLM (경유)"),
    ("minimax-", "MiniMax (경유)"),
    ("mimo-", "샤오미 MiMo (경유)"),
    ("deepseek-", "DeepSeek (경유)"),
    ("hy", "Hyperbolic (경유)"),
    ("longcat-", "LongCat (경유)"),
    ("omen-", "Omen (경유)"),
    ("ling-", "Ling (경유)"),
    ("nemotron-", "NVIDIA Nemotron (경유)"),
    ("laguna-", "Laguna (경유)"),
    ("north-", "North (경유)"),
]


def family_desc(model_id: str) -> str | None:
    low = (model_id or "").lower()
    for prefix, desc in FAMILY_DESC:
        if low.startswith(prefix):
            return desc
    return None

# --- Section 21: Console free group -----------------------------------------
_OPENCODE_FREE_GROUP: dict[str, dict[str, Any]] = {
    "deepseek-v4-flash-free": {
        "display": "DeepSeek V4 Flash Free",
        "protocol": "chat",
        "modalities": ["text"],
        "free": True,
    },
    "mimo-v2.5-free": {
        "display": "MiMo-V2.5 Free",
        "protocol": "chat",
        "modalities": ["UNKNOWN"],
        "free": True,
    },
    "laguna-s-2.1-free": {
        "display": "Laguna S 2.1 Free",
        "protocol": "chat",
        "modalities": ["text"],
        "free": True,
    },
    "ling-3.0-tiny-free": {
        "display": "Ling-3.0-tiny Free",
        "protocol": "chat",
        "modalities": ["text"],
        "free": True,
    },
    "longcat-2.0-free": {
        "display": "LongCat-2.0 Free",
        "protocol": "chat",
        "modalities": ["text"],
        "free": True,
    },
    "north-mini-code-free": {
        "display": "North Mini Code Free",
        "protocol": "chat",
        "modalities": ["text"],
        "free": True,
    },
    "nemotron-3-ultra-free": {
        "display": "Nemotron 3 Ultra Free",
        "protocol": "chat",
        "modalities": ["text"],
        "free": True,
    },
    "big-pickle": {
        "display": "Big Pickle",
        "protocol": "chat",
        "modalities": ["UNKNOWN"],
        "free": True,
        "desc_ko": "Big Pickle (무료)",
    },
    # Console discovery additions (runtime /models is source of truth)
    "muse-spark-1.3-contributor-free": {
        "display": "Muse Spark 1.3 Contributor Free",
        "protocol": "responses",
        "modalities": ["text"],
        "free": True,
        "contributor": True,
        "training_allowed": True,
        "region_limited": True,
        "desc_ko": "초저가 텍스트 무료 (학습사용 동의·지역제한)",
    },
    "muse-spark-1.2-contributor-free": {
        "display": "Muse Spark 1.2 Contributor Free",
        "protocol": "responses",
        "modalities": ["text"],
        "free": True,
        "contributor": True,
        "training_allowed": True,
        "region_limited": True,
        "desc_ko": "초저가 텍스트 무료 (학습사용 동의·지역제한)",
    },
    "nemotron-3.5-lightning-free": {
        "display": "Nemotron 3.5 Lightning Free",
        "protocol": "chat",
        "modalities": ["text"],
        "free": True,
    },
    "ling-3.0-flash-fin-free": {
        "display": "Ling 3.0 Flash Fin Free",
        "protocol": "chat",
        "modalities": ["text"],
        "free": True,
    },
}

# Console non-contributor Muse Spark variants
_MUSE_CONSOLE = {
    "muse-spark-1.3": {
        "display": "Muse Spark 1.3",
        "protocol": "responses",
        "modalities": ["text"],
        "role": "cheap_text",
        "free": False,
        "desc_ko": "Muse Spark (Console 경유)",
    },
    "muse-spark-1.2": {
        "display": "Muse Spark 1.2",
        "protocol": "responses",
        "modalities": ["text"],
        "role": "cheap_text",
        "free": False,
        "desc_ko": "Muse Spark (Console 경유)",
    },
}

OPENCODE_REGISTRY: dict[str, dict[str, Any]] = {}
OPENCODE_REGISTRY.update(_GO_EXTRA)
OPENCODE_REGISTRY.update(_DEEPSEEK)  # DeepSeek spec wins over generic extras
OPENCODE_REGISTRY.update(_MUSE)
OPENCODE_REGISTRY.update(_MUSE_CONSOLE)
OPENCODE_REGISTRY.update(_VISION)  # vision candidate spec wins
OPENCODE_REGISTRY.update(_OPENCODE_FREE_GROUP)

# Korean descriptions for popular non-OpenCode models (picker UI).
MODEL_DESC_KO = {
    "google/gemma-4-31b-it:free": "무료 비전 · SpriteRepair 기본 추천 (OpenRouter)",
    "google/gemma-4-26b-a4b-it:free": "무료 비전",
    "google/gemini-2.5-flash-lite": "저가 고속 비전",
    "google/gemini-2.5-flash": "고품질 비전",
    "qwen/qwen-2.5-vl-72b-instruct:free": "무료 비전 (대형)",
    "meta/llama-3.2-11b-vision-instruct:free": "무료 비전 (경량)",
    "meta/llama-3.2-11b-vision-instruct": "경량 비전",
    "openrouter/free": "무료 라우팅 (모델 순환)",
    "openai/gpt-4o-mini": "저가 비전",
    "huihui_ai/qwen3-vl-abliterated:8b-instruct": "내 PC 로컬 · 무료 · 약 3초",
}

OPENCODE_VISION_CANDIDATES = [    "deepseek-v4-flash-vision-exp",
    "kimi-k3",
    "qwen3.8-flash",
    "mimo-v2.5",
    "glm-5.3-flash",
]

# Section 22: snapshot only — never a permanent ranking.
OPENCODE_POPULAR_AS_OF_2026_09_10 = [
    "muse-spark-1.3-contributor",
    "deepseek-v4-flash",
    "mimo-v2.5",
    "muse-spark-1.2-contributor",
    "glm-5.3-flash",
    "nemotron-3-ultra-free",
    "omen-alpha",
    "deepseek-v4-flash-vision-exp",
    "deepseek-v4-pro",
    "qwen3.8-flash",
    "gpt-5.6-luna",
]

OPENCODE_FREE_GROUP = list(_OPENCODE_FREE_GROUP.keys())


def get_registry_entry(model_id: str) -> dict[str, Any] | None:
    return OPENCODE_REGISTRY.get((model_id or "").strip())


def _is_vision_registered(entry: dict[str, Any] | None) -> bool:
    if not entry:
        return False
    mods = entry.get("modalities") or []
    return any(m != "UNKNOWN" and "image" in str(m) for m in mods)


def model_badges(model_id: str, entry: dict[str, Any] | None, verified: dict[str, Any] | None = None) -> list[str]:
    """Return UI badge list: VISION/TEXT/FREE/GO/CONTRIBUTOR/REGION-LIMITED/..."""
    badges: list[str] = []
    entry = entry or get_registry_entry(model_id)
    if entry:
        mods = [str(m).lower() for m in (entry.get("modalities") or [])]
        if any("image" in m for m in mods):
            badges.append("VISION")
        elif all(m == "text" for m in mods):
            badges.append("TEXT")
        else:
            badges.append("UNKNOWN-MODALITY")
        if entry.get("free"):
            badges.append("FREE")
        if entry.get("contributor"):
            badges.append("CONTRIBUTOR")
        if entry.get("training_allowed"):
            badges.append("TRAINING_ALLOWED")
        if entry.get("region_limited"):
            badges.append("REGION-LIMITED")
        if entry.get("role"):
            badges.append(entry["role"].upper())
    if model_id in OPENCODE_POPULAR_AS_OF_2026_09_10:
        badges.append("POPULAR")
    v = (verified or {}).get(model_id) or {}
    status = v.get("status")
    if status == "VISION_VERIFIED":
        badges.append("LIVE-VERIFIED")
    elif status:
        badges.append(str(status))
    else:
        badges.append("UNVERIFIED")
    return badges
