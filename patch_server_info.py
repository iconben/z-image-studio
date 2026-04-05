import re

with open('src/zimage/server.py', 'r') as f:
    content = f.read()

# I need to add an /api/info endpoint in server.py
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

content = content.replace(old_endpoint, new_endpoint)

with open('src/zimage/server.py', 'w') as f:
    f.write(content)
