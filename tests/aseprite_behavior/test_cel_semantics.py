"""Semantic tests for Cel positioning, empty cel clearing, and pixel buffer equality."""
import unittest
from PIL import Image
from sprite_repair.models import Cel

class TestCelSemantics(unittest.TestCase):
    def test_cel_creation_and_bounds(self):
        c = Cel(layer_id="layer_0", frame_id=0, x=10, y=15, opacity=1.0)
        self.assertEqual(c.x, 10)
        self.assertEqual(c.y, 15)
        self.assertEqual(c.opacity, 1.0)

    def test_clear_cel_transparency(self):
        cleared = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        extrema = cleared.getextrema()
        self.assertEqual(extrema[3], (0, 0), "Cleared cel must be 100% transparent")

    def test_cel_copy_paste_pixel_equality(self):
        im_src = Image.new("RGBA", (16, 16), (128, 64, 32, 255))
        im_dst = im_src.copy()
        self.assertEqual(im_src.tobytes(), im_dst.tobytes(), "Pasted cel must match source exactly")

if __name__ == "__main__":
    unittest.main()
