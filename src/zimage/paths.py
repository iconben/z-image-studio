import json
import os
import shutil
from pathlib import Path
import platformdirs

APP_NAME = "z-image-studio"
CONFIG_DIR = Path.home() / f".{APP_NAME}"
CONFIG_PATH = CONFIG_DIR / "config.json"
_CONFIG_CACHE = None


def load_config() -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    if CONFIG_PATH.exists():
        try:
            _CONFIG_CACHE = json.loads(CONFIG_PATH.read_text())
        except Exception:
            _CONFIG_CACHE = {}
    else:
        _CONFIG_CACHE = {}
    return _CONFIG_CACHE


def get_data_dir() -> Path:
    """
    Returns the main data directory for app state (DB, LoRAs).
    Order: Z_IMAGE_STUDIO_DATA_DIR env -> platformdirs.user_data_dir("z-image-studio").
    """
    env_path = os.environ.get("Z_IMAGE_STUDIO_DATA_DIR")
    if env_path:
        path = Path(env_path).expanduser().resolve()
    else:
        cfg = load_config()
        cfg_path = cfg.get("Z_IMAGE_STUDIO_DATA_DIR") if isinstance(cfg, dict) else None
        if cfg_path:
            path = Path(cfg_path).expanduser().resolve()
        else:
            path = Path(platformdirs.user_data_dir(appname=APP_NAME, appauthor=False))

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_outputs_dir() -> Path:
    """Returns the directory for generated images."""
    env_path = os.environ.get("Z_IMAGE_STUDIO_OUTPUT_DIR")
    if env_path:
        path = Path(env_path).expanduser().resolve()
    else:
        cfg = load_config()
        cfg_path = cfg.get("Z_IMAGE_STUDIO_OUTPUT_DIR") if isinstance(cfg, dict) else None
        if cfg_path:
            path = Path(cfg_path).expanduser().resolve()
        else:
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
    return get_data_dir() / "zimage.db"


def get_config_path() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_PATH


def _copy_tree_if_exists(src: Path, dst: Path):
    if not src.exists() or src.resolve() == dst.resolve():
        return
    try:
        shutil.copytree(src, dst, dirs_exist_ok=True)
    except shutil.Error as exc:
        # Best-effort: ignore problematic entries (e.g., unreadable or broken symlinks)
        print(f"WARN: Partial copy from {src} to {dst} due to: {exc}")


def _move_tree_if_exists(src: Path, dst: Path):
    if not src.exists() or src.resolve() == dst.resolve():
        return
    if src.is_dir():
        for item in src.iterdir():
            target = dst / item.name
            if item.is_dir():
                _move_tree_if_exists(item, target)
            else:
                _move_file_if_exists(item, target)
        # Attempt to remove the now-empty source dir
        try:
            src.rmdir()
        except OSError:
            pass
    else:
        _move_file_if_exists(src, dst)


def _move_file_if_exists(src: Path, dst: Path):
    if not src.exists() or src.resolve() == dst.resolve():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(src, dst)
    except shutil.Error as exc:
        print(f"WARN: Could not move file from {src} to {dst}: {exc}")


def ensure_initial_setup():
    """Run one-time migration if config is missing, then write config.json."""
    config_path = get_config_path()
    if config_path.exists():
        return

    legacy_root = Path.cwd()
    print(f"INFO: No config found, migrating legacy data from {legacy_root}")

    outputs_dir = get_outputs_dir()
    loras_dir = get_loras_dir()
    db_path = get_db_path()
    print(f"INFO: Moving outputs -> {outputs_dir}")
    _move_tree_if_exists(legacy_root / "outputs", outputs_dir)
    print(f"INFO: Moving loras -> {loras_dir}")
    _move_tree_if_exists(legacy_root / "loras", loras_dir)
    print(f"INFO: Moving database -> {db_path}")
    _move_file_if_exists(legacy_root / "zimage.db", db_path)

    config = {
        "version": 1,
        "Z_IMAGE_STUDIO_DATA_DIR": None,
        "Z_IMAGE_STUDIO_OUTPUT_DIR": None,
    }
    global _CONFIG_CACHE
    _CONFIG_CACHE = config
    print(f"INFO: Writing config file to {config_path}")
    config_path.write_text(json.dumps(config, indent=2))
