# UI Reconstruction Plan — Desktop Pro Mode Editor Architecture

**Target**: `app/index.html`, `app/app.css`, `app/app.js`  
**Purpose**: Complete architectural redesign of SpriteRepair's interface, migrating from a stacked web form layout into a high-density, professional desktop animation studio modeled after Aseprite while preserving and highlighting SpriteRepair's proprietary AI/CV repair capabilities.

---

## 1. Ergonomic Layout Architecture

The reconstructed UI enforces the standard 6-region desktop studio hierarchy:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. MENU BAR                                                [ Mode: Pro / Simple ] [⚙]  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. CONTEXT BAR (Tool-sensitive options, coordinates, brush size, tolerances)           │
├─────────┬──────────────────────────────────────────────────────────────┬───────────────┤
│ 3. TOOL │ 4. MAIN CANVAS VIEWPORT (Dominant Area > 60%)                │ 5. RIGHT      │
│    RAIL │                                                              │    INSPECTOR  │
│ (32px)  │    • Centered Pan & Zoom Viewport (Middle Drag / Space+Drag) │ (280px Tabs)  │
│         │    • Pixel-Crisp Rendering + Pixel Grid (>= 400%)            │               │
│ [Select]│    • Dynamic Overlays: Foot Anchor, Safe BBox, Masks         │ [ Properties] │
│ [Move]  │    • Difference View / Onion Skin Overlays                   │ [ Layers    ] │
│ [Anchor]│    • In-canvas Drag Manipulators                             │ [ AI / QA   ] │
│ [Pivot] │                                                              │               │
│ [Crop]  │                                                              │               │
│ [Mask]  │                                                              │               │
│ [Erase] │                                                              │               │
│ [Zoom]  │                                                              │               │
│ ───     │                                                              │               │
│ [AI-Aln]│                                                              │               │
│ [AI-QA] │                                                              │               │
├─────────┴──────────────────────────────────────────────────────────────┴───────────────┤
│ 6. MATRIX TIMELINE (Height: 180px, resizable)                                          │
│    • Transport Bar: |◀  ◀  ▶ [Play]  ▶  ▶|   FPS: [12]  Loop: [🔁 Loop ▼]  [+Frame]    │
│    • Animation Tags Track (Color pill bands with range selection & name edit)          │
│    • Matrix Grid: Left Fixed Layers Column (Eye, Lock, Name)                           │
│                   Right Synchronized Frames Columns (0, 1, ... 15) with Cel matrix    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 7. STATUS BAR (X: 124 Y: 89 | Canvas: 501x278 | Frame: 3/16 | Zoom: 200% | Ready)     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Dimensional Density Specifications

To eliminate excessive scrolling and provide true desktop editor ergonomics, compact sizing standards are established:

| Component | Height / Width | Padding / Margins | Typography |
|---|---|---|---|
| **Top Menu Bar** | Height: `28px` | `0 8px`, gap `4px` | `12px`, 600 weight, monospace branding |
| **Context Bar** | Height: `34px` | `0 12px`, gap `8px` | `11px` labels, `12px` inputs |
| **Tool Rail** | Width: `36px` | Vertical padding `6px`, gap `4px` | `28×28px` icon buttons |
| **Right Inspector** | Width: `280px` (fixed right) | Internal padding `10px` | `12px` headings, `11px` inputs |
| **Matrix Timeline** | Height: `190px` (docked bottom) | Internal padding `4px` | `11px` headers, `10px` cel labels |
| **Timeline Layer Row** | Height: `26px` | Left padding `6px` | `11px` font, 16px eye/lock icons |
| **Timeline Frame Cell** | Width: `28px`, Height: `26px` | Centered 8px dot | `10px` frame index, `9px` duration |
| **Status Bar** | Height: `24px` (docked bottom) | `0 12px`, flex justify | `11px` monospace info |

---

## 3. Structural Decomposition by Component

### 3.1 Top Menu Bar
Standard desktop menu bar with dropdown menus triggering core commands and modal dialogs:
- **File**:
  - `Import SpriteSheet...` (`Ctrl+I`) -> Opens Import Dialog.
  - `Open Project...` (`Ctrl+O`) -> Loads `.spriteproject`.
  - `Save Project` (`Ctrl+S`) -> Writes `.spriteproject`.
  - `Export...` (`Ctrl+E`) -> Opens Export Dialog.
  - `Exit / Reset` -> Resets workspace.
