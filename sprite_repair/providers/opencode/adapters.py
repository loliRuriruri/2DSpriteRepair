"""Three API dialect adapters for OpenCode Go / Console models.

Normalized input: OpenAI-style ``messages`` list where each message is
``{"role": "user", "content": <str> | [part, ...]}`` and each part is either
``{"type": "text", "text": ...}`` or
``{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}``.

All adapters return plain text. Provider-specific errors are re-raised as
RuntimeError with the HTTP code (no secrets).
"""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from typing import Any

from sprite_repair.providers.opencode.registry import get_registry_entry

_PROTOCOL_ORDER = ("chat", "responses", "messages")

# OpenCode endpoints reject non-browser signatures (Cloudflare 1010) and the
# Go route requires a per-session routing id.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_session_ids: dict[str, str] = {}


def _session_id_for(base_url: str) -> str:
    import uuid

    if base_url not in _session_ids:
        _session_ids[base_url] = str(uuid.uuid4())
    return _session_ids[base_url]


def _base_headers(base_url: str, api_key: str) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _BROWSER_UA,
        "x-opencode-session": _session_id_for(base_url),
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def adapter_protocol_for(model_id: str) -> str:
    entry = get_registry_entry(model_id)
    protocol = (entry or {}).get("protocol") or "chat"
    return protocol if protocol in _PROTOCOL_ORDER else "chat"


def _split_data_url(url: str) -> tuple[str, str]:
    """Return (media_type, base64_data) from a data: URL."""
    m = re.match(r"^data:([^;,]+)?(;base64)?,(.*)$", url, re.S)
    if not m:
        return "image/png", url
    media = m.group(1) or "image/png"
    return media, m.group(3)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                t = p.get("text") or p.get("content")
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(parts)
    return str(content or "")


