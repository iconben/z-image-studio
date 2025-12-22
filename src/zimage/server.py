from fastapi import FastAPI, HTTPException, BackgroundTasks, Response, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator
from urllib.parse import quote
import asyncio
import time
import sqlite3
import shutil
import hashlib
import os
import sys
import uuid
import random
import json
# Handle both module execution and direct execution scenarios
try:
    from .engine import generate_image, cleanup_memory
    from .worker import run_in_worker, run_in_worker_nowait
    from .hardware import get_available_models, MODEL_ID_MAP, normalize_precision
    from .logger import get_logger
    from .storage import save_image, record_generation
    from .mcp_server import get_sse_app
    from . import db
    from . import migrations
    from .paths import (
        ensure_initial_setup,
        get_data_dir,
        get_loras_dir,
        get_outputs_dir,
    )
except ImportError:
    # When running directly (e.g., uv run src/zimage/cli.py serve)
    # Add the zimage directory to sys.path and import directly
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from engine import generate_image, cleanup_memory
    from worker import run_in_worker, run_in_worker_nowait
    from hardware import get_available_models, MODEL_ID_MAP, normalize_precision
    from logger import get_logger
    from storage import save_image, record_generation
    from mcp_server import get_sse_app
    import db
    import migrations
    from paths import (
        ensure_initial_setup,
        get_data_dir,
        get_loras_dir,
        get_outputs_dir,
    )

# Constants
MAX_LORA_FILE_SIZE = 1 * 1024 * 1024 * 1024 # 1 GB

# Directory Configuration
ensure_initial_setup()
OUTPUTS_DIR = get_outputs_dir()
LORAS_DIR = get_loras_dir()

logger = get_logger("zimage.server")

app = FastAPI()
# Initialize Database Schema
migrations.init_db()

