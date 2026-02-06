"""Tests for the `zimg info` CLI subcommand."""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from zimage import cli  # noqa: E402


@pytest.fixture
def fake_hardware():
    return {
        "device": "CPU",
        "ram_gb": 16.0,
        "vram_gb": None,
        "default_precision": "q8",
        "error": None,
    }


def test_collect_info_contains_expected_keys(fake_hardware):
    with patch.object(cli, "_collect_hardware_info", return_value=fake_hardware), patch.object(
        cli, "_get_app_version", return_value="1.2.3"
    ):
        info = cli.collect_info()

    assert info["app_name"] == "Z-Image Studio"
    assert info["package_name"] == "z-image-studio"
    assert info["version"] == "1.2.3"
    assert "paths" in info
    assert "env_overrides" in info
    assert "hardware" in info

    for path_key in [
        "module_file",
        "config_path",
        "data_dir",
        "outputs_dir",
        "loras_dir",
        "db_path",
    ]:
        assert path_key in info["paths"]
        assert isinstance(info["paths"][path_key], str)


def test_run_info_json_outputs_valid_json(capsys, fake_hardware):
    args = SimpleNamespace(json=True)
    with patch.object(cli, "collect_info") as collect_info_mock:
        collect_info_mock.return_value = {
            "app_name": "Z-Image Studio",
            "package_name": "z-image-studio",
            "version": "1.2.3",
            "python_version": "3.11.9",
            "platform": "Darwin",
            "is_frozen": False,
            "executable": "/usr/bin/python",
            "argv0": "zimg",
            "cwd": str(Path.cwd()),
            "paths": {
                "module_file": "a",
                "config_path": "b",
                "data_dir": "c",
                "outputs_dir": "d",
                "loras_dir": "e",
                "db_path": "f",
            },
            "env_overrides": {
                "Z_IMAGE_STUDIO_DATA_DIR": None,
                "Z_IMAGE_STUDIO_OUTPUT_DIR": None,
                "ZIMAGE_ENABLE_TORCH_COMPILE": None,
                "ZIMAGE_DISABLE_MCP": None,
            },
            "hardware": fake_hardware,
        }
        cli.run_info(args)

    output = capsys.readouterr().out
    parsed = json.loads(output)
    assert parsed["version"] == "1.2.3"
    assert parsed["hardware"]["device"] == "CPU"


def test_run_info_text_includes_hardware_error(capsys):
    args = SimpleNamespace(json=False)
    with patch.object(cli, "collect_info") as collect_info_mock:
        collect_info_mock.return_value = {
            "app_name": "Z-Image Studio",
            "package_name": "z-image-studio",
            "version": "1.2.3",
            "python_version": "3.11.9",
            "platform": "Darwin",
            "is_frozen": False,
            "executable": "/usr/bin/python",
            "argv0": "zimg",
            "cwd": str(Path.cwd()),
            "paths": {
                "module_file": "a",
                "config_path": "b",
                "data_dir": "c",
                "outputs_dir": "d",
                "loras_dir": "e",
                "db_path": "f",
            },
            "env_overrides": {
                "Z_IMAGE_STUDIO_DATA_DIR": None,
                "Z_IMAGE_STUDIO_OUTPUT_DIR": None,
                "ZIMAGE_ENABLE_TORCH_COMPILE": None,
                "ZIMAGE_DISABLE_MCP": None,
            },
            "hardware": {
                "device": "UNKNOWN",
                "ram_gb": None,
                "vram_gb": None,
                "default_precision": None,
                "error": "RuntimeError: failed to probe",
            },
        }
        cli.run_info(args)

    output = capsys.readouterr().out
    assert "Hardware:" in output
    assert "Error: RuntimeError: failed to probe" in output


def test_main_skips_db_init_for_info():
    with patch.object(cli, "run_info") as run_info_mock, patch.object(
        cli.migrations, "init_db"
    ) as init_db_mock, patch.object(sys, "argv", ["zimg", "info"]):
        cli.main()

    run_info_mock.assert_called_once()
    init_db_mock.assert_not_called()


def test_main_calls_db_init_for_non_info():
    with patch.object(cli, "run_models") as run_models_mock, patch.object(
        cli.migrations, "init_db"
    ) as init_db_mock, patch.object(sys, "argv", ["zimg", "models"]):
        cli.main()

    init_db_mock.assert_called_once()
    run_models_mock.assert_called_once()
