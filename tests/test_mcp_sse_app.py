import pytest
import json
import os
from unittest.mock import patch, MagicMock
from PIL import Image


def test_get_sse_app_callable():
    """Test that we can get an SSE app instance."""
    from zimage.mcp_server import get_sse_app

    app = get_sse_app()
    assert callable(getattr(app, "__call__", None))


def test_sse_content_structure_mock():
    """Test that SSE transport returns the same content structure as stdio using mocks."""
    pytest.importorskip("httpx")

    # Add the src directory to the path so we can import zimage
    import sys
    from pathlib import Path
    src_path = Path(__file__).parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from zimage.mcp_server import get_sse_app
    from httpx import AsyncClient

    # Create a mock image for testing
    mock_image = Image.new('RGB', (256, 256), color='red')

    # Mock the generation and related functions
    with patch('zimage.mcp_server._get_engine') as mock_get_engine, \
         patch('zimage.mcp_server._get_worker') as mock_get_worker, \
         patch('zimage.mcp_server.save_image') as mock_save, \
         patch('zimage.mcp_server.record_generation') as mock_record, \
         patch('zimage.hardware.normalize_precision') as mock_normalize:

        # Setup mocks
        mock_normalize.return_value = "q4"

        # Create a mock generate_image function that returns our mock image
        def mock_generate_image_func(*args, **kwargs):
            return mock_image

        # Create a mock cleanup function
        mock_cleanup_func = MagicMock()

        mock_get_engine.return_value = (mock_generate_image_func, mock_cleanup_func)

        async def mock_run_in_worker(func, **kwargs):
            # Simply return the mock image for any function call
            # This ensures we never call the actual generation code
            return mock_image

        mock_run_in_worker_nowait = MagicMock()
        mock_get_worker.return_value = (mock_run_in_worker, mock_run_in_worker_nowait)

        # Mock save_image to return a path with proper mock
        from pathlib import Path, PurePath
        mock_output_path = PurePath("/tmp/test_image.png")

        # Create a mock path object
        mock_path_obj = MagicMock()
        mock_path_obj.name = "test_image.png"
        mock_path_obj.__str__ = lambda: str(mock_output_path)
        mock_path_obj.resolve = lambda: mock_output_path
        mock_path_obj.stat = lambda: MagicMock(st_size=1024)
        mock_save.return_value = mock_path_obj

        # Set SSE mode
        os.environ["ZIMAGE_MCP_TRANSPORT"] = "sse"

        # Get the app
        app = get_sse_app()

        # Mock a context for SSE
        mock_ctx = MagicMock()
        mock_ctx.request_context.request.headers = {}
        mock_ctx.request_context.request.url = "http://localhost:8000/mcp/messages?session_id=test"
        # Mock session to not be closed
        mock_ctx._session._is_closed = False

        # Also mock MODEL_ID_MAP
        with patch('zimage.mcp_server.MODEL_ID_MAP', {'q4': 'test-model'}):
            # Import and test the generate function directly
            from zimage.mcp_server import generate

            # Run the test
            import asyncio

            async def run_test():
                try:
                    result = await generate(
                        prompt="a test image",
                        steps=2,
                        width=256,
                        height=256,
                        seed=12345,
                        precision="q4",
                        ctx=mock_ctx
                    )
                except Exception as e:
                    print(f"\nException during generate: {e}")
                    import traceback
                    traceback.print_exc()
                    raise

                
                # Verify structure
                assert len(result) == 3, f"Expected 3 content items, got {len(result)}"
                assert result[0].type == "text", "First content should be text"
                assert result[1].type == "resource_link", "Second content should be resource_link"
                assert result[2].type == "image", "Third content should be image"

                # Verify text content
                text_metadata = json.loads(result[0].text)
                assert text_metadata["seed"] == 12345
                assert "filename" in text_metadata
                assert "url" in text_metadata  # SSE should have URL, not file_path
                assert text_metadata["url"].startswith("http://"), "SSE should have absolute URL"

                # Verify resource link
                resource_content = result[1]
                # Convert URI to string if needed
                uri_str = str(resource_content.uri)
                assert uri_str.startswith("http://"), f"SSE should have absolute URL, got: {uri_str}"
                assert resource_content.mimeType == "image/png"
                assert resource_content.name == "test_image.png"

                # Verify image content
                image_content = result[2]
                assert image_content.mimeType == "image/png"
                assert len(image_content.data) > 0  # Should have base64 data

                return result

            # Run the async test
            result = asyncio.run(run_test())

        # Verify mocks were called
        # Note: We changed from mock_generate to mock_generate_image_func
        mock_get_engine.assert_called_once()
        mock_save.assert_called_once()
        mock_record.assert_called_once()


def test_stdio_content_structure_mock():
    """Test that stdio transport returns local file paths using mocks."""
    # Add the src directory to the path so we can import zimage
    import sys
    from pathlib import Path
    src_path = Path(__file__).parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Create a mock image for testing
    mock_image = Image.new('RGB', (256, 256), color='blue')

    # Mock the generation and related functions
    with patch('zimage.mcp_server._get_engine') as mock_get_engine, \
         patch('zimage.mcp_server._get_worker') as mock_get_worker, \
         patch('zimage.mcp_server.save_image') as mock_save, \
         patch('zimage.mcp_server.record_generation') as mock_record, \
         patch('zimage.hardware.normalize_precision') as mock_normalize:

        # Setup mocks
        mock_normalize.return_value = "q4"
        mock_generate = MagicMock(return_value=mock_image)
        mock_cleanup = MagicMock()
        mock_get_engine.return_value = (mock_generate, mock_cleanup)

        async def mock_run_in_worker(func, **kwargs):
            # Simply return the mock image for any function call
            # This ensures we never call the actual generation code
            return mock_image

        mock_run_in_worker_nowait = MagicMock()
        mock_get_worker.return_value = (mock_run_in_worker, mock_run_in_worker_nowait)

        # Mock save_image to return a path with proper mock
        from pathlib import Path, PurePath
        mock_output_path = PurePath("/tmp/test_stdio_image.png")

        # Create a mock path object
        mock_path_obj = MagicMock()
        mock_path_obj.name = "test_stdio_image.png"
        mock_path_obj.__str__ = lambda: str(mock_output_path)
        mock_path_obj.resolve = lambda: mock_output_path
        mock_path_obj.stat = lambda: MagicMock(st_size=2048)
        mock_save.return_value = mock_path_obj

        # Set stdio mode
        os.environ["ZIMAGE_MCP_TRANSPORT"] = "stdio"

        # Import and test the generate function directly
        from zimage.mcp_server import generate

        # Run the test
        import asyncio

        async def run_test():
            result = await generate(
                prompt="a test image",
                steps=2,
                width=256,
                height=256,
                seed=12345,
                precision="q4",
                ctx=None  # No context for stdio
            )

            # Verify structure
            assert len(result) == 3
            assert result[0].type == "text"
            assert result[1].type == "resource_link"
            assert result[2].type == "image"

            # Verify text content has file_path for stdio
            text_metadata = json.loads(result[0].text)
            assert "file_path" in text_metadata  # stdio should have file_path
            assert "url" not in text_metadata  # stdio shouldn't have url
            assert text_metadata["file_path"].startswith("/"), "Should be absolute path"

            # Verify resource link uses file:// for stdio
            resource_content = result[1]
            # Convert URI to string if needed
            uri_str = str(resource_content.uri)
            assert uri_str.startswith("file://"), f"stdio should use file:// URI, got: {uri_str}"

            return result

        # Run the async test
        result = asyncio.run(run_test())
