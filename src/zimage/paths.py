import os
from pathlib import Path
import platformdirs

APP_NAME = "z-image-studio"

def get_data_dir() -> Path:
    """
    Returns the main data directory for the application (DB, config, models).
    Prioritizes ZIMAGE_DATA_DIR environment variable.
    Falls back to user_data_dir via platformdirs (z-image-studio).
    Ensures the directory exists.
    """
    env_path = os.environ.get("ZIMAGE_DATA_DIR")
    if env_path:
        path = Path(env_path).expanduser().resolve()
    else:
        # Use standard user data directory (no dot prefix)
        path = Path(platformdirs.user_data_dir(appname=APP_NAME, appauthor=False))

    path.mkdir(parents=True, exist_ok=True)
    return path

def get_models_dir() -> Path:
    """Returns the directory for models."""
    path = get_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_outputs_dir() -> Path:
    """
    Returns the directory for generated images.
    Prioritizes ZIMAGE_OUTPUT_DIR.
    Falls back to ~/.z-image-studio.
    """
    env_path = os.environ.get("ZIMAGE_OUTPUT_DIR")
    if env_path:
        path = Path(env_path).expanduser().resolve()
    else:
        path = Path.home() / f".{APP_NAME}"

    path.mkdir(parents=True, exist_ok=True)
    return path

def get_loras_dir() -> Path:
    """Returns the directory for LoRA models."""
    path = get_data_dir() / "loras"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_db_path() -> Path:
    """Returns the path to the SQLite database."""
    return get_data_dir() / "zimage.db"
