# IMPLEMENTATION_PLAN

Principles: Grid != Frame Boundary; Anchor != BBox Center; Character != VFX bbox.
AI judges; Pillow/CV edits. Offline CV+manual if AI fails.

## Phases
1 Core — character/effect/combined bbox; neighbor overflow regression
2 Manual — crop LRTB; reference lock; Undo/Redo
3 Overflow — ownership components + mask brush
4 AI — default moonshotai/kimi-k3; /api/ai-models; dropdown; NN x8; cache; on/off
5 Polish — APNG, WebP, *.spriteproject, jitter/scale QA

## Next files
pipeline.py, ai_align.py, server.py, app/index.html, app/app.js
.env: AI_PROVIDER=nvidia, AI_MODEL_NVIDIA=moonshotai/kimi-k3

## Flow
sheet → process_sheet → optional ai_align → compose → preview/export

## Test
:5190 + 4x4 attack sheet (foot lock, VFX keep, no neighbor steal); AI-off export OK

## gorest
Absorb policy only; no full clone.

## Done (Phase 2 partial)
- Undo/Redo anchors (Ctrl+Z/Y)
- Crop pad/tight/safe via /api/crop-frame
- Reference frame + onionRef


## Done (Phase 3)
- /api/mask-stroke Include|Exclude|Erase|Restore
- mask_bases + sheet snapshot on process
- UI Paint mode brush on canvas



## Done Phase 4-5
- AI contact-sheet QA + .ai-cache
- Anim jitter/scale QA
- APNG + WebP export
- .spriteproject save
