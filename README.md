# Z-Image Studio

![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)
![PyTorch](https://img.shields.io/badge/PyTorch-%23EE4C2C.svg?style=flat&logo=PyTorch&logoColor=white)
![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97-Diffusers-yellow)
![Apple Silicon](https://img.shields.io/badge/Apple%20Silicon-MPS-gray?logo=apple)
[![Docs](https://img.shields.io/badge/docs-deepwiki.com-blue)](https://deepwiki.com/iconben/z-image-studio)

A web application and a command-line interface for the **Z-Image-Turbo** text-to-image generation model (`Tongyi-MAI/Z-Image-Turbo`).

This tool is designed to run efficiently on local machines, with specific optimizations for **Apple Silicon (MPS)**, falling back to CPU if unavailable.

## Features

*   **Z-Image-Turbo Model**: Utilizes the high-quality `Tongyi-MAI/Z-Image-Turbo` model via `diffusers`.
*   **Hybrid Interface**: 
    *   **CLI**: Fast, direct image generation from the terminal.
    *   **Web UI**: Modern web interface for interactive generation.
*   **MPS Acceleration**: Optimized for Mac users with Apple Silicon.
*   **Attention Slicing Auto-detection**: Automatically manages memory usage (e.g., enables attention slicing for systems with lower RAM/VRAM) to prevent Out-of-Memory errors and optimize performance.
*   **Seed Control**: Reproducible image generation via CLI or Web UI.
*   **Multiple LoRA Support**: Upload/manage LoRAs in the web UI, apply up to 4 with per-LoRA strengths in a single generation; CLI supports multiple `--lora` entries with optional strengths.
*   **Automatic Dimension Adjustment**: Ensures image dimensions are compatible (multiples of 16).
*   **Multilanguage Support on Web UI**: English, Japanese, Chinese Simplified are supported.
*   **History Pagination and Infinite Scroll**: Efficiently browse your past generations with a paginated history that loads more items as you scroll.
*   **Hardware-aware Model Recommendation**: The Web UI dynamically presents model precision options based on your system's detected RAM/VRAM, recommending the optimal choice for your hardware. You can also inspect available models and recommendations via the CLI.

## Requirements

*   Python >= 3.11
*   `uv` (recommended for dependency management)

## Global installation (as a CLI tool)

If you just want the `zimg` CLI to be available from anywhere, install it as a uv tool:

```bash
uv tool install git+https://github.com/iconben/z-image-studio.git
# or, if you have the repo cloned locally:
# git clone https://github.com/iconben/z-image-studio.git
# cd z-image-studio
# uv tool install .
```

After this, the `zimg` command is available globally:

```bash
zimg --help
```

To update z-image-studio:
```bash
uv tool upgrade z-image-studio
# or, if you have the repo cloned locally, you pull the latest source code:
# git pull
```

## Data Directory and Configuration

By default, Z-Image Studio uses the following directories:

*   **Data Directory** (Database, LoRAs): `~/.local/share/z-image-studio` (Linux), `~/Library/Application Support/z-image-studio` (macOS), or `%LOCALAPPDATA%\z-image-studio` (Windows).
*   **Output Directory** (Generated Images): `<Data Directory>/outputs` by default. 

### Configure the directory
*   **Config File**: `~/.z-image-studio/config.json` (created on first run after migration).
    *   Override the data directory with `Z_IMAGE_STUDIO_DATA_DIR`.
    *   If you want the output directory sit in another location instead of the data directory, you can override it with `Z_IMAGE_STUDIO_OUTPUT_DIR`.

Directory structure inside Data Directory by default:
*   `zimage.db`: SQLite database
*   `loras/`: LoRA models
*   `outputs/`: Generated image files

### One-time Migration (automatic)
On first run without an existing config file, the app migrates legacy data by moving:
*   `outputs/`, `loras/`, and `zimage.db` from the current working directory (old layout) into the new locations.

## Usage

After installation, you can use the `zimg` command directly from your terminal.

### 1. CLI Generation (Default Mode)
Generate images directly from the command line using the `generate` (or `gen`) subcommand.

```bash
# Basic generation
zimg generate "A futuristic city with neon lights"

# Using the alias 'gen'
zimg gen "A cute cat"

# Custom output path
zimg gen "A cute cat" --output "my_cat.png"

# High quality settings
zimg gen "Landscape view" --width 1920 --height 1080 --steps 20

# With a specific seed for reproducibility
zimg gen "A majestic dragon" --seed 12345

# Select model precision (full, q8, q4)
zimg gen "A futuristic city" --precision q8
```

### 2. Web Server Mode
Launch the web interface to generate images interactively.

```bash
# Start server on default port (http://localhost:8000)
zimg serve

# Start on custom host/port
zimg serve --host 0.0.0.0 --port 9090
```

Once started, open your browser to the displayed URL.

## Command Line Arguments

### Subcommand: `generate` (alias: `gen`)
| Argument | Short | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `prompt` | | `str` | Required | The text prompt for image generation. |
| `--output` | `-o` | `str` | `None` | Custom output filename. Defaults to `outputs/<prompt-slug>.png` inside the data directory. |
| `--steps` | | `int` | `9` | Number of inference steps. Higher usually means better quality. |
| `--width` | `-w` | `int` | `1280` | Image width (automatically adjusted to be a multiple of 8). |
| `--height` | `-H` | `int` | `720` | Image height (automatically adjusted to be a multiple of 8). |
| `--seed` | | `int` | `None` | Random seed for reproducible generation. |
| `--precision` | | `str` | `q8` | Model precision (`full`, `q8`, `q4`). `q8` is the default and balanced, `full` is higher quality but slower, `q4` is fastest and uses less memory. |
| `--lora` | | `str` | `[]` | LoRA filename or path, optionally with strength (`name.safetensors:0.8`). Can be passed multiple times (max 4); strength is clamped to -1.0..2.0. |

### Subcommand: `serve`
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host` | `str` | `0.0.0.0` | Host to bind the server to. |
| `--port` | `int` | `8000` | Port to bind the server to. |
| `--reload` | `bool` | `False` | Enable auto-reload (for development). |

### Subcommand: `models`
| Argument | Short | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| (None)   |       |       |         | Lists available image generation models, highlights the one recommended for your system's hardware, and displays their corresponding Hugging Face model IDs. |

## Screenshots

![Screenshot 1](docs/images/screenshot1.png)

![Screenshot 2](docs/images/screenshot2.png)

![Screenshot 3](docs/images/screenshot3.png)


## Development

### Installation in Project Virtual Environment

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/iconben/z-image-studio.git
    cd z-image-studio
    ```

### To run the source code directly without installation:

1.  **Run CLI:**
    ```bash
    uv run src/zimage/cli.py generate "A prompt"
    ```

2.  **Run Server:**
    ```bash
    uv run src/zimage/cli.py serve --reload
    ```

3.  **Run tests:**
    ```bash
    uv run pytest
    ```

### Optional: Install in editable mode:**
    First install it:
    ```bash
    uv pip install -e .
    ```

    After this, the `zimg` command is available **inside this virtual environment**:

    Then use the zimg command in either ways:

    Using `uv` (recommended):
    ```bash
    uv run zimg generate "A prompt"
    ```

    or use in more traditional way:
    ```bash
    source .venv/bin/activate  # Under Windows: .venv\Scripts\activate
    zimg serve
    ```

### Optional: Override the folder settings with environment variables
    If you do not want your development data mess up your production data,  
    You can define environment variable Z_IMAGE_STUDIO_DATA_DIR to change the data folder for
    You can also define environment variable Z_IMAGE_STUDIO_OUTPUT_DIR to change the output folder to another separate folder
## Notes

*   **Guidance Scale**: The script hardcodes `guidance_scale=0.0` as required by the Turbo model distillation process.
*   **Safety Checker**: Disabled by default to prevent false positives and potential black image outputs during local testing.