# Add global exception handler for SSE client disconnects
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle global exceptions, particularly SSE client disconnects."""
    if "ClosedResourceError" in str(exc) or "Broken pipe" in str(exc):
        logger.warning(f"Client disconnected during request: {exc}")
        return Response(status_code=200)

    # Log other unexpected errors
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Mount MCP SSE endpoint by default unless disabled via env flag
# Mounts at /mcp-sse (for SSE connection and POST messages)
# Note: For proper operation, set ZIMAGE_BASE_URL environment variable to your server's public URL.
# Example: ZIMAGE_BASE_URL=https://your-domain.com or ZIMAGE_BASE_URL=http://localhost:8000
ENABLE_MCP = os.getenv("ZIMAGE_DISABLE_MCP", "0") != "1"
if ENABLE_MCP:
    try:
        # Mount SSE at /mcp-sse
        sse_app = get_sse_app()
        app.mount("/mcp-sse", sse_app)
        logger.info(f"    Mounted MCP SSE endpoint at /mcp-sse")

        # Log URL configuration advice
        base_url = os.getenv("ZIMAGE_BASE_URL")
        if not base_url:
            logger.info(
                "    TIP: Set ZIMAGE_BASE_URL environment variable for reliable absolute URL generation\n"
            )
    except Exception as e:
        logger.error(f"Failed to mount MCP SSE endpoint: {e}")

def add_mcp_streamable_http_endpoints(fastapi_app: FastAPI):
    """Add MCP Streamable HTTP endpoints to the FastAPI app if enabled."""
    if not ENABLE_MCP:
        return

    @fastapi_app.post("/mcp", response_class=JSONResponse)
    async def handle_mcp_streamable_request(request: Request) -> JSONResponse:
        """
        Handle MCP JSON-RPC requests with streaming responses.

        This endpoint implements the MCP Streamable HTTP transport protocol:
        - Accepts JSON-RPC requests via POST
        - Returns streaming JSON responses
        - Supports initialize, tool calls, and progress reporting

        Clients should try this endpoint first, falling back to /mcp-sse if needed.
        """
        try:
            # Parse request body
            body = await request.body()
            request_data = json.loads(body.decode('utf-8'))

            method = request_data.get('method', 'unknown')
            logger.info(f"Received MCP Streamable HTTP request: {method}")

            # Collect responses and return a single JSON-RPC response for compatibility
            try:
                response_payload = None
                async for chunk in _process_mcp_streamable_request(request_data, request):
                    if isinstance(chunk, dict) and ("result" in chunk or "error" in chunk):
                        response_payload = chunk
                if response_payload is None:
                    response_payload = {
                        "jsonrpc": "2.0",
                        "id": request_data.get("id", None),
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": "No response generated"
                        }
                    }
            except Exception as e:
                logger.error(f"Error processing MCP Streamable HTTP request: {e}")
                response_payload = {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id", None),
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e)
                    }
                }

            return JSONResponse(
                content=response_payload,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                }
            )

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MCP Streamable HTTP request: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON request")

        except Exception as e:
            logger.error(f"Error handling MCP Streamable HTTP request: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @fastapi_app.options("/mcp")
    async def handle_mcp_streamable_options():
        """Handle CORS preflight requests for MCP Streamable HTTP."""
        return Response(
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )

# Add the streamable HTTP endpoints
add_mcp_streamable_http_endpoints(app)

# Log availability
if ENABLE_MCP:
    logger.info("    MCP Streamable HTTP endpoint available at /mcp")
    logger.info("    Clients should try /mcp first, fallback to /mcp-sse/sse if needed")
else:
    logger.info("    MCP endpoints disabled")

class LoraInput(BaseModel):
    filename: str
    strength: float = Field(ge=-1.0, le=2.0)

class GenerateRequest(BaseModel):
    prompt: str
    steps: int = 9
    width: int = 1280
    height: int = 720
    seed: int = None
    precision: str = "q8"
    loras: List[LoraInput] = []

class GenerateResponse(BaseModel):
    id: int
    image_url: str
    generation_time: float
    width: int
    height: int
    file_size_kb: float
    seed: int = None
    precision: str
    model_id: str
    loras: List[LoraInput] = []

@app.get("/models")
async def get_models():
    """Get list of available models with hardware recommendations."""
    return get_available_models()

@app.get("/loras")
async def get_loras():
    """List available LoRA files."""
    return db.list_loras()

@app.post("/loras")
async def upload_lora(
    file: UploadFile = File(...),
    display_name: Optional[str] = Form(None),
    trigger_word: Optional[str] = Form(None)
):
    """Upload a new LoRA file."""
    if not file.filename.endswith(".safetensors"):
         raise HTTPException(status_code=400, detail="Only .safetensors files are supported")
    
    # Process file in chunks for size validation and hash calculation
    hasher = hashlib.sha256()
    total_size = 0
    
    # Create a temporary file to store the upload while processing
    temp_upload_path = LORAS_DIR / f"{uuid.uuid4()}.tmp"
    try:
        with open(temp_upload_path, "wb") as temp_file:
            while True:
                chunk = await file.read(8192) # Read in 8KB chunks
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_LORA_FILE_SIZE:
                    raise HTTPException(status_code=413, detail=f"File too large. Max size is {MAX_LORA_FILE_SIZE / (1024*1024)} MB.")
                hasher.update(chunk)
                temp_file.write(chunk)
        
        file_hash = hasher.hexdigest()
        
        # Check if a LoRA with this hash already exists in DB
        existing_lora_by_hash = db.get_lora_by_hash(file_hash)
        if existing_lora_by_hash:
            # Check if the existing file on disk still has the same hash (corruption check)
            existing_path = LORAS_DIR / existing_lora_by_hash['filename']
            if existing_path.exists():
                with open(existing_path, "rb") as f:
                    # Stream hash check for existing file as well
                    existing_hasher = hashlib.sha256()
                    while True:
                        existing_chunk = f.read(8192)
                        if not existing_chunk:
                            break
                        existing_hasher.update(existing_chunk)
                    if existing_hasher.hexdigest() == file_hash:
                        # Same file, same content, already exists. Clean up temp and return existing.
                        os.remove(temp_upload_path)
                        return {"id": existing_lora_by_hash['id'], "filename": existing_lora_by_hash['filename'], "display_name": existing_lora_by_hash['display_name']}
            
            # If hash exists in DB but file doesn't exist or content changed, we'll proceed to create a new entry/file
            # (temp_upload_path still exists, will be used below)

        # Determine filename
        base_filename = Path(file.filename).name
        final_filename = base_filename
        
        # Resolve filename collisions for files on disk
        if (LORAS_DIR / final_filename).exists():
            # Read hash of existing file on disk (streamed)
            existing_disk_path = LORAS_DIR / final_filename
            existing_hasher = hashlib.sha256()
            with open(existing_disk_path, "rb") as f:
                while True:
                    existing_chunk = f.read(8192)
                    if not existing_chunk:
                        break
                    existing_hasher.update(existing_chunk)
                existing_disk_hash = existing_hasher.hexdigest()
            
            if existing_disk_hash == file_hash:
                # File with same name and same content exists on disk, and DB might be inconsistent or correct.
                # Find DB entry for this file. If none, create it, otherwise use existing.
                lora_info = db.get_lora_by_filename(final_filename)
                if lora_info:
                    os.remove(temp_upload_path) # Clean up temp file
                    return {"id": lora_info['id'], "filename": lora_info['filename'], "display_name": lora_info['display_name']}
                else:
                    # File exists on disk, content matches, but not in DB. Add to DB and reuse filename.
                    shutil.move(temp_upload_path, LORAS_DIR / final_filename) # Move temp to final, overwriting
                    new_id = db.add_lora(final_filename, display_name or base_filename, trigger_word, file_hash)
                    return {"id": new_id, "filename": final_filename, "display_name": display_name or base_filename}
            else:
                # Filename collision with different content, generate unique name
                name_parts = base_filename.rsplit('.', 1)
                unique_suffix = file_hash[:6] # Use a part of hash for uniqueness
                
                # Prevent overly long filenames
                if len(name_parts[0]) + len(unique_suffix) + 1 + len(name_parts[1]) > 250: # max filename length
                    name_parts[0] = name_parts[0][:250 - len(unique_suffix) - len(name_parts[1]) - 2] # Truncate base name
                
                final_filename = f"{name_parts[0]}_{unique_suffix}.{name_parts[1]}"
                
                # In very rare cases, even hash suffix might collide, add counter
                counter = 1
                while (LORAS_DIR / final_filename).exists():
                    final_filename = f"{name_parts[0]}_{unique_suffix}_{counter}.{name_parts[1]}"
                    counter += 1

        # Move the temporary uploaded file to its final destination
        shutil.move(temp_upload_path, LORAS_DIR / final_filename)
        
        # Add to DB
        new_id = db.add_lora(final_filename, display_name or base_filename, trigger_word, file_hash)
        
        return {"id": new_id, "filename": final_filename, "display_name": display_name or base_filename}
        
    except HTTPException: # Re-raise HTTPExceptions directly
        if temp_upload_path.exists():
            os.remove(temp_upload_path)
        raise
    except Exception as e:
        if temp_upload_path.exists():
            os.remove(temp_upload_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.delete("/loras/{lora_id}")
async def delete_lora(lora_id: int):
    """Delete a LoRA file and record."""
    conn = db._get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filename FROM lora_files WHERE id = ?", (lora_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="LoRA not found")
        
    filename = row['filename']
    file_path = LORAS_DIR / filename
    
    db.delete_lora(lora_id)
    
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError as e:
            logger.error(f"Error deleting LoRA file {file_path}: {e}")
            # We already deleted from DB, so it's a "soft" failure
            
    return {"message": "LoRA deleted"}


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    try:
        # Normalize and validate precision early to avoid KeyError inside engine
        try:
            precision = normalize_precision(req.precision)
        except ValueError as e:
            logger.error(f"Precision validation failed: {e}")
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid precision value."}
            )

        # Validate dimensions (must be multiple of 16)
        width = req.width if req.width % 16 == 0 else (req.width // 16) * 16
        height = req.height if req.height % 16 == 0 else (req.height // 16) * 16
        
        # Ensure minimums
        width = max(16, width)
        height = max(16, height)
        
        # Validate LoRAs
        if len(req.loras) > 4:
             return JSONResponse(status_code=400, content={"error": "Maximum 4 LoRAs allowed."})

        resolved_loras = [] # List of (path, strength) for engine
        db_loras = [] # List of {id, strength} for DB

        for lora_input in req.loras:
            # Check if it exists in DB/disk
            lora_info = db.get_lora_by_filename(lora_input.filename)
            if not lora_info:
                 return JSONResponse(status_code=400, content={"error": f"LoRA '{lora_input.filename}' not found"})
            
            lora_full_path = LORAS_DIR / lora_input.filename
            if not lora_full_path.exists():
                return JSONResponse(status_code=500, content={"error": f"LoRA file missing on disk: {lora_input.filename}"})
            
            resolved_loras.append((str(lora_full_path.resolve()), lora_input.strength))
            db_loras.append({"id": lora_info['id'], "strength": lora_input.strength})

        # Generate a random seed if none provided (for reproducibility tracking)
        if req.seed is None:
            req_seed = random.randint(0, 2**31 - 1)
            logger.info(f"Generated random seed: {req_seed}")
        else:
            req_seed = req.seed
        
        start_time = time.time()
        
        # Run generation in the dedicated worker thread
        image = await run_in_worker(
            generate_image,
            prompt=req.prompt,
            steps=req.steps,
            width=width,
            height=height,
            seed=req_seed,
            precision=precision,
            loras=resolved_loras
        )

        # Save file
        output_path = save_image(image, req.prompt, outputs_dir=OUTPUTS_DIR)
        filename = output_path.name

        duration = time.time() - start_time
        file_size_kb = output_path.stat().st_size / 1024

        # Get the actual HF ID used
        model_id = MODEL_ID_MAP[precision]

        # Record to DB
        new_id = record_generation(
            prompt=req.prompt,
            steps=req.steps,
            width=width,
            height=height,
            filename=filename,
            generation_time=duration,
            file_size_kb=file_size_kb,
            model=model_id,
            cfg_scale=0.0,
            seed=req_seed,
            precision=precision,
            loras=db_loras,
        )
        new_id = new_id or -1

        # Schedule cleanup to run AFTER the response is sent
        background_tasks.add_task(run_in_worker_nowait, cleanup_memory)
        
        return {
            "id": new_id,
            "image_url": f"/outputs/{quote(filename, safe='')}",
            "generation_time": round(duration, 2),
            "width": image.width,
            "height": image.height,
            "file_size_kb": round(file_size_kb, 1),
            "seed": req_seed,
            "precision": precision,
            "model_id": model_id,
            "loras": req.loras
        }
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
async def get_history(response: Response, limit: int = 20, offset: int = 0):
    items, total = db.get_history(limit, offset)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page-Size"] = str(limit)
    response.headers["X-Page-Offset"] = str(offset)
    return items

@app.delete("/history/{item_id}")
async def delete_history_item(item_id: int):
    conn = db._get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT filename FROM generations WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="History item not found")
    
    filename = row['filename']
    file_path = OUTPUTS_DIR / filename

    db.delete_generation(item_id)
    
    if file_path.exists():
        try:
            file_path.unlink()
        except OSError as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete associated image file: {e}")
    
    return {"message": "History item and associated file deleted successfully"}

@app.get("/download/{filename}")
async def download_image(filename: str):
    """Serve the image file as an attachment to force download."""
    # Basic path traversal protection: ensure filename is just a name
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = OUTPUTS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path, 
        media_type="image/png", 
        filename=filename,
        content_disposition_type="attachment"
    )

# MCP Streamable HTTP request processing function
async def _process_mcp_streamable_request(
    request_data: Dict[str, Any],
    http_request: Request
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Process an MCP request and yield streaming response chunks.

    Args:
        request_data: JSON-RPC request data
        http_request: FastAPI Request object for context

    Yields:
        Response chunks for streaming
    """
    method = request_data.get("method")
    params = request_data.get("params", {})
    request_id = request_data.get("id")

    # Create a lightweight context object with request context
    class StreamableHttpContext:
        """Lightweight context for Streamable HTTP requests."""
        def __init__(self, request):
            self.request_context = type('RequestContext', (), {
                'request': request
            })()

    ctx = StreamableHttpContext(http_request)

    try:
        if method == "initialize":
            # Handle initialize request
            result = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {
                        "tools": {
                            "listChanged": True
                        },
                        "progress": {
                            "progressToken": True
                        }
                    },
                    "serverInfo": {
                        "name": "Z-Image Studio",
                        "version": "1.0.0"
                    }
                }
            }
            yield result

        elif method == "tools/list":
            # Handle tools list request
            tools = [
                {
                    "name": "generate",
                    "description": "Generate an image from a text prompt",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "prompt": {"type": "string"},
                            "steps": {"type": "integer", "default": 9},
                            "width": {"type": "integer", "default": 1280},
                            "height": {"type": "integer", "default": 720},
                            "seed": {"type": ["integer", "null"], "default": None},
                            "precision": {"type": "string", "default": "q8", "enum": ["full", "q8", "q4"]}
                        },
                        "required": ["prompt"]
                    }
                },
                {
                    "name": "list_models",
                    "description": "List available image generation models and hardware recommendations",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "list_history",
                    "description": "List recent image generations history",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "default": 10},
                            "offset": {"type": "integer", "default": 0}
                        }
                    }
                }
            ]

            result = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools}
            }
            yield result

        elif method == "tools/call":
            # Handle tool execution request
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name == "generate":
                # Stream the generate function with progress
                async for chunk in _handle_generate_tool_streamable(arguments, ctx, request_id):
                    yield chunk

            elif tool_name == "list_models":
                result = await _handle_list_models_tool()
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result
                            }
                        ]
                    }
                }
                yield response

            elif tool_name == "list_history":
                limit = arguments.get("limit", 10)
                offset = arguments.get("offset", 0)
                result = await _handle_list_history_tool(limit, offset)
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result
                            }
                        ]
                    }
                }
                yield response

            else:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {tool_name}"
                    }
                }
                yield error_response

        else:
            # Unknown method
            error_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            yield error_response

    except Exception as e:
        logger.error(f"Error processing {method}: {e}")
        error_response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            }
        }
        yield error_response


