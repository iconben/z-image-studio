#!/usr/bin/env python3
"""
Test script to verify MCP SSE response structure.
This simulates what an MCP client would receive.
"""

import json
import asyncio
import sys

# Set stdio mode for testing before importing anything that uses it
import os
os.environ["ZIMAGE_MCP_TRANSPORT"] = "stdio"


def test_generate_response():
    """Test the generate function to see what it returns."""

    # Import the generate function
    from zimage.mcp_server import generate

    async def run_test():
        try:
            # Call the generate function with a simple prompt
            result = await generate(
                prompt="a simple test image",
                steps=1,  # Minimize for quick test
                width=256,
                height=256,
                seed=12345,
                precision="q4"  # Smallest model
            )

            print("=== MCP Response Structure ===")
            print(f"Number of content items: {len(result)}")
            print()

            for i, item in enumerate(result):
                print(f"Item {i}:")
                print(f"  Type: {item.type}")
                print(f"  Class: {type(item).__name__}")

                if hasattr(item, 'text'):
                    text = json.loads(item.text)
                    print(f"  Text content keys: {list(text.keys())}")
                    if 'filename' in text:
                        print(f"  Filename: {text['filename']}")
                    if 'url' in text:
                        print(f"  URL: {text['url']}")

                if hasattr(item, 'uri'):
                    print(f"  URI: {item.uri}")

                if hasattr(item, 'name'):
                    print(f"  Name: {item.name}")

                if hasattr(item, 'mimeType'):
                    print(f"  MIME Type: {item.mimeType}")

                if hasattr(item, 'data'):
                    print(f"  Data length: {len(item.data)} chars (base64)")

                print()

            # Show the full structure
            print("=== Full Response JSON ===")
            response_dict = {
                "result": {
                    "content": [
                        {
                            "type": item.type,
                            **{k: v for k, v in item.__dict__.items() if k != 'type'}
                        }
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
    return asyncio.run(run_test())


if __name__ == "__main__":
    test_generate_response()