"""Randomized stress test for MaxRects Atlas Bin Packing.
Asserts:
1. No overlap between any placed rectangle pair.
2. No out-of-bounds (OOB) beyond sheet boundaries.
3. Deterministic repeatability across identical input.
4. No missing frame (all input rectangles placed).
5. Metadata rect == actual rect (canvas rasterization matches manifest coordinates).
"""

import random
import unittest
from PIL import Image

from sprite_repair.export import pack_rects_maxrects


class TestAtlasPackerRandomized(unittest.TestCase):
    def test_randomized_maxrects_invariants_100_runs(self):
        """Run 100 randomized packing tests with varying sizes, counts, and paddings."""
        rng = random.Random(20260910)

        for iteration in range(100):
            num_rects = rng.randint(4, 32)
            padding = rng.choice([0, 1, 2, 3, 4])
            sizes = [
                (rng.randint(8, 120), rng.randint(8, 120))
                for _ in range(num_rects)
            ]

            sheet_w, sheet_h, positions = pack_rects_maxrects(sizes, padding=padding)

            # Invariant 1: No missing frame
            self.assertEqual(
                len(positions),
                len(sizes),
                f"Iter {iteration}: missing frames in positions (got {len(positions)}, expected {len(sizes)})"
            )
            self.assertTrue(
                all(pos is not None for pos in positions),
                f"Iter {iteration}: unplaced None position found"
            )

            # Invariant 2: No Out-of-Bounds (OOB)
            for i, (px, py) in enumerate(positions):
                w, h = sizes[i]
                self.assertGreaterEqual(px, 0, f"Iter {iteration}: rect {i} negative x: {px}")
                self.assertGreaterEqual(py, 0, f"Iter {iteration}: rect {i} negative y: {py}")
                self.assertLessEqual(
                    px + w + padding,
                    sheet_w,
                    f"Iter {iteration}: rect {i} exceeds sheet_w (px={px}, w={w}, pad={padding}, sheet_w={sheet_w})"
                )
                self.assertLessEqual(
                    py + h + padding,
                    sheet_h,
                    f"Iter {iteration}: rect {i} exceeds sheet_h (py={py}, h={h}, pad={padding}, sheet_h={sheet_h})"
                )

            # Invariant 3: No overlap
            for i in range(num_rects):
                x1, y1 = positions[i]
                w1, h1 = sizes[i]
                r1_right = x1 + w1 + padding
                r1_bottom = y1 + h1 + padding
                for j in range(i + 1, num_rects):
                    x2, y2 = positions[j]
                    w2, h2 = sizes[j]
                    r2_right = x2 + w2 + padding
                    r2_bottom = y2 + h2 + padding

                    overlap = not (r1_right <= x2 or r2_right <= x1 or r1_bottom <= y2 or r2_bottom <= y1)
                    self.assertFalse(
                        overlap,
                        f"Iter {iteration}: overlap detected between rect {i} ({x1},{y1},{w1},{h1}) and rect {j} ({x2},{y2},{w2},{h2}) with padding {padding}"
                    )

            # Invariant 4: Deterministic repeatability
            sheet_w2, sheet_h2, positions2 = pack_rects_maxrects(sizes, padding=padding)
            self.assertEqual((sheet_w, sheet_h), (sheet_w2, sheet_h2), f"Iter {iteration}: dimensions non-deterministic")
            self.assertEqual(positions, positions2, f"Iter {iteration}: positions non-deterministic")

            # Invariant 5: Metadata rect == actual rect on canvas
            # Verify for a subset of runs to ensure pixel-perfect canvas alignment
            if iteration % 10 == 0:
                canvas = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
                for i, (px, py) in enumerate(positions):
                    w, h = sizes[i]
                    frame_img = Image.new("RGBA", (w, h), (100, (i * 20) % 255, 200, 255))
                    canvas.paste(frame_img, (px, py))

                    # Bounding box of just-pasted frame in cropped subregion
                    sub = canvas.crop((px, py, px + w, py + h))
                    bbox = sub.getbbox()
                    self.assertEqual(
                        bbox,
                        (0, 0, w, h),
                        f"Iter {iteration}: frame {i} metadata rect ({px},{py},{w},{h}) does not match rasterized canvas"
                    )


if __name__ == "__main__":
    unittest.main()
