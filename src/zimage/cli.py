import argparse
import sys
from pathlib import Path
import traceback

# ANSI escape codes for colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

def log_info(message: str):
    print(f"{GREEN}INFO{RESET}: {message}")

def log_warn(message: str):
    print(f"{YELLOW}WARN{RESET}: {message}")

def log_error(message: str):
    print(f"{RED}ERROR{RESET}: {message}")

try:
    from .engine import generate_image
    from .hardware import get_available_models
    from . import db
    from . import migrations
    from .paths import (
        ensure_initial_setup,
        get_data_dir,
        get_loras_dir,
        get_outputs_dir,
    )
except ImportError:
    # Allow running as a script directly (e.g. python src/zimage/cli.py)
    sys.path.append(str(Path(__file__).parent))
    from engine import generate_image
    from hardware import get_available_models
    import db
    import migrations
    from paths import (
        ensure_initial_setup,
        get_data_dir,
        get_loras_dir,
        get_outputs_dir,
    )

# Directory Configuration
ensure_initial_setup()
OUTPUTS_DIR = get_outputs_dir()
LORAS_DIR = get_loras_dir()

def run_models(args):
    models_response = get_available_models()
    
    # Print device info
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
        # The 'id' field is now 'full', 'q8', 'q4' again.
        # The 'tasks' field is gone from ModelInfo.
        # So we just print id, hf_model_id and recommendation.
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
    print(f"DEBUG: cwd: {Path.cwd().resolve()}")

    # Ensure width/height are multiples of 16
    for name in ["width", "height"]:
        v = getattr(args, name)
        if v % 16 != 0:
            fixed = (v // 16) * 16
            if fixed < 16: fixed = 16
            log_warn(f"{name}={v} is not a multiple of 16, adjust to {fixed}")
            setattr(args, name, fixed)

    # Determine output path
    outputs_dir = OUTPUTS_DIR
    outputs_dir.mkdir(parents=True, exist_ok=True)

    if args.output is None:
        safe_prompt = "".join(
            c for c in args.prompt[:30] if c.isalnum() or c in "-_"
        )
        if not safe_prompt:
            safe_prompt = "image"
        filename = f"{safe_prompt}.png"
        output_path = outputs_dir / filename
    else:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            # If user gives relative path, put it under outputs/ for clarity
            output_path = outputs_dir / output_path

    print(f"DEBUG: final output path will be: {output_path.resolve()}")

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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        log_info(f"image saved to: {output_path.resolve()}")

    except Exception as e:
        log_error("exception during generation or saving:")
        print(e)
        traceback.print_exc()


def run_server(args):
    """Start the FastAPI server via uvicorn."""
    import uvicorn

    log_info(f"Starting web server at http://{args.host}:{args.port}")

    # Determine app string based on execution mode
    if not __package__:
        app_str = "server:app"
    else:
        app_str = "zimage.server:app"

    uvicorn.run(app_str, host=args.host, port=args.port, reload=args.reload)

def main():
    # Ensure DB is initialized
    migrations.init_db()

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
    parser_gen.add_argument("--precision", type=str, default="q8", choices=["full", "q8", "q4"], help="Model precision (full, q8, q4), default q8")
    
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
    parser_serve.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind the server to (default: 0.0.0.0)")
    parser_serve.add_argument("--port", type=int, default=8000, help="Port to bind the server to (default: 8000)")
    parser_serve.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    parser_serve.set_defaults(func=run_server)

    # Subcommand: models
    parser_models = subparsers.add_parser("models", help="List available models and recommendations")
    parser_models.set_defaults(func=run_models)
    
    # Subcommand: loras
    parser_loras = subparsers.add_parser("loras", help="Manage LoRA models")
    loras_subparsers = parser_loras.add_subparsers(dest="subcommand", required=True)
    
    # loras list
    parser_loras_list = loras_subparsers.add_parser("list", help="List available LoRAs")
    parser_loras_list.set_defaults(func=run_list_loras)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
