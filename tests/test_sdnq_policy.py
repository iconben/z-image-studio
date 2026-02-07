"""Tests for SDNQ compile policy precheck behavior."""

import os
import sys
from unittest.mock import patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from zimage import hardware, sdnq_policy  # noqa: E402


def test_apply_sdnq_compile_policy_respects_user_override(monkeypatch):
    monkeypatch.setenv("SDNQ_USE_TORCH_COMPILE", "1")

    with patch.object(sdnq_policy, "basic_has_triton", return_value=False) as basic_mock:
        sdnq_policy.apply_sdnq_compile_policy()

    basic_mock.assert_not_called()
    assert os.environ["SDNQ_USE_TORCH_COMPILE"] == "1"


def test_apply_sdnq_compile_policy_sets_eager_when_basic_triton_missing(monkeypatch):
    monkeypatch.delenv("SDNQ_USE_TORCH_COMPILE", raising=False)

    with patch.object(sdnq_policy, "basic_has_triton", return_value=False):
        sdnq_policy.apply_sdnq_compile_policy()

    assert os.environ["SDNQ_USE_TORCH_COMPILE"] == "0"


def test_apply_sdnq_compile_policy_keeps_auto_when_basic_triton_present(monkeypatch):
    monkeypatch.delenv("SDNQ_USE_TORCH_COMPILE", raising=False)

    with patch.object(sdnq_policy, "basic_has_triton", return_value=True):
        sdnq_policy.apply_sdnq_compile_policy()

    assert "SDNQ_USE_TORCH_COMPILE" not in os.environ


def test_has_sdnq_applies_policy_before_import():
    with patch.object(hardware, "apply_sdnq_compile_policy") as policy_mock:
        hardware.has_sdnq()

    policy_mock.assert_called_once()
