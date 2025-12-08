from fastapi import FastAPI, HTTPException, BackgroundTasks, Response, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Optional, List
import asyncio
import time
import threading
import sqlite3
import shutil
import hashlib
import os
import uuid

try:
    from .engine import generate_image
    from .hardware import get_available_models, MODEL_ID_MAP
    from . import db
    from . import migrations
    from .paths import (
        ensure_initial_setup,
        get_data_dir,
        get_loras_dir,
        get_outputs_dir,
    )
except ImportError:
    from engine import generate_image
    from hardware import get_available_models, MODEL_ID_MAP
    import db
    import migrations
    from paths import (
        ensure_initial_setup,
        get_data_dir,
        get_loras_dir,
        get_outputs_dir,
    )

# ANSI escape codes for colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def log_info(message: str):
    print(f"{GREEN}INFO{RESET}: {message}")

def log_warn(message: str):
    print(f"{YELLOW}WARN{RESET}: {message}")

# Constants
MAX_LORA_FILE_SIZE = 1 * 1024 * 1024 * 1024 # 1 GB

# Directory Configuration
ensure_initial_setup()
OUTPUTS_DIR = get_outputs_dir()
LORAS_DIR = get_loras_dir()

app = FastAPI()

# Initialize Database Schema
migrations.init_db()

@app.on_event("startup")
async def startup_event():
    log_info(f"\t  Data Directory: {get_data_dir()}")
    log_info(f"\t  Outputs Directory: {get_outputs_dir()}")

# Dedicated worker thread for MPS/GPU operations
# MPS on macOS is thread-sensitive. Accessing the model from multiple threads
# (even sequentially) can cause resource leaks (semaphores) and crashes.
# We use a single worker thread to ensure the model is always accessed from the same thread.
import queue
job_queue = queue.Queue()

def worker_loop():
    while True:
        task = job_queue.get()
        if task is None:
            break
        func, args, kwargs, future, loop = task
        try:
            result = func(*args, **kwargs)
            if future and loop:
                loop.call_soon_threadsafe(future.set_result, result)
        except Exception as e:
            if future and loop:
                loop.call_soon_threadsafe(future.set_exception, e)
        finally:
            job_queue.task_done()

worker_thread = threading.Thread(target=worker_loop, daemon=True)
worker_thread.start()

async def run_in_worker(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    job_queue.put((func, args, kwargs, future, loop))
    return await future

def run_in_worker_nowait(func, *args, **kwargs):
    """Fire and forget task for the worker thread."""
    job_queue.put((func, args, kwargs, None, None))

def cleanup_gpu():
    """
    Force garbage collection and MPS cache clearing.
    This is a slow operation (~seconds to minutes) but necessary to prevent OOM
    on memory-constrained MPS devices after large generations.
    """
    import gc
    import torch
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()

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
            print(f"Error deleting LoRA file {file_path}: {e}")
            # We already deleted from DB, so it's a "soft" failure
            
    return {"message": "LoRA deleted"}


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    try:
        # Validate precision early to avoid KeyError inside engine
        if req.precision not in MODEL_ID_MAP:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unsupported precision '{req.precision}'"}
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

        start_time = time.time()
        
        # Run generation in the dedicated worker thread
        image = await run_in_worker(
            generate_image,
            prompt=req.prompt,
            steps=req.steps,
            width=width,
            height=height,
            seed=req.seed,
            precision=req.precision,
            loras=resolved_loras
        )
        
        # Save file
        safe_prompt = "".join(c for c in req.prompt[:30] if c.isalnum() or c in "-_")
        if not safe_prompt:
            safe_prompt = "image"
        timestamp = int(time.time())
        filename = f"{safe_prompt}_{timestamp}.png"
        output_path = OUTPUTS_DIR / filename
        
        image.save(output_path)
        
        duration = time.time() - start_time
        file_size_kb = output_path.stat().st_size / 1024
        
        # Get the actual HF ID used (guard against bad inputs)
        model_id = MODEL_ID_MAP.get(req.precision)
        if model_id is None:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unsupported precision '{req.precision}'"}
            )

        # Record to DB
        new_id = db.add_generation(
            prompt=req.prompt,
            steps=req.steps,
            width=width,
            height=height,
            filename=filename,
            generation_time=duration,
            file_size_kb=file_size_kb,
            model=model_id,
            cfg_scale=0.0,
            seed=req.seed,
            status="succeeded",
            precision=req.precision,
            loras=db_loras
        )
        
        # Schedule cleanup to run AFTER the response is sent
        background_tasks.add_task(run_in_worker_nowait, cleanup_gpu)
        
        return {
            "id": new_id,
            "image_url": f"/outputs/{filename}",
            "generation_time": round(duration, 2),
            "width": image.width,
            "height": image.height,
            "file_size_kb": round(file_size_kb, 1),
            "seed": req.seed,
            "precision": req.precision,
            "model_id": model_id,
            "loras": req.loras
        }
    except Exception as e:
        print(f"Error generating image: {e}")
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
            print(f"Error deleting file {file_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete associated image file: {e}")
    
    return {"message": "History item and associated file deleted successfully"}

# Serve generated images
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

# Serve frontend
# Use absolute path for package-internal static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
