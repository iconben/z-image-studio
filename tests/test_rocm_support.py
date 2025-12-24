
import sys
import unittest
from unittest.mock import patch, MagicMock
import torch

# Mock torch.version if it doesn't exist or isn't what we want
if not hasattr(torch, "version"):
    torch.version = MagicMock()

from zimage.hardware import detect_device, get_available_models, should_enable_attention_slicing
from zimage.engine import is_torch_compile_safe, load_pipeline

class TestROCmSupport(unittest.TestCase):

    @patch("torch.version.hip", "6.1", create=True)
    @patch("torch.cuda.is_available", return_value=True)
    @patch("torch.backends.mps.is_available", return_value=False)
    def test_detect_device_rocm(self, mock_mps, mock_cuda):
        # Ensure detect_device returns "rocm" when hip is present and cuda is available
        device = detect_device()
        self.assertEqual(device, "rocm")

    @patch("torch.version.hip", "6.1", create=True)
    @patch("torch.cuda.is_available", return_value=False)
    @patch("torch.backends.mps.is_available", return_value=False)
    def test_detect_device_rocm_no_gpu(self, mock_mps, mock_cuda):
        # Ensure detect_device returns "cpu" when hip is present but cuda is NOT available
        device = detect_device()
        self.assertEqual(device, "cpu")

    @patch("zimage.hardware.detect_device", return_value="rocm")
    @patch("zimage.hardware.get_vram_gb", return_value=16.0)
    @patch("zimage.hardware.has_sdnq", return_value=True)
    def test_get_available_models_rocm(self, mock_sdnq, mock_vram, mock_detect):
        # Test model recommendations for ROCm with 16GB VRAM
        models = get_available_models()
        self.assertEqual(models["device"], "rocm")
        # 16GB VRAM -> full recommended
        full_model = next(m for m in models["models"] if m["id"] == "full")
        self.assertTrue(full_model["recommended"])

    @patch("zimage.engine.detect_device", return_value="rocm")
    def test_is_torch_compile_safe_rocm(self, mock_detect):
        # Should be False by default for ROCm
        self.assertFalse(is_torch_compile_safe())

    @patch("zimage.engine.detect_device", return_value="rocm")
    @patch("zimage.engine.os.getenv", return_value="1")
    def test_is_torch_compile_safe_rocm_forced(self, mock_env, mock_detect):
        # Should be True if forced via env var
        self.assertTrue(is_torch_compile_safe())

    @patch("zimage.hardware.detect_device", return_value="rocm")
    @patch("torch.cuda.is_available", return_value=True)
    @patch("torch.cuda.get_device_properties")
    def test_attention_slicing_rocm(self, mock_props, mock_cuda, mock_detect):
        # Mock 8GB VRAM
        mock_props.return_value.total_memory = 8 * (1024**3)
        self.assertTrue(should_enable_attention_slicing("rocm"))

        # Mock 24GB VRAM
        mock_props.return_value.total_memory = 24 * (1024**3)
        self.assertFalse(should_enable_attention_slicing("rocm"))

    @patch("zimage.engine.detect_device", return_value="rocm")
    @patch("zimage.engine.ZImagePipeline.from_pretrained")
    @patch("torch.cuda.is_available", return_value=True)
    @patch("torch.cuda.is_bf16_supported", return_value=True)
    def test_load_pipeline_rocm_device_mapping(self, mock_bf16, mock_cuda, mock_from_pretrained, mock_detect):
        # Verify that load_pipeline maps "rocm" to "cuda" for pipe.to()
        mock_pipe = MagicMock()
        mock_from_pretrained.return_value = mock_pipe
        
        load_pipeline(precision="q8")
        
        # Check that pipe.to was called with "cuda", not "rocm"
        mock_pipe.to.assert_called_with("cuda")

if __name__ == "__main__":
    unittest.main()
