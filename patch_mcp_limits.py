with open('src/zimage/mcp_server.py', 'r') as f:
    content = f.read()

# Let's add load_config to imports
old_imports = """try:
    from .hardware import get_available_models, normalize_precision, MODEL_ID_MAP
    from . import db
    from .storage import save_image, record_generation
    from .logger import get_logger, setup_logging
except ImportError:
    from hardware import get_available_models, normalize_precision, MODEL_ID_MAP
    import db
    from storage import save_image, record_generation
    from logger import get_logger, setup_logging"""

new_imports = """try:
    from .hardware import get_available_models, normalize_precision, MODEL_ID_MAP
    from . import db
    from .storage import save_image, record_generation
    from .logger import get_logger, setup_logging
    from .paths import load_config
except ImportError:
    from hardware import get_available_models, normalize_precision, MODEL_ID_MAP
    import db
    from storage import save_image, record_generation
    from logger import get_logger, setup_logging
    from paths import load_config"""

content = content.replace(old_imports, new_imports)

# Add limits check in _generate_impl
old_impl_start = """    try:
        await send_progress(0, "Initializing generation...")

        # Normalize and validate precision"""

new_impl_start = """    try:
        await send_progress(0, "Initializing generation...")

        # Enforce constraints
        config = load_config()
        max_steps = config.get("max_steps", 50)
        max_width = config.get("max_width", 4096)
        max_height = config.get("max_height", 4096)

        if steps > max_steps:
            raise ValueError(f"Requested steps ({steps}) exceeds the maximum allowed ({max_steps}).")
        if width > max_width:
            raise ValueError(f"Requested width ({width}) exceeds the maximum allowed ({max_width}).")
        if height > max_height:
            raise ValueError(f"Requested height ({height}) exceeds the maximum allowed ({max_height}).")

        # Normalize and validate precision"""

content = content.replace(old_impl_start, new_impl_start)

with open('src/zimage/mcp_server.py', 'w') as f:
    f.write(content)
