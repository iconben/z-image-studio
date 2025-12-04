import argparse
import sys
from pathlib import Path
import traceback

try:
    from .engine import generate_image
except ImportError:
    # Allow running as a script directly (e.g. python src/zimage/cli.py)
    sys.path.append(str(Path(__file__).parent))
    from engine import generate_image

def parse_generate_args(args=None):
    parser = argparse.ArgumentParser(
        description="Z-Image Turbo CLI (zimg)"
    )
    parser.add_argument(
        "prompt",
        type=str,
        help="Prompt for image generation",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output image path (optional, default: outputs/<prompt>.png)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=9,
        help="Sampling steps (default 9, try 15–25 for better quality)",
    )
    parser.add_argument(
        "--width",
        "-w",
        type=int,
        default=1280,
        help="Image width (must be multiple of 16), default 1280",
    )
    parser.add_argument(
        "--height",
        "-H",
        type=int,
        default=720,
        help="Image height (must be multiple of 16), default 720",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    return parser.parse_args(args)

def parse_serve_args(args=None):
    parser = argparse.ArgumentParser(description="Start Z-Image Web Server")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (dev mode)",
    )
    return parser.parse_args(args)

def run_generation(cli_args):
    args = parse_generate_args(cli_args)
    
    print(f"[debug] cwd: {Path.cwd().resolve()}")

    # Ensure width/height are multiples of 16
    for name in ["width", "height"]:
        v = getattr(args, name)
        if v % 16 != 0:
            fixed = (v // 16) * 16
            if fixed < 16: fixed = 16
            print(f"[warn] {name}={v} is not a multiple of 16, adjust to {fixed}")
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

    print(f"[debug] final output path will be: {output_path.resolve()}")

    # Generate image with strong logging & error handling
    try:
        image = generate_image(
            prompt=args.prompt,
            steps=args.steps,
            width=args.width,
            height=args.height,
            seed=args.seed,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        print(f"[info] image saved to: {output_path.resolve()}")

    except Exception as e:
        print("[error] exception during generation or saving:")
        print(e)
        traceback.print_exc()

def run_server(cli_args):
    import uvicorn
    args = parse_serve_args(cli_args)
    print(f"[info] Starting web server at http://{args.host}:{args.port}")
    
    # Determine app string based on execution mode
    if not __package__:
        # Running as script (flat layout simulation)
        app_str = "server:app"
    else:
        # Running as package
        app_str = "zimage.server:app"
        
    uvicorn.run(app_str, host=args.host, port=args.port, reload=args.reload)

def main():
    # Hybrid command dispatch
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # Shift args so "serve" isn't processed by the next parser
        run_server(sys.argv[2:])
    else:
        # Default mode: generation
        # Pass all args (excluding script name) to the generator parser
        run_generation(sys.argv[1:])

if __name__ == "__main__":
    main()