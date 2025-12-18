import asyncio
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP, Context
import mcp.types as types
from pathlib import Path
import time
import os
import json
import base64
import random

# Lazy import for yarl to avoid dependency issues
try:
    from yarl import URL
except ImportError:
    URL = None

try:
    from .hardware import get_available_models, normalize_precision, MODEL_ID_MAP
    from . import db
    from .storage import save_image, record_generation
    from .logger import get_logger, setup_logging
except ImportError:
    from hardware import get_available_models, normalize_precision, MODEL_ID_MAP
    import db
    from storage import save_image, record_generation
    from logger import get_logger, setup_logging

# Lazy imports for heavy dependencies
def _get_engine():
    try:
        from .engine import generate_image, cleanup_memory
        return generate_image, cleanup_memory
    except ImportError:
        from engine import generate_image, cleanup_memory
        return generate_image, cleanup_memory

def _get_worker():
    try:
        from .worker import run_in_worker, run_in_worker_nowait
        return run_in_worker, run_in_worker_nowait
    except ImportError:
        from worker import run_in_worker, run_in_worker_nowait
        return run_in_worker, run_in_worker_nowait

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
    precision: str = "q8",
    ctx: Optional[Context] = None
) -> list[types.TextContent | types.ResourceLink | types.ImageContent]:
    """
    Generate an image from a text prompt.
    
    Returns a consistent content array for both stdio and SSE transports:
    1. TextContent: Enhanced metadata including generation info and file details
    2. ResourceLink: Main image file reference with context-appropriate URI:
       - SSE: Absolute URL built from request context (X-Forwarded-* headers), ZIMAGE_BASE_URL, or relative path
       - Stdio: file:// URI for local access
    3. ImageContent: Thumbnail preview (base64 PNG, max 256px)
    
    URI Building Priority (SSE):
    1. Context parameter (ctx.request_context.request) - builds absolute URL from request headers
    2. ZIMAGE_BASE_URL environment variable - uses configured base URL
    3. Relative URL - fallback when no other method available
    
    File metadata (filename, file_path) is in TextContent to avoid duplication in ResourceLink.
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

    # Generate a random seed if none provided (for reproducibility tracking)
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
        logger.info(f"Generated random seed: {seed}")

    start_time = time.time()

    # Generate (lazy load engine and worker once)
    try:
        generate_image, cleanup_memory = _get_engine()
        run_in_worker, run_in_worker_nowait = _get_worker()

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
    
    # Build appropriate URI based on transport context
    if transport == "sse":
        # For SSE transport, build absolute URL using available information
        # Priority: 1. Use Context parameter (MCP 1.23.2 proper way), 2. ZIMAGE_BASE_URL, 3. relative URL
        resource_uri = None
        
        # Method 1: Use Context parameter (proper MCP 1.23.2 way)
        if ctx is not None:
            try:
                # Access request from context
                request = ctx.request_context.request
                if request:
                    # Build from headers if available (X-Forwarded-* for proxies)
                    if hasattr(request, 'headers'):
                        headers = request.headers
                        proto = headers.get('x-forwarded-proto') or headers.get('X-Forwarded-Proto')
                        host = headers.get('x-forwarded-host') or headers.get('X-Forwarded-Host')
                        
                        if proto and host:
                            resource_uri = f"{proto}://{host}"
                        elif hasattr(request, 'url') and URL:
                            url_obj = URL(request.url)
                            resource_uri = f"{url_obj.scheme}://{url_obj.host}"
                            if url_obj.port and url_obj.port not in (80, 443):
                                resource_uri += f":{url_obj.port}"
                    elif hasattr(request, 'base_url'):
                        resource_uri = str(request.base_url)
            except Exception:
                # Fall through to other methods if context access fails
                pass
        
        # Method 2: Use ZIMAGE_BASE_URL environment variable
        if not resource_uri and base_url:
            resource_uri = base_url
        
        # Method 3: Fallback to relative URL (least preferred, but better than nothing)
        if not resource_uri:
            resource_uri = relative_url
        else:
            # Only append relative path if resource_uri is an origin (no path) or a bare host.
            if resource_uri.startswith(("http://", "https://")):
                if URL:
                    url_obj = URL(resource_uri)
                    if not url_obj.path or url_obj.path == "/":
                        resource_uri = f"{resource_uri.rstrip('/')}{relative_url}"
                else:
                    # Fallback: treat as origin if it contains no path separators beyond scheme.
                    if resource_uri.rstrip("/").count("/") <= 2:
                        resource_uri = f"{resource_uri.rstrip('/')}{relative_url}"
            elif resource_uri.startswith("/"):
                # Already a relative path; keep as-is.
                pass
            else:
                # Treat as bare host (no scheme)
                resource_uri = f"{resource_uri.rstrip('/')}{relative_url}"
    else:
        # For stdio transport, use file:// URI for local access
        resource_uri = f"file://{output_path.resolve()}"

    # Create text content with generation info and file metadata
    text_content = types.TextContent(
        type="text",
        text=json.dumps({
            "message": "Image generated successfully",
            "duration_seconds": round(duration, 2),
            "width": width,
            "height": height,
            "precision": precision,
            "model_id": model_id,
            "seed": seed,
            "filename": filename,
            "file_path": str(output_path.resolve()),
        })
    )

    # Create resource link for the main image file (clean URI only)
    resource_content = types.ResourceLink(
        type="resource_link",
        name=filename,
        uri=resource_uri,
        mimeType="image/png",
    )

    # Create thumbnail image content (same for both transports)
    thumb = image.copy()
    thumb.thumbnail((256, 256))
    from io import BytesIO
    buf = BytesIO()
    thumb.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    image_content = types.ImageContent(type="image", data=img_b64, mimeType="image/png")

    # Return consistent content structure for both transports
    return [
        text_content,
        resource_content,
        image_content,
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
