@echo off
REM Windows build script for Z-Image Studio
REM Builds the PyInstaller executable

echo ========================================
echo Z-Image Studio Windows Build
echo ========================================

REM Get the script directory
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
cd /d "%PROJECT_ROOT%"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11+.
    exit /b 1
)

REM Install PyInstaller if not already installed
echo Checking PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous build artifacts
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Build the executable
echo Building executable with PyInstaller...
pyinstaller pyinstaller.spec --noconfirm

if exist dist\zimg.exe (
    echo ========================================
    echo Build successful!
    echo Executable: dist\zimg.exe
    echo ========================================
) else (
    echo ERROR: Build failed - executable not found.
    exit /b 1
)

endlocal
pause
