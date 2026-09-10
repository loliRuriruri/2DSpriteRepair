"""Dynamic model discovery for OpenCode Go / Console.

``GET {base}/models`` is the source of truth for availability. The bootstrap
registry only supplies protocol / modality / badge metadata and fallback
entries when discovery fails.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from sprite_repair.providers.opencode.registry import (
    OPENCODE_FREE_GROUP,
    OPENCODE_POPULAR_AS_OF_2026_09_10,
    OPENCODE_REGISTRY,
    OPENCODE_VISION_CANDIDATES,
    family_desc,
    get_registry_entry,
    model_badges,
)

_DISCOVER_TIMEOUT = 30


def fetch_opencode_models(base_url: str, api_key: str = "") -> tuple[list[str], str | None]:
    """Return (model_ids, error). Never raises."""
    base = (base_url or "").rstrip("/")
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        req = urllib.request.Request(f"{base}/models", headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=_DISCOVER_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        ids: list[str] = []
        for row in data.get("data") or []:
            if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"]:
                ids.append(row["id"])
        ids = sorted(set(ids))
        return ids, None
    except urllib.error.HTTPError as e:
        return [], f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return [], str(e)


def list_opencode_models_merged(
    provider: str,
    env: dict[str, str],
    *,
    base_url: str,
    verified: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merged catalog for UI + callers.

    Discovery list is authoritative for availability; registry fills
    protocol/modality/badges. Registry models missing from discovery are
    marked UNAVAILABLE.
    """
    verified = verified or {}
    discovered, error = fetch_opencode_models(base_url, env.get(
        "OPENCODE_GO_API_KEY" if provider == "opencode_go" else "OPENCODE_API_KEY", ""
    ))
    discovered_set = set(discovered)

    all_ids: list[str] = []
    for mid in OPENCODE_REGISTRY:
        if mid not in all_ids:
            all_ids.append(mid)
    for mid in discovered:
        if mid not in all_ids:
            all_ids.append(mid)

    def status_of(mid: str) -> str:
        v = verified.get(mid) or {}
        if v.get("status"):
            return str(v["status"])
        return "DISCOVERED" if mid in discovered_set else "UNAVAILABLE"

    models: list[str] = []
    models_meta: list[dict[str, Any]] = []
    for mid in all_ids:
        entry = get_registry_entry(mid) or {}
        models.append(mid)
        available = mid in discovered_set
        status = status_of(mid)
        desc = entry.get("desc_ko") or family_desc(mid)
        models_meta.append({
            "id": mid,
            "name": (entry.get("display") or mid),
            "available": available,
            "status": status,
            "protocol": entry.get("protocol") or "chat",
            "modalities": entry.get("modalities") or ["UNKNOWN"],
            "vision": any(m != "UNKNOWN" and "image" in str(m) for m in (entry.get("modalities") or [])),
            "vision_verified": status == "VISION_VERIFIED",
            "free": bool(entry.get("free")) or mid in OPENCODE_FREE_GROUP,
            "contributor": bool(entry.get("contributor")),
            "training_allowed": bool(entry.get("training_allowed")),
            "region_limited": bool(entry.get("region_limited")),
            "role": entry.get("role"),
            "recommended": bool(entry.get("recommended")),
            "price": entry.get("price"),
            "desc": desc,
            "badges": model_badges(mid, entry, verified),
            "note": entry.get("note"),
        })

    vision_models = [
        mid for mid in models
        if any(
            mm["id"] == mid and (mm["vision_verified"] or mm["vision"])
            for mm in models_meta
        )
    ]
    free_models = [m["id"] for m in models_meta if m["free"]]
    popular_models = [m for m in OPENCODE_POPULAR_AS_OF_2026_09_10 if m in models]

    default = None
    if vision_models:
        default = next((m for m in OPENCODE_VISION_CANDIDATES if m in vision_models), vision_models[0])
    else:
        default = next((m for m in OPENCODE_VISION_CANDIDATES if m in models), (models[0] if models else None))

    return {
        "ok": error is None,
        "provider": provider,
        "error": error,
        "models": models,
        "models_meta": models_meta,
        "vision_models": vision_models,
        "vision_default": default,
        "default": default,
        "free_models": free_models,
        "popular_models": popular_models,
        "popular_as_of": "2026-09-10",
        "vision_candidates": [m for m in OPENCODE_VISION_CANDIDATES if m in models],
        "discovered_count": len(discovered),
        "registry_count": len(OPENCODE_REGISTRY),
        "sort": "registry-then-discovery",
        "verified": verified,
    }
