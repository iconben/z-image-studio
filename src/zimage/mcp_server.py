import asyncio
from typing import Literal
from mcp.server.fastmcp import FastMCP
import mcp.types as types
from pathlib import Path
import time
import os
import json
import base64

try:
    from .engine import generate_image, cleanup_memory, MODEL_ID_MAP
    from .worker import run_in_worker, run_in_worker_nowait
    from .hardware import get_available_models, normalize_precision
    from . import db
    from .storage import save_image, record_generation
    from .logger import get_logger, setup_logging
except ImportError:
    from engine import generate_image, cleanup_memory, MODEL_ID_MAP
    from worker import run_in_worker, run_in_worker_nowait
    from hardware import get_available_models, normalize_precision
    import db
    from storage import save_image, record_generation
    from logger import get_logger, setup_logging

# Silence SDNQ/Triton noisy logs on stdout; keep MCP stdio clean
os.environ.setdefault("SDNQ_LOG_LEVEL", "ERROR")

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

    # Normalize and validate precision
    try:
        precision = normalize_precision(precision)
    except ValueError as e:
        raise ValueError(str(e))

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

    # Save file via shared storage helper
    output_path = save_image(image, prompt)
    filename = output_path.name

    duration = time.time() - start_time
    file_size_kb = output_path.stat().st_size / 1024
    model_id = MODEL_ID_MAP[precision]

    # Record to DB (Best effort)
    record_generation(
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
        precision=precision,
    )

    # Cleanup
    run_in_worker_nowait(cleanup_memory)

    transport = os.getenv("ZIMAGE_MCP_TRANSPORT", "stdio")
    base_url = os.getenv("ZIMAGE_BASE_URL")
    relative_url = f"/outputs/{filename}"
    absolute_url = f"{base_url.rstrip('/')}{relative_url}" if base_url else None

    result_meta = {
        "message": "Image generated successfully",
        "file_path": str(output_path.resolve()),
        "relative_url": relative_url,
        "absolute_url": absolute_url,
        "duration_seconds": round(duration, 2),
        "width": width,
        "height": height,
        "precision": precision,
        "model_id": model_id,
        "seed": seed,
    }

    if transport == "stdio":
        # Return a small thumbnail as base64 (max 400px on longest side) per MCP guidance
        thumb = image.copy()
        thumb.thumbnail((400, 400))
        from io import BytesIO
        buf = BytesIO()
        thumb.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return [
            types.TextContent(type="text", text=json.dumps(result_meta)),
            types.ImageContent(type="image", data=img_b64, mimeType="image/png"),
        ]
    else:
        # SSE: return URLs/paths only (no base64)
        return [
            types.TextContent(type="text", text=json.dumps(result_meta)),
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

def get_sse_app():
    """Return ASGI app for MCP SSE transport (mount under FastAPI)."""
    setup_logging()
    os.environ["ZIMAGE_MCP_TRANSPORT"] = "sse"
    return mcp.sse_app()

def run_stdio():
    """Run MCP over stdio (used by zimg-mcp and `zimg mcp`)."""
    setup_logging()
    os.environ["ZIMAGE_MCP_TRANSPORT"] = "stdio"
    mcp.run(transport="stdio")

# Legacy helper; prefer run_stdio or get_sse_app.
def run(transport: Literal["stdio", "sse"] = "stdio", host: str = "0.0.0.0", port: int = 8000):
    if transport == "stdio":
        run_stdio()
    elif transport == "sse":
        setup_logging()
        mcp.run(transport="sse", host=host, port=port)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Z-Image MCP Server (stdio only)")
    parser.add_argument("--transport", default="stdio", choices=["stdio"], help="Transport mode (stdio only)")
    args = parser.parse_args()

    run_stdio()

if __name__ == "__main__":
    main()
