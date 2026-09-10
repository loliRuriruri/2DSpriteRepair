# OPENCODE_PROVIDER_IMPLEMENTATION

> OpenCode Go / Console(Zen) provider expansion — SpriteRepair
> Date: 2026-09-10

## Providers

| Provider | value | Base URL | Key env | Model env | Fallback env |
|---|---|---|---|---|---|
| OpenCode Go | `opencode_go` | `https://opencode.ai/zen/go/v1` | `OPENCODE_GO_API_KEY` | `AI_MODEL_OPENCODE_GO` | `AI_FALLBACK_OPENCODE_GO` |
| OpenCode Console | `opencode` | `https://opencode.ai/zen/v1` | `OPENCODE_API_KEY` | `AI_MODEL_OPENCODE` | `AI_FALLBACK_OPENCODE` |

Existing providers (NVIDIA Build / OpenRouter / Ollama / Disabled) coexist.
`AI_PROVIDER` accepts: `ollama | opencode_go | opencode | openrouter | nvidia | disabled`.

## Code layout

```
sprite_repair/providers/
  __init__.py
  opencode/
    __init__.py
    registry.py      — bootstrap registry (protocol/modality/badges), never source of truth
    discovery.py     — GET {base}/models; merged catalog (availability from discovery)
    adapters.py      — chat/completions, responses, messages dialects + protocol fallback
    provider.py      — endpoint resolution, probes, verification state persistence
```

`sprite_repair/ai_align.py` extensions:
- `_provider_endpoint()` resolves opencode providers
- `_chat_completions()` dispatches opencode requests to `opencode_complete()`
- `list_ai_models()` → `list_opencode_models_merged()` (registry + discovery + verified status)
- `request_ai_alignments()` gains a provider-level fallback chain (§27) driven by
  `AI_FALLBACK_<PROVIDER>` (comma-separated model ids); retries on 429/401/403/timeout/network only
- opencode aligns use the labeled contact-sheet path with `max_side=1024` and
  one re-request retry on reasoning-only responses (deepseek reasoning models)

`server.py` endpoints:
- `GET /api/ai-config` — now includes `opencode_go` / `opencode` providers + key hints
- `GET /api/ai-models?provider=opencode_go|opencode` — merged dynamic catalog
- `POST /api/ai-set-model` — persists `AI_MODEL_OPENCODE_GO` / `AI_MODEL_OPENCODE`
- `POST /api/ai-keys` — persists `OPENCODE_GO_API_KEY` / `OPENCODE_API_KEY` (never echoed)
- `POST /api/ai-probe {provider, model, kind: vision|text|json}` — live capability probe
- `POST /api/ai-verified` — persisted verification state (no secrets)

## Required request headers (discovered live)

OpenCode endpoints reject non-browser signatures (Cloudflare 1010) and the Go
route requires a session routing id:

```
User-Agent: Mozilla/5.0 ... Chrome/126.0 Safari/537.36
x-opencode-session: <uuid4 per process per base-url>
Authorization: Bearer <key>        (optional for /models, required for inference)
```

`max_tokens` defaults to 8192 (deepseek reasoning models may emit thinking text
into `content`; 4096 caused truncation to reasoning-only responses).

## 3 API dialects

| Dialect | Endpoint | Used by |
|---|---|---|
| OpenAI chat | `{base}/chat/completions` | most models (deepseek, qwen, glm, minimax, grok, hy, omen, longcat, kimi-k3...) |
| OpenAI responses | `{base}/responses` | muse-spark-* (registry protocol) |
| Anthropic messages | `{base}/messages` | kimi-k2.6 (registry protocol) |

`opencode_complete()` tries registry protocol → chat → responses → messages.
Protocol hops are skipped on 401/403/429 (surfaced to provider fallback chain).
A 400 mentioning response_format retries once without JSON mode.

## Dynamic discovery

- `GET https://opencode.ai/zen/go/v1/models` → 36 ids (2026-09-10)
- `GET https://opencode.ai/zen/v1/models` → 70 ids (2026-09-10)
- Registry supplies display name / protocol / modalities / badges; discovery is
  the source of truth for availability. Registry ids absent from discovery are
  marked `UNAVAILABLE`.

## Capability probes (§24)

Vision probe: 4-frame labeled contact sheet, frame label 4 shifted 8px off the
ground baseline; prompt asks `{"problem_frames":[...]}` (1-based labels).
`VISION_VERIFIED` only when schema validates against `[4]`. Text probe expects
`OK`; JSON probe expects `{"ok": true}`.

Verification state persists in `workspace/opencode_verified.json` with monotonic
capability flags (`text_ok` / `json_ok` / `vision_ok`) so a weaker later probe
never demotes a stronger earlier one.

Statuses: `DISCOVERED | TEXT_VERIFIED | JSON_VERIFIED | VISION_VERIFIED |
IMPLEMENTED_NOT_LIVE_VERIFIED | REGION_UNAVAILABLE | AUTH_FAILED |
TEMPORARILY_UNAVAILABLE | DEPRECATED`

## Model Picker UI

- Provider select: Ollama / OpenCode Go / OpenCode Console / OpenRouter / NVIDIA Build / Disabled
- Group filter (opencode only): Recommended for Sprite QA / Vision Verified / Free / Popular / Coding / All
- Badges: VISION, TEXT, FREE, CONTRIBUTOR, TRAINING_ALLOWED, REGION-LIMITED, POPULAR, LIVE-VERIFIED, UNVERIFIED, status
- Buttons: Test Connection / Test JSON / Test Vision / Refresh Models
- Muse Spark CONTRIBUTOR warning + explicit confirm before applying (training_allowed + region_limited)

### Quick-pick modal (✨ 빠른 선택)

Screenshot-style picker: provider cards (5, with key-status dots) → preset
cards (recommended → vision-verified → popular → free, max 24) each showing
display name + id, Korean description, price chip, badges → custom-id input →
apply. Prices: Go from official docs snapshot (`price` in registry, 참고용);
OpenRouter live from `/models` pricing; Ollama shows 로컬 무료.

## Secrets

Only in `.env`: `OPENCODE_GO_API_KEY`, `OPENCODE_API_KEY`. Never logged,
never in responses (key hints are masked `abcd…wxyz`). `.gitignore` covers `.env`.

## Tests

`benchmark/test_opencode.py` (stdlib unittest):

```
.venv/Scripts/python.exe benchmark/test_opencode.py         # offline suite
.venv/Scripts/python.exe benchmark/test_opencode.py --live  # live calls (keys required)
```

Covers: go/console discovery, merged catalog, free group, unavailable marking,
registry ids (deepseek-flash alias!), muse flags, protocol selection, endpoint
resolution, invalid-key surfacing, and live: deepseek text x3, deepseek vision,
muse text x2, vision candidates, console free group.
