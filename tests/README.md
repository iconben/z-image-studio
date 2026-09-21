# Tests Directory

Pytest suite for the Z-Image Studio project. No test in this directory downloads
model weights or runs a model: every model interaction is mocked.

## Running

Run pytest through the interpreter in `.venv`, the same way CI does:

```bash
# Everything (unit + integration)
.venv/bin/python -m pytest

# Unit tier only -- the quick local loop
.venv/bin/python -m pytest -m "not integration and not requires_model"

# Integration tier only (spawns real `python -m zimage.mcp_server` subprocesses)
.venv/bin/python -m pytest -m integration
```

Avoid `uv run pytest`: `uv run` re-syncs the environment, which on Linux pulls the
CUDA `torch` wheel back in (about 2.6 GB of `nvidia-*` packages) and rewrites
`uv.lock`. CI installs with `UV_TORCH_BACKEND=cpu` for the same reason.

The repository-root `conftest.py` redirects `HOME`, the application state
(database, outputs) and the Hugging Face cache into a temporary directory, sets
`HF_HUB_OFFLINE=1`, and plants the config file that stops the one-time legacy
migration from moving real files out of the repository. A stray test can
therefore neither write to your real data dir nor start a model download.

To inspect what a run wrote:

| Knob | Effect |
|------|--------|
| `ZIMAGE_TEST_SCRATCH_DIR=/some/path` | Use that directory. A directory you supply is never deleted. |
| `ZIMAGE_TEST_KEEP_SCRATCH=1` | Keep a directory the session created itself. |
| `ZIMAGE_TEST_ALLOW_REAL_HF=1` | Opt out of the Hugging Face redirection, for the model tier. |

## Test tiers

Markers are registered in `pyproject.toml` and enforced by `--strict-markers`.

| Tier | Marker | Contains | Runs in CI |
|------|--------|----------|------------|
| Unit | *(none)* | Pure logic and mocked model/web layers | every push and PR |
| Integration | `@pytest.mark.integration` | Tests that spawn subprocesses or otherwise touch the OS | every push and PR |
| Model | `@pytest.mark.requires_model` | Tests needing real weights (the two skipped GPU tests in `test_mcp_integration.py`) | never |

A test may carry both `integration` and `requires_model`; both CI steps exclude
the model marker, so it stays out of CI either way.

## Adding tests

1. Name files `test_*.py` so pytest collects them.
2. Prefer plain `assert` and pytest fixtures over `unittest` boilerplate.
3. Mock anything that would load weights, hit the network, or write outside the
   scratch directory configured by `conftest.py`.
4. If a test genuinely needs real weights, mark it `@pytest.mark.requires_model`
   and keep it out of the default selection.

## Manual, non-pytest checks

Scripts that download and run the model live outside this directory, in
`scripts/` (for example `scripts/manual_mps_smoke.py`), so they can never be
collected by accident.
