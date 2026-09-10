# SpriteRepair — Editor Functional Upgrade Plan V2

**Document Version**: 2.0  
**Scope**: Technical architecture and implementation roadmap for Layer Groups, Reference Layers, Advanced Selection, Indexed Palette Mode, Enhanced Packed Atlas Export, and Aseprite Bridge.

---

## 1. Architectural Architecture & Module Upgrades

### 1.1 Layer Groups & Hierarchy (`sprite_repair/models.py`, `app/app.js`)
- **Data Model**: Extend `Layer` with `type: str = "image" | "group" | "reference"`, `parent_id: str | None = None`, `collapsed: bool = False`.
- **Inheritance Cascade**: Group visibility, opacity, and locked state cascade down the hierarchy to child layers during canvas compositing.
- **UI Matrix Representation**: Nested indentation in `#tlLayersCol` with folder expansion toggles (▶ / ▼) and drag-and-drop hierarchy reordering.

### 1.2 Reference Layers
- **Specification**: Dedicated layer holding source reference images (original AI sprite sheet, pose sketches, character models).
- **Behavior**:
  - Interactive opacity slider on canvas overlay.
  - Can be locked, translated, and scaled independently.
  - **Export Rule**: Automatically excluded from all game asset exports (`sheet.png`, `animation.json`, `frames/*.png`).

### 1.3 Advanced Selection Engine
- **Tools**:
  - **Rectangle Marquee**: Standard bounding box selection.
  - **Lasso Tool**: Freehand polygon boundary selection.
  - **Magic Wand Tool**: Contiguous alpha/color flood fill selection based on Euclidean distance threshold.
  - **Color Select Tool**: Global non-contiguous color selection.
- **Boolean Combiners**:
  - `New Selection` (default)
  - `Add to Selection` (`Shift + Drag`)
  - `Subtract from Selection` (`Alt + Drag`)
  - `Intersect with Selection` (`Shift + Alt + Drag`)
- **Pixel Art Policy**: Anti-aliasing and feathering strictly disabled by default to preserve hard pixel boundaries.

### 1.4 Ownership Mask & Selection Integration
- Direct context actions on active selections:
  - `Assign to Character`
  - `Assign to VFX`
  - `Assign to Exclude`
- Updates `mask_strokes` and triggers instant re-composition of character/VFX separation.

### 1.5 Indexed Palette Mode & Consistency
- **Quantization Modes**: 16, 32, 64, 128, 256 colors.
- **Dithering Options**: None (Nearest Hard Color), Floyd-Steinberg, Ordered Bayer (2x2, 4x4, 8x8).
- **Key Color Preservation**: Locks designated character skin and hair palette slots to avoid color distortion across frames.
- **Palette Consistency QA Integration**: Flags cross-frame Euclidean histogram drift exceeding 28% and offers "Normalize Palette to Reference Frame" action.

### 1.6 Enhanced SpriteSheet Export & Packed Atlas
- **MaxRects 2D Bin Packing**: Eliminates wasted empty canvas areas in standard grid sheets.
- **Gutter Padding**: Configurable border padding, shape padding, and inner padding (0–32px).
- **Extrude Filter (1px / 2px)**: Replicates edge pixels outward into padding gutters to prevent OpenGL/DirectX texture bleed and seam filtering artifacts.
- **Duplicate Frame Merge**: Exact frame hash deduplication with frame duration accumulation in `animation.json` and `aseprite.json`.
- **Split Layers & Split Tags**: Generates separate sheets for `Character` vs `VFX` or per tag (`Idle.png`, `Attack.png`).

### 1.7 Aseprite Host Bridge (`sprite_repair/bridge.py`)
- **Auto-Detection**: Scans `PATH`, `Program Files/Aseprite/Aseprite.exe`, `Steam/steamapps/common/Aseprite/aseprite.exe`.
- **CLI Automation**: Invokes headless batch commands:
  ```bash
  aseprite -b sheet.png --data anim.json --format json-array
  ```
- **Lua Bridge Generator**: Generates `export_bundle/import_to_aseprite.lua` script to reconstruct native `.aseprite` project files containing layers, frames, cels, durations, tags, and pivots.

---

## 2. Phased Milestone Execution Schedule

| Milestone | Deliverables | Verifiable Outcome |
|---|---|---|
| **Phase 1** | `tests/aseprite_behavior/` test suite | 100% pass on 10 semantic test modules |
| **Phase 2** | Layer Groups, Reference Layer, Advanced Selection, Palette Mode | Functional UI & canvas tools |
| **Phase 3** | Packed Atlas, Extrude, Duplicate Merge | Verified disk export bundles |
| **Phase 4** | `AsepriteBridge` CLI & Lua script exchange | Bidirectional import/export validated |
| **Phase 5** | AI Vision QA & Mask Suggestion refinement | Offline fallback verified |
| **Phase 6** | Multi-viewport visual QA & Final Matrix | Zero-failure master test execution |
