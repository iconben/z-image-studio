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


# Note: SSE connections in MCP don't have a traditional heartbeat mechanism.
# The connection is maintained through the HTTP persistent connection.
# Progress updates through ctx.report_progress() help keep the connection active.
# If clients timeout, they will disconnect and we handle that gracefully.


mcp = FastMCP("Z-Image Studio")

def _infer_transport(ctx: Optional[Context]) -> Literal["stdio", "sse"]:
    """Infer transport based on whether we have an HTTP request context."""
    if ctx and getattr(getattr(ctx, "request_context", None), "request", None):
        return "sse"
    return "stdio"

async def _generate_impl(
    prompt: str,
    steps: int,
    width: int,
    height: int,
    seed: int | None,
    precision: str,
    transport: Literal["stdio", "sse"],
    ctx: Optional[Context],
) -> list[types.TextContent | types.ResourceLink | types.ImageContent]:
    """Internal implementation for generate with explicit transport selection."""
    logger.info(f"Received generate request: {prompt}")

    # Helper function to send progress updates
    async def send_progress(percentage: int, message: str):
        """Send progress notification via SSE if available."""
        if transport == "sse" and ctx:
            try:
                # Use the context's report_progress method to send progress to client
                await ctx.report_progress(progress=percentage, total=100, message=message)
                logger.info(f"[{percentage}%] {message}")
            except Exception as e:
                # If progress reporting fails, continue without failing the generation
                logger.warning(f"Failed to send progress: {e}")

    try:
        await send_progress(0, "Initializing generation...")

        # Normalize and validate precision
        try:
            precision = normalize_precision(precision)
        except ValueError as e:
            raise ValueError(str(e))

        await send_progress(5, "Normalizing dimensions...")

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

        await send_progress(10, "Loading models...")

        # Generate (lazy load engine and worker once)
        try:
            generate_image, cleanup_memory = _get_engine()
            run_in_worker, run_in_worker_nowait = _get_worker()

            await send_progress(20, "Starting generation...")
            logger.info(
                "DEBUG: steps=%s, width=%s, height=%s, guidance_scale=0.0, seed=%s, precision=%s",
                steps,
                width,
                height,
                seed,
                precision,
            )

            # Run generation with progress updates
            image = await run_in_worker(
                generate_image,
                prompt=prompt,
                steps=steps,
                width=width,
                height=height,
                seed=seed,
                precision=precision,
            )

            await send_progress(90, "Saving image...")
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            await send_progress(0, f"Generation failed: {e}")
            raise RuntimeError(f"Generation failed: {e}")

        # Save file via shared storage helper
        output_path = save_image(image, prompt)
        filename = output_path.name

        await send_progress(95, "Recording to database...")

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

        await send_progress(100, "Complete!")

        # Cleanup
        run_in_worker_nowait(cleanup_memory)

    except Exception as e:
        logger.error(f"Error in generate function: {e}")
        raise

    base_url = os.getenv("ZIMAGE_BASE_URL")
    relative_url = f"/outputs/{filename}"

    # Build appropriate URI based on transport context
    if transport == "sse":
        # For SSE transport, build absolute URL using available information
        # Priority: 1. Extract from request context, 2. ZIMAGE_BASE_URL, 3. Default fallback
        resource_uri = None

        # Method 1: Extract base URL from request context
        if ctx is not None:
            try:
                # Access request from context
                if hasattr(ctx, "request_context") and ctx.request_context:
                    request = ctx.request_context.request

                    if request:
                        # Try multiple approaches to extract base URL

                        # Approach A: Extract from request object (FastAPI/Starlette style)
                        if hasattr(request, "headers") and hasattr(request, "url"):
                            headers = request.headers

                            # Check for proxy headers first (most reliable in production)
                            proto = headers.get("x-forwarded-proto") or headers.get("X-Forwarded-Proto") or "http"
                            host = headers.get("x-forwarded-host") or headers.get("X-Forwarded-Host")

                            if host:
                                # Use proxy headers if available
                                resource_uri = f"{proto}://{host}"
                                logger.debug(f"Built base URL from proxy headers: {resource_uri}")
                            else:
                                # Fall back to extracting from request URL
                                if hasattr(request, "url") and request.url:
                                    if URL:
                                        url_obj = URL(str(request.url))
                                        # Build base URL from request
                                        resource_uri = f"{url_obj.scheme}://{url_obj.host}"
                                        if url_obj.port and url_obj.port not in (80, 443):
                                            resource_uri += f":{url_obj.port}"
                                        logger.debug(f"Built base URL from request URL: {resource_uri}")
                                    else:
                                        # Fallback without URL library
                                        url_str = str(request.url)
                                        if url_str.startswith("http"):
                                            # Extract scheme and host
                                            from urllib.parse import urlparse

                                            parsed = urlparse(url_str)
                                            resource_uri = f"{parsed.scheme}://{parsed.netloc}"
                                            logger.debug(f"Built base URL via urlparse: {resource_uri}")

                        # Approach B: Check for base_url attribute
                        elif hasattr(request, "base_url") and request.base_url:
                            base_url_str = str(request.base_url)
                            if base_url_str.startswith(("http://", "https://")):
                                resource_uri = base_url_str.rstrip("/")
                                logger.debug(f"Using request.base_url: {resource_uri}")

                        # Approach C: Extract from scope (lower level)
                        elif hasattr(request, "scope") and request.scope:
                            scope = request.scope
                            # Extract from ASGI scope
                            headers = dict(scope.get("headers", []))
                            proto = headers.get(b"x-forwarded-proto", b"http").decode()
                            host = headers.get(b"x-forwarded-host")

                            if host:
                                host = host.decode()
                                resource_uri = f"{proto}://{host}"
                                logger.debug(f"Built base URL from ASGI scope: {resource_uri}")
                            else:
                                # Extract from server info in scope
                                server = scope.get("server", ("localhost", 8000))
                                scheme = scope.get("scheme", "http")
                                host_port = f"{server[0]}:{server[1]}" if server[1] != 80 else server[0]
                                resource_uri = f"{scheme}://{host_port}"
                                logger.debug(f"Built base URL from ASGI server: {resource_uri}")

            except Exception as e:
                logger.warning(f"Failed to extract base URL from request context: {e}")
                # Continue to other methods

        # Method 2: Use ZIMAGE_BASE_URL environment variable
        if not resource_uri and base_url:
            resource_uri = base_url.rstrip("/")
            logger.debug(f"Using ZIMAGE_BASE_URL: {resource_uri}")

        # Method 3: Intelligent fallback
        if not resource_uri:
            # Try to detect if we're in a known environment
            if "RENDER_EXTERNAL_URL" in os.environ:
                # Render.com deployment
                resource_uri = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
                logger.debug(f"Detected Render.com deployment: {resource_uri}")
            elif "HEROKU_APP_NAME" in os.environ:
                # Heroku deployment
                app_name = os.environ["HEROKU_APP_NAME"]
                resource_uri = f"https://{app_name}.herokuapp.com"
                logger.debug(f"Detected Heroku deployment: {resource_uri}")
            elif "KUBERNETES_SERVICE_HOST" in os.environ:
                # Kubernetes (use localhost for development)
                resource_uri = "http://localhost:8000"
                logger.warning(f"Detected Kubernetes deployment, using localhost: {resource_uri}")
            else:
                # Final fallback - try to determine from common patterns
                import socket

                hostname = socket.gethostname()

                # Check if we're running locally
                if hostname in ("localhost", "127.0.0.1") or hostname.endswith(".local"):
                    resource_uri = "http://localhost:8000"
                    logger.warning(f"Assuming local development, using: {resource_uri}")
                else:
                    # Last resort - this won't pass validation but provides context
                    logger.error("Cannot determine base URL for absolute URI generation")
                    logger.error("Please set ZIMAGE_BASE_URL environment variable")
                    # We'll raise a more informative error later

        # Now construct the full URL
        if resource_uri:
            # Ensure we have a proper base URL
            if not resource_uri.startswith(("http://", "https://")):
                # This shouldn't happen with our logic, but just in case
                resource_uri = f"http://{resource_uri}"

            # Combine base URL with relative path
            if URL:
                url_obj = URL(resource_uri)
                if not url_obj.path or url_obj.path == "/":
                    # It's just a scheme+host, append the path
                    resource_uri = f"{resource_uri.rstrip('/')}{relative_url}"
                else:
                    # Base URL already has a path, ensure proper joining
                    from urllib.parse import urljoin

                    resource_uri = urljoin(resource_uri.rstrip("/") + "/", relative_url.lstrip("/"))
            else:
                # Fallback URL construction
                resource_uri = f"{resource_uri.rstrip('/')}{relative_url}"

            logger.info(f"Generated absolute URI: {resource_uri}")
        else:
            # If we still don't have a valid URL, raise an error
            raise ValueError(
                "Cannot generate absolute URL for ResourceLink. "
                "Please set the ZIMAGE_BASE_URL environment variable to your server's public URL "
                "(e.g., https://your-domain.com or http://localhost:8000)"
            )
    else:
        # For stdio transport, use file:// URI for local access
        resource_uri = f"file://{output_path.resolve()}"

    # Create text content with generation info and file metadata
    # Note: For SSE (remote), we include the URL instead of local file path
    # For stdio (local), we include the local file path
    text_content_dict = {
        "message": "Image generated successfully",
        "duration_seconds": round(duration, 2),
        "width": width,
        "height": height,
        "precision": precision,
        "model_id": model_id,
        "seed": seed,
        "filename": filename,
    }

    # Add appropriate path/URL based on transport
    if transport == "sse":
        # For SSE, add the absolute URL that clients can use
        text_content_dict["url"] = resource_uri
        text_content_dict["access_note"] = "Access image via ResourceLink.uri or this URL"
    else:
        # For stdio, add local file path
        text_content_dict["file_path"] = str(output_path.resolve())
        text_content_dict["access_note"] = "Access image at the local file path"

    text_content = types.TextContent(
        type="text",
        text=json.dumps(text_content_dict),
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
    result = [
        text_content,
        resource_content,
        image_content,
    ]

    # For SSE transport, we need to handle potential client disconnections
    # that can happen during long-running operations like image generation
    if transport == "sse" and ctx is not None:
        try:
            # Check if the session is still active before returning
            # This helps prevent ClosedResourceError when client has disconnected
            if hasattr(ctx, "_session") and hasattr(ctx._session, "_is_closed"):
                if ctx._session._is_closed:
                    logger.warning("SSE client disconnected before response could be sent")
                    # Return a minimal response that won't crash
                    return [
                        types.TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "error": "Client disconnected (timeout). Image was generated successfully.",
                                    "filename": filename,
                                    "file_path": str(output_path.resolve()),
                                }
                            ),
                        )
                    ]
        except Exception:
            # If we can't check session status, just proceed normally
            pass

    return result

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

    For long-running operations (high steps/large images), this function will:
    - Send progress notifications at key milestones via ctx.report_progress()
    - Handle client disconnections gracefully
    """
    transport = _infer_transport(ctx)
    return await _generate_impl(
        prompt=prompt,
        steps=steps,
        width=width,
        height=height,
        seed=seed,
        precision=precision,
        transport=transport,
        ctx=ctx,
    )

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

    # Validate URL configuration for SSE mode
    base_url = os.getenv("ZIMAGE_BASE_URL")
    if base_url:
        # Validate that it's a proper URL
        if not base_url.startswith(('http://', 'https://')):
            logger.warning(f"ZIMAGE_BASE_URL should start with http:// or https://, got: {base_url}")
        else:
            logger.info(f"Using configured ZIMAGE_BASE_URL: {base_url}")
    else:
        # Check for known deployment environments
        if any(env in os.environ for env in ['RENDER_EXTERNAL_URL', 'HEROKU_APP_NAME']):
            logger.info("Will auto-detect base URL from deployment environment")
        else:
            logger.warning(
                "ZIMAGE_BASE_URL not set. The server will try to auto-detect the base URL from request context. "
                "If this fails, please set ZIMAGE_BASE_URL to your server's public URL."
            )

    return mcp.sse_app()

def run_stdio():
    """Run MCP over stdio (used by zimg-mcp and `zimg mcp`)."""
    setup_logging()
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
