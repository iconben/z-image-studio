import pytest
import json


def test_get_sse_app_callable():
    pytest.importorskip("diffusers")
    from zimage.mcp_server import get_sse_app

    app = get_sse_app()
    assert callable(getattr(app, "__call__", None))


@pytest.mark.asyncio
@pytest.mark.skip("Requires full model and GPU")
async def test_sse_content_structure():
    """Test that SSE transport returns the same content structure as stdio."""
    pytest.importorskip("diffusers")
    pytest.importorskip("httpx")
    
    from zimage.mcp_server import get_sse_app
    from httpx import AsyncClient
    
    app = get_sse_app()
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Initialize
        init_response = await client.post("/", json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            },
            "id": 1
        })
        
        assert init_response.status_code == 200
        init_data = init_response.json()
        assert init_data["id"] == 1
        
        # Send initialized notification
        notify_response = await client.post("/", json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        })
        
        assert notify_response.status_code == 200
        
        # Call generate tool
        call_response = await client.post("/", json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "generate",
                "arguments": {
                    "prompt": "a test image",
                    "steps": 2,
                    "width": 256,
                    "height": 256,
                    "seed": 12345
                }
            },
            "id": 2
        })
        
        assert call_response.status_code == 200
        call_data = call_response.json()
        assert call_data["id"] == 2
        assert "result" in call_data
        
        content = call_data["result"]["content"]
        
        # Verify same structure as stdio: 3 items in specific order
        assert len(content) == 3, f"Expected 3 content items, got {len(content)}"
        assert content[0]["type"] == "text", "First content should be text"
        assert content[1]["type"] == "resource", "Second content should be resource"
        assert content[2]["type"] == "image", "Third content should be image"
        
        # Verify text content (now includes file metadata)
        text_metadata = json.loads(content[0]["text"])
        assert "seed" in text_metadata
        assert text_metadata["seed"] == 12345
        assert "filename" in text_metadata
        assert "file_path" in text_metadata
        
        # Verify resource link (clean URI only, no _meta)
        resource_content = content[1]
        assert resource_content["type"] == "resource_link"
        assert "uri" in resource_content
        assert "name" in resource_content
        assert "mimeType" in resource_content
        # SSE should use absolute URL or relative path, not file://
        assert not resource_content["uri"].startswith("file://"), f"SSE should not use file:// URI, got: {resource_content['uri']}"
        assert resource_content["mimeType"] == "image/png"
        assert "_meta" not in resource_content, "ResourceLink should not have _meta"
        
        # Verify image content
        image_content = content[2]
        assert "data" in image_content
        assert image_content["mimeType"] == "image/png"