async def _handle_generate_tool_streamable(
    arguments: Dict[str, Any],
    ctx,  # Mock context with request_context
    request_id: Any
) -> AsyncGenerator[Dict[str, Any], None]:
    """Handle the generate tool with streaming progress for Streamable HTTP."""
    # Initialize logger outside try block so it's available in exception handlers
    try:
        from .logger import get_logger
    except ImportError:
        # When running directly, add to path and import
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from logger import get_logger
    logger = get_logger(__name__)

    # Import shared MCP generation implementation
    try:
        from .mcp_server import _generate_impl
        import mcp.types as types
    except ImportError:
        # When running directly, add to path and import
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from mcp_server import _generate_impl
        import mcp.types as types

    try:
        prompt = arguments.get("prompt")
        steps = arguments.get("steps", 9)
        width = arguments.get("width", 1280)
        height = arguments.get("height", 720)
        seed = arguments.get("seed")
        precision = arguments.get("precision", "q8")

        result = await _generate_impl(
            prompt=prompt,
            steps=steps,
            width=width,
            height=height,
            seed=seed,
            precision=precision,
            transport="streamable_http",
            ctx=ctx,
        )

        content = []
        for item in result:
            if isinstance(item, types.TextContent):
                content.append({"type": "text", "text": item.text})
            elif isinstance(item, types.ResourceLink):
                content.append(
                    {
                        "type": "resource_link",
                        "name": item.name,
                        "uri": str(item.uri),
                        "mimeType": item.mimeType,
                    }
                )
            elif isinstance(item, types.ImageContent):
                content.append(
                    {
                        "type": "image",
                        "data": item.data,
                        "mimeType": item.mimeType,
                    }
                )

        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": content},
        }

        # Warn if payload size is likely to exceed client limits (e.g., 1MB for some clients)
        response_size = len(json.dumps(response).encode("utf-8"))
        if response_size > 1_000_000:
            logger.warning(
                "Streamable HTTP response size is %d bytes; may exceed client limits",
                response_size
            )

        yield response
    except Exception as e:
        logger.error(f"Error in generate tool: {e}")
        error_response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32603,
                "message": "Generation failed",
                "data": str(e)
            }
        }
        yield error_response

  

async def _handle_list_models_tool() -> str:
    """Handle the list_models tool."""
    try:
        from .mcp_server import list_models
        return await list_models()
    except ImportError:
        # When running directly, add to path and import
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from mcp_server import list_models
        return await list_models()


async def _handle_list_history_tool(limit: int, offset: int) -> str:
    """Handle the list_history tool."""
    try:
        from .mcp_server import list_history
        return await list_history(limit, offset)
    except ImportError:
        # When running directly, add to path and import
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from mcp_server import list_history
        return await list_history(limit, offset)

# Serve generated images
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

# Serve frontend
# Use absolute path for package-internal static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
