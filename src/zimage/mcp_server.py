import asyncio
from typing import Literal
from mcp.server.fastmcp import FastMCP
import mcp.types as types
from pathlib import Path
import time
import base64

try:
    from .engine import generate_image, cleanup_memory, MODEL_ID_MAP
    from .worker import run_in_worker, run_in_worker_nowait
    from .hardware import get_available_models
    from . import db
    from .logger import get_logger, setup_logging
except ImportError:
    from engine import generate_image, cleanup_memory, MODEL_ID_MAP
    from worker import run_in_worker, run_in_worker_nowait
    from hardware import get_available_models
    import db
    from logger import get_logger, setup_logging

# Ensure logging is set up to write to stderr
logger = get_logger("zimage.mcp")

# Initialize DB if not already (it handles if exists)
# We need to ensure DB is initialized because this might be the first run
try:
    from . import migrations
    migrations.init_db()
except ImportError:
    import migrations
    migrations.init_db()


mcp = FastMCP("Z-Image Studio")

@mcp.tool()
async def generate(
    prompt: str,
    steps: int = 9,
    width: int = 1280,
    height: int = 720,
    seed: int | None = None,
    precision: str = "q8"
) -> list[types.TextContent | types.ImageContent]:
    """
    Generate an image from a text prompt.
    Returns the path to the saved image and the image content.
    """
    logger.info(f"Received generate request: {prompt}")

    # Validate precision
    if precision not in MODEL_ID_MAP:
        # We can't raise ValueError easily if we want to return a nice error message to the model?
        # But raising exception is fine, MCP handles it.
        valid = ", ".join(MODEL_ID_MAP.keys())
        raise ValueError(f"Unsupported precision '{precision}'. Available: {valid}")

    # Validate dimensions
    width = width if width % 16 == 0 else (width // 16) * 16
    height = height if height % 16 == 0 else (height // 16) * 16
    width = max(16, width)
    height = max(16, height)

    start_time = time.time()

    # Generate
    try:
        image = await run_in_worker(
            generate_image,
            prompt=prompt,
            steps=steps,
            width=width,
            height=height,
            seed=seed,
            precision=precision
        )
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise RuntimeError(f"Generation failed: {e}")

    # Save file
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)

    safe_prompt = "".join(c for c in prompt[:30] if c.isalnum() or c in "-_")
    if not safe_prompt:
        safe_prompt = "image"
    timestamp = int(time.time())
    filename = f"{safe_prompt}_{timestamp}.png"
    output_path = outputs_dir / filename

    image.save(output_path)

    duration = time.time() - start_time
    file_size_kb = output_path.stat().st_size / 1024
    model_id = MODEL_ID_MAP[precision]

    # Record to DB (Best effort)
    try:
        db.add_generation(
            prompt=prompt,
            steps=steps,
            width=width,
            height=height,
            filename=filename,
            generation_time=duration,
            file_size_kb=file_size_kb,
            model=model_id,
            cfg_scale=0.0,
            seed=seed,
            status="succeeded",
            precision=precision
        )
    except Exception as e:
        logger.warning(f"Failed to record generation to DB: {e}")

    # Cleanup
    run_in_worker_nowait(cleanup_memory)

    # Convert image to base64 for embedding
    from io import BytesIO
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

    return [
        types.TextContent(
            type="text",
            text=f"Image generated successfully in {duration:.2f}s.\nSaved to: {output_path.resolve()}"
        ),
        types.ImageContent(
            type="image",
            data=img_b64,
            mimeType="image/png"
        )
    ]

@mcp.tool()
async def list_models() -> str:
    """List available image generation models and hardware recommendations."""
    models_info = get_available_models()
    # Format nicely as text
    lines = []
    lines.append(f"Device: {models_info['device'].upper()}")
    if models_info.get('ram_gb'):
        lines.append(f"RAM: {models_info['ram_gb']:.1f} GB")
    if models_info.get('vram_gb'):
        lines.append(f"VRAM: {models_info['vram_gb']:.1f} GB")
    lines.append("\nAvailable Models:")
    for m in models_info['models']:
        rec = " (Recommended)" if m.get('recommended') else ""
        lines.append(f"- {m['id']}: {m['hf_model_id']}{rec}")

    return "\n".join(lines)

@mcp.tool()
async def list_history(limit: int = 10, offset: int = 0) -> str:
    """List recent image generations history."""
    items, total = db.get_history(limit, offset)
    if not items:
        return "No history found."

    lines = [f"History ({offset}-{offset+len(items)} of {total}):"]
    for item in items:
        lines.append(f"ID: {item['id']}, Prompt: {item['prompt']}, File: {item['filename']}, Time: {item['created_at']}")
    return "\n".join(lines)

def run(transport: Literal["stdio", "sse"] = "stdio", host: str = "0.0.0.0", port: int = 8000):
    setup_logging()
    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "sse":
        # FastMCP run method supports sse
        mcp.run(transport="sse", host=host, port=port)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Z-Image MCP Server")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"], help="Transport mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE")
    args = parser.parse_args()

    run(transport=args.transport, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
