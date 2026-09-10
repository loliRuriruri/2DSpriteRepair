# SpriteRepair — Current Feature Inventory

**Audit Date**: 2026-09-10  
**Target Environment**: Python 3.11/3.13 (`sprite_repair` module, `server.py`) + Vanilla ES6 Web App (`app/`)  
**Audit Purpose**: Complete, granular enumeration of existing codebase capabilities, identifying operational readiness, verification status, and architectural gaps prior to Aseprite-grade functional reconstruction.

---

## 1. Feature Status Inventory Table

| Feature | Module / File | Backend Status | Frontend Status | Actually Usable | Verified | Known Problems / Architecture Gaps |
|---|---|:---:|:---:|:---:|:---:|---|
| **Grid Seed & Frame Extraction** | `sprite_repair/pipeline.py`<br>`server.py` (`/api/process`) | Implemented | Implemented | **YES** | **YES** (16/16 frames) | Fixed cell assumption relaxed via seed flood, but initial guess still requires user col/row input or simple peak detection. |
| **Variable Crop & Flood Expansion** | `sprite_repair/pipeline.py` | Implemented | Implemented | **YES** | **YES** | Works via `expand_ratio` (1.15x) and alpha threshold. Does not yet separate intertwined neighbor components automatically. |
| **Foot / Root Anchor Detection** | `sprite_repair/pipeline.py` (`estimate_foot_anchor`) | Implemented | Implemented | **YES** | **YES** (stdev 0.00px) | Base heuristics use bottom solid row & center of mass. Dynamic jump/aerial frames require manual anchor pin or AI assist. |
| **Root Anchor Normalization** | `sprite_repair/pipeline.py` (`recompose_with_anchors`) | Implemented | Implemented | **YES** | **YES** | Re-centers frames onto unified ground plane without jitter. |
| **Global Safe Canvas Expansion** | `sprite_repair/pipeline.py` (`compose_on_canvas`) | Implemented | Implemented | **YES** | **YES** (501x278) | Computes bounding union of all anchor-relative frame boundaries; guarantees zero clipping for large attack slashes. |
| **VFX Overflow Recovery** | `sprite_repair/pipeline.py` | Implemented | Implemented | **YES** | **YES** | Scans adjacent grid boundaries. Currently merges overflow into frame canvas; needs explicit separation into VFX Cel/Layer. |
| **Domain Data Models (Project/Layer/Cel/Frame/Tag/Slice)** | `sprite_repair/models.py` | Implemented | Partially Implemented | **YES** (Backend)<br>**PARTIAL** (Frontend) | **YES** (Backend models)<br>**NO** (Frontend) | Backend dataclasses are complete with JSON serialization. Frontend still uses loose flat state (`state.frames`, `state.layers`) without true Cel matrix bindings. |
| **Timeline Matrix Component** | `app/index.html`<br>`app/app.js`<br>`app/app.css` | Implemented | Partially Implemented | **PARTIAL** | **NO** | Matrix markup exists in `#asepriteTimeline`, but legacy raw thumbnail strip (`#timeline`) is still appended below it. Lacks cel drag-and-drop, range selection, and inline duration editing. |
| **Linked Cels** | `sprite_repair/models.py` (`linked_cel_id`) | Implemented | Missing | **NO** (UI) | **NO** | Backend model supports `linked_cel_id`. Frontend lacks link indicator, "Link Selected Cels" button, and shared buffer synchronization. |
| **Layer Management (CRUD, Visibility, Lock)** | `sprite_repair/models.py`<br>`app/app.js` | Implemented | Partially Implemented | **PARTIAL** | **NO** | Visibility and Lock toggle work on Character/VFX layers in memory. Lacks layer reordering, blend modes, opacity slider, and layer duplication. |
| **Animation Tags & Loop Playback** | `sprite_repair/models.py`<br>`app/app.js` | Implemented | Partially Implemented | **PARTIAL** | **NO** | Tags render as pills and jump to frame; lacks Tag Properties dialog (name, color, from/to, direction: forward/reverse/pingpong). |
| **Slices & Hitbox / Hurtbox / Pivot** | `sprite_repair/models.py` (`Slice`) | Implemented | Missing | **NO** (UI) | **NO** | Data model exists. Frontend has zero UI to display, draw, or adjust rectangular collision or custom pivot slices on the canvas. |
| **Selection & Mask System** | `server.py` (`/api/mask-stroke`)<br>`app/app.js` | Implemented | Partially Implemented | **PARTIAL** | **NO** | Mode radio buttons (exclude, include, erase, restore) exist. Lacks marquee/lasso selection, alpha mask threshold, invert, and marching ants. |
| **Frame Ownership Brush** | `server.py`<br>`sprite_repair/pipeline.py`<br>`app/app.js` | Implemented | Partially Implemented | **PARTIAL** | **NO** | Backend applies strokes against sheet alpha. Frontend lacks cursor size indicator, layer-specific targeting, and visual preview of mask overlay. |
| **Animation-Safe Autocrop** | `server.py` (`/api/crop-frame`)<br>`sprite_repair/pipeline.py` | Implemented | Partially Implemented | **PARTIAL** | **NO** | Manual L/R/T/B inputs work. Autocrop buttons exist, but do not compute the sequence-wide anchor-safe minimal bounding box. |
| **Palette Management & Color Quantization** | `sprite_repair/palette.py`<br>`sprite_repair/recolor.py` | Implemented | Missing | **NO** (UI) | **NO** | Backend contains median cut, k-means, and color replacement. Frontend has no palette swatch bar, color picker tool, or drift QA. |
| **Procedural Motion Generation** | `sprite_repair/breathe.py`<br>`sprite_repair/motion.py` | Implemented | Missing | **NO** (UI) | **NO** | 7 procedural motions (breathe, float, bob, etc.) implemented in Python backend; omitted from the current UI stage. |
| **Stage Viewport & Playback Controls** | `app/app.js`<br>`app/index.html` | Implemented | Implemented | **YES** | **YES** | Play, Pause, Step Forward/Back, Loop/Pingpong/Once, FPS (1-60), Zoom (1x, 2x, 3x, 4x, Fit), Pan (Space+Drag) all functional. |
| **Onion Skinning (Past / Future / Ref Frame)** | `app/app.js` | Implemented | Implemented | **YES** | **YES** | Canvas overlays previous frame (red tint) or reference frame. Lacks multi-step opacity decay, future frame (blue tint), and layer isolation. |
| **Difference View** | `app/app.js` | Missing | Missing | **NO** | **NO** | No delta pixel overlay or body/foot drift visualization comparing normalized frames against each other. |
| **Pixel Grid & Snap** | `app/app.js` | Missing | Missing | **NO** | **NO** | Canvas renders pixelated scaling, but does not display pixel grid lines at >= 4x zoom or allow snapping. |
| **Multi-Format Export Engine** | `sprite_repair/export.py`<br>`server.py` (`/api/export`) | Implemented | Implemented | **YES** | **YES** | Generates PNG sequence, SpriteSheet atlas, `animation.json`, `aseprite.json`, animated GIF (no ghosting), APNG, and WebP. |
| **Project Persistence (`.spriteproject`)** | `sprite_repair/project.py`<br>`server.py`<br>`app/app.js` | Implemented | Implemented | **YES** | **YES** | Saves and loads complete JSON project file with lossless anchor, layer, and frame metadata. |
| **AI Provider Abstraction** | `sprite_repair/ai_align.py` | Implemented | Implemented | **YES** | **YES** | Configures NVIDIA Build (Kimi K3 / Gemini Flash Lite) & OpenRouter with fallback to disabled/offline CV engine. |
| **AI Foot / Scale Alignment** | `sprite_repair/ai_align.py`<br>`server.py` (`/api/ai-align`) | Implemented | Implemented | **YES** (with API key)<br>**OFFLINE** (Fallback) | **PARTIAL** | Functional when user supplies `NVCF_API_KEY`. Graceful fallback to CV heuristics when offline or key missing. |
| **AI Contact Sheet Vision QA** | `sprite_repair/ai_qa.py`<br>`server.py` (`/api/ai-qa`) | Implemented | Implemented | **YES** (with API key) | **PARTIAL** | Analyzes grid sheet via vision LLM; caches JSON response. Output displayed as text in `#qaBox`. |
| **Rule-Based Animation QA (Jitter/Scale)** | `sprite_repair/qa.py`<br>`server.py` (`/api/anim-qa`) | Implemented | Implemented | **YES** | **YES** | Calculates standard deviation of anchors, body center drift, and aspect ratio outliers across frames. |
| **Undo / Redo Command Stack** | `app/app.js` | Partially Implemented | Partially Implemented | **PARTIAL** | **NO** | Only stores anchor snapshots. Lacks Command pattern for layer edits, cel modifications, crop adjustments, and brush strokes. |
| **Desktop Pro Mode Workspace Shell** | `app/index.html`<br>`app/app.css` | N/A | UI Exists but Layout Broken | **NO** | **NO** | 10 control panels stacked vertically in left sidebar. Canvas compressed. No Right Inspector tabs. Raw frames clutter the page bottom. |

