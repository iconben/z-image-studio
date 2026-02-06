"""Tests for `zimg models clear` CLI behavior."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from zimage import cli  # noqa: E402


def test_remove_cached_model_for_precision_removes_repo_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf-home"))

    repo_dir = tmp_path / "hf-home" / "hub" / "models--Disty0--Z-Image-Turbo-SDNQ-int8"
    repo_dir.mkdir(parents=True)
    (repo_dir / "config.json").write_text("{}", encoding="utf-8")

    with patch.object(
        cli,
        "_load_model_id_map",
        return_value={
            "full": "Tongyi-MAI/Z-Image-Turbo",
            "q8": "Disty0/Z-Image-Turbo-SDNQ-int8",
            "q4": "Disty0/Z-Image-Turbo-SDNQ-uint4-svd-r32",
        },
    ):
        removed, cache_dir = cli._remove_cached_model_for_precision("q8")

    assert removed is True
    assert cache_dir == repo_dir
    assert not repo_dir.exists()


def test_remove_cached_model_for_precision_no_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf-home"))

    with patch.object(
        cli,
        "_load_model_id_map",
        return_value={
            "full": "Tongyi-MAI/Z-Image-Turbo",
            "q8": "Disty0/Z-Image-Turbo-SDNQ-int8",
            "q4": "Disty0/Z-Image-Turbo-SDNQ-uint4-svd-r32",
        },
    ):
        removed, cache_dir = cli._remove_cached_model_for_precision("q4")

    assert removed is False
    assert cache_dir.name == "models--Disty0--Z-Image-Turbo-SDNQ-uint4-svd-r32"


def test_run_models_clear_parser_dispatch(capsys):
    with patch.object(cli, "run_models_clear") as clear_mock, patch.object(
        cli.migrations, "init_db"
    ) as init_db_mock, patch.object(sys, "argv", ["zimg", "models", "clear", "q8"]):
        cli.main()

    init_db_mock.assert_called_once()
    clear_mock.assert_called_once()


def test_run_models_lists_cache_flags_and_path(capsys):
    with patch.object(cli, "_load_get_available_models") as get_models_loader, patch.object(
        cli, "_get_model_cache_info"
    ) as cache_info_mock:
        get_models_loader.return_value = lambda: {
            "device": "cpu",
            "ram_gb": 16.0,
            "vram_gb": None,
            "models": [
                {"id": "q8", "hf_model_id": "Disty0/Z-Image-Turbo-SDNQ-int8", "recommended": True},
                {"id": "q4", "hf_model_id": "Disty0/Z-Image-Turbo-SDNQ-uint4-svd-r32", "recommended": False},
            ],
        }

        cache_info_mock.side_effect = [
            {
                "cached": True,
                "cache_path": "/tmp/cache/q8",
                "cache_size_bytes": 1024,
                "cache_size_human": "1.0 KB",
            },
            {
                "cached": False,
                "cache_path": "/tmp/cache/q4",
                "cache_size_bytes": None,
                "cache_size_human": "-",
            },
        ]
        cli.run_models(SimpleNamespace())

    output = capsys.readouterr().out
    assert "Precision" in output
    assert "Recommended" in output
    assert "Cached" in output
    assert "q8" in output and "yes" in output and "1.0 KB" in output
    assert "q4" in output and "-" in output
    assert "cache_path: /tmp/cache/q8" in output
    assert "cache_path: /tmp/cache/q4" in output


def test_run_models_clear_uses_cached_files_wording(capsys):
    args = SimpleNamespace(precision="q8")
    with patch.object(cli, "_remove_cached_model_for_precision", return_value=(True, Path("/tmp/hf/models--q8"))), patch.object(
        cli, "_load_model_id_map", return_value={"q8": "Disty0/Z-Image-Turbo-SDNQ-int8"}
    ):
        cli.run_models_clear(args)

    output = capsys.readouterr().out
    assert "Cleared cached files for 'q8'" in output
    assert "Cache directory deleted:" in output
