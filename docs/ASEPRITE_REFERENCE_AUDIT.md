# Aseprite Reference Audit — Structural, Widget & Workflow Analysis

**Reference Target**: Aseprite v1.3.18.5 Portable (`data/gui.xml`, `data/widgets/*.xml`, `theme.xml`)  
**Audit Purpose**: Analyze the official Aseprite UI hierarchy, widget schemas, timeline interaction model, keyboard short-cuts, and workflow conventions without copying proprietary binary code or graphics, establishing the exact ergonomic baseline for SpriteRepair's Pro Mode.

---

## 1. Top-Level Workspace Hierarchy

In Aseprite, the desktop workspace strictly follows a compact, five-region layout designed to maximize canvas visibility while keeping timeline and tool parameters accessible within minimal mouse travel:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Menu Bar (File, Edit, Sprite, Layer, Frame, Select, View, Help)        │
├────────────────────────────────────────────────────────────────────────┤
│ Context Bar (Tool-specific attributes, Brush size, Tolerance, Mode)    │
├────────┬──────────────────────────────────────────────┬────────────────┤
│ Tool   │                                              │ Inspector      │
│ Rail   │               Main Canvas                    │                │
│ (28px) │         (Pan, Zoom, Pixel Grid,              │ • Properties   │
│        │          Anchor / Mask Overlays)             │ • Layers       │
│        │                                              │ • Diagnostics  │
├────────┴──────────────────────────────────────────────┴────────────────┤
│ Timeline (Tags Bar, Frame Header, Layer Rows, Cel Matrix)              │
├────────────────────────────────────────────────────────────────────────┤
│ Status Bar (Coords X, Y, Canvas WxH, Zoom %, Color Swatch, Tooltip)   │
└────────────────────────────────────────────────────────────────────────┘
```

### Proportions & Density Conventions:
- **Menu Bar**: ~24px height; standard dropdown cascading menus.
- **Context Bar**: 28–32px height; horizontally scrollable / flexing container that changes its children instantly whenever the active tool in the Tool Rail changes.
- **Tool Rail**: 28–32px width; single or double column icon rail docked to the left edge of the viewport.
- **Main Canvas**: Dominates the viewport (>60% of total window area). Supports infinite canvas panning with middle-mouse or `Space + Drag`, and smooth step zooming on mouse wheel centered at cursor.
- **Inspector Panel**: 240–280px width docked to the right, organized into dedicated vertical tabs (Properties, Layers, QA/Diagnostics).
- **Timeline**: Docked at the bottom (140–200px height default, resizable split bar).
- **Status Bar**: 22–24px height at the very bottom; displays cursor position, canvas dimensions, active cel coordinates, and tool feedback.

---

## 2. Core Functional Components & Widget Audits

### 2.1 Timeline Matrix (`data/widgets/timeline_conf.xml`)
The timeline is the heart of Aseprite's animation workflow. It is built as a strict 2D coordinate matrix:
- **Rows = Layers**: Stacking order from bottom (background) to top (foreground). Each row has:
  - Visibility Eye toggle (`👁️` / `🚫`).
  - Lock toggle (`🔒` / `🔓`).
  - Layer name (double click to rename).
  - Continuous/Linked layer status.
- **Columns = Frames**: Sequential animation steps (Frame 0, 1, 2, ... N).
  - Column Header displays frame number and duration (e.g. `80ms`).
  - Header click selects the entire frame across all layers.
- **Cells = Cels (`Cel = Layer × Frame`)**:
  - Empty Cel: Open dot / transparent slot.
  - Occupied Cel: Filled circle or miniature preview.
  - Active Cel: Blue/accent highlighted bounding outline.
  - Multi-select: Box selection across contiguous rectangular cel blocks, or Ctrl+Click additive.
- **Tags Track**: Positioned above the frame column headers.
  - Displays colored horizontal bands spanning `from_frame` to `to_frame`.
  - Double clicking tag band opens Tag Properties.
  - Clicking a tag band selects all frames within that animation segment.

### 2.2 Linked Cels (`data/widgets/cel_properties.xml`)
- **Concept**: Two or more cels across different frames that share the identical underlying image buffer.
- **Visual Representation**: A horizontal connecting bar or linked icon bridging the circular cel indicators in the timeline.
- **Workflow**:
  - Editing a linked cel modifies all linked counterparts simultaneously.
  - "Unlink Cel" creates an independent deep copy of the image buffer at that specific frame.
  - Crucial for game sprites: static shadows, looping effect overlays, and held weapon frames avoid redundant memory and duplicate edits.

### 2.3 Layer Management (`data/widgets/layer_properties.xml`)
Aseprite models layers with rich compositing metadata:
- **Layer Name**: String identifier.
- **Layer Type**: Normal image layer, Background layer, or Group.
- **Blend Mode**: Normal, Multiply, Screen, Overlay, Darken, Lighten, Color Dodge, etc.
- **Opacity**: 0 to 255 (0% to 100%).
- **Stack Operations**: Drag-and-drop layer reordering; Shift+N adds a new layer; Duplicate layer; Delete layer.

### 2.4 Frame Management (`data/widgets/frame_properties.xml`)
- **Frame Duration**: Milliseconds (default 100ms or 80ms for 12 FPS). Per-frame duration override allows custom anticipation/impact hold frames.
- **Operations**:
  - `Alt+N`: New empty frame or duplicate active frame.
  - Drag frame column header: Reorders frames horizontally.
  - Reverse frames, duplicate frames, delete frames.

### 2.5 Tag Management (`data/widgets/tag_properties.xml`)
- Fields:
  - `name`: String (e.g. `idle`, `walk`, `attack`, `hurt`, `die`).
  - `from`: Start frame index.
  - `to`: End frame index.
  - `anidir`: Animation direction (`Forward`, `Reverse`, `Ping-pong`).
  - `repeat`: Repeat loop count (`0` = infinite).
  - `color`: RGB tag banner color for visual differentiation in timeline.

### 2.6 Onion Skinning (`data/widgets/timeline_conf.xml`)
- Controls:
  - Global toggle (`F3`).
  - `Prev Frames`: Number of preceding frames rendered behind/over active cel (1–5).
  - `Next Frames`: Number of subsequent frames rendered (1–5).
  - `Opacity Base` & `Opacity Step`: Gradual alpha fade as frame distance increases.
  - `Tint Colors`: Standard red tint for past frames, blue tint for future frames.
  - `Loop within Tag`: Restricts onion skinning to current tag boundaries instead of leaking into unrelated animation clips.

### 2.7 Canvas, Zoom, Pan & Pixel Grid (`data/widgets/grid_settings.xml`)
- **Pixel Grid**: Automatic 1px grid line overlay visible when canvas zoom >= 400% (4x).
- **Tile/Frame Grid**: Configurable rectangular guide grid (e.g. 32×32, 64×64).
- **Navigation**:
  - `Space + Left Drag` or `Middle Click Drag`: Smooth pan without modifying active tool.
  - `Mouse Wheel`: Zoom centered at pointer position.
  - `1`, `2`, `3`, `4`, `5` or `Ctrl+0`: Preset zoom levels (100%, 200%, 300%, 400%, Fit Canvas).

### 2.8 Selection & Masking (`data/widgets/modify_selection.xml`)
- **Selection Types**: Rectangular marquee, Ellipse, Lasso, Magic Wand (Alpha / Color similarity).
- **Selection Operations**:
  - Add to selection (`Shift + Drag`).
  - Subtract from selection (`Alt + Drag`).
  - Intersect selection.
  - Invert selection (`Ctrl+Shift+I`).
  - Expand / Contract selection by N pixels.
  - Clear selection (`Ctrl+D`).

### 2.9 Autocrop & Canvas Resizing (`data/widgets/canvas_size.xml`, `sprite_size.xml`)
- **Trim / Autocrop**: Eliminates transparent border pixels across active frame or all frames.
- **Canvas Size**: Resizes workspace with anchor placement (Top-Left, Center, Bottom-Center, etc.).

### 2.10 Slices & Pivots (`data/widgets/slice_properties.xml`)
- **Slices**: Named 2D bounding boxes defined across frames.
- **Properties**: Name, Bounds (`x, y, w, h`), Center 9-slice guides, and Pivot (`x, y`).
- **Game Engine Value**: Used by Unity, Godot, and Unreal for weapon mount points, hitboxes, and foot placement roots.

### 2.11 Import SpriteSheet Workflow (`data/widgets/import_sprite_sheet.xml`)
- **Dialog Options**:
  - Select Source Image File.
  - Sheet Type: `Horizontal Strip`, `Vertical Strip`, or `Matrix / Rows & Columns`.
  - Frame Dimensions: `Width` × `Height` in pixels.
  - Offset & Padding: `X, Y` start offset and internal border padding.
  - Real-time Grid Preview with frame count calculation.

### 2.12 Export SpriteSheet Workflow (`data/widgets/export_sprite_sheet.xml`)
- **Layout Tabs**:
  - Sheet Type: Packed (Best fit), By Rows, By Columns.
  - Border Padding & Inner Padding.
  - Trim options: Trim individual cels vs retain uniform canvas.
- **Output Tabs**:
  - Output Image (PNG atlas).
  - JSON Data File: Hash / Array format with frame rects, durations, tags, and layer lists.
  - Split options: Split layers into separate atlases or merge composite.

---

## 3. Official Aseprite Standard Shortcuts Baseline

Aseprite keyboard shortcuts established in `gui.xml`:

| Key | Default Aseprite Action | SpriteRepair Mapping |
|---|---|---|
| `Enter` | Play / Stop animation playback | **ADOPT** (Toggle Play/Pause) |
| `Shift+Enter` | Preview animation window | **ADOPT** (Focus/Open Preview modal) |
| `Space + Drag` | Pan canvas viewport | **ADOPT** (Canvas navigation) |
| `Tab` | Show / Hide Timeline | **ADOPT** (Toggle bottom timeline) |
| `F3` | Toggle Onion Skinning | **ADOPT** (Toggle onion skin overlay) |
| `Left / Right` | Step Previous / Next Frame | **ADOPT** (Frame step) |
| `, / .` | Step Frame within Active Tag | **ADOPT** (Tag-bounded frame step) |
| `Home / End` | Jump to First / Last Frame | **ADOPT** (Boundary navigation) |
| `Shift+N` | New Layer | **ADOPT** (Create new layer) |
| `Alt+N` | New Frame | **ADOPT** (Duplicate/Insert frame) |
| `Ctrl+Z` | Undo last action | **ADOPT** (Universal command undo) |
| `Ctrl+Y` / `Ctrl+Shift+Z` | Redo last action | **ADOPT** (Universal command redo) |
| `Ctrl+I` | Import SpriteSheet dialog | **ADOPT** (Open Import dialog) |
| `Ctrl+E` | Export SpriteSheet dialog | **ADOPT** (Open Export dialog) |
| `Ctrl+S` | Save Project | **ADOPT** (Save `.spriteproject`) |
| `Ctrl+D` | Deselect all | **ADOPT** (Clear active selection) |
| `Ctrl+Shift+I` | Invert Selection | **ADOPT** (Invert mask/selection) |
| `A` | *(Aseprite: Tool)* | **SPRITE REPAIR EXTENSION**: Auto Align Root |
| `Shift+A` | *(Aseprite: None)* | **SPRITE REPAIR EXTENSION**: AI Vision Repair |
| `J` | *(Aseprite: None)* | **SPRITE REPAIR EXTENSION**: Jitter / Scale QA |
