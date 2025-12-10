from __future__ import annotations

from pathlib import Path
import time
from typing import Optional

try:
    from .paths import get_outputs_dir
    from .logger import get_logger
    from . import db
except ImportError:  # pragma: no cover
    from paths import get_outputs_dir  # type: ignore
    from logger import get_logger  # type: ignore
    import db  # type: ignore

logger = get_logger("zimage.storage")

def sanitize_prompt(prompt: str, max_len: int = 30) -> str:
    safe = "".join(c for c in prompt[:max_len] if c.isalnum() or c in "-_")
    return safe or "image"

def save_image(image, prompt: str, outputs_dir: Optional[str | Path] = None, ext: str = "png") -> Path:
    """
    Save a PIL image to the outputs directory with a prompt-based filename.

    Returns the full Path to the saved file.
    """
    base_dir = Path(outputs_dir) if outputs_dir else Path(get_outputs_dir())
    base_dir.mkdir(parents=True, exist_ok=True)

    safe_prompt = sanitize_prompt(prompt)
    timestamp = int(time.time())
    filename = f"{safe_prompt}_{timestamp}.{ext}"
    output_path = base_dir / filename
    logger.info(f"Saving image to {output_path}")

    image.save(output_path)
    return output_path

def record_generation(
    prompt: str,
    steps: int,
    width: int,
    height: int,
    filename: str,
    generation_time: float,
    file_size_kb: float,
    model: str,
    precision: str,
    seed: Optional[int],
    cfg_scale: float = 0.0,
):
    """
    Persist a generation record to the DB. Best-effort with logging.
    Returns the new record ID or None on failure.
    """
    try:
        return db.add_generation(
            prompt=prompt,
            steps=steps,
            width=width,
            height=height,
            filename=filename,
            generation_time=generation_time,
            file_size_kb=file_size_kb,
            model=model,
            cfg_scale=cfg_scale,
            seed=seed,
            status="succeeded",
            precision=precision,
        )
    except Exception as e:  # pragma: no cover
        logger.error(f"Failed to record generation to DB: {e}")
        return None
