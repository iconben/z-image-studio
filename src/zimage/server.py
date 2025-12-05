from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from pathlib import Path
import asyncio
import time
import threading
import sqlite3

try:
    from .engine import generate_image, get_available_models, MODEL_ID_MAP
    from . import db
    from . import migrations
except ImportError:
    from engine import generate_image, get_available_models, MODEL_ID_MAP
    import db
    import migrations

app = FastAPI()

# Initialize Database Schema
migrations.init_db()

# Ensure outputs directory exists
OUTPUTS_DIR = Path("outputs")
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

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

class GenerateRequest(BaseModel):
    prompt: str
    steps: int = 9
    width: int = 1280
    height: int = 720
    seed: int = None
    precision: str = "q8"

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

@app.get("/models")
async def get_models():
    """Get list of available models with hardware recommendations."""
    return get_available_models()

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
        
        start_time = time.time()
        
        # Run generation in the dedicated worker thread
        image = await run_in_worker(
            generate_image,
            prompt=req.prompt,
            steps=req.steps,
            width=width,
            height=height,
            seed=req.seed,
            precision=req.precision
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
            precision=req.precision
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
            "model_id": model_id
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
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
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
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# Serve frontend
# Use absolute path for package-internal static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
