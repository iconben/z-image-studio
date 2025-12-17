import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path


class TestWebServerSeedGeneration(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(self.repo_root / "src"))

    def test_web_server_seed_generation_logic(self):
        """Test that the web server generates seeds correctly when seed is None."""
        # Import the actual web server module
        try:
            from zimage.server import app
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI not available")
            return
        
        # Create a test client
        client = TestClient(app)
        
        # Mock the heavy dependencies with proper async mocks
        # Create a callable async mock that tracks invocations
        run_worker_calls = []
        
        async def mock_run_worker(func, **kwargs):
            run_worker_calls.append((func, kwargs))
            return func(**kwargs)
        
        with patch('zimage.server.generate_image') as mock_generate_image, \
             patch('zimage.server.save_image') as mock_save_image, \
             patch('zimage.server.record_generation') as mock_record_generation, \
             patch('zimage.server.run_in_worker', side_effect=mock_run_worker), \
             patch('zimage.server.cleanup_memory'):
            
            # Setup mocks
            mock_image = MagicMock()
            mock_image.width = 256
            mock_image.height = 256
            mock_generate_image.return_value = mock_image
            
            mock_path = MagicMock()
            mock_path.name = "test_image.png"
            mock_path.stat.return_value.st_size = 1024
            mock_save_image.return_value = mock_path
            
            mock_record_generation.return_value = 1
            
            # Make the request with seed=None (omit seed field to test default None behavior)
            response = client.post("/generate", json={
                "prompt": "test prompt",
                "steps": 2,
                "width": 256,
                "height": 256,
                # Omit seed field to test the default None behavior
                "precision": "q8"
            })
            
            # Verify the response
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            # The key assertion: seed should NOT be null, it should be a generated integer
            self.assertIn("seed", data, "Seed not found in response")
            self.assertIsNotNone(data["seed"], "Seed should not be null")
            self.assertIsInstance(data["seed"], int, f"Seed should be an integer, got {type(data['seed'])}")
            self.assertGreaterEqual(data["seed"], 0, "Seed should be non-negative")
            self.assertLessEqual(data["seed"], 2**31 - 1, f"Seed {data['seed']} should be within valid range")
            
            # Verify that run_in_worker was actually called (to ensure endpoint uses it)
            self.assertGreater(len(run_worker_calls), 0, "run_in_worker should have been called")
            
            # Verify that generate_image was called through run_in_worker
            self.assertEqual(len(run_worker_calls), 1, "run_in_worker should be called exactly once")
            called_func, called_kwargs = run_worker_calls[0]
            self.assertIs(called_func, mock_generate_image, "run_in_worker should call the mocked generate_image function")
            
            # Verify that generate_image was called with the generated seed (not None)
            mock_generate_image.assert_called_once()
            call_kwargs = mock_generate_image.call_args[1]
            self.assertIn("seed", call_kwargs)
            self.assertIsNotNone(call_kwargs["seed"], "generate_image should be called with non-None seed")
            self.assertIsInstance(call_kwargs["seed"], int, "generate_image seed should be an integer")
            
            # Verify that record_generation was called with the generated seed
            mock_record_generation.assert_called_once()
            call_kwargs = mock_record_generation.call_args[1]
            self.assertIn("seed", call_kwargs)
            self.assertIsNotNone(call_kwargs["seed"], "record_generation should be called with non-None seed")
            self.assertIsInstance(call_kwargs["seed"], int, "record_generation seed should be an integer")

    def test_web_server_seed_preservation(self):
        """Test that the web server preserves provided seeds."""
        try:
            from zimage.server import app
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI not available")
            return
        
        client = TestClient(app)
        
        # Create a callable async mock that tracks invocations
        run_worker_calls = []
        
        async def mock_run_worker(func, **kwargs):
            run_worker_calls.append((func, kwargs))
            return func(**kwargs)
        
        with patch('zimage.server.generate_image') as mock_generate_image, \
             patch('zimage.server.save_image') as mock_save_image, \
             patch('zimage.server.record_generation') as mock_record_generation, \
             patch('zimage.server.run_in_worker', side_effect=mock_run_worker):
            
            # Setup mocks
            mock_image = MagicMock()
            mock_image.width = 256
            mock_image.height = 256
            mock_generate_image.return_value = mock_image
            
            mock_path = MagicMock()
            mock_path.name = "test_image.png"
            mock_path.stat.return_value.st_size = 1024
            mock_save_image.return_value = mock_path
            
            mock_record_generation.return_value = 1
            
            # Test with a specific seed
            test_seed = 12345
            response = client.post("/generate", json={
                "prompt": "test prompt",
                "steps": 2,
                "width": 256,
                "height": 256,
                "seed": test_seed,  # Provide a specific seed
                "precision": "q8"
            })
            
            # Verify the response
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            # Should preserve the provided seed
            self.assertEqual(data["seed"], test_seed, "Should preserve provided seed")
            
            # Verify that run_in_worker was actually called
            self.assertGreater(len(run_worker_calls), 0, "run_in_worker should have been called")
            self.assertEqual(len(run_worker_calls), 1, "run_in_worker should be called exactly once")
            
            # Verify that generate_image was called with the provided seed through run_in_worker
            called_func, called_kwargs = run_worker_calls[0]
            self.assertIs(called_func, mock_generate_image, "run_in_worker should call the mocked generate_image function")
            self.assertEqual(called_kwargs["seed"], test_seed, "generate_image should be called with provided seed")


if __name__ == '__main__':
    unittest.main()