- **Edit**:
  - `Undo` (`Ctrl+Z`)
  - `Redo` (`Ctrl+Y`)
  - `Cut Cel` (`Ctrl+X`)
  - `Copy Cel` (`Ctrl+C`)
  - `Paste Cel` (`Ctrl+V`)
  - `Clear / Delete Cel` (`Del`)
- **Frame**:
  - `New Frame` (`Alt+N`)
  - `Duplicate Frame` (`Ctrl+D`)
  - `Delete Frame`
  - `Frame Properties...` (Duration editor)
  - `Reverse Frames`
- **Layer**:
  - `New Layer` (`Shift+N`)
  - `Duplicate Layer`
  - `Delete Layer`
  - `Layer Properties...` (Opacity, Blend Mode)
- **View**:
  - `Show Pixel Grid` (Toggle)
  - `Show Onion Skin` (`F3`)
  - `Show Difference View`
  - `Fit to Screen` (`Ctrl+0`)
  - `Zoom 100% / 200% / 400%`
- **AI & Repair**:
  - `Auto Grid Detect`
  - `Auto Foot Align` (`A`)
  - `AI Vision Repair` (`Shift+A`)
  - `Run Animation QA` (`J`)
  - `AI Provider Keys...`
- **Mode Switcher**:
  - Toggle button in top-right: `[ Pro Mode ]` / `[ Simple Mode ]`.

### 3.2 Dynamic Context Bar
The Context Bar sits immediately under the Menu Bar. Its contents change dynamically based on the currently active tool in the Tool Rail:

1. **When Tool = Anchor**:
   - `Type: [Foot Anchor ▼]` | `X: [ 124 ]` `Y: [ 269 ]` | `[Auto Detect]` | `[Lock Root]` | `Reference Frame: [None ▼]`
2. **When Tool = Ownership Mask Brush**:
   - `Mode: (•) Character  ( ) VFX  ( ) Exclude  ( ) Restore` | `Size: [ 8px ]` | `Falloff: [Hard ▼]` | `[Invert Mask]` | `[Clear Mask]`
3. **When Tool = Crop / Canvas**:
   - `Mode: [Animation-Safe Autocrop ▼]` | `L: [0]` `R: [0]` `T: [0]` `B: [0]` | `[Tight Crop]` | `[Safe Crop]` | `[Apply]`
4. **When Tool = Select / Move**:
   - `Selection: Rect / Lasso` | `Nudge: [←] [↑] [↓] [→]` | `[Flip H]` | `[Flip V]` | `[Center on Foot]`
5. **When Tool = Difference View**:
   - `Compare With: [Previous Frame ▼]` | `Mode: [Delta Pixels ▼]` | `Highlight: Red/Cyan` | `Drift: X: +0px, Y: 0px`

### 3.3 Left Tool Rail (36px Compact)
Vertical tool strip on the left containing 28px square icon buttons with keyboard tooltips:
- `[V]` **Select Tool** (Rectangular / Cel select)
- `[M]` **Move Tool** (Cel transform & offset)
- `[A]` **Anchor Tool** (Foot root & ground plane)
- `[P]` **Pivot / Slice Tool** (Hitboxes & weapon sockets)
- `[C]` **Crop Tool** (Canvas & safe boundaries)
- `[B]` **Ownership Mask Brush** (Character vs VFX segregation)
- `[E]` **Eraser Tool** (Alpha exclusion)
- `[D]` **Difference View Tool** (Subpixel drift inspector)
- `[Z]` **Zoom / Pan Tool**
- `───` *(Divider)*
- `[AI]` **AI Align Assist** (Vision-guided pose & grounding)
- `[QA]` **Animation QA Inspector** (Jitter & scale report)

### 3.4 Dominant Center Main Canvas (>60% Viewport Area)
The primary workspace canvas viewport:
- **Pan & Zoom**: Free pan via `Middle Click Drag` or `Space + Left Drag`; zoom centered at mouse cursor via wheel.
- **Pixel Crisp**: `image-rendering: pixelated;` at all zoom levels.
- **Pixel Grid Overlay**: At zoom >= 4x, renders a delicate 1px grid line overlay delineating individual pixel boundaries.
- **Multi-layer Composition**: Composites all visible layers according to their order, opacity, and blend modes.
- **Interactive Overlays**:
  - Red crosshair for Foot Anchor with draggable handle.
  - Safe global canvas boundary outline.
  - Ownership mask color tint (Green = Character, Blue = VFX, Red = Excluded).
  - Onion skin overlays (Previous = Red tint, Future = Blue tint).
  - Difference delta pixels (High-contrast cyan/magenta flash on changed pixels).

