# REAL_WORLD_GPT_SPRITESHEET_BENCHMARK

> Generated: 2026-09-20T00:28
> Human review: 2026-09-20T12:00:00Z

## Corpus
- Sheets: 27 (required >= 20) → COMPLETE
- Frames: 432 (required >= 320)
- All real GPT-generated 4x4 sheets (ChatGPT), no synthetic fixtures used

## KPI
| KPI | Value |
|---|---|
| Sheet-level Auto Success Rate | 0.0% |
| Frame-level Auto Success Rate | 62.5% |
| Manual Intervention Rate | 37.5% |
| Frame Detection Success Rate | 100.0% |
| Export Success Rate | 100.0% |
| Anchor Correction Rate | 10.2% |
| Mask/Ownership Correction Rate | 0.0% |
| Crop Correction Rate | 0.0% |
| VFX Clipping Rate | 0.0% |
| Neighbor Contamination Rate | 1.6% |
| Scale QA Failure Rate | 20.8% |
| Palette QA Failure Rate | 4.9% |
| Reprocess Required Rate | 0.0% |

## Fix frames per sheet
- Mean: 6.0 · Median: 4.0 · P90: 14.0

## Time saved
- Manual total: 864.0 min · SpriteRepair total: 3.0 min
- Time Saved %: mean 99.67 · median 99.8 · p90 99.8
- SpriteRepair auto pipeline: mean 6.03s process + 0.62s export per sheet

## Anchor accuracy (human GT subset)
- N=44 · mean 4.33px · median 4.74px · p90 6.4px
- <=1px: 2.3% · <=2px: 11.4% · >3px: 70.5%

## Failure Top 5 (by human review frequency)
| Rank | Type | Count | Rate |
|---|---|---|---|
| 1 | SCALE_FIX | 90 | 20.8% |
| 2 | ANCHOR_FIX | 44 | 10.2% |
| 3 | PALETTE_FIX | 21 | 4.9% |
| 4 | NEIGHBOR_CONTAMINATION | 7 | 1.6% |

## Automatic hints (not ground truth)
- scale_drift_auto_flags: 116
- palette_drift_auto_flags: 62
- neighbor_auto_flags: 127
- clip_auto_flags: 0
- chroma_applied: 27

## Corpus diversity
- prompt classes: bow_ranged_shot, dash_attack, dodge_roll, explosion_blast, fire_magic, great_sword_slash, hand_to_hand_combo, heavy_strike, ice_projectile, lightning_beam, magic_cast, projectile_throw, spear_thrust, spin_attack, sword_attack
- difficulty tags: bow, cape, coat, dash, fire, great_sword, ground_shadow, hand_to_hand, ice, imperfect_solid_bg, jump, large_explosion, large_silhouette_change, large_vfx, lightning_beam, long_hair, projectile, short_sword, skirt, spear, spin, transparent_bg, vfx_below_feet
- All required diversity types covered

## Per-sheet
See `results.csv` / `results.json`.
