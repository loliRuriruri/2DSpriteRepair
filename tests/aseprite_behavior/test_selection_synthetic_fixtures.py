"""Deterministic synthetic fixture verification for Selection algorithms:
Magic Wand, Color Range, Lasso, and Polygon.
Asserts exact expected mask, pixel count, bounding box, and SHA-256 hash.
"""

import hashlib
import unittest
from PIL import Image, ImageDraw


def color_diff(r1: int, g1: int, b1: int, a1: int, r2: int, g2: int, b2: int, a2: int) -> int:
    if a1 < 10 and a2 < 10:
        return 0
    if (a1 < 10) != (a2 < 10):
        return 255
    return max(abs(r1 - r2), abs(g1 - g2), abs(b1 - b2), abs(a1 - a2))


def magic_wand_select(img: Image.Image, start_x: int, start_y: int, tolerance: int = 0) -> bytearray:
    """4-way BFS flood fill matching SpriteRepair app.js selection engine."""
    w, h = img.size
    data = img.tobytes()
    s_idx = (start_y * w + start_x) * 4
    sr, sg, sb, sa = data[s_idx], data[s_idx + 1], data[s_idx + 2], data[s_idx + 3]

    mask = bytearray(w * h)
    visited = bytearray(w * h)
    queue = [(start_x, start_y)]
    visited[start_y * w + start_x] = 1

    head = 0
    while head < len(queue):
        x, y = queue[head]
        head += 1
        mask[y * w + x] = 1

        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h:
                npos = ny * w + nx
                if not visited[npos]:
                    visited[npos] = 1
                    idx = npos * 4
                    diff = color_diff(sr, sg, sb, sa, data[idx], data[idx + 1], data[idx + 2], data[idx + 3])
                    if diff <= tolerance:
                        queue.append((nx, ny))
    return mask


def color_range_select(img: Image.Image, start_x: int, start_y: int, tolerance: int = 0) -> bytearray:
    """Full frame color range scan matching SpriteRepair app.js selection engine."""
    w, h = img.size
    data = img.tobytes()
    s_idx = (start_y * w + start_x) * 4
    sr, sg, sb, sa = data[s_idx], data[s_idx + 1], data[s_idx + 2], data[s_idx + 3]

    mask = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            diff = color_diff(sr, sg, sb, sa, data[idx], data[idx + 1], data[idx + 2], data[idx + 3])
            if diff <= tolerance:
                mask[y * w + x] = 1
    return mask


def polygon_rasterize_mask(w: int, h: int, points: list[tuple[int, int]]) -> bytearray:
    """Polygon rasterization matching HTML5 Canvas fill path used in app.js."""
    canvas = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(canvas)
    draw.polygon(points, fill=255)
    raw = canvas.tobytes()
    return bytearray(1 if b > 128 else 0 for b in raw)


class TestSelectionSyntheticFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Create a 64x64 deterministic synthetic test fixture image:
        - Quad 1 (0..31, 0..31): Solid Red (255, 0, 0, 255)
        - Quad 2 (32..63, 0..31): Solid Blue (0, 0, 255, 255) with 4 Green noise pixels
        - Quad 3 (0..31, 32..63): Gradient ramp (gray 100 to 200)
        - Quad 4 (32..63, 32..63): White circle (radius 12, center 48, 48) on transparent (0, 0, 0, 0)
        """
        cls.w = 64
        cls.h = 64
        cls.fixture = Image.new("RGBA", (cls.w, cls.h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(cls.fixture)

        # Quad 1: Solid Red
        draw.rectangle((0, 0, 31, 31), fill=(255, 0, 0, 255))

        # Quad 2: Solid Blue
        draw.rectangle((32, 0, 63, 31), fill=(0, 0, 255, 255))
        # 4 Green noise pixels in Quad 2
        cls.noise_pts = [(35, 5), (40, 10), (50, 20), (60, 25)]
        for px, py in cls.noise_pts:
            cls.fixture.putpixel((px, py), (0, 255, 0, 255))

        # Quad 3: Gray Gradient
        for y in range(32, 64):
            val = int(100 + (y - 32) * (100 / 31))
            for x in range(32):
                cls.fixture.putpixel((x, y), (val, val, val, 255))

        # Quad 4: White Circle on Transparent
        draw.ellipse((48 - 12, 48 - 12, 48 + 12, 48 + 12), fill=(255, 255, 255, 255))

    def test_magic_wand_quad1_solid(self):
        """Magic Wand on Quad 1 solid red must select exactly 1024 contiguous pixels."""
        mask = magic_wand_select(self.fixture, 10, 10, tolerance=0)
        count = sum(mask)
        mask_hash = hashlib.sha256(mask).hexdigest()

        # Quad 1: exactly 32x32 = 1024 pixels
        self.assertEqual(count, 1024)
        self.assertEqual(mask_hash, "82b1d07c4604244329b5d0fa3c098f267ccbc182a2de111cebecdec6e8a64f30")

        # Verify boundaries: must be strictly inside x < 32 and y < 32
        for y in range(self.h):
            for x in range(self.w):
                val = mask[y * self.w + x]
                if x < 32 and y < 32:
                    self.assertEqual(val, 1)
                else:
                    self.assertEqual(val, 0)

    def test_magic_wand_quad4_circle(self):
        """Magic Wand inside Quad 4 circle must select exactly 489 circle raster pixels."""
        mask = magic_wand_select(self.fixture, 48, 48, tolerance=0)
        count = sum(mask)
        mask_hash = hashlib.sha256(mask).hexdigest()

        self.assertEqual(count, 489)
        self.assertEqual(mask_hash, "5f415420263a6f959ece93978ef685bdd087229855974519682a20a4ad6dcc94")

        # Ensure all selected pixels are inside Quad 4
        for y in range(self.h):
            for x in range(self.w):
                if mask[y * self.w + x]:
                    self.assertGreaterEqual(x, 32)
                    self.assertGreaterEqual(y, 32)

    def test_color_range_isolated_pixels(self):
        """Color Range targeting Green (0, 255, 0, 255) must find exactly the 4 noise pixels."""
        mask = color_range_select(self.fixture, 35, 5, tolerance=0)
        count = sum(mask)
        mask_hash = hashlib.sha256(mask).hexdigest()

        self.assertEqual(count, 4)
        self.assertEqual(mask_hash, "20a3bb7dd6124ff709259fc7b05d5bf01e732b9f2388d7da58705c8fc7fdb7b1")

        # Verify exact coordinates
        found_pts = [(x, y) for y in range(self.h) for x in range(self.w) if mask[y * self.w + x]]
        self.assertEqual(sorted(found_pts), sorted(self.noise_pts))

    def test_polygon_rasterization_invariants(self):
        """Polygon selection of a fixed triangle [(10, 10), (50, 10), (30, 40)]."""
        pts = [(10, 10), (50, 10), (30, 40)]
        mask = polygon_rasterize_mask(self.w, self.h, pts)
        count = sum(mask)
        mask_hash = hashlib.sha256(mask).hexdigest()

        self.assertEqual(count, 651)
        self.assertEqual(mask_hash, "4f7bf0fe89b5e92ca99cabcb819be63aa54a797b1646c95270e79a69aee79f1e")

    def test_lasso_closed_loop_invariants(self):
        """Lasso selection of a diamond loop [(32, 10), (54, 32), (32, 54), (10, 32), (32, 10)]."""
        pts = [(32, 10), (54, 32), (32, 54), (10, 32), (32, 10)]
        mask = polygon_rasterize_mask(self.w, self.h, pts)
        count = sum(mask)
        mask_hash = hashlib.sha256(mask).hexdigest()

        self.assertEqual(count, 1013)
        self.assertEqual(mask_hash, "f7bf7e0d03f791ef681f593be48c65fee5aea9f5a21e45c248bfb683c42dca68")


if __name__ == "__main__":
    unittest.main()
