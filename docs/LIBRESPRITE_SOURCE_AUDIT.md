# SpriteRepair — LibreSprite Source Audit & GPL Compliance Assessment

**Audit Target**: LibreSprite Official Repository — https://github.com/LibreSprite/LibreSprite  
**Locked Commit SHA**: `77855cf3092b333d19afd9c870e58c01b2f06d01`  
**Audit Purpose**: Analyze LibreSprite's open-source C++ architecture (forked from the last GPLv2 release of Aseprite v0.8.1-v1.1) to extract structural insights for clean-room implementation in SpriteRepair, while evaluating license requirements and maintaining independent codebase governance.

---

## 1. GPLv2 Legal Boundary & Strategic Policy (Verified Against Repository)

1. **GPLv2 Distribution and Derivative-Work Requirements (GPLv2 배포 및 2차적 저작물 요건)**:
   - LibreSprite root `LICENSE.txt` verifies that the project is governed by the **GNU General Public License Version 2, June 1991 (GPLv2)**.
   - Text citation (`src/app/app.h`): *"This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License version 2 as published by the Free Software Foundation."*
   - Under Section 2 of GPLv2, distributing a work containing or derived from GPLv2 code mandates licensing the entire derivative work under GPLv2 and disclosing complete source code.
   - To preserve complete commercial distribution freedom and allow independent proprietary licensing of SpriteRepair and its CV/AI modules, zero GPLv2 code is copied, linked, or incorporated into SpriteRepair.
2. **Clean-Room Independent Implementation Policy**:
   - **Zero Source Copying**: Exactly 0 lines of LibreSprite code files, functions, or headers have been imported or merged into SpriteRepair.
   - **Architectural Reference Only**: Data structures, memory management strategies, and algorithmic workflows are analyzed strictly as conceptual architectural references.
   - **Independent Clean-Room Creation**: All corresponding features in SpriteRepair (e.g., Layer Groups, Advanced Selection, Indexed Color quantization, MaxRects atlas bin packing) have been authored independently from scratch in Python and JavaScript.

---

## 2. LibreSprite Subsystem Audit & Classification

| Subsystem / Component | Description & Architectural Strategy | Official Upstream License | Classification | SpriteRepair Strategic Decision |
|---|---|---|:---:|---|
| **Document & Sprite Model** | `src/doc/document.cpp`, `sprite.cpp`: Document owns Sprite; Sprite owns Image buffer and Palette. | **MIT License** (historical, `src/doc/document.h`) | `REFERENCE_ONLY` | Adopt document/sprite separation cleanly in `sprite_repair/models.py`. Implemented independently. 0 lines copied. |
| **Layer Hierarchy & Trees** | `src/doc/layer.cpp`, `layer_folder.cpp`: Hierarchical tree of LayerImage and LayerFolder with parent-child links. | **MIT License** (historical) | `REFERENCE_ONLY` | Adopt LayerGroup and parent_id hierarchy model in SpriteRepair's dataclasses. 0 lines copied. |
| **Cel & Linked Cel Ownership** | `src/doc/cel.cpp`: Cels store position (x,y), opacity, and reference to shared or unique Image instances. | **MIT License** (historical) | `REFERENCE_ONLY` | Adopt shared image pointer / canvas clone semantic model in SpriteRepair editor. 0 lines copied. |
| **Timeline Matrix State** | `src/app/ui/timeline.cpp`: Decouples visual header geometry from underlying document frame list. | **GPLv2** (`src/app/app.h`) | `REFERENCE_ONLY` | Recreated in CSS Grid and HTML5 Canvas with independent horizontal scroll synchronization. 0 lines copied. |
| **Undo / Redo Commands** | `src/app/undo_history.cpp`: Reversible transactional undo commands. | **GPLv2** (`src/app/app.h`) | `REFERENCE_ONLY` | Guide SpriteRepair's transition from full snapshots to delta-based command history. 0 lines copied. |
| **Selection & Mask Engine** | `src/doc/mask.cpp`: 1-bit / 8-bit alpha mask plane with rectangular, polygonal, and flood fill bounds. | **MIT License** (historical) | `REFERENCE_ONLY` | Build standalone Canvas-based 2D Selection Mask supporting Add/Subtract/Intersect operations. 0 lines copied. |
| **Indexed Color & Palettes** | `src/doc/palette.cpp`: 256-color table with fast color indexing and Euclidean distance matching. | **MIT License** (historical) | `REFERENCE_ONLY` | Implement Python/Pillow-based quantization and Floyd-Steinberg dithering with cross-frame lock in `sprite_repair/export.py`. 0 lines copied. |
| **Drawing & Pixel Engine** | `src/app/tools/`: Bresenham line drawing, flood fill, pixel-perfect pencil algorithm. | **GPLv2** (`src/app/app.h`) | `REFERENCE_ONLY` | Implement pixel-perfect nearest-neighbor Canvas drawing tools in `app/app.js`. 0 lines copied. |
| **Onion Skinning** | `src/app/ui/editor/onion_skin.cpp`: Preceding/succeeding frame blend with alpha tinting. | **GPLv2** (`src/app/app.h`) | `REFERENCE_ONLY` | Independently implemented in SpriteRepair; enhanced with configurable step counts. 0 lines copied. |
| **Theme & UI Graphics** | LibreSprite retro icon sets and UI skin sheets. | **GPLv2 / CC** | `NOT_NEEDED` | Excluded. SpriteRepair uses a modern dark-mode Studio Pro theme. 0 assets copied. |

---

## 3. Strict 5-Tier Status Classification for Clean-Room Features

| Feature Subsystem | Clean-Room Implementation in SpriteRepair | Status | Verification Reference |
|---|---|:---:|---|
| **Layer Groups & Reference Layers** | Collapsible groups, recursive visibility, `[GRP]` / `[REF]` badges | `VERIFIED` | Verified via Headless Edge CDP E2E interaction suite (`verify_source_adoption_features.js`). |
| **Advanced Selection (5 Modes)** | Rect, Lasso, Polygon, Magic Wand, Color Range | `VERIFIED` | Verified via dedicated Headless Edge CDP suite (`test_selection_e2e.js`) and synthetic fixtures (`test_selection_synthetic_fixtures.py`). |
| **MaxRects Atlas Bin Packing** | Genuine BSSF algorithm with maximal sub-rectangle splitting and pruning | `VERIFIED` | Verified via 100-run randomized stress test (`test_atlas_packer_randomized.py`): `overlap==0`, `out_of_bounds==0`, `deterministic==True`, `efficiency>0.65`. |
| **Indexed Palette (16–256)** | Median cut cross-frame locked palette, alpha preservation, Floyd-Steinberg | `VERIFIED` | Verified via `test_packing_palette_invariants.py` across 16, 32, 64, 128, 256 color targets. |
| **Aseprite Bridge Detection & Schema** | Binary detection, CLI batch execution, official schema generation | `SCHEMA_VERIFIED` | Verified via `test_aseprite_runtime_validation.py` using host portable binary (v1.3.18.5-trial). |
| **Aseprite Full Write Roundtrip** | Subprocess save of PNG sheet and Lua execution | `RUNTIME_COMPATIBILITY_NOT_VERIFIED` | Trial binary restricts disk save operations and Lua execution at runtime. Strictly classified per directive. |
| **Cloud Vision AI Assist** | Remote vision LLM analysis (NVIDIA Build / OpenRouter) | `CLOUD_AI_VERIFIED` | Verified with live NVIDIA API call to `moonshotai/kimi-k3` returning problem frame diagnosis and disk cache generation (`test_live_kimi_k3.py`). |
