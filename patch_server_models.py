import re

with open('src/zimage/server.py', 'r') as f:
    content = f.read()

# 1. Remove the /info endpoint we added
old_info = """@app.get("/info")
async def get_info():
    \"\"\"Return system info including paths, config and hardware constraints.\"\"\"
    try:
        from .cli import collect_info
        return collect_info()
    except ImportError:
        # Fallback if relative import fails
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from cli import collect_info
        return collect_info()

"""
content = content.replace(old_info, "")

# 2. Update /models endpoint to include constraints
old_models = """@app.get("/models")
async def get_models():
    \"\"\"Get list of available models with hardware recommendations.\"\"\"
    return get_available_models()"""

new_models = """@app.get("/models")
async def get_models():
    \"\"\"Get list of available models with hardware recommendations and constraints.\"\"\"
    from .paths import load_config
    config = load_config()
    models_info = get_available_models()

    # Inject constraints into the response
    models_info['constraints'] = {
        "max_steps": config.get("max_steps", 50),
        "max_width": config.get("max_width", 4096),
        "max_height": config.get("max_height", 4096),
    }
    return models_info"""

content = content.replace(old_models, new_models)

with open('src/zimage/server.py', 'w') as f:
    f.write(content)
