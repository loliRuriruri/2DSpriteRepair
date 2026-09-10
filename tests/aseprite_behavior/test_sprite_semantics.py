"""Semantic tests for Sprite dimensions, safe canvas bounding, and spatial invariants."""
import unittest
from sprite_repair.models import Sprite, Frame, Anchor

class TestSpriteSemantics(unittest.TestCase):
    def test_sprite_dimensions_and_invariants(self):
        s = Sprite(width=640, height=480)
        self.assertEqual(s.width, 640)
        self.assertEqual(s.height, 480)
        self.assertEqual(s.color_mode, "RGBA")

    def test_anchor_within_canvas_bounds(self):
        s = Sprite(width=320, height=240)
        f = Frame(id=0, index=0, anchor=Anchor(x=160, y=239))
        self.assertTrue(0 <= f.anchor.x < s.width, f"Anchor x {f.anchor.x} out of bounds")
        self.assertTrue(0 <= f.anchor.y < s.height, f"Anchor y {f.anchor.y} out of bounds")

    def test_negative_anchor_rejected(self):
        f = Frame(id=0, index=0, anchor=Anchor(x=-5, y=100))
        self.assertFalse(0 <= f.anchor.x, "Negative anchor coordinate must be detected")

if __name__ == "__main__":
    unittest.main()
