import re

with open('src/zimage/server.py', 'r') as f:
    content = f.read()

# Try again to patch
old_endpoint = """@app.get("/api/models")
async def get_models():"""

new_endpoint = """@app.get("/api/info")
async def get_info():
    \"\"\"Return system info including paths, config and hardware constraints.\"\"\"
    try:
        from .cli import collect_info
        return collect_info()
    except ImportError:
        # Fallback if relative import fails
        from cli import collect_info
        return collect_info()

@app.get("/api/models")
async def get_models():"""

if old_endpoint in content:
    content = content.replace(old_endpoint, new_endpoint)
else:
    print("Could not find endpoint to replace.")

with open('src/zimage/server.py', 'w') as f:
    f.write(content)
