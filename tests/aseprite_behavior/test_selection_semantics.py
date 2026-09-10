"""Semantic tests for 2D Selection Mask boolean operations and hard pixel boundaries."""
import unittest

def rect_mask(w: int, h: int, x0: int, y0: int, x1: int, y1: int) -> set[tuple[int, int]]:
    return {(x, y) for x in range(x0, x1) for y in range(y0, y1) if 0 <= x < w and 0 <= y < h}

class TestSelectionSemantics(unittest.TestCase):
    def test_selection_union(self):
        m1 = rect_mask(32, 32, 0, 0, 10, 10)
        m2 = rect_mask(32, 32, 5, 5, 15, 15)
        union = m1 | m2
        self.assertEqual(len(union), 100 + 100 - 25) # 175 pixels

    def test_selection_difference(self):
        m1 = rect_mask(32, 32, 0, 0, 10, 10)
        m2 = rect_mask(32, 32, 5, 0, 10, 10)
        diff = m1 - m2
        self.assertEqual(len(diff), 50)
        self.assertTrue(all(p[0] < 5 for p in diff))

    def test_selection_intersection(self):
        m1 = rect_mask(32, 32, 0, 0, 10, 10)
        m2 = rect_mask(32, 32, 5, 5, 15, 15)
        intersect = m1 & m2
        self.assertEqual(len(intersect), 25)

if __name__ == "__main__":
    unittest.main()
