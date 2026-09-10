# OPENCODE_MODEL_CATALOG_2026_09_10

> Snapshot of `GET /models` results on 2026-09-10. NOT a hardcoded source of
> truth — runtime discovery always wins. Popular ranking is a point-in-time
> snapshot only (`POPULAR_AS_OF_2026_09_10`).
> Merged UI catalog: Go 50 entries (36 discovered + registry), Console 90.

## OpenCode Go — 36 models

```text
minimax-m3, minimax-m2.7, minimax-m2.5,
kimi-k3, kimi-k2.7-code, kimi-k2.6, kimi-k2.5,
longcat-2.0,
glm-5, glm-5.1, glm-5.2, glm-5.3, glm-5.3-flash,
deepseek-flash (display: DeepSeek V4.1 Flash), deepseek-v4-pro,
deepseek-v4-flash, deepseek-v4-flash-vision-exp,
qwen3.5-plus, qwen3.6-plus, qwen3.7-plus, qwen3.7-max, qwen3.8-max, qwen3.8-flash,
mimo-v2-pro, mimo-v2-omni, mimo-v2.5-pro, mimo-v2.5,
hy3, hy3-preview, hy4-preview,
gpt-5.6-luna,
grok-4.5, grok-4.6,
muse-spark-1.3-contributor, muse-spark-1.2-contributor,
omen-alpha
```

Note: `deepseek-flash` is the Go model id for **DeepSeek V4.1 Flash**
(per OpenCode Go docs; not `deepseek-v4.1-flash`).

## OpenCode Console / Zen — 70 models (excerpt by family)

```text
claude-fable-5, claude-fable-5-1, claude-opus-5, claude-opus-4-8, claude-opus-4-7,
claude-opus-4-6, claude-opus-4-5, claude-sonnet-5, claude-sonnet-4-6, claude-sonnet-4-5,
claude-sonnet-4, claude-haiku-4-5,
gemini-3-flash, gemini-3.1-pro, gemini-3.5-flash, gemini-3.5-flash-lite,
gemini-3.6-flash, gemini-3.7-flash, gemini-3.8-flash,
gpt-5, gpt-5.1, gpt-5.1-codex, gpt-5.1-codex-max, gpt-5.1-codex-mini, gpt-5.2,
gpt-5.2-codex, gpt-5.3-codex, gpt-5.3-codex-spark, gpt-5.4, gpt-5.4-mini,
gpt-5.4-nano, gpt-5.4-pro, gpt-5.5, gpt-5.5-pro, gpt-5.6-luna, gpt-5.6-sol,
gpt-5.6-terra, gpt-5-nano, gpt-5-codex, gpt-6-astra,
grok-build-0.1, grok-4.5, grok-4.6,
muse-spark-1.2, muse-spark-1.3,
deepseek-v4-pro, deepseek-v4-flash, deepseek-v4-flash-vision-exp,
glm-5, glm-5.1, glm-5.2, glm-5.3, glm-5.3-flash,
minimax-m2.5, minimax-m2.7, minimax-m3,
kimi-k2.5, kimi-k2.6, kimi-k2.7-code, kimi-k3,
qwen3.5-plus, qwen3.6-plus,
big-pickle, deepseek-v4-flash-free, muse-spark-1.3-contributor-free,
muse-spark-1.2-contributor-free, mimo-v2.5-free, ling-3.0-flash-fin-free,
nemotron-3-ultra-free, nemotron-3.5-lightning-free
```

## Console Free group (discovered)

```text
big-pickle                    TEXT_VERIFIED (live)
deepseek-v4-flash-free        TEMPORARILY_UNAVAILABLE (upstream 500, 2026-09-10)
muse-spark-1.3-contributor-free
muse-spark-1.2-contributor-free
mimo-v2.5-free
ling-3.0-flash-fin-free
nemotron-3-ultra-free         TEMPORARILY_UNAVAILABLE (upstream 500, 2026-09-10)
nemotron-3.5-lightning-free
```

Directive §21 ids NOT on Console `/models` (marked UNAVAILABLE at runtime):
`laguna-s-2.1-free`, `ling-3.0-tiny-free`, `longcat-2.0-free`, `north-mini-code-free`.
Free status is never assumed permanent.

## Popular snapshot (OpenCode usage stats, 2026-09-10)

```text
muse-spark-1.3-contributor, deepseek-v4-flash, mimo-v2.5,
muse-spark-1.2-contributor, glm-5.3-flash, nemotron-3-ultra-free,
omen-alpha, deepseek-v4-flash-vision-exp, deepseek-v4-pro,
qwen3.8-flash, gpt-5.6-luna
```

## Bootstrap registry (protocol / modality)

Official Go endpoint table (docs/go, 2026-09-10):

| Model | Protocol | Registry modalities |
|---|---|---|
| deepseek-flash | chat | text |
| deepseek-v4-pro | chat | text |
| deepseek-v4-flash | chat | text |
| deepseek-v4-flash-vision-exp | chat | text+image |
| kimi-k3 | chat | text+image+video |
| kimi-k2.7-code | chat | text |
| kimi-k2.6 | chat | text |
| qwen3.8-flash | messages | text+image+video |
| qwen3.8-max | messages | text+image |
| qwen3.7-max / plus, qwen3.6-plus | messages | UNKNOWN |
| mimo-v2.5 / v2.5-pro | chat | text+image(+audio+video) |
| glm-5.3-flash / 5.3 / 5.2 / 5.1 | chat | (flash: text+image+video+pdf) |
| minimax-m3 / m2.7 / m2.5 | messages | text |
| muse-spark-1.3-contributor | responses | text |
| muse-spark-1.2-contributor | responses | text |
| gpt-5.6-luna | responses | text+image |
| grok-4.6 | responses | UNKNOWN |

Modalities marked UNKNOWN are resolved only by live probes — never by name.

## Go pricing snapshot ($/1M input, 2026-09-10, indicative)

GLM-5.3-Flash $0.15 · GLM-5.3/5.2/5.1 $1.40 · Kimi K3 $3.00 ·
Kimi K2.7/K2.6 $0.95 · LongCat-2.0 $0.30 · MiMo-V2.5 $0.14 · MiMo-V2.5-Pro $0.435 ·
MiniMax $0.30 · Muse Spark Contributor $0.10 · Qwen3.8 Max $2.00 ·
Qwen3.8 Flash $0.15 · DeepSeek V4.1 Flash $0.15(비수기) · V4 Pro $0.66(비수기) ·
V4 Flash $0.15(비수기) · V4 Flash Vision Exp $0.15(비수기) · Hy4 $0.834 ·
Hy3 $0.14 · Grok 4.6 $2.00 · GPT 5.6 Luna $0.20.
OpenRouter prices are fetched live from `/models` pricing.
