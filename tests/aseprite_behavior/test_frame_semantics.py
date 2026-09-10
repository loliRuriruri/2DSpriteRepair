"""Semantic tests for Frame lifecycle, duplication, duration, and ordering."""
import unittest
from sprite_repair.models import Frame, Anchor, Rect, Cel, Point

class TestFrameSemantics(unittest.TestCase):
    def test_frame_creation_and_defaults(self):
        f = Frame(id=1, index=0, duration_ms=80)
        self.assertEqual(f.duration_ms, 80)
        self.assertEqual(f.index, 0)
        self.assertIsNone(f.linked_cel_id)

    def test_frame_duplication_deep_copy(self):
        f1 = Frame(id=1, index=0, duration_ms=100, anchor=Anchor(x=50, y=80), pivot=Point(x=25, y=40))
        f1_dict = f1.to_dict()
        f2 = Frame.from_dict(f1_dict)
        f2.id = 2
        f2.index = 1
        f2.anchor.x = 99
        self.assertEqual(f1.anchor.x, 50, "Mutating copy must not affect original")
        self.assertEqual(f2.anchor.x, 99)

    def test_frame_sequence_reversal(self):
        frames = [Frame(id=i, index=i, duration_ms=80 * (i + 1)) for i in range(4)]
        reversed_frames = list(reversed(frames))
        for new_idx, rf in enumerate(reversed_frames):
            rf.index = new_idx
        self.assertEqual([f.id for f in reversed_frames], [3, 2, 1, 0])
        self.assertEqual([f.index for f in reversed_frames], [0, 1, 2, 3])

if __name__ == "__main__":
    unittest.main()
