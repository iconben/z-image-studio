# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Z-Image Studio macOS .app bundle.

Build command:
    pyinstaller packaging/macos/pyinstaller/macos.spec

The resulting .app bundle will be in the dist/ directory.
"""

import os
import sys
from pathlib import Path

block_cipher = None

ROOT_DIR = Path.cwd().resolve()
SRC_DIR = ROOT_DIR / "src"
STATIC_DIR = SRC_DIR / "zimage" / "static"
I18N_DIR = STATIC_DIR / "i18n"

a = Analysis(
    [str(SRC_DIR / "zimage" / "cli.py")],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=[
        (str(STATIC_DIR / "index.html"), "static"),
        (str(STATIC_DIR / "favicon.ico"), "static"),
        (str(STATIC_DIR / "manifest.json"), "static"),
        (str(STATIC_DIR / "logo-180.png"), "static"),
        (str(STATIC_DIR / "css"), "static/css"),
        (str(STATIC_DIR / "js"), "static/js"),
        (str(I18N_DIR), "static/i18n"),
    ],
    hiddenimports=[
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
        "python_multipart",
        "multipart",
        "sqlite3",
        "mcp",
        "mcp.server",
        "mcp.server.stdio",
        "mcp.types",
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
        "accelerate",
        "accelerate.utils",
        "accelerate.state",
        "peft",
        "peft.tuners",
        "peft.tuners.lora",
        "peft.utils",
        "sdnq",
        "sdnq.sdnq",
        "PIL",
        "PIL.Image",
        "PIL.PngImagePlugin",
        "platformdirs",
        "psutil",
        "click",
        "httpx",
        "anyio",
        "sniffio",
        "idna",
        "email_validator",
        "logging",
        "logging.handlers",
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
    [],
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Z-Image Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    onefile=False,
)

app = BUNDLE(
    exe,
    name="Z-Image Studio.app",
    bundle_identifier="com.z-image-studio.app",
    info_plist={
        "CFBundleName": "Z-Image Studio",
        "CFBundleDisplayName": "Z-Image Studio",
        "CFBundleIdentifier": "com.z-image-studio.app",
        "CFBundleVersion": "1",
        "CFBundleShortVersionString": "1",
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "Z-Image Studio",
        "NSHumanReadableCopyright": "Copyright 2024. All rights reserved.",
        "LSMinimumSystemVersion": "10.15",
        "NSPrincipalClass": "NSApplication",
    },
)
