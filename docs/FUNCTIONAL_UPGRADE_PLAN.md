# SpriteRepair — Functional Upgrade Plan & Implementation Roadmap (Phases B – G)

**Target Codebase**: `app/` (HTML/CSS/JS) & `sprite_repair/` (Python Engine)  
**Execution Objective**: Methodically implement the audited Aseprite workflows, Desktop Studio UI Shell, and advanced SpriteRepair AI/CV capabilities across Phases B through G with zero regression to the existing CV engine.

---

## 1. Upgrade Phase Breakdown

### Phase B: Desktop Studio Shell Reconstruction
**Goal**: Replace the vertical stacked layout in `app/index.html` and `app/app.css` with the 6-region desktop studio layout.

1. **Markup Restructuring (`app/index.html`)**:
   - Create top Menu Bar with native dropdown menus (`File`, `Edit`, `Frame`, `Layer`, `View`, `AI`, `Help`).
   - Create dynamic Context Bar with placeholder slots for Tool options.
   - Create 36px left Tool Rail with icon buttons (`Select`, `Move`, `Anchor`, `Pivot`, `Crop`, `Mask`, `Eraser`, `Diff`, `Zoom`, `AI Align`, `AI QA`).
   - Create primary Canvas Viewport container configured for centered pan/zoom (`canvas#view`).
   - Create tabbed Right Inspector with 3 tabs: `Properties`, `Layers`, and `AI QA`.
   - Create Bottom Timeline container with transport bar, tags band, and synchronized layer/cel matrix.
   - Create 24px Status Bar at the bottom.
   - Move complex forms to dedicated modal dialogs: `#importModal`, `#exportModal`, `#aiSettingsModal`, `#tagModal`.
2. **CSS Desktop Studio Styling (`app/app.css`)**:
   - Implement CSS Grid / Flex layout anchoring header, footer, sidebars, and fluid center canvas.
   - Set dark theme palette modeled on Aseprite dark aesthetics (`#232328`, `#2b2c33`, `#373844`, accent `#6aa8ff`).
   - Enforce compact button sizes (28–32px) and high-density typography (10–12px monospace/sans-serif).
   - Style 2D Cel matrix with fixed left column, horizontally scrolling frame columns, and hover/active states.

---

### Phase C: Functional Editor Core
**Goal**: Wire interactive Cel, Layer, Frame, Anchor, and Mask manipulation into `app/app.js` and connect to backend.

1. **Cel Matrix Interactivity**:
   - Implement full 2D Cel matrix: clicking a cel selects the active frame and active layer.
   - Support Shift+Click rectangular range selection and Ctrl+Click additive cel selection.
   - Cel deletion, clearing, duplication, and moving between frame columns.
2. **Layer CRUD & Properties**:
   - Add/Remove layers in UI and synchronize with `Project` data model.
   - Layer visibility toggle (`👁️`), layer lock toggle (`🔒`).
   - Layer opacity slider (0–100%) with real-time canvas preview.
   - Layer blending modes (Normal, Multiply, Screen, Add).
3. **Frame CRUD & Duration**:
   - Insert new frame (`Alt+N`), duplicate active frame, delete frame.
   - Inline frame duration editing in column header (e.g. 80ms, 120ms).
4. **Universal Command Pattern Undo / Redo (`UndoManager`)**:
   - Replace the legacy flat anchor history with a full Command stack:
     - `MoveAnchorCommand(frameIndex, oldAnchor, newAnchor)`
     - `EditCelCommand(layerId, frameId, oldBuffer, newBuffer)`
     - `LayerPropertyCommand(layerId, property, oldValue, newValue)`
     - `FrameDurationCommand(frameIndex, oldMs, newMs)`
     - `CropCommand(oldBounds, newBounds)`
     - `OwnershipMaskCommand(frameIndex, oldMask, newMask)`
   - Full bidirectional `Ctrl+Z` (Undo) and `Ctrl+Y` (Redo).

---

### Phase D: Aseprite-Derived Workflows
**Goal**: Complete core animation features derived from Aseprite reference audit.

1. **Linked Cels Workflow**:
   - When multiple cels are selected across frames, provide "Link Cels" command.
   - Linked cels reference the same underlying cel ID / image buffer.
   - Timeline renders a connecting link indicator bar between linked cel dots.
   - Editing any linked cel updates all linked instances; "Unlink Cel" breaks the link into a deep copy.
2. **Animation Tags & Loop Bounds**:
   - Tag Manager dialog: Add, Edit, Delete tags with `name`, `from_frame`, `to_frame`, `color`, and `direction` (forward, reverse, ping-pong).
   - Timeline tag pills display colored spans.
   - Transport player loops strictly within the active tag's frame boundaries when a tag is selected.
