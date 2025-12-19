"""Tests for MCP Streamable HTTP transport implementation."""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add the src directory to the path so we can import zimage
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from zimage.server import app, add_mcp_streamable_http_endpoints


def test_streamable_http_endpoints_added():
    """Test that Streamable HTTP endpoints are added to the app when enabled."""
    # Enable streamable HTTP
    import os
    original_value = os.environ.get("ZIMAGE_DISABLE_MCP")
    os.environ["ZIMAGE_DISABLE_MCP"] = "0"

    try:
        # Create a fresh app and add endpoints
        from fastapi import FastAPI
        test_app = FastAPI()
        add_mcp_streamable_http_endpoints(test_app)

        # Check that the endpoint was added
        routes = [route.path for route in test_app.routes]
        assert "/mcp" in routes

    finally:
        # Restore original environment value
        if original_value is None:
            os.environ.pop("ZIMAGE_DISABLE_MCP", None)
        else:
            os.environ["ZIMAGE_DISABLE_MCP"] = original_value


def test_streamable_http_endpoints_disabled():
    """Test that Streamable HTTP endpoints are not added when disabled."""
    # Disable streamable HTTP by patching the global variable
    with patch('zimage.server.ENABLE_MCP', False):
        # Create a fresh app and add endpoints
        from fastapi import FastAPI
        test_app = FastAPI()
        add_mcp_streamable_http_endpoints(test_app)

        # Check that the endpoint was not added (exclude FastAPI default routes)
        routes = [route.path for route in test_app.routes if route.path not in ['/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc']]
        assert "/mcp" not in routes


@patch('zimage.server.ENABLE_MCP', True)
def test_streamable_http_initialize_request():
    """Test MCP initialize request through Streamable HTTP transport."""
    from fastapi.testclient import TestClient

    # Create test client with the main app
    client = TestClient(app)

    # Test initialize request
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }

    # Mock the response stream since we can't easily test streaming responses
    with patch('zimage.server._process_mcp_streamable_request') as mock_process:
        mock_process.return_value = AsyncMock()

        # Send the request
        response = client.post("/mcp", json=init_request)

        # Should get a streaming response
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert isinstance(response.json(), dict)
        assert "jsonrpc" in response.json()

        # Verify the request was processed
        mock_process.assert_called_once()


@patch('zimage.server.ENABLE_MCP', True)
def test_streamable_http_options_request():
    """Test CORS preflight request for Streamable HTTP transport."""
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Test OPTIONS request
    response = client.options("/mcp")

    # Should return CORS headers
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
    assert "access-control-allow-headers" in response.headers


@patch('zimage.server.ENABLE_MCP', True)
def test_streamable_http_invalid_json():
    """Test that invalid JSON returns appropriate error."""
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Send invalid JSON
    response = client.post(
        "/mcp",
        data="invalid json",
        headers={"content-type": "application/json"}
    )

    # Should return 400 for invalid JSON
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_process_mcp_streamable_request_initialize():
    """Test the _process_mcp_streamable_request function with initialize method."""
    from zimage.server import _process_mcp_streamable_request
    from unittest.mock import MagicMock

    # Create mock request
    mock_request = MagicMock()

    # Test initialize request
    request_data = {
        "method": "initialize",
        "id": 1,
        "params": {}
    }

    # Process the request
    results = []
    async for chunk in _process_mcp_streamable_request(request_data, mock_request):
        results.append(chunk)

    # Should get initialize response
    assert len(results) == 1
    assert "jsonrpc" in results[0]
    assert results[0]["jsonrpc"] == "2.0"
    assert "result" in results[0]
    assert results[0]["result"]["protocolVersion"] == "2025-03-26"


@pytest.mark.asyncio
async def test_process_mcp_streamable_request_tools_list():
    """Test the _process_mcp_streamable_request function with tools/list method."""
    from zimage.server import _process_mcp_streamable_request
    from unittest.mock import MagicMock

    # Create mock request
    mock_request = MagicMock()

    # Test tools list request
    request_data = {
        "method": "tools/list",
        "id": 2,
        "params": {}
    }

    # Process the request
    results = []
    async for chunk in _process_mcp_streamable_request(request_data, mock_request):
        results.append(chunk)

    # Should get tools list response
    assert len(results) == 1
    assert "jsonrpc" in results[0]
    assert "result" in results[0]
    assert "tools" in results[0]["result"]

    # Check that expected tools are present
    tools = results[0]["result"]["tools"]
    tool_names = [tool["name"] for tool in tools]
    assert "generate" in tool_names
    assert "list_models" in tool_names
    assert "list_history" in tool_names


