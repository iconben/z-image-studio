with open('src/zimage/server.py', 'r') as f:
    content = f.read()

# Add config check to generate endpoint
old_generate = """@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    try:
        # Normalize and validate precision early to avoid KeyError inside engine"""

new_generate = """@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    try:
        from .paths import load_config
        config = load_config()
        max_steps = config.get("max_steps", 50)
        max_width = config.get("max_width", 4096)
        max_height = config.get("max_height", 4096)

        if req.steps > max_steps:
            raise HTTPException(status_code=400, detail=f"Requested steps ({req.steps}) exceeds the maximum allowed ({max_steps}).")
        if req.width > max_width:
            raise HTTPException(status_code=400, detail=f"Requested width ({req.width}) exceeds the maximum allowed ({max_width}).")
        if req.height > max_height:
            raise HTTPException(status_code=400, detail=f"Requested height ({req.height}) exceeds the maximum allowed ({max_height}).")

        # Normalize and validate precision early to avoid KeyError inside engine"""

content = content.replace(old_generate, new_generate)

with open('src/zimage/server.py', 'w') as f:
    f.write(content)