3. **Advanced Multi-Frame Onion Skinning**:
   - Past frames count (1–5) rendered in red tint with progressive alpha falloff.
   - Future frames count (1–5) rendered in blue tint with progressive alpha falloff.
   - Layer filter: restrict onion skinning to current active layer or composite all layers.
4. **Pixel Grid & Snapping**:
   - At zoom levels >= 4x (400%), render subtle 1px pixel grid lines matching canvas pixels.
   - Snap anchor and slice drag manipulations to integer pixel boundaries.
5. **Modal Import & Export Dialogs**:
   - `Import SpriteSheet` (`Ctrl+I`): Interactive sheet preview with draggable column/row guides and seed flood detection.
   - `Export Assets` (`Ctrl+E`): Full options dialog supporting PNG Sequence, Atlas PNG, `animation.json`, `aseprite.json`, GIF, APNG, WebP, and direct ZIP bundle download.

---

### Phase E: SpriteRepair-Specific Repair Capabilities
**Goal**: Solidify and expose SpriteRepair's proprietary Computer Vision capabilities.

1. **Ownership Mask Brush**:
   - Dedicated canvas brush tool with radius slider (1–64px) and cursor ring.
   - 4 Semantic Modes:
     - **Character Core**: Assigns pixels to character layer.
     - **VFX Component**: Assigns pixels to VFX layer.
     - **Exclude**: Marks adjacent frame overflow for elimination.
     - **Restore**: Recovers original raw pixels from source sheet seed.
   - Colorized mask overlay on canvas with instant toggle.
2. **Difference View Inspector**:
   - Compares active frame with previous frame or user-designated Reference Frame.
   - Renders difference canvas highlighting pixel delta:
     - High-contrast Cyan/Magenta flash on altered pixels.
     - Visual body center drift vector.
     - Foot anchor drift readout (`ΔX: +0px, ΔY: 0px`).
3. **Animation-Safe Autocrop**:
   - Evaluates all frames relative to their normalized foot anchors.
   - Calculates the minimum union bounding rectangle that encloses all character and VFX content across all frames.
   - Applies uniform global canvas cropping in a single click without clipping any frame.
4. **Automated Jitter & Scale QA Integration**:
   - Backend `qa.py` evaluates anchor standard deviation and aspect ratio variance.
   - Bad frames with jitter > 2px or scale variance > 5% display warning indicators directly on their Timeline frame header.
   - Right Inspector AI QA tab lists flagged frames with jump-to-frame links.

---

### Phase F: AI Vision Assist & Optimization
**Goal**: Integrate optional vision LLMs (NVIDIA Build / Kimi K3 / Gemini Flash Lite) for high-level animation QA.

1. **Contact Sheet Vision QA**:
   - Generates contact sheet of all normalized frames and queries the vision provider.
   - Parses structured JSON: overall animation continuity, foot slip detection, bad frame identification, scale outlier flags.
   - Local disk cache prevents duplicate API calls.
2. **AI Provider Management**:
   - Settings dialog to input and test NVIDIA / OpenRouter API keys.
   - Safe storage in `.env`.
   - Complete graceful offline fallback: if no API key is provided or offline, all CV heuristics and manual editor tools remain 100% operational.

---

### Phase G: Polish, Visual QA & Regression Testing
**Goal**: Comprehensive verification across viewports, user workflows, and automated test suites.

1. **Multi-Viewport Visual QA**:
   - Verify layout responsiveness and proportions at:
     - `1920 × 1080` (Full HD Desktop)
     - `1440 × 900` (MacBook / Laptop Standard)
     - `1280 × 720` (Compact Desktop)
   - Confirm canvas maintains >60% viewport area, timeline remains docked with horizontal scroll, and right inspector tabs function without layout breakage.
2. **End-to-End Workflow Regression**:
   - Import 16-frame 4×4 attack spritesheet.
   - Verify 16 frame detection, foot anchor stabilization (`stdev < 1.0px`), VFX recovery without clipping.
   - Execute manual edits: nudge anchor, paint ownership mask, edit frame duration, create animation tag.
   - Export all formats and verify ZIP bundle contents.
   - Save `.spriteproject` and reload, ensuring 100% state fidelity.
3. **Regression Test Suites**:
   - Run `test_models.py`
   - Run `test_milestone_attack_4x4.py`
   - Run `test_live_server.py`
4. **Documentation**:
   - Create final `walkthrough.md` with before/after comparisons and verification artifacts.
