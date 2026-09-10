"""OpenCode provider tests (stdlib unittest, no external deps).

Run:
    .venv/Scripts/python.exe -m unittest benchmark.test_opencode -v
    .venv/Scripts/python.exe benchmark/test_opencode.py --live

Without OPENCODE_GO_API_KEY / OPENCODE_API_KEY, live call tests are skipped
and models remain IMPLEMENTED_NOT_LIVE_VERIFIED.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sprite_repair.ai_align import load_dotenv, opencode_endpoint  # noqa: E402
from sprite_repair.providers.opencode import (  # noqa: E402
    OPENCODE_VISION_CANDIDATES,
    adapter_protocol_for,
    fetch_opencode_models,
    list_opencode_models_merged,
    load_verification_state,
    opencode_complete,
    probe_opencode_json,
    probe_opencode_text,
    probe_opencode_vision,
)
from sprite_repair.providers.opencode.registry import get_registry_entry  # noqa: E402

LIVE = "--live" in sys.argv


class TestModelDiscovery(unittest.TestCase):
    def test_go_discovery(self):
        ids, err = fetch_opencode_models("https://opencode.ai/zen/go/v1")
        self.assertIsNone(err)
        self.assertGreaterEqual(len(ids), 10)
        for must in ("deepseek-flash", "deepseek-v4-flash-vision-exp", "muse-spark-1.3-contributor", "kimi-k3", "qwen3.8-flash", "mimo-v2.5", "glm-5.3-flash"):
            self.assertIn(must, ids)

    def test_console_discovery(self):
        ids, err = fetch_opencode_models("https://opencode.ai/zen/v1")
        self.assertIsNone(err)
        self.assertGreaterEqual(len(ids), 1)

    def test_merged_catalog(self):
        env = load_dotenv()
        res = list_opencode_models_merged("opencode_go", env, base_url="https://opencode.ai/zen/go/v1")
        self.assertTrue(res["ok"])
        self.assertIn("deepseek-v4-flash-vision-exp", res["models"])
        self.assertIn("muse-spark-1.3-contributor", res["models"])
        for mm in res["models_meta"]:
            self.assertIn("badges", mm)
            self.assertIn("protocol", mm)
            self.assertIn("modalities", mm)
        self.assertGreaterEqual(len(res["free_models"]), 5)
        self.assertIn("deepseek-v4-flash-free", res["free_models"])

    def test_free_models_group(self):
        env = load_dotenv()
        res = list_opencode_models_merged("opencode", env, base_url="https://opencode.ai/zen/v1")
        free = set(res["free_models"])
        self.assertIn("deepseek-v4-flash-free", free)
        self.assertIn("nemotron-3-ultra-free", free)
        self.assertIn("big-pickle", free)

    def test_model_unavailable_marked(self):
        env = load_dotenv()
        res = list_opencode_models_merged("opencode_go", env, base_url="https://opencode.ai/zen/go/v1")
        for mm in res["models_meta"]:
            if mm["id"] not in ("", ) and not mm.get("available", True):
                self.assertEqual(mm["status"], "UNAVAILABLE")
                break


class TestRegistry(unittest.TestCase):
    def test_deepseek_ids(self):
        self.assertEqual(get_registry_entry("deepseek-flash")["display"], "DeepSeek V4.1 Flash")
        self.assertEqual(get_registry_entry("deepseek-v4-flash-vision-exp")["modalities"], ["text", "image"])

    def test_muse_spark_flags(self):
        e = get_registry_entry("muse-spark-1.3-contributor")
        self.assertTrue(e["contributor"])
        self.assertTrue(e["training_allowed"])
        self.assertTrue(e["region_limited"])
        self.assertEqual(e["protocol"], "responses")

    def test_vision_candidates(self):
        for m in OPENCODE_VISION_CANDIDATES:
            self.assertIn(m, get_registry_entry(m) and OPENCODE_VISION_CANDIDATES)

    def test_no_name_heuristic_vision(self):
        e = get_registry_entry("deepseek-v4-flash")
        self.assertEqual(e["modalities"], ["text"])


class TestAdapters(unittest.TestCase):
    def test_protocol_selection(self):
        # Protocols follow the official Go endpoint table (docs/go):
        # chat: kimi-k2.6/k2.7, deepseek-*, glm-*, kimi-k3, mimo, hy...
        # responses: muse-spark-*, gpt-5.6-luna, grok-4.6
        # messages: minimax-*, qwen3.*
        self.assertEqual(adapter_protocol_for("muse-spark-1.3-contributor"), "responses")
        self.assertEqual(adapter_protocol_for("deepseek-v4-pro"), "chat")
        self.assertEqual(adapter_protocol_for("kimi-k2.6"), "chat")
        self.assertEqual(adapter_protocol_for("minimax-m3"), "messages")
        self.assertEqual(adapter_protocol_for("qwen3.8-flash"), "messages")
        self.assertEqual(adapter_protocol_for("grok-4.6"), "responses")

    def test_endpoint_resolution(self):
        env = {}
        base, key, model = opencode_endpoint("opencode_go", env)
        self.assertEqual(base, "https://opencode.ai/zen/go/v1")
        self.assertEqual(model, "deepseek-v4-flash-vision-exp")
        base2, _, model2 = opencode_endpoint("opencode", env)
        self.assertEqual(base2, "https://opencode.ai/zen/v1")
        self.assertEqual(model2, "deepseek-v4-flash-free")


class TestAuthErrorSurfacing(unittest.TestCase):
    def test_invalid_key_not_fallback_protocol_hop(self):
        # No key -> 401/403; must surface as RuntimeError, not hop protocols
        with self.assertRaises(RuntimeError) as cm:
            opencode_complete(
                base_url="https://opencode.ai/zen/go/v1",
                api_key="",
                model="deepseek-v4-flash-vision-exp",
                messages=[{"role": "user", "content": "hi"}],
                timeout=30,
            )
        self.assertRegex(str(cm.exception), r"HTTP 40[13]")


class TestLiveCalls(unittest.TestCase):
    """Skipped unless --live and keys exist. See docs/OPENCODE_MODEL_LIVE_VERIFICATION.md."""

    def _env(self) -> dict[str, str]:
        return load_dotenv()

    def _require(self, provider: str):
        env = self._env()
        spec_key = "OPENCODE_GO_API_KEY" if provider == "opencode_go" else "OPENCODE_API_KEY"
        if not LIVE or not env.get(spec_key):
            self.skipTest(f"{spec_key} not set or --live not passed (IMPLEMENTED_NOT_LIVE_VERIFIED)")

    def test_deepseek_v4_1_flash_text(self):
        self._require("opencode_go")
        r = probe_opencode_text("opencode_go", "deepseek-flash", self._env())
        self.assertTrue(r["ok"], r)

    def test_deepseek_v4_pro_text(self):
        self._require("opencode_go")
        r = probe_opencode_text("opencode_go", "deepseek-v4-pro", self._env())
        self.assertTrue(r["ok"], r)

    def test_deepseek_v4_flash_text(self):
        self._require("opencode_go")
        r = probe_opencode_text("opencode_go", "deepseek-v4-flash", self._env())
        self.assertTrue(r["ok"], r)

    def test_deepseek_v4_flash_vision_image(self):
        self._require("opencode_go")
        r = probe_opencode_vision("opencode_go", "deepseek-v4-flash-vision-exp", self._env())
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["status"], "VISION_VERIFIED")

    def test_muse_spark_1_3_text(self):
        self._require("opencode_go")
        r = probe_opencode_text("opencode_go", "muse-spark-1.3-contributor", self._env())
        self.assertTrue(r["ok"], r)

    def test_muse_spark_1_2_text(self):
        self._require("opencode_go")
        r = probe_opencode_text("opencode_go", "muse-spark-1.2-contributor", self._env())
        self.assertTrue(r["ok"], r)

    def test_vision_capability_probe_schema(self):
        self._require("opencode_go")
        for model in OPENCODE_VISION_CANDIDATES:
            with self.subTest(model=model):
                r = probe_opencode_vision("opencode_go", model, self._env())
                self.assertIn(r["status"], ("VISION_VERIFIED", "JSON_VERIFIED", "UNVERIFIED", "REGION_UNAVAILABLE", "AUTH_FAILED", "TEMPORARILY_UNAVAILABLE"))

    def test_free_models_discovery_console(self):
        self._require("opencode")
        r = probe_opencode_text("opencode", "deepseek-v4-flash-free", self._env())
        self.assertTrue(r["ok"], r)


class TestVerificationState(unittest.TestCase):
    def test_state_roundtrip(self):
        state = load_verification_state()
        self.assertIsInstance(state, dict)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *(["--verbose"] if not any(a.startswith("-") for a in sys.argv[1:]) else [])])
