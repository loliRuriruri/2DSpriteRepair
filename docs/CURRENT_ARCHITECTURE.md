# CURRENT_ARCHITECTURE — SpriteRepair Studio (Phase 0 Audit)

**Date**: 2026-09-10  
**Repository Path**: `C:\TEST\MikuChat-Lab\projects\SpriteRepair`  
**Purpose**: Comprehensive audit of current architecture, assets, capabilities, limitations, and technical debt in accordance with Section 4 and Section 66 (Phase 0) of the AI Sprite Animation Repair Studio Master Specification.

---

## 1. Executive Summary & Repository Status

SpriteRepair is a high-performance Python + Vanilla Web stack designed for importing, segmenting, repairing, and exporting 2D sprite sheets. Rather than a fragile end-to-end neural generator, it employs a deterministic, offline-capable Computer Vision (CV) core based on flood-fill segmentation, soft-boundary expansion, and foot-anchor normalization, with optional AI vision assistance (NVIDIA Build Kimi K3, OpenRouter, Ollama) and retro pixel art enhancements.

### Codebase Statistics
- **Backend**: Pure Python 3.13 + Pillow, 15 modules, 5,015 lines of code.
- **Frontend**: Vanilla HTML5 / ES6 JavaScript / CSS3, 2,411 lines (app.js: 1,937 lines, index.html: 474 lines).
- **External Dependencies**: Pillow only (`requirements.txt: Pillow>=10.0.0`). Zero heavyweight web frameworks (uses Python stdlib `http.server.ThreadingHTTPServer`), ensuring zero-install instant startup.
- **Execution Mode**: Local standalone server on `http://127.0.0.1:5190` via `SpriteRepair.bat`.

---

## 2. Component-by-Component Audit

### 2.1 Backend Architecture (`server.py` & `sprite_repair/`)

| Module | Lines | Current Responsibilities | Status & Reusability |
| :--- | :--- | :--- | :--- |
| `server.py` | 1087 | Threading HTTP server, session management (`CURRENT_SESSION`), REST endpoints, static file server with socket streaming. | **Core**. High reuse. Needs migration from raw dicts to `models.py`. |
| `sprite_repair/pipeline.py` | 968 | Alpha mask extraction, grid detection (`estimate_grid`), expansion flood-fill with core protection, character/VFX separation, foot anchor detection (`estimate_foot_anchor`), global canvas composition (`compose_on_canvas`), anchor recomposition, ownership mask brush. | **Core Engine**. High reuse. Reusable CV algorithms; needs separation into clean modular components. |
| `sprite_repair/export.py` | 257 | Multi-format exporter: PNG sequences, combined SpriteSheet, `manifest.json`, `aseprite.json` (frameTags, layers, cels), animated GIF, APNG, WebP, packaged ZIP. | **High Reuse**. Formats already support Aseprite JSON and multi-target animation files. |
| `sprite_repair/project.py` | 53 | `.spriteproject` JSON serializer/deserializer. | **Moderate**. To be upgraded in Phase 1 to serialize full `Project`, `Layer`, `Cel`, and `Tag` models. |
| `sprite_repair/chromakey.py` | 279 | 4-pass analytical chroma-key: solid threshold, Chebyshev 8-way frontier, alpha unmixing, trapped despill. | **Complete & Reusable**. Works on input sheets prior to grid segmentation. |
| `sprite_repair/palette.py` | 125 | Retro color quantization (Pico-8, GameBoy, DB32, EDG32, Sweetie 16, CGA) with CIELAB Euclidean color distance. | **Complete & Reusable**. Directly satisfies retro styling tools. |
| `sprite_repair/motion.py` | 319 | Procedural motion synthesis: 7 modes (`breathe`, `jump`, `hit`, `hover`, `charge`, `bounce`, `down`) via affine matrix warping and secondary harmonic delay. | **Complete & Reusable**. Enhances manual animation generation. |
| `sprite_repair/breathe.py` | 249 | Specialized multi-band anatomical breathing loop synthesizer. | **Complete & Reusable**. |
| `sprite_repair/ai_align.py` | 1250 | Multi-provider AI vision client (NVIDIA Build, OpenRouter, Ollama) supporting Kimi K3, Qwen 2.5/VL, Claude, etc. with retry, fallback, and validation. | **Complete & Reusable**. AI assist module for Phase 6. |
| `sprite_repair/ai_qa.py` | 140 | AI contact sheet builder and visual QA evaluator with MD5 hashing cache in `.ai-cache`. | **Complete & Reusable**. |
| `sprite_repair/qa.py` | 70 | Classical animation QA: anchor jitter detection, scale anomaly detection, bbox overflow analysis. | **Core QA**. High reuse. |
| `sprite_repair/recolor.py` | 113 | Hue/saturation/lightness recoloring with luminance preservation. | **Complete & Reusable**. |
| `sprite_repair/multipart.py` | 64 | Stdlib multipart/form-data parser without external libraries. | **Utility**. Fully functioning. |

---

### 2.2 Frontend Architecture (`app/`)

- **`app/index.html`**:
  - `panel controls`: Sheet upload, grid settings (Auto/NxM), chroma key background removal, scale normalization, procedural motion studio, retro palette switcher, AI configuration & provider keys.
  - `panel stage`:
    - Canvas workspace with pixel editing tools: Anchor tool, Pencil, Eraser, Eyedropper, Bucket.
    - Onion Skinning: Dual-tint overlays (Past = Red tint, Future = Blue tint, Reference = Green tint).
    - Timeline strip: Thumbnail filmstrip with frame reordering, multi-frame selection, deletion, reference frame locking.
    - Animation preview player: Forward, Reverse, Ping-Pong playback, FPS control, scale/zoom toggle.
  - `panel manual-panel`:
    - Anchor nudging (1px arrow buttons, anchor locking).
    - Crop editors (tight crop, safe padding, LRTB numerical adjustments).
    - Ownership mask brush (Include, Exclude, Erase, Restore).
  - `panel qa-panel`:
    - Rule-based QA flags (Jitter, Scale Anomaly, Overflow).
    - AI QA feedback display.
    - Export action panel (ZIP download with PNG sequence, spritesheet, animation.json, aseprite.json, preview.gif, apng, webp).

