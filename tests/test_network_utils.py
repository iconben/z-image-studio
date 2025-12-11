#!/usr/bin/env python3
"""Test suite for network_utils.py"""

import sys
import os
from unittest import mock

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from zimage.network_utils import get_local_ips, get_accessible_urls, format_server_urls


def test_get_local_ips():
    """Test getting local IP addresses."""
    print("Testing get_local_ips():")
    ips = get_local_ips()
    print(f"  Found IPs: {ips}")

    # Assertions
    assert isinstance(ips, list), "Should return a list"
    assert len(ips) > 0, "Should return at least one IP"
    assert "127.0.0.1" in ips, "Should always include localhost"

    # Check that all returned values are valid IPv4 addresses
    for ip in ips:
        parts = ip.split('.')
        assert len(parts) == 4, f"Invalid IP format: {ip}"
        for part in parts:
            assert 0 <= int(part) <= 255, f"Invalid IP octet: {part}"

    print("  ✓ All assertions passed")
    print()


def test_get_accessible_urls():
    """Test getting accessible URLs."""
    print("Testing get_accessible_urls() with host='0.0.0.0', port=8000:")
    urls, primary = get_accessible_urls("0.0.0.0", 8000)
    print(f"  Primary URL: {primary}")
    print(f"  All URLs: {urls}")

    # Assertions
    assert primary == "http://localhost:8000", "Primary should be localhost for 0.0.0.0"
    assert isinstance(urls, list), "Should return a list"
    assert len(urls) > 0, "Should return at least one URL"
    assert "http://127.0.0.1:8000" in urls, "Should include localhost URL"

    print("  ✓ All assertions passed")
    print()

    print("Testing get_accessible_urls() with host='127.0.0.1', port=3000:")
    urls, primary = get_accessible_urls("127.0.0.1", 3000)
    print(f"  Primary URL: {primary}")
    print(f"  All URLs: {urls}")

    # Assertions
    assert primary == "http://127.0.0.1:3000", "Primary should match the host"
    assert isinstance(urls, list), "Should return a list"
    assert len(urls) == 1, "Should return only one URL for specific host"
    assert urls[0] == primary, "Single URL should equal primary"

    print("  ✓ All assertions passed")
    print()


def test_format_server_urls():
    """Test formatting server URLs."""
    print("Testing format_server_urls() with host='0.0.0.0', port=8000:")
    formatted = format_server_urls("0.0.0.0", 8000)
    print("  Output:")
    for line in formatted.split('\n'):
        print(f"    {line}")

    # Assertions
    lines = formatted.split('\n')
    assert len(lines) >= 2, "Should have at least 2 lines for 0.0.0.0"
    assert "http://localhost:8000" in lines[0], "First line should be localhost"
    assert "Other accessible URLs:" in formatted, "Should include accessible URLs label"
    assert "http://127.0.0.1:8000" in formatted, "Should include localhost IP"

    print("  ✓ All assertions passed")
    print()

    print("Testing format_server_urls() with host='localhost', port=9000:")
    formatted = format_server_urls("localhost", 9000)
    print("  Output:")
    for line in formatted.split('\n'):
        print(f"    {line}")

    # Assertions
    assert formatted == "      http://localhost:9000", "Should return single URL with indentation for specific host"

    print("  ✓ All assertions passed")
    print()


def test_edge_cases():
    """Test edge cases and error conditions."""
    print("Testing edge cases:")

    # Test with different ports
    _, primary = get_accessible_urls("0.0.0.0", 3000)
    assert primary == "http://localhost:3000", "Should work with port 3000"

    _, primary = get_accessible_urls("0.0.0.0", 8080)
    assert primary == "http://localhost:8080", "Should work with port 8080"

    # Test with IPv4 addresses
    urls, primary = get_accessible_urls("192.168.1.100", 8000)
    assert primary == "http://192.168.1.100:8000", "Should work with specific IPv4"
    assert len(urls) == 1, "Should return single URL for specific IPv4"

    # Test format with IPv6 (should handle gracefully)
    formatted = format_server_urls("::1", 8000)  # IPv6 localhost
    assert isinstance(formatted, str), "Should return string for IPv6"

    print("  ✓ All edge cases passed")
    print()


def run_all_tests():
    """Run all test functions."""
    print("=" * 50)
    print("Network Utilities Test Suite")
    print("=" * 50)
    print()

    tests = [
        test_get_local_ips,
        test_get_accessible_urls,
        test_format_server_urls,
        test_edge_cases,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ✗ Test {test.__name__} failed: {e}")
            failed += 1
            print()

    print("=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("All tests passed! ✅")
    else:
        print("Some tests failed! ❌")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)