def _openai_messages_flat(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert normalized messages into a single-user chat.completions form."""
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content")
        if isinstance(content, list):
            parts: list[dict[str, Any]] = []
            for p in content:
                if p.get("type") == "image_url":
                    url = (p.get("image_url") or {}).get("url") or ""
                    if url.startswith("data:"):
                        media, b64 = _split_data_url(url)
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{media};base64,{b64}"},
                        })
                else:
                    text = p.get("text") if isinstance(p, dict) else str(p)
                    parts.append({"type": "text", "text": text})
            out.append({"role": role, "content": parts})
        else:
            out.append({"role": role, "content": content})
    return out


def _http_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"opencode HTTP {e.code}: {err_body}") from None
    except (TimeoutError, OSError) as e:
        raise RuntimeError(f"opencode network timeout/error: {e}") from None


def _chat_request(base_url: str, api_key: str, model: str, messages: list[dict[str, Any]], timeout: float, json_mode: bool = True) -> str:
    url = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": _openai_messages_flat(messages),
        "temperature": 0.1,
        "max_tokens": 8192,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = _base_headers(base_url, api_key)
    data = _http_json(url, payload, headers, timeout)
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    content = msg.get("content")
    text = _content_text(content)
    if not text.strip():
        for k in ("reasoning_content", "reasoning"):
            if isinstance(msg.get(k), str) and msg[k].strip():
                return msg[k]
        raise RuntimeError(f"opencode {model}: empty chat content")
    return text


def _responses_request(base_url: str, api_key: str, model: str, messages: list[dict[str, Any]], timeout: float, json_mode: bool = True) -> str:
    url = f"{base_url}/responses"
    inp: list[dict[str, Any]] = []
    for m in messages:
        content = m.get("content")
        parts: list[dict[str, Any]] = []
        if isinstance(content, str):
            parts.append({"type": "input_text", "text": content})
        else:
            for p in content or []:
                if p.get("type") == "image_url":
                    img_url = (p.get("image_url") or {}).get("url") or ""
                    media, b64 = _split_data_url(img_url)
                    parts.append({"type": "input_image", "image_url": f"data:{media};base64,{b64}"})
                else:
                    text = p.get("text") if isinstance(p, dict) else str(p)
                    parts.append({"type": "input_text", "text": text})
        inp.append({"role": m.get("role", "user"), "content": parts})
    payload: dict[str, Any] = {
        "model": model,
        "input": inp,
        "temperature": 0.1,
        "max_output_tokens": 8192,
    }
    if json_mode:
        payload["text"] = {"format": {"type": "json_object"}}
    headers = _base_headers(base_url, api_key)
    data = _http_json(url, payload, headers, timeout)
    parts_text: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for c in item.get("content") or []:
                if isinstance(c, dict) and isinstance(c.get("text"), str):
                    parts_text.append(c["text"])
        elif isinstance(item.get("text"), str):
            parts_text.append(item["text"])
    text = "\n".join(parts_text)
    if not text.strip():
        raise RuntimeError(f"opencode {model}: empty responses output")
    return text


def _messages_request(base_url: str, api_key: str, model: str, messages: list[dict[str, Any]], timeout: float, json_mode: bool = True) -> str:
    url = f"{base_url}/messages"
    out_msgs: list[dict[str, Any]] = []
    for m in messages:
        content = m.get("content")
        parts: list[dict[str, Any]] = []
        if isinstance(content, str):
            parts.append({"type": "text", "text": content})
        else:
            for p in content or []:
                if p.get("type") == "image_url":
                    img_url = (p.get("image_url") or {}).get("url") or ""
                    media, b64 = _split_data_url(img_url)
                    parts.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": media, "data": b64},
                    })
                else:
                    text = p.get("text") if isinstance(p, dict) else str(p)
                    parts.append({"type": "text", "text": text})
        out_msgs.append({"role": m.get("role", "user"), "content": parts})
    payload: dict[str, Any] = {
        "model": model,
        "messages": out_msgs,
        "max_tokens": 8192,
        "temperature": 0.1,
    }
    headers = _base_headers(base_url, api_key)
    headers["anthropic-version"] = "2023-06-01"
    if api_key:
        headers["x-api-key"] = api_key
    data = _http_json(url, payload, headers, timeout)
    parts_text = []
    for c in data.get("content") or []:
        if isinstance(c, dict) and isinstance(c.get("text"), str):
            parts_text.append(c["text"])
    text = "\n".join(parts_text)
    if not text.strip():
        raise RuntimeError(f"opencode {model}: empty messages content")
    return text


def opencode_complete(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    timeout: float = 120.0,
    json_mode: bool = True,
    force_protocol: str | None = None,
) -> str:
    """Dispatch to the right dialect for the model, with protocol fallback.

    Fallback order: registry protocol -> chat -> responses -> messages.
    AUTH failures (401/403) and rate limits (429) are NOT retried on other
    protocols; they surface to the caller for provider-level fallback.
    """
    protocols: list[str] = []
    if force_protocol:
        protocols.append(force_protocol)
    protocols.append(adapter_protocol_for(model))
    for p in _PROTOCOL_ORDER:
        if p not in protocols:
            protocols.append(p)

    last_err: RuntimeError | None = None
    for p in protocols:
        try:
            if p == "chat":
                return _chat_request(base_url, api_key, model, messages, timeout, json_mode)
            if p == "responses":
                return _responses_request(base_url, api_key, model, messages, timeout, json_mode)
            return _messages_request(base_url, api_key, model, messages, timeout, json_mode)
        except RuntimeError as e:
            msg = str(e)
            # Do not hop protocols on auth/rate-limit failures
            if "HTTP 401" in msg or "HTTP 403" in msg or "HTTP 429" in msg:
                raise
            last_err = e
            # 400 may mean "response_format unsupported"; retry once without JSON mode
            if "HTTP 400" in msg and json_mode:
                try:
                    if p == "chat":
                        return _chat_request(base_url, api_key, model, messages, timeout, json_mode=False)
                    if p == "responses":
                        return _responses_request(base_url, api_key, model, messages, timeout, json_mode=False)
                    return _messages_request(base_url, api_key, model, messages, timeout, json_mode=False)
                except RuntimeError as e2:
                    last_err = e2
    raise RuntimeError(f"opencode all protocols failed for {model}: {last_err}")

