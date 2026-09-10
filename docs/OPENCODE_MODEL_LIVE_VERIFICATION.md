# OPENCODE_MODEL_LIVE_VERIFICATION

> Live probe results against OpenCode Go / Console, 2026-09-10.
> Persisted machine-readable state: `workspace/opencode_verified.json`
> (monotonic flags: text_ok / json_ok / vision_ok; status derived).

## Go (https://opencode.ai/zen/go/v1)

| Model | Text | JSON | Vision | Latency (probe) | Status |
|---|---|---|---|---|---|
| deepseek-flash (V4.1 Flash) | ✔ | — | — | 1.57s | TEXT_VERIFIED |
| deepseek-v4-pro | ✔ | — | — | 2.03s | TEXT_VERIFIED |
| deepseek-v4-flash | ✔ | — | — | 1.81s | TEXT_VERIFIED |
| deepseek-v4-flash-vision-exp | — | ✔ | ✔ | 2.3s | VISION_VERIFIED |
| kimi-k3 | — | — | ✔ | 33.07s | VISION_VERIFIED |
| qwen3.8-flash | — | — | ✔ | 10.04s | VISION_VERIFIED |
| mimo-v2.5 | — | — | ✔ | 4.19s | VISION_VERIFIED |
| glm-5.3-flash | — | — | ✔ | 1.87s | VISION_VERIFIED |
| muse-spark-1.3-contributor | ✔ | — | — | 18.36s | TEXT_VERIFIED |
| muse-spark-1.2-contributor | ✔ | — | — | 1.9s | TEXT_VERIFIED |

All 5 vision candidates passed the 4-frame shifted-anchor probe
(`{"problem_frames":[4]}`, 1-based label) → image input + meaningful JSON +
schema validation OK. Not name-heuristic: live probe only.

## Console (https://opencode.ai/zen/v1)

| Model | Text | Status |
|---|---|---|
| big-pickle (free) | ✔ | TEXT_VERIFIED |
| deepseek-v4-flash-free | ✘ | TEMPORARILY_UNAVAILABLE (upstream 500 "Model is unavailable") |
| nemotron-3-ultra-free | ✘ | TEMPORARILY_UNAVAILABLE (upstream 500) |

Free models are upstream-flaky at probe time; free status is not assumed
permanent and `/models` always wins.

## End-to-end validation

- AI foot-anchor align on real GPT 4x4 sheet (`benchmark/corpus/gpt_sheet_001.png`):
  OpenCode Go + deepseek-v4-flash-vision-exp → 16 frames, 24.2s, consistent
  baseline anchors (jump frame correctly off-baseline).
- Provider fallback chain (`AI_FALLBACK_OPENCODE_GO`) wired and retryable on
  429/401/403/timeout/network.

## Test suite

```
.venv/Scripts/python.exe benchmark/test_opencode.py --live
Ran 21 tests in 82.762s — OK (skipped=1: console free, key gate)
```

Without keys the live tests skip → `IMPLEMENTED_NOT_LIVE_VERIFIED`.

## Muse Spark contributor conditions

`muse-spark-1.3-contributor` / `1.2-contributor` (Go) and
`muse-spark-*-contributor-free` (Console):
- UI badges CONTRIBUTOR / TRAINING_ALLOWED / REGION-LIMITED
- Explicit user confirmation required before applying
- Not used by default for sensitive/personal images
- Vision capability NOT assumed; text-only in registry until a vision probe passes
