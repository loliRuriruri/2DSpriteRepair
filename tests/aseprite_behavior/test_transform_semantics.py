"""Semantic tests for transform group invariants (C2 x C2 and C4) and anchor preservation."""
import unittest
from PIL import Image

def transform_fliph(im: Image.Image, anchor: dict) -> tuple[Image.Image, dict]:
    w, h = im.size
    res = im.transpose(Image.FLIP_LEFT_RIGHT)
    new_anchor = {"x": w - 1 - anchor["x"], "y": anchor["y"]}
    assert 0 <= new_anchor["x"] < w, f"Anchor x {new_anchor['x']} out of bounds"
    assert 0 <= new_anchor["y"] < h, f"Anchor y {new_anchor['y']} out of bounds"
    return res, new_anchor

def transform_flipv(im: Image.Image, anchor: dict) -> tuple[Image.Image, dict]:
    w, h = im.size
    res = im.transpose(Image.FLIP_TOP_BOTTOM)
    new_anchor = {"x": anchor["x"], "y": h - 1 - anchor["y"]}
    assert 0 <= new_anchor["x"] < w, f"Anchor x {new_anchor['x']} out of bounds"
    assert 0 <= new_anchor["y"] < h, f"Anchor y {new_anchor['y']} out of bounds"
    return res, new_anchor

def transform_rot90(im: Image.Image, anchor: dict) -> tuple[Image.Image, dict]:
    w, h = im.size
    res = im.transpose(Image.ROTATE_270) # 90 deg clockwise
    new_anchor = {"x": h - 1 - anchor["y"], "y": anchor["x"]}
    assert 0 <= new_anchor["x"] < h, f"Anchor x {new_anchor['x']} out of bounds"
    assert 0 <= new_anchor["y"] < w, f"Anchor y {new_anchor['y']} out of bounds"
    return res, new_anchor

class TestTransformSemantics(unittest.TestCase):
    def setUp(self):
        self.w, self.h = 64, 48
        self.im0 = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        # Add distinct non-symmetric feature
        for x in range(10, 20):
            for y in range(5, 15):
                self.im0.putpixel((x, y), (x * 10, y * 10, 150, 255))
        self.anchor0 = {"x": 25, "y": 40}

    def test_fliph_twice_identity(self):
        im1, a1 = transform_fliph(self.im0, self.anchor0)
        im2, a2 = transform_fliph(im1, a1)
        self.assertEqual(a2, self.anchor0)
        self.assertEqual(im2.tobytes(), self.im0.tobytes())

    def test_flipv_twice_identity(self):
        im1, a1 = transform_flipv(self.im0, self.anchor0)
        self.assertEqual(a1["y"], self.h - 1 - 40)
        self.assertTrue(a1["y"] >= 0, "Anchor y must never be negative")
        im2, a2 = transform_flipv(im1, a1)
        self.assertEqual(a2, self.anchor0)
        self.assertEqual(im2.tobytes(), self.im0.tobytes())

    def test_rotate90_four_times_identity(self):
        im, a = self.im0, self.anchor0
        for _ in range(4):
            im, a = transform_rot90(im, a)
        self.assertEqual(a, self.anchor0)
        self.assertEqual(im.size, (self.w, self.h))
        self.assertEqual(im.tobytes(), self.im0.tobytes())

if __name__ == "__main__":
    unittest.main()
