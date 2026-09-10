"""OpenCode Go / Console multi-model provider for SpriteRepair.

- OpenCode Go      : https://opencode.ai/zen/go/v1     (OPENCODE_GO_API_KEY)
- OpenCode Console : https://opencode.ai/zen/v1        (OPENCODE_API_KEY)

Three API dialects are supported per model: OpenAI chat/completions,
OpenAI responses, Anthropic-style messages. The model registry selects the
adapter; runtime probing promotes capabilities (VISION_VERIFIED etc).
"""

from sprite_repair.providers.opencode.registry import (
    OPENCODE_REGISTRY,
    OPENCODE_FREE_GROUP,
    OPENCODE_POPULAR_AS_OF_2026_09_10,
    OPENCODE_VISION_CANDIDATES,
    get_registry_entry,
    model_badges,
)
from sprite_repair.providers.opencode.discovery import (
    fetch_opencode_models,
    list_opencode_models_merged,
)
from sprite_repair.providers.opencode.adapters import (
    opencode_complete,
    adapter_protocol_for,
)
from sprite_repair.providers.opencode.provider import (
    OPENCODE_PROVIDERS,
    opencode_endpoint,
    probe_opencode_vision,
    probe_opencode_text,
    probe_opencode_json,
    load_verification_state,
    save_verification_state,
)

__all__ = [
    "OPENCODE_REGISTRY",
    "OPENCODE_FREE_GROUP",
    "OPENCODE_POPULAR_AS_OF_2026_09_10",
    "OPENCODE_VISION_CANDIDATES",
    "get_registry_entry",
    "model_badges",
    "fetch_opencode_models",
    "list_opencode_models_merged",
    "opencode_complete",
    "adapter_protocol_for",
    "OPENCODE_PROVIDERS",
    "opencode_endpoint",
    "probe_opencode_vision",
    "probe_opencode_text",
    "probe_opencode_json",
    "load_verification_state",
    "save_verification_state",
]
