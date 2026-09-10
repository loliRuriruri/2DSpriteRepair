"""Semantic tests for Palette consistency, histogram calculation, and color drift detection."""
import unittest
from PIL import Image
from sprite_repair.qa import compute_frame_color_histogram, check_palette_consistency

class TestPaletteSemantics(unittest.TestCase):
    def test_color_histogram_uniformity(self):
        im = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
        hist = compute_frame_color_histogram(im)
        self.assertAlmostEqual(sum(hist), 1.0, places=3)

    def test_palette_drift_detection(self):
        f1 = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
        f2 = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
        f3 = Image.new("RGBA", (32, 32), (0, 255, 0, 255))

        warns = check_palette_consistency([f1, f2, f3], threshold=0.28)
        self.assertTrue(any(w.get("frame") == 2 for w in warns), "Frame 2 (green) must be flagged for palette drift")

if __name__ == "__main__":
    unittest.main()
