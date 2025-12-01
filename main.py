import argparse
from pathlib import Path
import traceback
from engine import generate_image

def parse_args():
    parser = argparse.ArgumentParser(
        description="Z-Image Turbo CLI (prompt, resolution, optional save path)"
    )
    parser.add_argument(
        "prompt",
        type=str,
        nargs="?", # Make prompt optional so we can just run --web
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
        help="Image width (must be multiple of 8), default 768",
    )
    parser.add_argument(
        "--height",
        "-H",
        type=int,
        default=720,
        help="Image height (must be multiple of 8), default 768",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Start web server interface",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.web:
        import uvicorn
        print("[info] Starting web server at http://localhost:8000")
        uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
        return

    if not args.prompt:
        print("Error: 'prompt' is required unless --web is specified.")
        return

    print(f"[debug] cwd: {Path.cwd().resolve()}")

    # Ensure width/height are multiples of 16
    for name in ["width", "height"]:
        v = getattr(args, name)
        if v % 8 != 0:
            fixed = (v // 16) * 16
            print(f"[warn] {name}={v} is not a multiple of 8, adjust to {fixed}")
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
        image = generate_image(args.prompt, args.steps, args.width, args.height)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        print(f"[info] image saved to: {output_path.resolve()}")

    except Exception as e:
        print("[error] exception during generation or saving:")
        print(e)
        traceback.print_exc()


if __name__ == "__main__":
    main()