- **`app/app.js`**:
  - Client state container managing `project`, `activeFrameIndex`, `frames`, `canvas`, `zoom`, `onionSkin`, `tools`, and `undo/redo` history stack.
  - Synchronous bidirectional communication with backend REST endpoints.
  - Pixel-perfect canvas rendering using `image-rendering: pixelated` and sub-pixel snapping.

---

## 3. Data Model Analysis & Critical Deficiencies

### Current Data Structure (Legacy Dictionaries)
Currently, frames and canvas are represented as loosely typed nested dictionaries:
```python
{
    "canvas": {"w": 128, "h": 160, "anchor": {"x": 64, "y": 150}},
    "frames": [
        {
            "frame": 0,
            "rect": {"x": 0, "y": 0, "w": 128, "h": 160},
            "anchor": {"x": 64, "y": 150},
            "offset": {"x": 10, "y": 5},
            "duration": 80,
            "character_bbox": {"x": 23, "y": 18, "w": 132, "h": 271},
            "effect_bbox": {"x": 121, "y": 61, "w": 263, "h": 153},
            "combined_bbox": {"x": 23, "y": 18, "w": 361, "h": 271},
            "qa_warnings": ["Jitter: anchor shifted by 12px"]
        }
    ]
}
```

### Identified Deficiencies (Master Spec Sections 7, 8, 9, 10):
1. **Lack of Layer & Cel Abstraction**:
   - Each frame currently holds a single merged RGBA image.
   - Character pixels, VFX pixels, and background/shadow are baked together. Modifying or nudging VFX independently from the character body is impossible without a Cel layer hierarchy (`Cel = Layer x Frame`).
2. **Missing Animation Tags**:
   - No structured representation for animation sub-sequences (e.g., `Idle: 0-3`, `Attack_Windup: 4-7`, `Slash_VFX: 8-12`, `Recovery: 13-15`).
3. **No Slices or Separate Pivot System**:
   - Slices (sub-regions like hitboxes, hurtboxes, head position) are absent. Pivot is hard-coupled to the single Foot Anchor.
4. **Global vs Local Frame Duration**:
   - Frame duration is currently treated as uniform (`duration_ms` default 80ms) rather than per-frame variable timings.
5. **Lack of Strict Type Validation**:
   - Dictionaries are mutated arbitrarily across `pipeline.py`, `server.py`, and `export.py`, risking key discrepancies.

---

## 4. Reusable Modules vs Required New Modules

### Highly Reusable Components (Keep & Integrate)
1. `sprite_repair/chromakey.py`: Excellent 4-pass color unmixing; keep intact.
2. `sprite_repair/palette.py`: Retro palette quantization; keep intact.
3. `sprite_repair/motion.py`: Procedural animation synthesis; keep intact.
4. `sprite_repair/ai_align.py` & `ai_qa.py`: Multi-model vision pipeline with Kimi K3 support, retry logic, and cache.
5. `sprite_repair/export.py`: Multi-format exporters (GIF, APNG, WebP, Aseprite JSON); keep core encoders.
6. `sprite_repair/pipeline.py`: Flood-fill segmentation, core body seed protection, anchor estimation, and canvas max-extent calculation.

### Deprecated / Refactor Targets
1. `pipeline.py.bak_double`: Dead backup file; remove.
2. Raw dictionary passing: Encapsulate in `sprite_repair/models.py`.
3. Monolithic frame image in session: Evolve to support multi-layer cels (`character_cel`, `vfx_cel`, `shadow_cel`).

### Newly Required Modules
1. **`sprite_repair/models.py` (Phase 1)**:
   - Typed dataclasses: `Project`, `Sprite`, `Frame`, `Layer`, `Cel`, `Tag`, `Slice`, `Anchor`, `Diagnostics`, `ExportSettings`.
   - Bidirectional serialization: `to_dict()`, `from_dict()`, `to_json()`, `from_json()`, `from_legacy_dict()`, `to_legacy_dict()`.
2. **`sprite_repair/layers.py` (Phase 2 & 4)**:
   - Cel composition, layer visibility, opacity blending, and independent layer transforms.

---

## 5. Technical Debt & Safety Invariants

1. **No External Framework Bloat**:
   - Maintain pure Python stdlib + Pillow for maximum portability and zero-install operation on Windows.
2. **Offline First**:
   - Every operation (grid detection, frame extraction, anchor calculation, alignment, QA, export) must function 100% offline without any API keys or network connection.
   - AI features are strictly opt-in advisory assists.
3. **Non-destructive Invariant**:
   - Raw extracted frame cels and original spritesheet must remain immutable in memory so any crop, mask, or anchor adjustment can be non-destructively recalculated.
4. **Backward Compatibility**:
   - Legacy session dictionary APIs used by `app.js` must continue to work during each incremental phase.

---

## 6. Audit Conclusion & Readiness

The SpriteRepair repository provides a rock-solid, working foundation. The core CV segmentation and alignment algorithms are already functional and performant. The primary prerequisite to achieving the Aseprite-grade AI Repair Studio vision is **Phase 1: Implementing the Core Data Model (`models.py`)**, followed by **Phase 2: Core Sprite Repair pipeline migration and verification on real 4x4 attack sprite sheets**.
