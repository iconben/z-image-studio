"""Shared pytest configuration for the z-image-studio test suite.

Why this file mutates ``os.environ`` at import time instead of inside a fixture:
several modules read these variables while they are being imported (``zimage.db``
resolves its database path on import, ``zimage.server`` runs
``ensure_initial_setup()`` on import -- which can *move* legacy ``outputs/``,
``loras/`` and ``zimage.db`` out of the current working directory). A fixture
would run too late to redirect that.

The suite is kept hermetic on purpose:

* Application data and database writes go to a throwaway directory, never to a
  developer's real data dir.
* ``HF_HUB_OFFLINE=1`` makes any accidental model download raise instead of
  quietly consuming gigabytes of bandwidth and disk. This is what guarantees that
  CI never touches model weights, since no test in the suite needs them.

Set ``ZIMAGE_TEST_SCRATCH_DIR`` to keep the scratch directory elsewhere (useful
when debugging a failure and you want to inspect what the tests wrote), and
``ZIMAGE_TEST_KEEP_SCRATCH=1`` to keep it after the session ends.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

_SCRATCH_ENV_VAR = "ZIMAGE_TEST_SCRATCH_DIR"


def _isolate_test_environment() -> None:
    """Point every persistent path at a session-scoped temporary directory."""
    existing = os.environ.get(_SCRATCH_ENV_VAR)
    if existing:
        scratch = Path(existing)
        scratch.mkdir(parents=True, exist_ok=True)
    else:
        scratch = Path(tempfile.mkdtemp(prefix="zimage-tests-"))
        os.environ[_SCRATCH_ENV_VAR] = str(scratch)

    # Application state (see zimage.paths): the database, generated images and
    # LoRA downloads all resolve underneath these.
    os.environ["Z_IMAGE_STUDIO_DATA_DIR"] = str(scratch / "data")
    os.environ["Z_IMAGE_STUDIO_OUTPUT_DIR"] = str(scratch / "outputs")

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
    """Remove the scratch directory once the session has finished."""
    scratch = os.environ.get(_SCRATCH_ENV_VAR)
    if scratch and not os.environ.get("ZIMAGE_TEST_KEEP_SCRATCH"):
        shutil.rmtree(scratch, ignore_errors=True)
