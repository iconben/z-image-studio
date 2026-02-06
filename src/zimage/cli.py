import argparse
import sys
import os
import json
import platform
from pathlib import Path
import traceback
from importlib.metadata import PackageNotFoundError, version as package_version

# ANSI escape codes for colors (kept for stdout output in run_models)
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

try:
    if getattr(sys, "frozen", False):
        # Running in PyInstaller bundle. Import light modules eagerly.
        try:
            from zimage import db
            from zimage import migrations
            from zimage.paths import (
                ensure_initial_setup,
                get_data_dir,
                get_loras_dir,
                get_outputs_dir,
                get_db_path,
                get_config_path,
            )
            from zimage.logger import get_logger, setup_logging
        except ImportError:
            # Fallback if zimage package is not found (e.g. flattened)
            import db
            import migrations
            from paths import (
                ensure_initial_setup,
                get_data_dir,
                get_loras_dir,
                get_outputs_dir,
                get_db_path,
                get_config_path,
            )
            from logger import get_logger, setup_logging
    elif __package__:
        from . import db
        from . import migrations
        from .paths import (
            ensure_initial_setup,
            get_data_dir,
            get_loras_dir,
            get_outputs_dir,
            get_db_path,
            get_config_path,
        )
        from .logger import get_logger, setup_logging
    else:
        # Allow running as a script directly (e.g. python src/zimage/cli.py)
        sys.path.append(str(Path(__file__).parent))
        import db
        import migrations
        from paths import (
            ensure_initial_setup,
            get_data_dir,
            get_loras_dir,
            get_outputs_dir,
            get_db_path,
            get_config_path,
        )
        from logger import get_logger, setup_logging
except ImportError:
    # Fallback for direct execution and flattened layouts.
    sys.path.append(str(Path(__file__).parent))
    import db
    import migrations
    from paths import (
        ensure_initial_setup,
        get_data_dir,
        get_loras_dir,
        get_outputs_dir,
        get_db_path,
        get_config_path,
    )
    from logger import get_logger, setup_logging

# Directory Configuration
ensure_initial_setup()
OUTPUTS_DIR = get_outputs_dir()
LORAS_DIR = get_loras_dir()

logger = get_logger("zimage.cli")

def log_info(message: str):
    logger.info(message)

def log_warn(message: str):
    logger.warning(message)

def log_error(message: str):
    logger.error(message)


def _load_generation_modules():
    """Lazily load heavy generation dependencies."""
    try:
        if getattr(sys, "frozen", False):
            try:
                from zimage.engine import generate_image
                from zimage.storage import save_image, record_generation
            except ImportError:
                from engine import generate_image
                from storage import save_image, record_generation
        elif __package__:
            from .engine import generate_image
            from .storage import save_image, record_generation
        else:
            sys.path.append(str(Path(__file__).parent))
            from engine import generate_image
            from storage import save_image, record_generation
    except ImportError:
        sys.path.append(str(Path(__file__).parent))
        from engine import generate_image
        from storage import save_image, record_generation
    return generate_image, save_image, record_generation


def _load_get_available_models():
    """Lazily load hardware detection dependency."""
    try:
        if getattr(sys, "frozen", False):
            try:
                from zimage.hardware import get_available_models
            except ImportError:
                from hardware import get_available_models
        elif __package__:
            from .hardware import get_available_models
        else:
            sys.path.append(str(Path(__file__).parent))
            from hardware import get_available_models
    except ImportError:
        sys.path.append(str(Path(__file__).parent))
        from hardware import get_available_models
    return get_available_models


def _round_gb(value):
    if value is None:
        return None
    return round(float(value), 1)


