"""Semantic tests for game asset export file integrity and schema validation."""
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from sprite_repair.export import export_bundle

class TestExportSemantics(unittest.TestCase):
    def test_export_animation_bundle_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            frames = [Image.new("RGBA", (64, 64), (100, i * 50, 150, 255)) for i in range(4)]
            anchors = [{"x": 32, "y": 60} for _ in range(4)]
            out_dir = tmp_path / "out"

            result_payload = {
                "source": "test_anim",
                "canvas": {"w": 64, "h": 64},
                "duration_ms": 80,
                "frames": [{"frame": i, "anchor": {"x": 32, "y": 60}, "duration": 80, "rect": {"x": 0, "y": 0, "w": 64, "h": 64}} for i in range(4)],
                "composed_frames": frames,
                "raw_frame_images": frames,
                "frame_images": frames,
            }

            out = export_bundle(result_payload, out_dir)
            self.assertTrue(out.is_dir())

            # 1. Verify PNG sequence
            frames_dir = out_dir / "frames"
            png_files = sorted(frames_dir.glob("*.png"))
            self.assertEqual(len(png_files), 4)

            # 2. Verify spritesheet
            sheet_file = out_dir / "spritesheet.png"
            self.assertTrue(sheet_file.is_file())

            # 3. Verify preview.gif
            gif_file = out_dir / "preview.gif"
            self.assertTrue(gif_file.is_file())

            # 4. Verify animation.json
            anim_json = json.loads((out_dir / "animation.json").read_text(encoding="utf-8"))
            self.assertEqual(len(anim_json["frames"]), 4)
            self.assertTrue(all(f["anchor"]["x"] == 32 for f in anim_json["frames"]))

            # 5. Verify aseprite.json
            ase_json = json.loads((out_dir / "aseprite.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ase_json["frames"]), 4)

    def test_packed_atlas_and_extrude_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            frames = [Image.new("RGBA", (32, 48), (50, 100, 150, 255)) for _ in range(6)]
            out_dir = tmp_path / "packed_out"
            result_payload = {
                "source": "packed_anim",
                "canvas": {"w": 32, "h": 48},
                "frames": [{"frame": i, "anchor": {"x": 16, "y": 48}, "duration": 80} for i in range(6)],
                "frame_images": frames,
            }
            res = export_bundle(result_payload, out_dir, pack_mode="packed", padding=4, extrude=2)
            self.assertTrue(res.is_dir())
            with Image.open(out_dir / "spritesheet.png") as sheet:
                self.assertTrue(sheet.size[0] > 0)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["meta"]["pack_mode"], "packed")
            self.assertEqual(manifest["meta"]["extrude"], 2)
            self.assertEqual(manifest["meta"]["padding"], 4)

    def test_indexed_color_quantization_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            frames = [Image.new("RGBA", (32, 32), (x * 40, y * 40, 100, 255)) for x in range(2) for y in range(2)]
            out_dir = tmp_path / "indexed_out"
            result_payload = {
                "source": "indexed_anim",
                "canvas": {"w": 32, "h": 32},
                "frames": [{"frame": i, "anchor": {"x": 16, "y": 32}, "duration": 80} for i in range(4)],
                "frame_images": frames,
            }
            res = export_bundle(result_payload, out_dir, color_mode="indexed", palette_colors=16)
            self.assertTrue(res.is_dir())
            with Image.open(out_dir / "frames" / "000.png") as f0:
                self.assertEqual(f0.size, (32, 32))

    def test_duplicate_frame_merge_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            f_unique = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
            f_dup = Image.new("RGBA", (16, 16), (255, 0, 0, 255)) # exact duplicate
            f_other = Image.new("RGBA", (16, 16), (0, 255, 0, 255))
            frames = [f_unique, f_dup, f_other]
            out_dir = tmp_path / "dup_out"
            result_payload = {
                "source": "dup_anim",
                "canvas": {"w": 16, "h": 16},
                "frames": [
                    {"frame": 0, "anchor": {"x": 8, "y": 16}, "duration": 80},
                    {"frame": 1, "anchor": {"x": 8, "y": 16}, "duration": 80},
                    {"frame": 2, "anchor": {"x": 8, "y": 16}, "duration": 80},
                ],
                "frame_images": frames,
            }
            res = export_bundle(result_payload, out_dir, merge_duplicates=True)
            self.assertTrue(res.is_dir())
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            # Frame 0 and 1 share the same rendered image, with accumulated duration
            f0 = manifest["frames"]["frame_000"]
            f1 = manifest["frames"]["frame_001"]
            self.assertEqual(f0["frame"], f1["frame"])

if __name__ == "__main__":
    unittest.main()
