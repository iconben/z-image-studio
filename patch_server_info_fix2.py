with open('src/zimage/server.py', 'r') as f:
    content = f.read()

old_endpoint = """@app.get("/models")
async def get_models():"""

new_endpoint = """@app.get("/info")
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

@app.get("/models")
async def get_models():"""

content = content.replace(old_endpoint, new_endpoint)

with open('src/zimage/server.py', 'w') as f:
    f.write(content)
