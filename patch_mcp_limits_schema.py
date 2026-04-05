with open('src/zimage/mcp_server.py', 'r') as f:
    content = f.read()

old_func = """@mcp.tool()
async def generate(
    prompt: str,
    steps: int = 9,
    width: int = 1280,
    height: int = 720,"""

# Import Field from pydantic to annotate bounds. FastMCP uses Pydantic.
old_imports = "from urllib.parse import quote"
new_imports = "from urllib.parse import quote\nfrom pydantic import Field"

new_func = """@mcp.tool()
async def generate(
    prompt: str,
    steps: int = Field(default=9, description="Number of inference steps (max bounded by server config)"),
    width: int = Field(default=1280, description="Image width in pixels (max bounded by server config)"),
    height: int = Field(default=720, description="Image height in pixels (max bounded by server config)"),"""

content = content.replace(old_imports, new_imports)
content = content.replace(old_func, new_func)

with open('src/zimage/mcp_server.py', 'w') as f:
    f.write(content)