def _collect_hardware_info():
    try:
        get_available_models = _load_get_available_models()
        models_response = get_available_models()
        return {
            "device": str(models_response.get("device", "unknown")).upper(),
            "ram_gb": _round_gb(models_response.get("ram_gb")),
            "vram_gb": _round_gb(models_response.get("vram_gb")),
            "default_precision": models_response.get("default_precision"),
            "error": None,
        }
    except Exception as exc:
        return {
            "device": "UNKNOWN",
            "ram_gb": None,
            "vram_gb": None,
            "default_precision": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _get_app_version() -> str:
    try:
        return package_version("z-image-studio")
    except PackageNotFoundError:
        pass
    except Exception:
        pass

    try:
        import tomllib
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        return str(data.get("project", {}).get("version", "unknown"))
    except Exception:
        return "unknown"


def collect_info():
    hardware = _collect_hardware_info()
    return {
        "app_name": "Z-Image Studio",
        "package_name": "z-image-studio",
        "version": _get_app_version(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "is_frozen": bool(getattr(sys, "frozen", False)),
        "executable": str(Path(sys.executable).resolve()),
        "argv0": sys.argv[0],
        "cwd": str(Path.cwd().resolve()),
        "paths": {
            "module_file": str(Path(__file__).resolve()),
            "config_path": str(get_config_path().resolve()),
            "data_dir": str(get_data_dir().resolve()),
            "outputs_dir": str(get_outputs_dir().resolve()),
            "loras_dir": str(get_loras_dir().resolve()),
            "db_path": str(get_db_path().resolve()),
        },
        "env_overrides": {
            "Z_IMAGE_STUDIO_DATA_DIR": os.environ.get("Z_IMAGE_STUDIO_DATA_DIR"),
            "Z_IMAGE_STUDIO_OUTPUT_DIR": os.environ.get("Z_IMAGE_STUDIO_OUTPUT_DIR"),
            "ZIMAGE_ENABLE_TORCH_COMPILE": os.environ.get("ZIMAGE_ENABLE_TORCH_COMPILE"),
            "ZIMAGE_DISABLE_MCP": os.environ.get("ZIMAGE_DISABLE_MCP"),
        },
        "hardware": hardware,
    }


def format_info_text(info: dict) -> str:
    lines = [
        f"Application: {info['app_name']}",
        f"Version: {info['version']}",
        f"Package: {info['package_name']}",
        "",
        "Runtime:",
        f"  Python: {info['python_version']}",
        f"  Platform: {info['platform']}",
        f"  Frozen Build: {'yes' if info['is_frozen'] else 'no'}",
        f"  Executable: {info['executable']}",
        f"  argv0: {info['argv0']}",
        f"  CWD: {info['cwd']}",
        "",
        "Paths:",
        f"  Module File: {info['paths']['module_file']}",
        f"  Config Path: {info['paths']['config_path']}",
        f"  Data Dir: {info['paths']['data_dir']}",
        f"  Outputs Dir: {info['paths']['outputs_dir']}",
        f"  LoRAs Dir: {info['paths']['loras_dir']}",
        f"  DB Path: {info['paths']['db_path']}",
        "",
        "Environment Overrides:",
        f"  Z_IMAGE_STUDIO_DATA_DIR: {info['env_overrides']['Z_IMAGE_STUDIO_DATA_DIR']}",
        f"  Z_IMAGE_STUDIO_OUTPUT_DIR: {info['env_overrides']['Z_IMAGE_STUDIO_OUTPUT_DIR']}",
        f"  ZIMAGE_ENABLE_TORCH_COMPILE: {info['env_overrides']['ZIMAGE_ENABLE_TORCH_COMPILE']}",
        f"  ZIMAGE_DISABLE_MCP: {info['env_overrides']['ZIMAGE_DISABLE_MCP']}",
        "",
        "Hardware:",
        f"  Device: {info['hardware']['device']}",
        f"  RAM (GB): {info['hardware']['ram_gb']}",
        f"  VRAM (GB): {info['hardware']['vram_gb']}",
        f"  Default Precision: {info['hardware']['default_precision']}",
    ]
    if info["hardware"]["error"]:
        lines.append(f"  Error: {info['hardware']['error']}")
    return "\n".join(lines)


def run_info(args):
    info = collect_info()
    if args.json:
        print(json.dumps(info, indent=2))
        return
    print(format_info_text(info))


def run_models(args):
    get_available_models = _load_get_available_models()
    models_response = get_available_models()
    
    # Print device info to stdout (CLI output)
    print(f"Device: {models_response['device'].upper()}")
    if models_response['ram_gb'] is not None:
        print(f"RAM: {models_response['ram_gb']:.1f} GB")
    if models_response['vram_gb'] is not None:
        print(f"VRAM: {models_response['vram_gb']:.1f} GB")

    print("\nAvailable Models:")
    if not models_response['models']:
        log_warn("No models available for this hardware configuration.")
        return

    for m in models_response['models']:
        rec_str = f" {GREEN}(Recommended){RESET}" if m.get('recommended') else ""
        print(f"  * {m['id']} -> {m['hf_model_id']}{rec_str}")

def run_list_loras(args):
    loras = db.list_loras()
    if not loras:
        print("No LoRAs found in database.")
        print("Use the web UI to upload LoRAs or place .safetensors files in the 'loras' folder and upload via API.")
        return

    print("Available LoRAs:")
    for l in loras:
        print(f"  * {l['display_name']} (File: {l['filename']}, ID: {l['id']})")

def run_generation(args):
    generate_image, save_image, record_generation = _load_generation_modules()
    logger.info(f"DEBUG: cwd: {Path.cwd().resolve()}")

    # Ensure width/height are multiples of 16
    for name in ["width", "height"]:
        v = getattr(args, name)
        if v % 16 != 0:
            fixed = (v // 16) * 16
            if fixed < 16: fixed = 16
            log_warn(f"{name}={v} is not a multiple of 16, adjust to {fixed}")
            setattr(args, name, fixed)

    # Determine output path (default via storage helper)
    output_path = Path(args.output) if args.output else None

    # Resolve LoRA Paths
    loras = []
    if args.lora:
        for filename, strength in args.lora:
            # Resolve file (loras_dir is global, if relative file paths are given)
            lora_path = None
            p = Path(filename)
            if p.exists() and p.is_file():
                 lora_path = str(p.resolve())
            else:
                p_local = LORAS_DIR / filename # Use global LORAS_DIR
                if p_local.exists() and p_local.is_file():
                    lora_path = str(p_local.resolve())
                else:
                     log_error(f"LoRA file not found: {filename}")
                     continue # Skip invalid ones
            
            loras.append((lora_path, strength))

    # Generate image with strong logging & error handling
    try:
        image = generate_image(
            prompt=args.prompt,
            steps=args.steps,
            width=args.width,
            height=args.height,
            seed=args.seed,
            precision=args.precision,
            loras=loras
        )
        if output_path is None:
            final_path = save_image(image, args.prompt)
        else:
            if not output_path.is_absolute():
                output_path = OUTPUTS_DIR / output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path)
            final_path = output_path
        log_info(f"image saved to: {final_path.resolve()}")

        # Record history unless opted out
        if not args.no_history:
            record_generation(
                prompt=args.prompt,
                steps=args.steps,
                width=args.width,
                height=args.height,
                filename=final_path.name,
                generation_time=0.0,  # CLI does not track duration currently
                file_size_kb=final_path.stat().st_size / 1024,
                model="unknown",
                cfg_scale=0.0,
                seed=args.seed,
                precision=args.precision,
            )

    except Exception as e:
        log_error("exception during generation or saving:")
        logger.error(str(e))
        traceback.print_exc()


def run_server(args):
    """Start the FastAPI server via uvicorn."""
    import uvicorn

    # Handle both module execution and direct execution scenarios
    if __package__:
        from .network_utils import format_server_urls
    else:
        # When running directly (e.g., uv run src/zimage/cli.py serve)
        # Add the zimage directory to sys.path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        # Now network_utils.py should be directly importable
        import network_utils
        format_server_urls = network_utils.format_server_urls

    # Log paths first so they appear before MCP mount or uvicorn startup messages
    logger.info(f"Data Directory: {get_data_dir()}")
    logger.info(f"Outputs Directory: {get_outputs_dir()}")

    # Determine app string based on execution mode
    if not __package__:
        app_str = "server:app"
    else:
        app_str = "zimage.server:app"

    # Set environment variable to control MCP transport availability in web server
    if args.disable_mcp:
        os.environ["ZIMAGE_DISABLE_MCP"] = "1"
        log_info("    MCP: All web server endpoints disabled (/mcp and /mcp-sse)")

    # Display all accessible URLs
    server_urls = format_server_urls(args.host, args.port)
    log_info(f"Starting web server at:\n{server_urls}")

    uvicorn.run(
        app_str,
        host=args.host,
        port=args.port,
        reload=args.reload,
        timeout_graceful_shutdown=args.timeout_graceful_shutdown,
    )

def run_mcp(args):
    try:
        from .mcp_server import run_stdio
    except ImportError:
        from mcp_server import run_stdio
    run_stdio()

def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Z-Image Studio: local image toolkit (CLI + Web UI)")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # Subcommand: generate (aliases: gen)
    parser_gen = subparsers.add_parser("generate", aliases=["gen"], help="Generate an image from a prompt")
    parser_gen.add_argument("prompt", type=str, help="Prompt for image generation")
    parser_gen.add_argument("--output", "-o", type=str, default=None, help="Output image path (optional, default: outputs/<prompt>.png)")
    parser_gen.add_argument("--steps", type=int, default=9, help="Sampling steps (default 9, try 15–25 for better quality)")
    parser_gen.add_argument("--width", "-w", type=int, default=1280, help="Image width (must be multiple of 16), default 1280")
    parser_gen.add_argument("--height", "-H", type=int, default=720, help="Image height (must be multiple of 16), default 720")
    parser_gen.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser_gen.add_argument("--precision", type=str.lower, default="q8", choices=["full", "q8", "q4"], help="Model precision (full, q8, q4), default q8")
    parser_gen.add_argument("--no-history", action="store_true", help="Do not record this generation in history database")
    
    def lora_strength_type(value):
        fvalue = float(value)
        if fvalue < -1.0 or fvalue > 2.0:
            raise argparse.ArgumentTypeError(f"strength must be between -1.0 and 2.0 (inclusive), got {fvalue}")
        return fvalue

    class LoraAction(argparse.Action):
        def __call__(self, parser, namespace, value, option_string=None):
            parts = value.rsplit(':', 1)
            filename = parts[0]
            strength = 1.0
            
            if len(parts) == 2:
                try:
                    strength = lora_strength_type(parts[1])
                except argparse.ArgumentTypeError as e:
                    raise argparse.ArgumentTypeError(f"Invalid strength for LoRA '{filename}': {e}")
            
            # Get the list of loras, or initialize if not present
            loras = getattr(namespace, self.dest, [])
            loras.append((filename, strength))
            setattr(namespace, self.dest, loras)

    parser_gen.add_argument("--lora", action=LoraAction, default=[], help="LoRA filename or path, optionally with strength (e.g. 'pixel.safetensors:0.8'). Strength must be between -1.0 and 2.0. Can be used multiple times.")
    parser_gen.set_defaults(func=run_generation)

    # Subcommand: serve
    parser_serve = subparsers.add_parser("serve", help="Start Z-Image Web Server")
    parser_serve.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to (default: 0.0.0.0 for all interfaces)")
    parser_serve.add_argument("--port", type=int, default=8000, help="Port to bind the server to (default: 8000)")
    parser_serve.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    parser_serve.add_argument(
        "--timeout-graceful-shutdown",
        type=int,
        default=5,
        help="Seconds to wait for graceful shutdown before forcing exit (default: 5)",
    )

    # MCP transport options
    mcp_group = parser_serve.add_argument_group("MCP Transport Options")
    mcp_group.add_argument("--disable-mcp", action="store_true", help="Disable all MCP endpoints (/mcp and /mcp-sse)")

    parser_serve.set_defaults(func=run_server)

    # Subcommand: models
    parser_models = subparsers.add_parser("models", help="List available models and recommendations")
    parser_models.set_defaults(func=run_models)

    # Subcommand: info
    parser_info = subparsers.add_parser("info", help="Show application and environment diagnostics")
    parser_info.add_argument("--json", action="store_true", help="Output diagnostics as JSON")
    parser_info.set_defaults(func=run_info)
    
    # Subcommand: loras
    parser_loras = subparsers.add_parser("loras", help="Manage LoRA models")
    loras_subparsers = parser_loras.add_subparsers(dest="subcommand", required=True)
    
    # loras list
    parser_loras_list = loras_subparsers.add_parser("list", help="List available LoRAs")
    parser_loras_list.set_defaults(func=run_list_loras)

    # Subcommand: mcp
    parser_mcp = subparsers.add_parser("mcp", help="Start Z-Image MCP Server (stdio only)")
    parser_mcp.set_defaults(func=run_mcp)

    args = parser.parse_args()
    if args.command != "info":
        # Ensure DB is initialized for commands that use app state.
        migrations.init_db()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
