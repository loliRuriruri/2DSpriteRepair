"""Invariant verification for genuine MaxRects 2D packing and Indexed Palette quantization."""
import math
import unittest
from PIL import Image, ImageDraw
from sprite_repair.export import (
    pack_rects_maxrects,
    pack_rects_shelf,
    pack_rects,
    quantize_animation_palette,
    quantize_to_indexed,
)

class TestPackingAndPaletteInvariants(unittest.TestCase):
    def setUp(self):
        self.sizes = [
            (32, 48), (64, 64), (16, 80), (50, 20),
            (120, 60), (45, 90), (30, 30), (70, 40),
            (80, 80), (15, 15), (60, 100), (40, 40),
            (90, 50), (25, 60), (55, 35), (75, 45)
        ]

    def test_maxrects_overlap_and_bounds_invariants(self):
        """Verify MaxRects guarantees: overlap == 0, out_of_bounds == 0, deterministic == True, efficiency."""
        for padding in (0, 1, 2, 4):
            w, h, positions = pack_rects_maxrects(self.sizes, padding=padding)
            self.assertEqual(len(positions), len(self.sizes))

            # 1. Out of bounds invariant
            for i, (px, py) in enumerate(positions):
                pw, ph = self.sizes[i]
                self.assertGreaterEqual(px, 0, f"Negative X at rect {i}")
                self.assertGreaterEqual(py, 0, f"Negative Y at rect {i}")
                self.assertLessEqual(px + pw + padding, w, f"Rect {i} exceeds sheet width")
                self.assertLessEqual(py + ph + padding, h, f"Rect {i} exceeds sheet height")

            # 2. Overlap invariant (pairwise overlap == 0)
            overlaps = 0
            for i in range(len(self.sizes)):
                x1, y1 = positions[i]
                w1, h1 = self.sizes[i]
                r1_right = x1 + w1 + padding
                r1_bottom = y1 + h1 + padding
                for j in range(i + 1, len(self.sizes)):
                    x2, y2 = positions[j]
                    w2, h2 = self.sizes[j]
                    r2_right = x2 + w2 + padding
                    r2_bottom = y2 + h2 + padding

                    # Check intersection
                    if not (r1_right <= x2 or r2_right <= x1 or r1_bottom <= y2 or r2_bottom <= y1):
                        overlaps += 1

            self.assertEqual(overlaps, 0, f"Found {overlaps} overlapping rectangle pairs in MaxRects packing (padding={padding})")

            # 3. Determinism invariant
            w2, h2, positions2 = pack_rects_maxrects(self.sizes, padding=padding)
            self.assertEqual((w, h), (w2, h2))
            self.assertEqual(positions, positions2)

            # 4. Packing efficiency ratio (> 0.65 for diverse sizes)
            total_rect_area = sum(rw * rh for rw, rh in self.sizes)
            sheet_area = w * h
            efficiency = total_rect_area / sheet_area
            self.assertGreater(efficiency, 0.65, f"Efficiency ratio {efficiency:.2f} is below 0.65")

    def test_algorithm_naming_and_dispatch(self):
        """Verify genuine naming: Shelf is Shelf, MaxRects is MaxRects."""
        w_mr, h_mr, pos_mr = pack_rects(self.sizes, padding=2, algorithm="maxrects")
        w_sh, h_sh, pos_sh = pack_rects(self.sizes, padding=2, algorithm="shelf")
        
        # Shelf and MaxRects produce distinct layouts
        self.assertNotEqual(pos_mr, pos_sh, "MaxRects and Shelf returned identical positions; check dispatch")

    def test_indexed_palette_invariants_16_to_256(self):
        """Verify color count <= target, alpha preservation, determinism, cross-frame palette lock for 16, 32, 64, 128, 256."""
        # Generate 16 synthetic animation frames with rich color gradients and transparent borders
        frames = []
        for fi in range(16):
            im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(im)
            # Center character blob with gradient colors
            for r in range(24, 0, -2):
                col = (int(fi * 15 + r * 8) % 256, int(r * 10) % 256, int(fi * 20 + r * 5) % 256, 255)
                draw.ellipse((32 - r, 32 - r, 32 + r, 32 + r), fill=col)
            # Add some distinct VFX sparks per frame
            draw.rectangle((10, 10, 15, 15), fill=(255, 200, fi * 15, 255))
            frames.append(im)

        targets = [16, 32, 64, 128, 256]
        for target_k in targets:
            # Test dither=none
            q_frames = quantize_animation_palette(frames, num_colors=target_k, dither="none", lock_palette=True)
            self.assertEqual(len(q_frames), 16)

            # 1. Cross-frame palette lock & color count <= target_k
            global_opaque_colors = set()
            for fi, qf in enumerate(q_frames):
                raw = frames[fi]
                raw_bytes = raw.tobytes()
                q_bytes = qf.tobytes()

                # 2. Alpha preservation: transparent pixels must remain (0, 0, 0, 0)
                for idx in range(0, len(raw_bytes), 4):
                    orig_a = raw_bytes[idx + 3]
                    if orig_a == 0:
                        self.assertEqual(q_bytes[idx:idx+4], b"\x00\x00\x00\x00", f"Frame {fi}: alpha=0 pixel not preserved as (0,0,0,0)")
                    else:
                        global_opaque_colors.add(q_bytes[idx:idx+3])

            self.assertLessEqual(len(global_opaque_colors), target_k,
                                 f"Target {target_k} exceeded: got {len(global_opaque_colors)} unique opaque colors across animation")

            # 3. Determinism: repeated quantization yields exact same byte output
            q_frames_repeat = quantize_animation_palette(frames, num_colors=target_k, dither="none", lock_palette=True)
            for fi in range(16):
                self.assertEqual(q_frames[fi].tobytes(), q_frames_repeat[fi].tobytes(),
                                 f"Quantization non-deterministic for frame {fi} at k={target_k}")

            # 4. Dither test: floyd-steinberg preserves alpha and respects <= target_k
            q_frames_fs = quantize_animation_palette(frames, num_colors=target_k, dither="floyd-steinberg", lock_palette=True)
            global_fs_colors = set()
            for fi, qf in enumerate(q_frames_fs):
                raw = frames[fi]
                raw_bytes = raw.tobytes()
                q_bytes = qf.tobytes()
                for idx in range(0, len(raw_bytes), 4):
                    orig_a = raw_bytes[idx + 3]
                    if orig_a == 0:
                        self.assertEqual(q_bytes[idx:idx+4], b"\x00\x00\x00\x00")
                    else:
                        global_fs_colors.add(q_bytes[idx:idx+3])

            self.assertLessEqual(len(global_fs_colors), target_k,
                                 f"FS Dither Target {target_k} exceeded: got {len(global_fs_colors)} unique colors")

if __name__ == "__main__":
    unittest.main()