---

## 2. Summary of Operational Capabilities vs Deficiencies

### Verified Strengths (Preserve 100%)
1. **Core CV Pipeline**: Variable crop, soft-flood frame expansion, foot anchor detection, root normalization, and global safe canvas expansion function with high precision (verified against real 16-frame 4×4 attack spritesheet).
2. **Export Infrastructure**: Multi-format game-ready bundle generator (PNG seq, SpriteSheet, engine metadata, Aseprite JSON, GIF, APNG, WebP) produces clean, zero-ghosting outputs.
3. **Project Persistence**: Full `.spriteproject` roundtrip serialization preserves all state offline.
4. **AI Resilience**: System operates 100% offline via robust CV algorithms, treating AI LLMs as optional advisory plugins.

### Critical Deficiencies to Resolve in Upgrade
1. **Layout Hierarchy (Failed UI Paradigm)**:
   - The UI currently presents a long, scrolling web form on the left that pushes controls off-screen.
   - The main canvas is constrained and subordinate to the control panels.
   - Raw frame thumbnails are dumped at the bottom, duplicating data and violating desktop editor norms.
2. **Timeline Matrix Incompleteness**:
   - The matrix DOM is not fully synchronized with layer properties (opacity, blend mode).
   - Selection is limited to single cels; range selection (Shift), additive selection (Ctrl), and cel drag/drop are missing.
3. **Tool Context Sensitivity**:
   - All tool parameters (anchor coordinates, mask brushes, crop inputs, AI models) are permanently displayed simultaneously rather than dynamically populating a unified Context Bar.
4. **Inspector Absence**:
   - Properties, Layers, and AI Diagnostics are scattered across arbitrary collapsible sections instead of being unified into a tabbed Right Inspector.
5. **Undo/Redo Breadth**:
   - Undo/Redo only reverts anchor nudges. It does not revert layer changes, cel edits, crop boundaries, or mask strokes.
