"""Tests for the disable_history option (issue #94).

Covers the three layers the option touches:
* paths.history_disabled() resolution (env var > config file)
* storage.record_generation() no-op behavior
* the /history endpoint returning an empty list when disabled
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path


class TestHistoryDisabledResolution(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(self.repo_root / "src"))
        from zimage import paths
        self.paths = paths

    def test_default_is_enabled(self):
        with patch.dict("os.environ", {}, clear=True), \
             patch.object(self.paths, "load_config", return_value={}):
            self.assertFalse(self.paths.history_disabled())

    def test_config_file_enables(self):
        with patch.dict("os.environ", {}, clear=True), \
             patch.object(self.paths, "load_config", return_value={"disable_history": True}):
            self.assertTrue(self.paths.history_disabled())

    def test_env_var_overrides_config(self):
        with patch.dict("os.environ", {"ZIMAGE_DISABLE_HISTORY": "1"}, clear=True), \
             patch.object(self.paths, "load_config", return_value={"disable_history": False}):
            self.assertTrue(self.paths.history_disabled())

    def test_env_var_falsy_values(self):
        for value in ("0", "false", "no", "off"):
            with self.subTest(value=value), \
                 patch.dict("os.environ", {"ZIMAGE_DISABLE_HISTORY": value}, clear=True), \
                 patch.object(self.paths, "load_config", return_value={}):
                self.assertFalse(self.paths.history_disabled())


class TestRecordGenerationNoop(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(self.repo_root / "src"))
        from zimage import storage
        self.storage = storage

    def test_record_generation_skips_db_when_disabled(self):
        with patch("zimage.storage.history_disabled", return_value=True), \
             patch("zimage.storage.db") as mock_db:
            result = self.storage.record_generation(
                prompt="p", steps=1, width=64, height=64, filename="f.png",
                generation_time=1.0, file_size_kb=1.0, model="m",
                precision="q8", seed=1,
            )
            self.assertIsNone(result)
            mock_db.add_generation.assert_not_called()

    def test_record_generation_writes_when_enabled(self):
        with patch("zimage.storage.history_disabled", return_value=False), \
             patch("zimage.storage.db") as mock_db:
            mock_db.add_generation.return_value = 7
            result = self.storage.record_generation(
                prompt="p", steps=1, width=64, height=64, filename="f.png",
                generation_time=1.0, file_size_kb=1.0, model="m",
                precision="q8", seed=1,
            )
            self.assertEqual(result, 7)
            mock_db.add_generation.assert_called_once()


class TestHistoryEndpointDisabled(unittest.TestCase):
    def test_history_returns_empty_when_disabled(self):
        try:
            from zimage.server import app
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI not available")
            return

        client = TestClient(app)

        with patch("zimage.paths.history_disabled", return_value=True):
            response = client.get("/history?limit=20&offset=0")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        self.assertEqual(response.headers.get("X-Total-Count"), "0")

    def test_models_endpoint_exposes_flag(self):
        try:
            from zimage.server import app
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI not available")
            return

        client = TestClient(app)
        with patch("zimage.paths.history_disabled", return_value=True), \
             patch("zimage.server.get_available_models", return_value={"models": [], "device": "CPU"}):
            response = client.get("/models")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["constraints"]["disable_history"])


if __name__ == "__main__":
    unittest.main()
