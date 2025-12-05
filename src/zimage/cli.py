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
    from .engine import generate_image, get_available_models
except ImportError:
    # Allow running as a script directly (e.g. python src/zimage/cli.py)
    sys.path.append(str(Path(__file__).parent))
    from engine import generate_image, get_available_models

def run_models(args):
    models = get_available_models()
    print("Available Models:")
    for m in models:
        rec_str = f" {GREEN}(Recommended){RESET}" if m['recommended'] else ""
        print(f"  * {m['id']}{rec_str}")

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
    outputs_dir = Path("outputs")
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

    # Generate image with strong logging & error handling
    try:
        image = generate_image(
            prompt=args.prompt,
            steps=args.steps,
            width=args.width,
            height=args.height,
            seed=args.seed,
            precision=args.precision,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        log_info(f"image saved to: {output_path.resolve()}")

    except Exception as e:
        log_error("exception during generation or saving:")
        print(e)
        traceback.print_exc()

def run_server(args):
    import uvicorn
    log_info(f"Starting web server at http://{args.host}:{args.port}")
    
    # Determine app string based on execution mode
    if not __package__:
        # Running as script (flat layout simulation)
        app_str = "server:app"
    else:
        # Running as package
        app_str = "zimage.server:app"
        
    uvicorn.run(app_str, host=args.host, port=args.port, reload=args.reload)

def main():
    parser = argparse.ArgumentParser(description="Z-Image Turbo CLI (zimg)")
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

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
