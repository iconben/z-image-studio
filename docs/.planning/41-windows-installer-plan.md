# Plan: Windows Installer and Packaging Mechanism for z-image-studio

## Overview
Create a Windows installer that bundles the Python application with all dependencies, following Windows conventions (shortcuts, licensing), and integrate it into the CI pipeline for automatic release builds.

## Architecture Decision

**Recommendation: PyInstaller + Inno Setup**
- **PyInstaller**: Creates standalone Windows executable with embedded Python
- **Inno Setup**: Creates professional Windows installer with Start Menu shortcuts
- License: Apache 2.0 (use LICENSE file as-is)

**Alternative considered**: pip-based installation (rejected - requires users to install Python first)

## Implementation Plan

### Phase 1: Windows Compatibility Fixes

#### 1.1 Add Windows RAM Detection (`src/zimage/hardware.py`)
- Use `psutil` for cross-platform RAM detection (adds dependency)
- Currently `get_ram_gb()` returns `None` on Windows
- Implement Windows-compatible memory reading

#### 1.2 Verify Platformdirs Paths
- `src/zimage/paths.py` already uses `platformdirs`
- Verify Windows paths work correctly after testing

### Phase 2: PyInstaller Build Setup

#### 2.1 Create PyInstaller Spec File
- Target CLI entrypoint (`zimage.cli:main`)
- Configure to default to "serve" subcommand on launch
- Add wrapper/batch script that:
  1. Launches the server
  2. Auto-opens browser to `http://localhost:8000`
- Include all hidden imports for FastAPI, torch, diffusers
- Bundle static assets (HTML, CSS, JS, i18n)
- Handle PyTorch's native libraries

#### 2.2 Build Scripts
- `scripts/build-windows.bat` - Windows build script
- `scripts/build-windows.sh` - Cross-platform build script for CI
- Verify all dependencies collected correctly

#### 2.3 Test Executable
- Verify bundled app works offline
- Test GPU detection and hardware access
- Ensure server launches and browser opens correctly

### Phase 3: Inno Setup Installer

#### 3.1 Create Installer Script (`installer/windows/z-image-studio.iss`)
- Install to `Program Files\z-image-studio`
- Include LICENSE file
- Create Start Menu shortcuts:
  - **"Z-Image Studio (Web UI)"** - Launches server, opens browser to web UI
  - **"Z-Image Studio CLI"** - Console window for CLI usage
- Add uninstaller registration
- Create `AppData\Local\z-image-studio` for user data (outputs, LoRAs)
- Optional: File associations if needed

#### 3.2 Web UI Launcher Details
- Shortcut runs executable with `serve` command
- Batch wrapper or executable auto-opens `http://localhost:8000` in default browser
- Consider using `python -m webbrowser` or Windows `start` command

#### 3.3 Build Script
- `scripts/build-installer.bat` - Build the .exe installer

### Phase 4: CI/CD Integration

#### 4.1 GitHub Actions Workflow (`.github/workflows/release-windows.yml`)
- Trigger on git tags matching `v*`
- Use `windows-latest` runner
- Steps:
  1. Checkout code
  2. Install Inno Setup via Chocolatey (`choco install innosetup`)
  3. Setup Python with uv
  4. Install PyInstaller
  5. Build standalone executable
  6. Build Inno Setup installer
  7. Create release artifacts
  8. Upload to GitHub Releases as assets

#### 4.2 Version Handling
- Use existing version from `pyproject.toml`
- Tag-based releases (`git tag v1.2.3`)

### Phase 5: Documentation and Testing

#### 5.1 README Updates
- Add "Windows Installation" section
- Document hardware requirements (NVIDIA GPU recommended)
- Explain installation location and user data paths
- Document Start Menu shortcuts

#### 5.2 Testing Checklist
- [ ] Clean install on Windows 10/11
- [ ] Verify all dependencies bundled
- [ ] Test "Z-Image Studio (Web UI)" shortcut - server starts, browser opens
- [ ] Test "Z-Image Studio CLI" shortcut - console opens
- [ ] Test application functionality in browser
- [ ] Test uninstaller removes all files
- [ ] Verify GPU detection works
- [ ] Test offline functionality

## Files to Create/Modify

### New Files
- `pyinstaller.spec` - PyInstaller configuration
- `scripts/build-windows.bat` - Windows build script
- `scripts/build-windows.sh` - CI build script
- `installer/windows/z-image-studio.iss` - Inno Setup script
- `.github/workflows/release-windows.yml` - CI workflow

### Modified Files
- `src/zimage/hardware.py` - Add Windows RAM detection (add psutil dependency)
- `README.md` - Add Windows installation section

## Dependencies to Add
- `psutil` - Cross-platform system metrics (for RAM detection)
- `pyinstaller` - Build-time only

## CI Tools
- `choco install innosetup` - Inno Setup on Windows runners

## Complexity Notes
- PyInstaller bundling of PyTorch/diffusers is complex - may need iterative fixes for hidden imports
- PyTorch native libraries need proper handling
- Large binary size expected (500MB-2GB depending on GPU support)
- Browser auto-open needs proper timing (wait for server to be ready)
