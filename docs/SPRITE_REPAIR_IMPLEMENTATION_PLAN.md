# SPRITE_REPAIR_IMPLEMENTATION_PLAN — Phased Architecture & Execution Roadmap

**Date**: 2026-09-10  
**Repository Path**: `C:\TEST\MikuChat-Lab\projects\SpriteRepair`  
**Standard**: Conforming to Sections 4, 6, 7, 8, 9, 10, and 66 of the AI Sprite Animation Repair Studio Master Specification.

---

## 1. Core Foundational Invariants

All implementation steps adhere strictly to the non-negotiable principles:
1. `Grid != Actual Frame Boundary` (Variable flood segmentation allows frames to extend across grid boundaries).
2. `Character Anchor != Bounding Box Center` (Foot anchor pinned to the root of the character body, not geometry center).
3. `Character Bounding Box != VFX Bounding Box` (High-density character body mask separated from peripheral particles and effects).
4. `AI is an Advisory Assist, Never a Mandatory Dependency` (100% offline functionality must always be maintained).
5. `Non-Destructive Editing` (Original frames and sheet data are preserved; crops, masks, and recompositions are non-destructive).

---

## 2. Phase-by-Phase Roadmap

```text
Phase 0: Repository Audit [COMPLETED]
    │
    ▼
Phase 1: Core Data Model Refactor (Project, Sprite, Frame, Layer, Cel, Tag, Slice, Anchor, Diagnostics)
    │
    ▼
Phase 2: Core Sprite Repair Pipeline Integration & 4x4 Attack Sheet Milestone Validation
    │
    ▼
Phase 3: Aseprite-Grade Animation Editor (Layer timeline, Per-frame durations, Onion skin refinements)
    │
    ▼
Phase 4: Advanced Character/VFX Ownership, Connected Components & Overflow Repair
    │
    ▼
Phase 5: Automated Animation QA (Jitter, Scale Anomaly, Difference View, Auto-correction)
    │
    ▼
Phase 6: AI Vision Assist Integration (NVIDIA Kimi K3, Contact Sheet QA, Structured JSON feedback)
    │
    ▼
Phase 7: Advanced Studio Tools (Tags, Slices, Pivot system, Pixel retouch palette integration)
    │
    ▼
Phase 8: Master Asset Exporters (PNG sequence, Atlas SpriteSheet, Aseprite JSON, GIF, APNG, WebP)
    │
    ▼
Phase 9: Polish, Keyboard Shortcuts, Regression Testing & Packaging
```

---

## 3. Detailed Specifications for Phase 1 & Phase 2

### Phase 1: Core Data Model Refactor

#### Objective
Transition from untyped, loose dictionary structures to a structured, type-safe, and serializable domain model in `sprite_repair/models.py`.

#### Concrete Data Classes (`sprite_repair/models.py`):
1. **`Point`**: `x: int`, `y: int`
2. **`Rect`**: `x: int`, `y: int`, `width: int`, `height: int`
   - Helper properties: `left`, `top`, `right`, `bottom`, `center_x`, `center_y`
3. **`Anchor`**:
   - `x: int`, `y: int`, `type: str = "foot"` ("foot" | "root" | "center" | "custom"), `locked: bool = False`
4. **`Diagnostics`**:
   - `jitter: bool = False`, `scale_anomaly: bool = False`, `overflow: bool = False`, `review_required: bool = False`, `warnings: list[str] = field(default_factory=list)`
5. **`Layer`**:
   - `id: str`, `name: str`, `type: str = "character"` ("character" | "vfx" | "shadow" | "correction" | "mask" | "reference"), `visible: bool = True`, `opacity: float = 1.0`, `blend_mode: str = "normal"`, `locked: bool = False`
6. **`Cel`**:
   - `layer_id: str`, `frame_id: int`, `x: int = 0`, `y: int = 0`, `opacity: float = 1.0`, `visible: bool = True`, `image_data: str | None = None` (base64 data URL), `linked_cel_id: str | None = None`
7. **`Frame`**:
   - `id: int`, `index: int`, `duration_ms: int = 80`, `nominal_rect: Rect`, `content_rect: Rect`, `character_bbox: Rect | None = None`, `effect_bbox: Rect | None = None`, `combined_bbox: Rect | None = None`, `anchor: Anchor`, `offset: Point = Point(0, 0)`, `diagnostics: Diagnostics = Diagnostics()`, `cels: list[Cel] = field(default_factory=list)`
8. **`Tag`**:
   - `name: str`, `from_frame: int`, `to_frame: int`, `direction: str = "forward"` ("forward" | "reverse" | "pingpong"), `repeat: int = 0`
9. **`Slice`**:
   - `name: str`, `bounds: Rect`, `pivot: Point | None = None`
10. **`Sprite`**:
    - `width: int`, `height: int`, `anchor: Point`, `color_mode: str = "RGBA"`
