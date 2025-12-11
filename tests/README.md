# Tests Directory

This directory contains test suites for the Z-Image Studio project.

## Running Tests

### Run all tests:
```bash
python -m tests.test_network_utils
```

Or directly:
```bash
python tests/test_network_utils.py
```

### Individual test modules:
- `test_network_utils.py` - Tests for network utility functions

## Test Structure

Each test file is a standalone module that can be run independently. Tests include:

1. **Unit tests** for individual functions
2. **Integration tests** for combined functionality
3. **Edge case testing** for unusual scenarios
4. **Regression tests** to ensure bugs don't reappear

## Adding New Tests

When adding new test files:

1. Name them `test_*.py` following Python conventions
2. Include proper docstrings explaining what's being tested
3. Use assertions to verify expected behavior
4. Print informative output for debugging
5. Return `True` on success, raise exceptions on failure

## Test Coverage Goals

- All utility functions should have tests
- Edge cases should be covered
- Error conditions should be tested
- Performance should be considered where relevant