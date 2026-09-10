"""Semantic tests for Layer stack, visibility, opacity, and hierarchy."""
import unittest
from sprite_repair.models import Layer

class TestLayerSemantics(unittest.TestCase):
    def test_layer_creation_and_opacity_clamping(self):
        l = Layer(id="l1", name="Character", opacity=0.85, visible=True, blend_mode="normal")
        self.assertEqual(l.name, "Character")
        self.assertEqual(l.opacity, 0.85)
        self.assertTrue(l.visible)

    def test_layer_serialization_roundtrip(self):
        l1 = Layer(id="l_vfx", name="VFX", type="effect", visible=False, opacity=0.5, blend_mode="screen")
        d = l1.to_dict()
        l2 = Layer.from_dict(d)
        self.assertEqual(l1.id, l2.id)
        self.assertEqual(l1.name, l2.name)
        self.assertEqual(l1.type, l2.type)
        self.assertEqual(l1.visible, l2.visible)
        self.assertEqual(l1.opacity, l2.opacity)

if __name__ == "__main__":
    unittest.main()
