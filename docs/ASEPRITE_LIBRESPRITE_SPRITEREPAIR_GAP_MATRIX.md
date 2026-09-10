# SpriteRepair — 3-Way Feature Gap Matrix (Aseprite vs. LibreSprite vs. SpriteRepair)

**Audit Scope**: Detailed functional comparison across all three systems.  
**Decisions**:
- KEEP_SPRITEREPAIR: Preserve existing superior proprietary implementation (CV, AI, Anchor, Safe Canvas).
- ADOPT_ASEPRITE_BEHAVIOR: Implement clean-room equivalent of Aseprite v1.3 UX / behavioral specification.
- ADAPT_LIBRESPRITE_CONCEPT: Adapt open-source data model or algorithm concept cleanly.
- ADD_NEW: Novel hybrid feature combining AI/CV repair with manual pixel editing.
- IGNORE: Exclude from SpriteRepair roadmap (e.g., tilemaps, vector tools).

---

## 3-Way Feature Matrix

| Feature Area | Aseprite v1.3 | LibreSprite v1.1 | SpriteRepair Current | Architectural Decision | Priority | Notes / Strategy |
|---|---|---|---|:---:|:---:|---|
| **Auto Grid Detection** | Manual only | Manual only | Auto Heuristic + Valley analysis | KEEP_SPRITEREPAIR | P0 | Core AI/CV differentiator. Relax fixed cell limits. |
| **VFX Overflow Recovery** | None (manual paste) | None (manual paste) | Soft flood seed expansion | KEEP_SPRITEREPAIR | P0 | Core CV differentiator. Recovers clipped VFX. |
| **Foot Ground Anchor** | Manual pivot slice | None | Auto lowest-opaque detection | KEEP_SPRITEREPAIR | P0 | Auto foot alignment to safe canvas baseline. |
| **Global Safe Canvas** | Manual canvas resize | Manual canvas resize | Dynamic anchor extent bounding | KEEP_SPRITEREPAIR | P0 | Prevents frame jumping and character cutoff. |
| **AI Animation Vision QA** | None | None | NVIDIA Build Kimi K3 integration | KEEP_SPRITEREPAIR | P0 | Detects pose continuity, anatomy, and jitter. |
| **Timeline Matrix Layout** | Fixed 2D grid matrix | 2D widget matrix | Synchronized CSS Grid matrix | ADOPT_ASEPRITE_BEHAVIOR | P0 | Already verified; maintain exact Aseprite visual layout. |
| **Linked Cels** | Real shared image pointer | Real shared image pointer | Shared linked_cel_id + sync | ADOPT_ASEPRITE_BEHAVIOR | P0 | Verified in semantic suite; sync on mutation, clone on unlink. |
| **Layer Groups** | Hierarchical folders | Hierarchical folders | Flat list with type tag | ADAPT_LIBRESPRITE_CONCEPT | P0 | Implement parent-child folder hierarchy in models and UI. |
| **Reference Layers** | Dedicated non-export overlay | Basic layer only | Custom layer type | ADOPT_ASEPRITE_BEHAVIOR | P0 | Add dedicated non-exporting canvas overlay layer with opacity. |
| **Advanced Selection** | Rect, Lasso, Wand, Color | Rect, Lasso, Wand | Rectangular Marquee | ADOPT_ASEPRITE_BEHAVIOR | P1 | Extend to Lasso, Polygon, Magic Wand, and Color Select. |
| **Ownership Mask Synergy** | None | None | Brush strokes (Char/VFX/Exclude) | ADD_NEW | P0 | Assign active selection directly to Character/VFX masks. |
| **Custom Pivot Manipulator** | Center/custom slice pivot | Center only | Interactive draggable dashed circle | ADOPT_ASEPRITE_BEHAVIOR | P0 | Fully decoupled from root ground anchor. |
| **Transforms Invariants** | Nearest-neighbor /C_4$ | Nearest-neighbor /C_4$ | Mathematically proven invariants | ADOPT_ASEPRITE_BEHAVIOR | P0 | FlipH^2, FlipV^2, Rot90^4 proven with zero pixel mismatch. |
| **Indexed Color Mode** | 256-color palette + dither | 256-color palette + dither | RGBA only | ADAPT_LIBRESPRITE_CONCEPT | P1 | Implement 16/32/64/128/256 quantization + Floyd-Steinberg. |
| **Palette Consistency QA** | None | None | 64-bin RGB histogram drift QA | KEEP_SPRITEREPAIR | P0 | Alert if cross-frame color drift exceeds 28%. |
| **Packed Atlas Export** | MaxRects bin packing | Basic packing | Standard grid packing | ADOPT_ASEPRITE_BEHAVIOR | P1 | Add 2D bin packing to minimize texture wastage. |
| **Extrude (1px / 2px)** | Border duplicate into padding | None | None | ADOPT_ASEPRITE_BEHAVIOR | P1 | Duplicate edge pixels outward to eliminate GPU bleeding. |
| **Duplicate Frame Merge** | Exact match merge + duration | None | None | ADOPT_ASEPRITE_BEHAVIOR | P1 | Exact and near-duplicate frame detection with duration merge. |
| **Split Layers / Tags Export** | Split sheet by layer/tag | Split sheet | Single sheet export | ADOPT_ASEPRITE_BEHAVIOR | P1 | Export isolated sheets per tag (Idle, Attack) and layer. |
| **Aseprite Host Bridge** | Native CLI / Lua API | None | None | ADOPT_ASEPRITE_BEHAVIOR | P0 | Aseprite detection, CLI wrapper, and bidirectional Lua script. |
| **Native .aseprite Parser** | Native read/write | Reverse-engineered reader | JSON exchange format | IGNORE (Phase 2 P2) | P2 | CLI/Lua bridge prioritized over brittle binary parser. |
| **Tilemap / Tileset Tools** | Advanced tile editing | Basic tileset | None | IGNORE | P3 | Out of scope for sprite animation repair studio. |
| **Advanced Brush Dynamics** | Pressure, tilt, pattern | Basic patterns | Hard-edge pixel pencil/eraser | IGNORE | P3 | Hard-edge pixel art precision prioritized over brush painting. |
