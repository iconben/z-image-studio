"""Shared pytest configuration for the z-image-studio test suite.

This file sits at the repository root rather than in ``tests/`` so that the
isolation below applies to *every* test pytest collects in this tree, not only to
the ones under ``tests/``.

Why this file mutates ``os.environ`` at import time instead of inside a fixture:
several modules read these variables while they are being imported (``zimage.db``
resolves its database path on import, ``zimage.server`` runs
``ensure_initial_setup()`` on import -- which can *move* legacy ``outputs/``,
``loras/`` and ``zimage.db`` out of the current working directory). A fixture
would run too late to redirect that.

The suite is kept hermetic on purpose:

* ``HOME`` points into the scratch tree and a placeholder config is written
  before anything imports ``zimage``. ``ensure_initial_setup()`` returns early
  when that config exists, which is what stops the one-time legacy migration from
  moving real files out of the repository -- and into a directory this session
  deletes. It also keeps the developer's own config file from being read (a
  personal ``ZIMAGE_ENABLE_TORCH_COMPILE`` would otherwise change test outcomes)
  or overwritten.
* Application data and database writes go to a throwaway directory, never to a
  developer's real data dir.
* ``HF_HUB_OFFLINE=1`` makes any accidental model download raise instead of
  quietly consuming gigabytes of bandwidth and disk. This is what guarantees that
  CI never touches model weights, since no test in the suite needs them.

Escape hatches:

* ``ZIMAGE_TEST_SCRATCH_DIR`` -- use a specific scratch directory. A directory
  this session creates is deleted at the end; one you supply is left alone, so
  you can inspect it after a failure.
* ``ZIMAGE_TEST_KEEP_SCRATCH`` -- set to ``1``/``true``/``yes``/``on`` to keep a
  session-created scratch directory.
* ``ZIMAGE_TEST_ALLOW_REAL_HF=1`` -- skip the Hugging Face redirection entirely,
  so the ``requires_model`` tier can use your real cache. Pair it with
  ``HF_HOME`` if your weights do not live under ``$HOME/.cache/huggingface``.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

_SCRATCH_ENV_VAR = "ZIMAGE_TEST_SCRATCH_DIR"
_KEEP_ENV_VAR = "ZIMAGE_TEST_KEEP_SCRATCH"
_ALLOW_REAL_HF_ENV_VAR = "ZIMAGE_TEST_ALLOW_REAL_HF"

#: Values of ``ZIMAGE_TEST_KEEP_SCRATCH`` that mean "yes".
_TRUTHY = {"1", "true", "yes", "on"}

#: Mirrors what ``zimage.paths.ensure_initial_setup()`` writes on a fresh
#: install, so tests see the defaults an app-level user would have.
_PLACEHOLDER_CONFIG = {
    "version": 1,
    "Z_IMAGE_STUDIO_DATA_DIR": None,
    "Z_IMAGE_STUDIO_OUTPUT_DIR": None,
    "ZIMAGE_ENABLE_TORCH_COMPILE": None,
    "max_steps": 50,
    "max_width": 4096,
    "max_height": 4096,
}

#: False when the user supplied ``ZIMAGE_TEST_SCRATCH_DIR``: we only ever delete
#: what we created ourselves.
_scratch_is_ours = False


def _write_placeholder_config(scratch: Path) -> Path:
    """Mark the scratch home as "already set up" so the legacy migration is a no-op.

    ``zimage.paths`` builds ``CONFIG_DIR`` from ``Path.home()`` and
    ``ensure_initial_setup()`` returns immediately once ``config.json`` exists
    there.
    """
    home = scratch / "home"
    config_dir = home / ".z-image-studio"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    config_path.write_text(json.dumps(_PLACEHOLDER_CONFIG, indent=2), encoding="utf-8")
    return home


def _isolate_test_environment() -> None:
    """Point every persistent path at a session-scoped temporary directory."""
    global _scratch_is_ours

    existing = os.environ.get(_SCRATCH_ENV_VAR)
    if existing:
        scratch = Path(existing).expanduser()
        scratch.mkdir(parents=True, exist_ok=True)
    else:
        scratch = Path(tempfile.mkdtemp(prefix="zimage-tests-"))
        os.environ[_SCRATCH_ENV_VAR] = str(scratch)
        _scratch_is_ours = True

    # Application state (see zimage.paths): the database, generated images and
    # LoRA downloads all resolve underneath these.
    os.environ["Z_IMAGE_STUDIO_DATA_DIR"] = str(scratch / "data")
    os.environ["Z_IMAGE_STUDIO_OUTPUT_DIR"] = str(scratch / "outputs")

    # Redirect the home directory into the scratch tree before `zimage` (and with
    # it `zimage.paths`) is imported, then plant the config that keeps the legacy
    # migration from running against the real working directory.
    home = _write_placeholder_config(scratch)
    os.environ["HOME"] = str(home)
    os.environ["USERPROFILE"] = str(home)  # Path.home() on Windows

    if os.environ.get(_ALLOW_REAL_HF_ENV_VAR) == "1":
        return

    # Hugging Face caches. `zimage.cli._resolve_hf_hub_cache_dir()` prefers
    # HF_HUB_CACHE and HUGGINGFACE_HUB_CACHE over HF_HOME, so a developer who has
    # either exported would have `zimg models clear` tests resolve -- and delete --
    # paths inside their real model cache. Clearing them makes HF_HOME
    # authoritative, which is what the tests assume.
    for variable in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE"):
        os.environ.pop(variable, None)

    # Offline mode turns a would-be download into a hard failure, which is exactly
    # what we want in CI.
    os.environ["HF_HOME"] = str(scratch / "hf")
    os.environ["HF_HUB_OFFLINE"] = "1"


_isolate_test_environment()


def pytest_sessionfinish(session, exitstatus) -> None:
    """Remove the scratch directory, but only if this session created it."""
    if not _scratch_is_ours:
        return
    if os.environ.get(_KEEP_ENV_VAR, "").strip().lower() in _TRUTHY:
        return
    scratch = os.environ.get(_SCRATCH_ENV_VAR)
    if scratch:
        shutil.rmtree(scratch, ignore_errors=True)
