import pytest


def test_get_sse_app_callable():
    pytest.importorskip("diffusers")
    from zimage.mcp_server import get_sse_app

    app = get_sse_app()
    assert callable(getattr(app, "__call__", None))
