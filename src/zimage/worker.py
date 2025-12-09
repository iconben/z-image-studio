import threading
import asyncio
import queue
from typing import Callable, Any

# Dedicated worker thread for MPS/GPU operations
# MPS on macOS is thread-sensitive. Accessing the model from multiple threads
# (even sequentially) can cause resource leaks (semaphores) and crashes.
# We use a single worker thread to ensure the model is always accessed from the same thread.

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
                if not loop.is_closed():
                    loop.call_soon_threadsafe(future.set_result, result)
        except Exception as e:
            if future and loop:
                if not loop.is_closed():
                    loop.call_soon_threadsafe(future.set_exception, e)
        finally:
            job_queue.task_done()

# Start worker thread on import
worker_thread = threading.Thread(target=worker_loop, daemon=True)
worker_thread.start()

async def run_in_worker(func: Callable, *args, **kwargs) -> Any:
    """Run a blocking function in the dedicated worker thread and await result."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    job_queue.put((func, args, kwargs, future, loop))
    return await future

def run_in_worker_nowait(func: Callable, *args, **kwargs):
    """Fire and forget task for the worker thread."""
    job_queue.put((func, args, kwargs, None, None))

def run_in_worker_sync(func: Callable, *args, **kwargs) -> Any:
    """Run a function in the worker thread and block until it completes (for non-async usage)."""
    result_container = {}
    event = threading.Event()

    def wrapper():
        try:
            result_container["data"] = func(*args, **kwargs)
        except Exception as e:
            result_container["error"] = e
        finally:
            event.set()

    job_queue.put((wrapper, (), {}, None, None))
    event.wait()

    if "error" in result_container:
        raise result_container["error"]
    return result_container.get("data")
