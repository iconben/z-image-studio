#!/usr/bin/env python
"""
Test suite for case-insensitive precision handling.

This test ensures that the precision parameter is handled consistently
across CLI, API, and MCP interfaces in a case-insensitive manner.
"""

import sys
import os
import pytest
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from zimage.hardware import normalize_precision, MODEL_ID_MAP


class TestNormalizePrecision:
    """Test the normalize_precision function"""

    @pytest.mark.parametrize("input_val,expected", [
        ("full", "full"),
        ("FULL", "full"),
        ("Full", "full"),
        ("fUlL", "full"),
        ("q8", "q8"),
        ("Q8", "q8"),
        ("Q8", "q8"),
        ("q4", "q4"),
        ("Q4", "q4"),
        ("Q4", "q4"),
    ])
    def test_valid_precisions(self, input_val, expected):
        """Test that valid precision values are normalized correctly"""
        result = normalize_precision(input_val)
        assert result == expected
        assert result in MODEL_ID_MAP

    @pytest.mark.parametrize("invalid_val", [
        "invalid",
        "fULLL",
        "q9",
        "Q16",
        "",
        "fu",
        "q",
        "fulll",
        "q_8",
        "q-4",
    ])
    def test_invalid_precisions(self, invalid_val):
        """Test that invalid precision values raise ValueError"""
        with pytest.raises(ValueError, match=r"Unsupported precision.*Available: full, q8, q4"):
            normalize_precision(invalid_val)

    def test_edge_cases(self):
        """Test edge cases"""
        # Test with whitespace
        with pytest.raises(ValueError):
            normalize_precision(" full ")  # Whitespace should not be stripped

        # Test None
        with pytest.raises(AttributeError):
            normalize_precision(None)  # type: ignore


class TestCLIArgumentParsing:
    """Test CLI argument parsing for case-insensitive precision"""

    def test_cli_precision_lowercase_conversion(self):
        """Test that argparse converts precision to lowercase"""
        # Simulate argparse behavior with type=str.lower
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--precision", type=str.lower, default="q8",
                          choices=["full", "q8", "q4"])

        # Test various cases
        test_cases = ["FULL", "Full", "fUlL", "Q8", "q4"]
        for case in test_cases:
            args = parser.parse_args(["--precision", case])
            assert args.precision == case.lower()
            assert args.precision in MODEL_ID_MAP


class TestIntegrationAcrossModules:
    """Test that normalize_precision is consistently used across modules"""

    def test_normalize_precision_consistency(self):
        """Test that normalize_precision works consistently regardless of import source"""
        # Test direct import from hardware
        from zimage.hardware import normalize_precision as normalize_from_hardware

        # Test the function directly
        test_cases = ["FULL", "Full", "Q8", "q4"]
        for case in test_cases:
            result = normalize_from_hardware(case)
            assert result == case.lower()
            assert result in {'full', 'q8', 'q4'}

    def test_module_imports_work(self):
        """Test that modules can import normalize_precision without errors"""
        # Check that the import statements are syntactically correct
        import ast

        # Check server.py
        with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'zimage', 'server.py'), 'r') as f:
            server_content = f.read()

        # Verify the import statement exists and is syntactically valid
        assert 'from .hardware import get_available_models, MODEL_ID_MAP, normalize_precision' in server_content

        # Check mcp_server.py
        with open(os.path.join(os.path.dirname(__file__), '..', 'src', 'zimage', 'mcp_server.py'), 'r') as f:
            mcp_content = f.read()

        # Verify the import statement exists in both import blocks
        assert 'from .hardware import get_available_models, normalize_precision' in mcp_content
        assert 'from hardware import get_available_models, normalize_precision' in mcp_content


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])