@pytest.mark.asyncio
async def test_process_mcp_streamable_request_unknown_method():
    """Test the _process_mcp_streamable_request function with unknown method."""
    from zimage.server import _process_mcp_streamable_request
    from unittest.mock import MagicMock

    # Create mock request
    mock_request = MagicMock()

    # Test unknown method
    request_data = {
        "method": "unknown_method",
        "id": 3,
        "params": {}
    }

    # Process the request
    results = []
    async for chunk in _process_mcp_streamable_request(request_data, mock_request):
        results.append(chunk)

    # Should get error response
    assert len(results) == 1
    assert "jsonrpc" in results[0]
    assert "error" in results[0]
    assert results[0]["error"]["code"] == -32601
    assert "Method not found" in results[0]["error"]["message"]


@patch('zimage.server.ENABLE_MCP', False)
def test_streamable_http_endpoint_disabled_integration():
    """Integration test that the endpoint is actually disabled when flag is set."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from zimage.server import add_mcp_streamable_http_endpoints

    # Create a fresh FastAPI app
    test_app = FastAPI()

    # Add endpoints with MCP disabled via patch
    add_mcp_streamable_http_endpoints(test_app)

    # Create test client
    client = TestClient(test_app)

    # Try to access the disabled endpoint
    response = client.post("/mcp", json={"method": "test"})

    # Should return 404 since endpoint should not be mounted
    assert response.status_code == 404


@pytest.mark.asyncio
@patch('zimage.server._handle_list_models_tool')
async def test_process_mcp_streamable_request_list_models(mock_list_models):
    """Test the _process_mcp_streamable_request function with tools/call for list_models."""
    from zimage.server import _process_mcp_streamable_request
    from unittest.mock import MagicMock

    # Mock the list_models function
    mock_list_models.return_value = "Test models list"

    # Create mock request
    mock_request = MagicMock()

    # Test list_models tool call
    request_data = {
        "method": "tools/call",
        "id": 4,
        "params": {
            "name": "list_models",
            "arguments": {}
        }
    }

    # Process the request
    results = []
    async for chunk in _process_mcp_streamable_request(request_data, mock_request):
        results.append(chunk)

    # Should get tool response
    assert len(results) == 1
    assert "jsonrpc" in results[0]
    assert "result" in results[0]
    assert "content" in results[0]["result"]

    # Check content structure
    content = results[0]["result"]["content"]
    assert len(content) == 1
    assert content[0]["type"] == "text"
    assert content[0]["text"] == "Test models list"

    # Verify the mock was called
    mock_list_models.assert_called_once()


@pytest.mark.asyncio
@patch('zimage.server._handle_list_history_tool')
async def test_process_mcp_streamable_request_list_history(mock_list_history):
    """Test the _process_mcp_streamable_request function with tools/call for list_history."""
    from zimage.server import _process_mcp_streamable_request
    from unittest.mock import MagicMock

    # Mock the list_history function
    mock_list_history.return_value = "Test history list"

    # Create mock request
    mock_request = MagicMock()

    # Test list_history tool call
    request_data = {
        "method": "tools/call",
        "id": 5,
        "params": {
            "name": "list_history",
            "arguments": {
                "limit": 10,
                "offset": 0
            }
        }
    }

    # Process the request
    results = []
    async for chunk in _process_mcp_streamable_request(request_data, mock_request):
        results.append(chunk)

    # Should get tool response
    assert len(results) == 1
    assert "jsonrpc" in results[0]
    assert "result" in results[0]
    assert "content" in results[0]["result"]

    # Check content structure
    content = results[0]["result"]["content"]
    assert len(content) == 1
    assert content[0]["type"] == "text"
    assert content[0]["text"] == "Test history list"

    # Verify the mock was called with correct arguments
    mock_list_history.assert_called_once_with(10, 0)