11. **`Project`**:
    - `name: str`, `version: str = "2.0"`, `sprite: Sprite`, `layers: list[Layer]`, `frames: list[Frame]`, `tags: list[Tag]`, `slices: list[Slice]`, `export_settings: dict`

#### Compatibility & Interoperability Layer:
- Provide `to_dict()`, `from_dict()`, `to_legacy_dict()`, and `from_legacy_dict()` to guarantee 100% backward compatibility with existing front-end communication (`server.py` and `app.js`).

---

### Phase 2: Core Sprite Repair Pipeline Integration

#### Objective
Refactor `sprite_repair/pipeline.py` and `server.py` to produce and consume `Project` and `Frame` models, and validate against a real 16-frame (4x4) AI-generated attack sprite sheet.

#### Concrete Changes:
1. **`sprite_repair/pipeline.py`**:
   - Modify `process_sheet()`:
     - Returns a fully populated `Project` instance (and legacy dict view).
     - Instantiates default layers (`Character`, `VFX`).
     - Populates per-frame `nominal_rect`, `content_rect`, `character_bbox`, `effect_bbox`, `anchor`, and `diagnostics`.
   - Modify `compose_on_canvas()` & `recompose_with_anchors()`:
     - Operates cleanly on `Project` and `Frame` dataclasses.
2. **`server.py`**:
   - Store `CURRENT_PROJECT: Project | None` alongside `CURRENT_SESSION`.
   - Update `/api/process`, `/api/recompose`, `/api/crop-frame`, `/api/mask-stroke`, `/api/export` to maintain state synchronization between dataclasses and client payloads.
3. **Milestone Validation & Verification Criteria**:
   - Import real 4x4 attack sprite sheet (16 frames).
   - Verify 16 extracted frames with accurate foot anchors.
   - Verify global canvas expansion prevents VFX and weapon cutoffs.
   - Verify frame preview playback shows rock-solid foot grounding with zero jitter.
   - Verify export of PNG sequence, SpriteSheet atlas, `manifest.json`, `aseprite.json`, GIF, APNG, and WebP.

---

## 4. File-by-File Modification Plan

| File | Proposed Change | Rationale |
| :--- | :--- | :--- |
| `sprite_repair/models.py` | **[NEW FILE]** Complete dataclass hierarchy (`Project`, `Frame`, `Layer`, `Cel`, `Tag`, `Slice`, `Anchor`, `Diagnostics`). | Phase 1 requirement: Establish formal domain architecture. |
| `sprite_repair/pipeline.py` | **[MODIFY]** Adapt `process_sheet`, `recompose_with_anchors`, `compose_on_canvas` to build and use `Project` / `Frame`. Clean up unused backups. | Phase 2 requirement: Pipe CV extractions into standard models. |
| `sprite_repair/pipeline.py.bak_double` | **[DELETE]** Redundant backup file. | Cleanliness & technical debt reduction. |
| `sprite_repair/project.py` | **[MODIFY]** Upgrade `read_project` and `write_project` to serialize `Project` model directly to `.spriteproject` JSON format. | Phase 1 & 9: Robust project save/load. |
| `sprite_repair/export.py` | **[MODIFY]** Accept `Project` instance alongside legacy dicts for exporting spritesheet, metadata, Aseprite JSON, GIF, APNG, WebP. | Phase 8 & standard export conformity. |
| `server.py` | **[MODIFY]** Manage `CURRENT_PROJECT` in server state; seamlessly serialize model objects in API responses. | Seamless API bridging. |
| `app/app.js` & `app/index.html` | **[INCREMENTAL UPDATE]** Retain existing UI while preparing for Layer/Cel timeline and tag views in Phase 3. | Preserve UX stability and non-breaking incremental progress. |

---

## 5. Comprehensive Automated & Manual Testing Plan

1. **Unit & Model Tests** (`test_models.py`):
   - Serialization and deserialization roundtrip (`Project -> JSON -> Project`).
   - Legacy dict conversion roundtrip (`Legacy Dict -> Project -> Legacy Dict`).
2. **Pipeline Integration Tests** (`test_pipeline_models.py`):
   - Process `samples/keqing_idle_3x3.png` and `samples/synthetic_4x4.png`.
   - Verify `Project.frames` length, valid bounding boxes, foot anchor offsets, and global canvas dimensions.
3. **Milestone Attack Sheet Validation** (`test_attack_4x4_milestone.py`):
   - Process full 16-frame AI-generated attack sheet (`media_1788968095319.png`).
   - Measure foot anchor stability variance (< 3.0 px across animation).
   - Verify character bbox vs effect bbox distinction.
   - Generate test exports: PNG sequence, atlas, `aseprite.json`, GIF, APNG, WebP.
4. **End-to-End Server API Tests** (`test_server_api.py`):
   - HTTP tests against `/api/process`, `/api/recompose`, `/api/export`, `/api/save-project`.
   - Ensure all responses return HTTP 200 with matching model data.
