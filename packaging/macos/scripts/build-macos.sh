#!/bin/bash
# Build script for Z-Image Studio macOS .app bundle and .dmg
# Usage: ./build-macos.sh [--version X.X.X]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

VERSION=""
SIGN_IDENTITY=""
SIGN_ENTITLEMENTS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            VERSION="$2"
            shift 2
            ;;
        --sign-identity)
            SIGN_IDENTITY="$2"
            shift 2
            ;;
        --sign-entitlements)
            SIGN_ENTITLEMENTS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$VERSION" ]; then
    if command -v git &> /dev/null && git describe --tags --abbrev=0 &> /dev/null; then
        VERSION=$(git describe --tags --abbrev=0 | sed 's/^v//')
    else
        VERSION="0.1.0"
    fi
fi

echo "========================================"
echo "Z-Image Studio macOS Build"
echo "Version: $VERSION"
echo "========================================"

if ! command -v python &> /dev/null; then
    echo "ERROR: Python not found."
    exit 1
fi

if ! command -v pyinstaller &> /dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

if ! command -v create-dmg &> /dev/null; then
    echo "Installing create-dmg..."
    if command -v brew &> /dev/null; then
        brew install create-dmg
    else
        echo "ERROR: Homebrew not found. Please install create-dmg manually."
        exit 1
    fi
fi

echo "Cleaning previous builds..."
rm -rf dist/build dist/*.app dist/*.dmg

echo "Building .app bundle with PyInstaller..."
SPEC_FILE="$PROJECT_ROOT/packaging/macos/pyinstaller/macos.spec"

if [ ! -f "$SPEC_FILE" ]; then
    echo "ERROR: Spec file not found: $SPEC_FILE"
    exit 1
fi

pyinstaller "$SPEC_FILE" \
    --noconfirm \
    --distpath dist

if [ ! -d "dist/Z-Image Studio.app" ]; then
    echo "ERROR: Build failed - .app bundle not found."
    exit 1
fi

APP_PATH="$PROJECT_ROOT/dist/Z-Image Studio.app"
CONTENTS_PATH="$APP_PATH/Contents"
MACOS_PATH="$CONTENTS_PATH/MacOS"
RESOURCES_PATH="$CONTENTS_PATH/Resources"

echo "Creating Info.plist..."
cat > "$CONTENTS_PATH/Info.plist" << 'INFOPLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>Z-Image Studio</string>
    <key>CFBundleIdentifier</key>
    <string>com.z-image-studio.app</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Z-Image Studio</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>VERSION_PLACEHOLDER</string>
    <key>CFBundleVersion</key>
    <string>VERSION_PLACEHOLDER</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright 2024. All rights reserved.</string>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>Image</string>
            <key>LSHandlerRank</key>
            <string>Alternate</string>
            <key>LSItemContentTypes</key>
            <array>
                <string>public.png-image</string>
                <string>public.jpeg-image</string>
            </array>
        </dict>
    </array>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
INFOPLIST

sed -i '' "s/VERSION_PLACEHOLDER/$VERSION/g" "$CONTENTS_PATH/Info.plist"

echo "Copying launcher script..."
if [ -f "$SCRIPT_DIR/launchers/macos-launcher.sh" ]; then
    cp "$SCRIPT_DIR/launchers/macos-launcher.sh" "$MACOS_PATH/"
    chmod +x "$MACOS_PATH/macos-launcher.sh"
fi

if [ -n "$SIGN_IDENTITY" ]; then
    echo "Signing .app bundle..."
    codesign --sign "$SIGN_IDENTITY" \
        --timestamp \
        --entitlements "$SIGN_ENTITLEMENTS" \
        --force \
        --deep \
        "$APP_PATH"
fi

DMG_NAME="Z-Image-Studio-macOS-arm64-${VERSION}.dmg"
echo "Creating .dmg file: $DMG_NAME..."

if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: .app bundle not found at $APP_PATH"
    ls -la "$PROJECT_ROOT/dist/"
    exit 1
fi

create-dmg \
    --volname "Z-Image Studio" \
    --window-pos 200 120 \
    --window-size 800 600 \
    --icon-size 100 \
    --icon "Z-Image Studio.app" 200 190 \
    --hide-extension "Z-Image Studio.app" \
    --app-drop-link 600 185 \
    "$PROJECT_ROOT/dist/$DMG_NAME" \
    "$APP_PATH"

if [ ! -f "dist/$DMG_NAME" ]; then
    echo "ERROR: DMG creation failed."
    exit 1
fi

if [ -n "$SIGN_IDENTITY" ]; then
    echo "Signing .dmg file..."
    codesign --sign "$SIGN_IDENTITY" \
        --timestamp \
        --force \
        "dist/$DMG_NAME"
fi

echo "Computing SHA256 checksum..."
SHA256=$(shasum -a 256 "dist/$DMG_NAME" | cut -d' ' -f1)
CHECKSUM_FILE="dist/${DMG_NAME}.sha256"
echo "$SHA256  $DMG_NAME" > "$CHECKSUM_FILE"

echo "========================================"
echo "Build successful!"
echo "App Bundle: dist/Z-Image Studio.app"
echo "DMG: dist/$DMG_NAME"
echo "Checksum: $CHECKSUM_FILE"
echo "SHA256: $SHA256"
echo "========================================"
