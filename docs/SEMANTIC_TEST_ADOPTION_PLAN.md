# SpriteRepair — Semantic Test Adoption Plan & Invariant Oracle Specification

**Target Suite**: `tests/aseprite_behavior/` & `scratch/run_semantic_suite.js`  
**Philosophy**: Reject superficial pass criteria (e.g. "function executed without throwing", "HTTP 200", "file was written"). A test passes **if and only if** mathematical invariants hold, pixel buffers match bit-for-bit, and state is preserved losslessly across roundtrips.

---

## 1. Mathematical Invariant Axioms

Every operation in SpriteRepair must satisfy strict spatial and algebraic axioms:

1. **Spatial Bounding Axiom**:
   - For all frames $f$: $0 \le \text{anchor}_f.x < \text{width}_f$, and $0 \le \text{anchor}_f.y < \text{height}_f$.
   - For all frames $f$: $0 \le \text{pivot}_f.x < \text{width}_f$, and $0 \le \text{pivot}_f.y < \text{height}_f$.
   - Any transformation resulting in a negative coordinate or out-of-bounds position is an immediate invariant failure.

2. **Group Theory Transform Symmetries**:
   - **Horizontal Reflection** ($R_h \in C_2$):
     $R_h \circ R_h = I \implies \text{pixels}(R_h(R_h(I))) \equiv \text{pixels}(I)$  
     $\text{anchor.x} \mapsto W - 1 - x \mapsto W - 1 - (W - 1 - x) = x$
   - **Vertical Reflection** ($R_v \in C_2$):
     $R_v \circ R_v = I \implies \text{pixels}(R_v(R_v(I))) \equiv \text{pixels}(I)$  
     $\text{anchor.y} \mapsto H - 1 - y \mapsto H - 1 - (H - 1 - y) = y$
   - **90° Clockwise Rotation** ($R_{90} \in C_4$):
     $R_{90}^4 = I \implies \text{pixels}(R_{90}^4(I)) \equiv \text{pixels}(I)$  
     $(x, y) \mapsto (H - 1 - y, x) \mapsto (W - 1 - x, H - 1 - y) \mapsto (y, W - 1 - x) \mapsto (x, y)$

3. **Linked Cel Mutation & Decoupling Axioms**:
   - **Propagation**:
     $\text{link}(C_a, C_b) \implies \left( \Delta(C_a) \implies \text{pixels}(C_b) \equiv \text{pixels}(C_a) \right)$
   - **Isolation**:
     $\text{unlink}(C_b) \implies \left( \Delta(C_a) \implies \text{pixels}(C_b) \equiv \text{pixels}_{\text{pre}}(C_b) \neq \text{pixels}(C_a) \right)$

4. **10-Item Persistence Lossless Roundtrip Axiom**:
   $$\text{State}_{\text{original}} \xrightarrow{\text{Save}} \text{Disk} \xrightarrow{\text{Purge Memory}} \emptyset \xrightarrow{\text{Load}} \text{State}_{\text{loaded}} \implies \text{DeepEqual}(\text{State}_{\text{original}}, \text{State}_{\text{loaded}}) \equiv \text{True}$$
   Fields audited: `anchors`, `pivots`, `layers`, `linked_cel_ids`, `tags`, `durations`, `ownership_masks`, `canvas`, `crops`, `cels`.

---

## 2. Directory Structure for `tests/aseprite_behavior/`

```text
tests/
  aseprite_behavior/
    __init__.py
    conftest.py
    test_sprite_semantics.py
    test_frame_semantics.py
    test_layer_semantics.py
    test_cel_semantics.py
    test_linked_cel_semantics.py
    test_transform_semantics.py
    test_selection_semantics.py
    test_undo_semantics.py
    test_export_semantics.py
    test_palette_semantics.py
```

---

## 3. Test Specification Breakdown

| Module | Core Assertions & Semantic Verification |
|---|---|
| `test_sprite_semantics.py` | Validates sprite dimensioning, safe canvas expansion bounds, and anchor coordinate limits. |
| `test_frame_semantics.py` | Validates insertion, duplication, deletion, index renumbering, and sequence reversal. |
| `test_layer_semantics.py` | Validates layer tree hierarchy, parent-child inheritance of visibility/opacity, and blend modes. |
| `test_cel_semantics.py` | Validates cel bounds, empty cel clearing to alpha 0, copy/paste exact pixel buffer matches. |
| `test_linked_cel_semantics.py` | Validates shared mutation propagation and deep clone isolation on unlinking. |
| `test_transform_semantics.py` | Validates $C_2 \times C_2$ and $C_4$ pixel buffer identities and spatial boundary assertions. |
| `test_selection_semantics.py` | Validates boolean ops (Union, Difference, Intersection) and hard-edge pixel isolation. |
| `test_undo_semantics.py` | Validates exact state reversion across 10 actions (transform, layer, anchor, mask). |
| `test_export_semantics.py` | Reads exported disk files; asserts frame counts, durations, and metadata schemas. |
| `test_palette_semantics.py` | Validates color quantization, dithering accuracy, and key color preservation. |
