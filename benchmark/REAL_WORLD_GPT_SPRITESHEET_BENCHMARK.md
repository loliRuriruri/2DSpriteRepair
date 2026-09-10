# REAL_WORLD_GPT_SPRITESHEET_BENCHMARK

> Generated: 2026-09-10T23:41
> Human review: PENDING

## Corpus
- Sheets: 27 (required >= 20) → COMPLETE
- Frames: 432 (required >= 320)
- All real GPT-generated 4x4 sheets (ChatGPT), no synthetic fixtures used

## KPI
| KPI | Value |
|---|---|
| Sheet-level Auto Success Rate | 0.0% |
| Frame-level Auto Success Rate | 100.0% |
| Manual Intervention Rate | 0.0% |
| Frame Detection Success Rate | 100.0% |
| Export Success Rate | 100.0% |
| Anchor Correction Rate | 0.0% |
| Mask/Ownership Correction Rate | 0.0% |
| Crop Correction Rate | 0.0% |
| VFX Clipping Rate | 0.0% |
| Neighbor Contamination Rate | 0.0% |
| Scale QA Failure Rate | 0.0% |
| Palette QA Failure Rate | 0.0% |
| Reprocess Required Rate | 0.0% |

## Fix frames per sheet
- Mean: 0.0 · Median: 0.0 · P90: 0.0

## Time saved
- Manual total: 0.0 min · SpriteRepair total: 0.0 min
- Time Saved %: mean 0.0 · median 0.0 · p90 0.0
- SpriteRepair auto pipeline: mean 12.94s process + 0.86s export per sheet

## Anchor accuracy (human GT subset)
- GT anchor clicks not provided (ANCHOR_FIX 시 GT x/y 미입력)

## Failure Top 5 (by human review frequency)
- No failures recorded (all frames PASS)

## Automatic hints (not ground truth)
- scale_drift_auto_flags: 77
- palette_drift_auto_flags: 71
- neighbor_auto_flags: 16
- clip_auto_flags: 0
- chroma_applied: 27

## Corpus diversity
- prompt classes: (미기입)
- difficulty tags: (미기입)
- MISSING required types: short sword, great sword, spear, bow, projectile, hand-to-hand, fire, ice, lightning/beam, large explosion, long hair, cape/coat/skirt, ground shadow, VFX below feet, jump, dash, spin, large silhouette change, transparent BG, imperfect/solid BG

## Per-sheet
See `results.csv` / `results.json`.