### 3.5 Right Inspector (280px with Tabbed Navigation)
A dedicated property panel with 3 permanent tabs:

#### Tab 1: Properties
- **Cel Properties**: Local Cel `(x, y)` position, Opacity (0–100%), Linked Cel status (`Linked to Frame X` / `Unlink`).
- **Frame Properties**: Frame Index, Duration (ms), Nominal Rect, Content BBox, Character BBox, VFX BBox.
- **Sprite Properties**: Global Canvas Dimensions (`501 × 278`), Color Depth, Frame Count (`16`).

#### Tab 2: Layers
- Vertical layer stack list with drag handle for reordering.
- Eye (visibility) and Padlock (lock) toggles.
- Layer Name with inline rename.
- Opacity range slider (0%–100%) and Blend Mode dropdown (Normal, Multiply, Screen, Add).
- Add Layer (`+`) and Delete Layer (`-`) buttons.

#### Tab 3: AI Diagnostics & QA
- **Jitter Diagnostics**: Root anchor standard deviation, Body center drift status (`Stable / Review / Critical`).
- **Scale Consistency**: Sequence median height comparison, per-frame variance percentage.
- **VFX Overflow**: Adjacent boundary clipping check.
- **AI Vision QA**: Contact sheet overview analysis button, structured confidence score, pose continuity rating, and detected anomalies list.

### 3.6 Bottom Matrix Timeline (190px Docked)
The core animation sequencer:
1. **Transport Bar**:
   - `|◀` First Frame, `◀` Prev Frame, `▶ Play / ⏸ Pause`, `▶` Next Frame, `▶|` Last Frame.
   - FPS number input (`12` default), Loop mode dropdown (`Loop`, `Ping-pong`, `Once`).
   - `+ Frame`, `Duplicate Frame`, `Delete Frame`.
   - `Onion Skin` toggle with past/future frame inputs.
2. **Animation Tags Track**:
   - Visual colored horizontal ribbons across frame indices (e.g. `Idle [0-3]`, `Attack [4-9]`, `Recovery [10-15]`).
   - Clicking tag activates loop bounds. Double clicking opens Tag Edit modal.
3. **Matrix Grid**:
   - **Left Column (Fixed)**: Layer labels with visibility/lock indicators.
   - **Right Area (Horizontally Scrollable)**:
     - Top row: Frame column headers with frame indices (`0`, `1`, `2`...) and duration badges (`80ms`).
     - Matrix rows: 2D Cel matrix (`Layer × Frame`). Each cell indicates empty slot (`·`), occupied cel (`■`), linked cel (`🔗`), or active selection (`[■]`).
   - Synchronized scrolling ensures layer names stay anchored on the left while frame columns scroll horizontally.

### 3.7 Bottom Status Bar (24px)
- Cursor position `(X, Y)`.
- Global canvas dimensions (`501 × 278 px`).
- Active frame / cel indicator (`Frame 3/16, Layer: Character`).
- Zoom factor (`200%`).
- System status / feedback (`Ready`, `Anchor updated`, `Auto-aligned 16 frames`).

---

## 4. Modal Dialogs Architecture

To prevent left-sidebar bloat, complex multi-step workflows are moved to clean modal dialogs:
1. **Import SpriteSheet Dialog (`Ctrl+I`)**:
   - Interactive preview of source sheet with overlay grid lines.
   - Columns, Rows, Cell Width, Cell Height, Padding, and Offset controls.
   - Auto Grid Seed detection button.
2. **Export Game Assets Dialog (`Ctrl+E`)**:
   - Checkboxes for export formats: PNG Sequence, SpriteSheet Atlas, `animation.json`, `aseprite.json`, GIF, APNG, WebP.
   - Options: Power of Two sizing, Trim transparent pixels, Per-layer split.
   - Direct ZIP download or single-file downloads.
3. **AI Settings & API Keys Dialog**:
   - Provider selection (NVIDIA Build / OpenRouter).
   - API Key input fields with secure local `.env` persistence.
   - Vision model selector (Kimi K3 / Gemini Flash Lite).
