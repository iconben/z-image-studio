with open('src/zimage/cli.py', 'r') as f:
    content = f.read()

old_run_gen = """def run_generation(args):
    generate_image, save_image, record_generation = _load_generation_modules()
    logger.info(f"DEBUG: cwd: {Path.cwd().resolve()}")

    # Ensure width/height are multiples of 16"""

new_run_gen = """def run_generation(args):
    generate_image, save_image, record_generation = _load_generation_modules()
    logger.info(f"DEBUG: cwd: {Path.cwd().resolve()}")

    # Check constraints
    config = load_config()
    max_steps = config.get("max_steps", 50)
    max_width = config.get("max_width", 4096)
    max_height = config.get("max_height", 4096)

    if args.steps > max_steps:
        log_error(f"Requested steps ({args.steps}) exceeds the maximum allowed ({max_steps}).")
        sys.exit(1)
    if args.width > max_width:
        log_error(f"Requested width ({args.width}) exceeds the maximum allowed ({max_width}).")
        sys.exit(1)
    if args.height > max_height:
        log_error(f"Requested height ({args.height}) exceeds the maximum allowed ({max_height}).")

    # Ensure width/height are multiples of 16"""

content = content.replace(old_run_gen, new_run_gen)

with open('src/zimage/cli.py', 'w') as f:
    f.write(content)
