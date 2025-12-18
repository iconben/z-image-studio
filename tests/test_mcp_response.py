#!/usr/bin/env python3
"""Test script to verify MCP response structure (mocked)."""

import json
import asyncio
from unittest.mock import patch, MagicMock
from PIL import Image

def test_generate_response():
    """Test the generate function to see what it returns."""

    # Import the internal implementation to set transport explicitly
    from zimage.mcp_server import _generate_impl

    # Create a mock image for testing
    mock_image = Image.new("RGB", (256, 256), color="green")

    # Mock the generation and related functions
    with patch("zimage.mcp_server._get_engine") as mock_get_engine, \
         patch("zimage.mcp_server._get_worker") as mock_get_worker, \
         patch("zimage.mcp_server.save_image") as mock_save, \
         patch("zimage.mcp_server.record_generation") as mock_record, \
         patch("zimage.hardware.normalize_precision") as mock_normalize:

        # Setup mocks
        mock_normalize.return_value = "q4"
        mock_generate = MagicMock(return_value=mock_image)
        mock_cleanup = MagicMock()
        mock_get_engine.return_value = (mock_generate, mock_cleanup)

        async def mock_run_in_worker(func, **kwargs):
            return mock_image

        mock_run_in_worker_nowait = MagicMock()
        mock_get_worker.return_value = (mock_run_in_worker, mock_run_in_worker_nowait)

        # Mock save_image to return a path-like mock
        from pathlib import PurePath
        mock_output_path = PurePath("/tmp/test_image.png")

        mock_path_obj = MagicMock()
        mock_path_obj.name = "test_image.png"
        mock_path_obj.__str__ = lambda: str(mock_output_path)
        mock_path_obj.resolve = lambda: mock_output_path
        mock_path_obj.stat = lambda: MagicMock(st_size=1024)
        mock_save.return_value = mock_path_obj

        async def run_test():
            try:
                # Call the generate function with a simple prompt
                result = await _generate_impl(
                    prompt="a simple test image",
                    steps=1,  # Minimize for quick test
                    width=256,
                    height=256,
                    seed=12345,
                    precision="q4",  # Smallest model
                    transport="stdio",
                    ctx=None,
                )

                print("=== MCP Response Structure ===")
                print(f"Number of content items: {len(result)}")
                print()

                for i, item in enumerate(result):
                    print(f"Item {i}:")
                    print(f"  Type: {item.type}")
                    print(f"  Class: {type(item).__name__}")

                    if hasattr(item, "text"):
                        text = json.loads(item.text)
                        print(f"  Text content keys: {list(text.keys())}")
                        if "filename" in text:
                            print(f"  Filename: {text['filename']}")
                        if "url" in text:
                            print(f"  URL: {text['url']}")

                    if hasattr(item, "uri"):
                        print(f"  URI: {item.uri}")

                    if hasattr(item, "name"):
                        print(f"  Name: {item.name}")

                    if hasattr(item, "mimeType"):
                        print(f"  MIME Type: {item.mimeType}")

                    if hasattr(item, "data"):
                        print(f"  Data length: {len(item.data)} chars (base64)")

                    print()

                # Show the full structure
                print("=== Full Response JSON ===")
                response_dict = {
                    "result": {
                        "content": [
                            (item.model_dump(mode="json") if hasattr(item, "model_dump") else item.__dict__)
                            for item in result
                        ]
                    }
                }
                print(json.dumps(response_dict, indent=2))

                return result

            except Exception as e:
                print(f"Error testing generate: {e}")
                import traceback
                traceback.print_exc()
                return None

        # Run the async test
        result = asyncio.run(run_test())

        assert result is not None
        assert len(result) == 3
        mock_get_engine.assert_called_once()
        mock_save.assert_called_once()
        mock_record.assert_called_once()


if __name__ == "__main__":
    test_generate_response()
