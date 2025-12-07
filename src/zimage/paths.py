import os
from pathlib import Path
import platformdirs

def get_data_dir() -> Path:
    """
    Returns the main data directory for the application.
    Prioritizes ZIMAGE_DATA_DIR environment variable.
    Falls back to user_data_dir via platformdirs.
    Ensures the directory exists.
    """
    env_path = os.environ.get("ZIMAGE_DATA_DIR")
    if env_path:
        path = Path(env_path).expanduser().resolve()
    else:
        path = Path(platformdirs.user_data_dir(appname="z-image-studio", appauthor=False))

    path.mkdir(parents=True, exist_ok=True)
    return path

def get_outputs_dir() -> Path:
    """Returns the directory for generated images."""
    path = get_data_dir() / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_loras_dir() -> Path:
    """Returns the directory for LoRA models."""
    path = get_data_dir() / "loras"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_db_path() -> Path:
    """Returns the path to the SQLite database."""
    # The database file itself is not a directory, so we don't mkdir it,
    # but the parent directory is guaranteed by get_data_dir().
    return get_data_dir() / "zimage.db"
