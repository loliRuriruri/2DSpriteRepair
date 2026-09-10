# SpriteRepair — Current Feature Inventory V2

**Audit Date**: 2026-09-10  
**Baseline Verification Suite**: scratch/run_semantic_suite.js, scratch/run_full_e2e.js, scratch/verify_export_semantics.py  
**Classification Rules**:
- VERIFIED: Proven operational through semantic state, pixel data, and invariant assertion tests.
- IMPLEMENTED_NOT_VERIFIED: Code exists in repository, but lacks end-to-end semantic assertion proof.
- IMPLEMENTED_NOT_LIVE_VERIFIED: Network/Cloud dependent feature operational with offline fallback, awaiting live cloud production key.
- PARTIAL: Incomplete implementation lacking key requirements.
- MISSING: Planned or referenced feature with no current implementation.
- BROKEN: Code fails or violates invariants during execution.

---

## Comprehensive Feature Census

| Feature | File/Module | Backend | Frontend | E2E | Semantic Test | Status | Notes |
|---|---|:---:|:---:|:---:|:---:|:---:|---|
| **Auto Grid Seed & Frame Extraction** | sprite_repair/pipeline.py<br>server.py | YES | YES | YES | YES | VERIFIED | 16/16 frames extracted from ttack_4x4_real.png. Filename regex + density valley fallback. |
| **Soft Flood & VFX Overflow Recovery** | sprite_repair/pipeline.py | YES | YES | YES | YES | VERIFIED | Connected component flood recovers VFX beyond seed boundaries up to expand ratio. |
| **4-Pass Chroma Key & Despill** | sprite_repair/chromakey.py | YES | YES | YES | YES | VERIFIED | Hard cut, frontier growth, unmixing, and trapped-spill despill removes solid background. |
| **Foot / Root Anchor Detection** | sprite_repair/pipeline.py | YES | YES | YES | YES | VERIFIED | Lowest-opaque pixel heuristic with anchor clamping and numerical nudging. |
| **Global Safe Canvas Normalization** | sprite_repair/pipeline.py | YES | YES | YES | YES | VERIFIED | Maximum anchor-relative extent bounding ensures zero frame-to-frame clipping. |
| **Anchor Jitter QA** | sprite_repair/qa.py | YES | YES | YES | YES | VERIFIED | Sequence delta analysis flags anchor jitter > 2px. |
| **Scale Consistency QA** | sprite_repair/qa.py | YES | YES | YES | YES | VERIFIED | Height, width, and aspect ratio drift calculated against sequence median. |
| **Palette Uniformity QA** | sprite_repair/qa.py | YES | YES | YES | YES | VERIFIED | 64-bin normalized RGB histogram comparison detects color drift across frames. |
| **Difference / Ghost View** | pp/app.js<br>pp/app.css | N/A | YES | YES | YES | VERIFIED | Difference blend mode overlays previous frame against current frame. |
| **Onion Skinning** | pp/app.js | N/A | YES | YES | YES | VERIFIED | Configurable preceding (-1) and succeeding (+1) tinted ghost overlays on canvas. |
| **Aseprite Timeline Matrix** | pp/app.js<br>pp/index.html | N/A | YES | YES | YES | VERIFIED | Synchronized 2D grid matrix with horizontally scrollable frame headers and layer headers. |
| **Layer CRUD & Reorder** | pp/app.js<br>server.py | YES | YES | YES | YES | VERIFIED | Layer add, rename, delete, move up/down, visibility toggle, opacity, and blend mode. |
| **Layer Groups** | sprite_repair/models.py<br>pp/app.js | PARTIAL | PARTIAL | NO | NO | PARTIAL | Basic layer type field exists; hierarchical folder groups and nested collapse pending. |
| **Reference Layer** | sprite_repair/models.py<br>pp/app.js | PARTIAL | PARTIAL | NO | NO | PARTIAL | Can mark layer as custom; dedicated non-exporting canvas overlay pending. |
| **Frame CRUD & Reorder** | pp/app.js | N/A | YES | YES | YES | VERIFIED | Blank frame insertion, duplication, deletion, shift left/right, and sequence reversal. |
| **Cel CRUD & Multi-Select** | pp/app.js | N/A | YES | YES | YES | VERIFIED | Cel copy, paste, clear, duplicate, and Shift/Ctrl range and discrete multi-selection. |
| **Linked Cel Real Shared Edit** | pp/app.js<br>server.py | YES | YES | YES | YES | VERIFIED | Shared linked_cel_id. Mutation on Cel A propagates to B; unlinking fully decouples B. |
| **Nearest-Neighbor Transforms** | pp/app.js | N/A | YES | YES | YES | VERIFIED | FlipH, FlipV, Rotate90 with pixel buffer preservation and mathematical group invariants. |
| **Custom Pivot Editing** | pp/app.js<br>sprite_repair/models.py | YES | YES | YES | YES | VERIFIED | Interactive draggable dashed circle manipulator independent of root anchor. |
| **Selection Tools (Marquee)** | pp/app.js | N/A | YES | YES | YES | VERIFIED | Drag rectangle selection with marching-ants visual feedback. |
| **Advanced Selection (Lasso/Wand)** | pp/app.js | N/A | NO | NO | NO | MISSING | Lasso, Polygon, Magic Wand, and Color Select with Add/Subtract boolean ops pending. |
| **Character / VFX Ownership Masks** | sprite_repair/pipeline.py<br>server.py | YES | YES | YES | YES | VERIFIED | Brush strokes and bounding assignment persistent in frame metadata. |
| **Standalone Preview Modal** | pp/app.js<br>pp/index.html | N/A | YES | YES | YES | VERIFIED | Isolated viewport with independent FPS, zoom (100%-400%), loop, and backgrounds. |
| **Command Pattern Undo / Redo** | pp/app.js | N/A | YES | YES | YES | VERIFIED | Full snapshot state history capturing anchors, pivots, layers, tags, cels, and frames. |
| **PNG Sequence Export** | sprite_repair/export.py | YES | YES | YES | YES | VERIFIED | RGBA format with transparency preserved across all 16 frames. |
| **SpriteSheet Grid Export** | sprite_repair/export.py | YES | YES | YES | YES | VERIFIED | Clean unified atlas sheet output. |
| **Packed Atlas (Bin Packing)** | sprite_repair/export.py | PARTIAL | NO | NO | NO | PARTIAL | Standard grid packing present; MaxRects tight packing pending. |
| **Padding & Extrude (1px/2px)** | sprite_repair/export.py | PARTIAL | NO | NO | NO | PARTIAL | Cell padding supported; pixel edge extrusion for texture bleed mitigation pending. |
| **Animated GIF Export** | sprite_repair/export.py | YES | YES | YES | YES | VERIFIED | 16 frames, exact 80ms duration verified via Pillow ImageSequence. |
| **Animated PNG (APNG) Export** | sprite_repair/export.py | YES | YES | YES | YES | VERIFIED | 16 frames validated via APNG encoder. |
| **Animated WebP Export** | sprite_repair/export.py | YES | YES | YES | YES | VERIFIED | 16 frames lossy/lossless WebP validated. |
| **Engine Metadata (animation.json)** | sprite_repair/export.py | YES | YES | YES | YES | VERIFIED | Schema with frame bounding boxes, valid anchors, and tags. |
| **Aseprite Metadata (aseprite.json)** | sprite_repair/export.py | YES | YES | YES | YES | VERIFIED | Valid schema matching Aseprite JSON array output format (RGBA8888). |
| **Project Persistence Roundtrip** | sprite_repair/project.py<br>server.py | YES | YES | YES | YES | VERIFIED | 100% deep equal match across 10 fields after clean session restart. |
| **Indexed Color Mode** | sprite_repair/export.py | NO | NO | NO | NO | MISSING | 16/32/64/128/256 palette quantization and dithering algorithms pending. |
| **Aseprite Executable Bridge** | sprite_repair/bridge.py | NO | NO | NO | NO | MISSING | Host Aseprite detection, CLI wrapper, and bidirectional Lua script exchange pending. |
| **AI Vision QA (NVIDIA Kimi K3)** | sprite_repair/ai_qa.py | YES | YES | YES | YES | IMPLEMENTED_NOT_LIVE_VERIFIED | Full endpoint and offline fallback verified; live cloud verification pending key. |
| **Selective 2nd Pass Deep QA** | sprite_repair/ai_qa.py | YES | YES | YES | YES | IMPLEMENTED_NOT_LIVE_VERIFIED | Strip assembly for flagged frames verified; live cloud verification pending key. |
