# SpriteRepair — Aseprite Source Adoption & License Audit

**Audit Target**: Aseprite Official Repository — https://github.com/aseprite/aseprite  
**Locked Commit SHA**: `375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9`  
**Audit Purpose**: Verify modern UX conventions, behavioral specifications, API/CLI interfaces, and test case oracles for SpriteRepair adoption while strictly preventing EULA copyright violations.

---

## 1. Strict License & Legal Governance Boundary (Verified Against Repository)

1. **Aseprite Root Application License**:
   - Upstream root `EULA.txt` governs the Aseprite desktop application.
   - Text citation: *"END-USER LICENSE AGREEMENT FOR ASEPRITE... By installing, copying, or otherwise using the SOFTWARE PRODUCT, you agree to be bound by the terms of this EULA."*
   - **Absolute Prohibition**: No C++ source code under the EULA is copied, translated, or incorporated into SpriteRepair.
2. **Subsystem Permissive Licenses**:
   - `src/doc/`: Governed by `src/doc/LICENSE.txt`, which is **MIT License** (*"Copyright (c) 2018-present Igara Studio S.A., Copyright (c) 2001-2018 David Capello. Permission is hereby granted, free of charge... MIT license."*).
   - `tests/`: Governed by `tests/LICENSE.txt`, which is **MIT License** (*"Copyright (c) 2018-2023 Igara Studio S.A., Copyright (c) 2018 David Capello. Permission is hereby granted, free of charge... MIT license."*).
   - `src/dio/`, `src/render/`, `src/ui/`: Each contains an independent `LICENSE.txt` under the **MIT License**.
3. **Data Assets (No Blanket Assumptions)**:
   - `data/fonts/`: Governed by `data/fonts/LICENSE.txt`, which is **Creative Commons Attribution 4.0 International (CC BY 4.0)**, NOT proprietary. Regardless, SpriteRepair excludes upstream font files and utilizes system fonts and CSS typography.
   - `data/extensions/aseprite-theme/`: Governed by `LICENSE.txt` under **CC BY 4.0**. Excluded; SpriteRepair uses an independent Studio Pro theme and custom SVG icons.
4. **Format & API Specifications**:
   - `docs/ase-file-specs.md`: Technical documentation describing binary container structures. Referenced purely for clean-room interoperability.
   - CLI & Lua API signatures: Non-copyrightable functional interfaces used to format script generator outputs and CLI subprocess invocations.

---

## 2. Aseprite Module-by-Module Source Audit & Classification

| Source Path / Component | Description & Functionality | Official Upstream License | Classification | SpriteRepair Adoption Strategy |
|---|---|---|:---:|---|
| `src/doc/` | Document, Sprite, Layer, Frame, Cel, Tag, Slice, Palette data models | **MIT License** (`src/doc/LICENSE.txt`) | `SPECIFICATION_REFERENCE` | Reference data structures and lifecycle semantics. Implemented independently in Python (`models.py`) and JavaScript (`app.js`). 0 lines copied. |
| `src/app/commands/` | Undo/redo, canvas transforms, layer operations, cel linking, frame insertion | **Aseprite EULA** (`EULA.txt`) | `BEHAVIOR_REFERENCE_ONLY` | Adopt command taxonomy and keyboard shortcuts (Ctrl+Z, Ctrl+Y, Ctrl+C/V, Alt+N, Shift+N, F2-F4). 0 lines copied. |
| `src/app/cmd/` | Transactional delta commands for undo history | **Aseprite EULA** (`EULA.txt`) | `BEHAVIOR_REFERENCE_ONLY` | Guide SpriteRepair command/delta undo transition. 0 lines copied. |
| `src/app/ui/timeline/` | 2D timeline matrix: layers on Y, frames on X, cel brackets, linked cels | **Aseprite EULA** (`EULA.txt`) | `BEHAVIOR_REFERENCE_ONLY` | Guide DOM rendering, scroll synchronization, and multi-selection bracket ergonomics. 0 lines copied. |
| `tests/` (Behavior Tests) | Functional unit tests for sprite math, cels, tags, transforms | **MIT License** (`tests/LICENSE.txt`) | `TEST_ORACLE_REFERENCE` | Recreate mathematical invariants (group symmetries $C_2 \times C_2$, $C_4$) as independent clean-room unit tests in `tests/aseprite_behavior/`. 0 lines copied. |
| `docs/ase-file-specs.md` | Binary specification for `.ase` and `.aseprite` container format | Technical Format Spec | `SPECIFICATION_REFERENCE` | Reference for binary structure understanding under interoperability standards. Initial pipeline operates via clean-room Lua bridge. |
| `api/` (Lua Scripting API) | Lua API specification (`app.sprite`, `app.layer`, `app.cel`, `app.command`) | API Specification | `API_BRIDGE` | Generate standalone Lua scripts (`import_to_aseprite.lua`) to reconstruct documents via external Aseprite executable. |
| CLI (`aseprite --batch ...`) | Headless command-line flags (`--sheet`, `--data`, `--split-layers`, `--trim`) | CLI Specification | `API_BRIDGE` | Build Python wrapper (`AsepriteBridge`) to invoke host Aseprite for automated sheet generation and conversion. |
| `data/skins/`, `data/fonts/` | Theme atlases, icon sheets, fonts | **CC BY 4.0** (`data/fonts/LICENSE.txt`) | `NOT_NEEDED` | Strictly excluded. SpriteRepair utilizes modern CSS variables, SVG vectors, and system typography. |

---

## 3. Host Binary Runtime Validation Findings

Tested with portable Aseprite executable `Aseprite.exe` (v1.3.18.5-trial):

1. **Detection & CLI Execution (`VERIFIED`)**:
   - `AsepriteBridge.detect()` auto-detects binary path and parses version: `1.3.18.5-trial`.
   - `aseprite.exe --batch --version` executes cleanly with exit code 0.
2. **Metadata JSON Generation (`SCHEMA_VERIFIED`)**:
   - `aseprite.exe --batch [frames] --data out.json --format json-array --list-tags --list-layers` executes with exit code 0 and produces official schema JSON metadata with frames, meta, and layers.
3. **Disk Save & Lua Scripting Restrictions (`RUNTIME_COMPATIBILITY_NOT_VERIFIED`)**:
   - Trial binary enforces: *"Save operation is not supported in trial version"*, suppressing disk image output.
   - Trial build was compiled with `#ifndef ENABLE_SCRIPTING`, rejecting `--script` flag at runtime.
   - Therefore, per Master Directive rules, `aseprite.json` is classified as `SCHEMA_VERIFIED`, while full write roundtrip is classified as `RUNTIME_COMPATIBILITY_NOT_VERIFIED` pending full-version host binary.
