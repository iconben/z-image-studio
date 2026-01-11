# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Z-Image Studio Windows executable.

Build command:
    pyinstaller pyinstaller.spec

The resulting executable will be in the dist/ directory.
"""

import os
import sys
from pathlib import Path

block_cipher = None

# Paths - use current working directory since __file__ is not available in spec context
ROOT_DIR = Path.cwd().resolve()
SRC_DIR = ROOT_DIR / "src"
STATIC_DIR = SRC_DIR / "zimage" / "static"
I18N_DIR = STATIC_DIR / "i18n"

a = Analysis(
    [str(SRC_DIR / "zimage" / "cli.py")],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=[
        # Static web assets
        (str(STATIC_DIR / "index.html"), "static"),
        (str(STATIC_DIR / "favicon.ico"), "static"),
        (str(STATIC_DIR / "manifest.json"), "static"),
        (str(STATIC_DIR / "logo-180.png"), "static"),
        # CSS
        (str(STATIC_DIR / "css"), "static/css"),
        # JavaScript
        (str(STATIC_DIR / "js"), "static/js"),
        # i18n translations
        (str(I18N_DIR), "static/i18n"),
    ],
    hiddenimports=[
        # FastAPI and dependencies
        "fastapi",
        "fastapi.staticfiles",
        "fastapi.responses",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.server",
        "starlette",
        "starlette.responses",
        "starlette.staticfiles",
        "starlette.routing",
        "starlette.templating",
        "pydantic",
        "pydantic.json_schema",
        "pydantic.functional_validators",
        # Multipart forms
        "python_multipart",
        "multipart",
        # Database
        "sqlite3",
        # MCP
        "mcp",
        "mcp.server",
        "mcp.server.stdio",
        "mcp.types",
        # PyTorch and transformers (critical for image generation)
        "torch",
        "torch._ops",
        "torch.cuda",
        "torch.mps",
        "torch.nn",
        "torch.nn.modules",
        "torch.optim",
        "torch.utils",
        "torch.utils.model_zoo",
        "torchvision",
        "torchvision.models",
        "torchvision.transforms",
        "transformers",
        "transformers.models",
        "transformers.tokenization_utils",
        "transformers.tokenization_utils_base",
        "transformers.image_processing_utils",
        "transformers.image_utils",
        # Accelerate
        "accelerate",
        "accelerate.utils",
        "accelerate.state",
        # PEFT (LoRA support)
        "peft",
        "peft.tuners",
        "peft.tuners.lora",
        "peft.utils",
        # SDNQ (quantization)
        "sdnq",
        "sdnq.sdnq",
        # Image processing
        "PIL",
        "PIL.Image",
        "PIL.PngImagePlugin",
        # Other utilities
        "platformdirs",
        "psutil",
        "click",
        "httpx",
        "anyio",
        "sniffio",
        "idna",
        "email_validator",
        # Logging
        "logging",
        "logging.handlers",
        # Path handling
        "pathlib",
        "shutil",
        "json",
        "hashlib",
        "uuid",
        "asyncio",
        "concurrent",
        "concurrent.futures",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "test",
        "pytest",
        "unittest",
        "pydoc",
        "doctest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="zimg",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon=None, can set to icon='path/to/icon.ico' later
)
