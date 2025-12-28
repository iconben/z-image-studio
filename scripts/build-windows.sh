#!/bin/bash
# Cross-platform build script for Z-Image Studio Windows executable
# This script is used by CI to build on Windows runners

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "========================================"
echo "Z-Image Studio Windows Build (CI)"
echo "========================================"

# Check for Python
if ! command -v python &> /dev/null; then
    echo "ERROR: Python not found."
    exit 1
fi

# Install PyInstaller
echo "Installing PyInstaller..."
pip install pyinstaller

# Clean previous builds
rm -rf dist build

# Build with PyInstaller
echo "Building executable..."
pyinstaller pyinstaller.spec --noconfirm

if [ -f "dist/zimg.exe" ]; then
    echo "========================================"
    echo "Build successful!"
    echo "Executable: dist/zimg.exe"
    echo "========================================"
else
    echo "ERROR: Build failed - executable not found."
    exit 1
fi
