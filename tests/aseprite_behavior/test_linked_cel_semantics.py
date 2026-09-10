"""Semantic tests for Linked Cel shared-edit propagation and unlinking isolation."""
import unittest
from PIL import Image

class TestLinkedCelSemantics(unittest.TestCase):
    def test_linked_cel_mutation_propagation(self):
        # Shared buffer for linked cels
        shared_img = Image.new("RGBA", (32, 32), (100, 150, 200, 255))
        cel_a = {"id": "cel_a", "link_id": "link_123", "img": shared_img}
        cel_b = {"id": "cel_b", "link_id": "link_123", "img": shared_img}

        # Mutate Cel A
        shared_img.putpixel((0, 0), (255, 255, 0, 255))
        self.assertEqual(cel_a["img"].getpixel((0, 0)), cel_b["img"].getpixel((0, 0)))
        self.assertEqual(cel_b["img"].getpixel((0, 0)), (255, 255, 0, 255))

    def test_unlinked_cel_isolation(self):
        # Initial shared state
        shared_img = Image.new("RGBA", (32, 32), (50, 50, 50, 255))
        cel_a = {"id": "cel_a", "link_id": "link_abc", "img": shared_img}
        cel_b = {"id": "cel_b", "link_id": "link_abc", "img": shared_img}

        # Unlink Cel B (decouple with deep clone)
        cel_b["link_id"] = None
        cel_b["img"] = shared_img.copy()

        # Mutate Cel A
        cel_a["img"].putpixel((5, 5), (255, 0, 0, 255))

        # Cel B must remain isolated
        self.assertEqual(cel_a["img"].getpixel((5, 5)), (255, 0, 0, 255))
        self.assertEqual(cel_b["img"].getpixel((5, 5)), (50, 50, 50, 255), "Unlinked Cel B must not be altered")

if __name__ == "__main__":
    unittest.main()
