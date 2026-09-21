# Tests Directory

Pytest suite for the Z-Image Studio project. No test in this directory downloads
model weights or runs a model: every model interaction is mocked.

## Running

```bash
# Everything (unit + integration)
uv run pytest

# Unit tier only -- the quick local loop
uv run pytest -m "not integration and not requires_model"

# Integration tier only (spawns real `python -m zimage.mcp_server` subprocesses)
uv run pytest -m integration
```

`tests/conftest.py` redirects all application state (database, outputs, Hugging
Face cache) into a temporary directory and sets `HF_HUB_OFFLINE=1`, so a stray
test can never write to your real data dir or start a model download. To inspect
what a run wrote, set `ZIMAGE_TEST_TMPDIR=/some/path` and
`ZIMAGE_TEST_KEEP_SCRATCH=1`.

## Test tiers

Markers are registered in `pyproject.toml` and enforced by `--strict-markers`.

| Tier | Marker | Contains | Runs in CI |
|------|--------|----------|------------|
| Unit | *(none)* | Pure logic and mocked model/web layers | every push and PR |
| Integration | `@pytest.mark.integration` | Tests that spawn subprocesses or otherwise touch the OS | every push and PR |
| Model | `@pytest.mark.requires_model` | Tests needing real weights (none today) | never |

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
