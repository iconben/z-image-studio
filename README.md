# Z-Image CLI

A command-line interface for the **Z-Image-Turbo** text-to-image generation model (`Tongyi-MAI/Z-Image-Turbo`).

This tool is designed to run efficiently on local machines, with specific optimizations for **Apple Silicon (MPS)**, falling back to CPU if unavailable.

## Features

*   **Z-Image-Turbo Model**: Utilizes the high-quality `Tongyi-MAI/Z-Image-Turbo` model via `diffusers`.
*   **Hybrid Interface**: 
    *   **CLI**: Fast, direct image generation from the terminal.
    *   **Web UI**: Modern web interface for interactive generation.
*   **MPS Acceleration**: Optimized for Mac users with Apple Silicon.
*   **Attention Slicing Auto-detection**: Automatically manages memory usage (e.g., enables attention slicing for systems with lower RAM/VRAM) to prevent Out-of-Memory errors and optimize performance.
*   **Seed Control**: Reproducible image generation via CLI or Web UI.
*   **Automatic Dimension Adjustment**: Ensures image dimensions are compatible (multiples of 8).

## Requirements

*   Python >= 3.11
*   `uv` (recommended for dependency management)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd zimage-cli
    ```

2.  **Install dependencies and package in editable mode:**
    Using `uv` (recommended):
    ```bash
    uv pip install -e .
    ```

    This will install all dependencies and make the `zimage` command available globally.

## Usage

After installation, you can use the `zimage` command directly from your terminal.

### 1. CLI Generation (Default Mode)
Generate images directly from the command line.

```bash
# Basic generation
zimage "A futuristic city with neon lights"

# Custom output path
zimage "A cute cat" --output "my_cat.png"

# High quality settings
zimage "Landscape view" --width 1920 --height 1080 --steps 20

# With a specific seed for reproducibility
zimage "A majestic dragon" --seed 12345
```

### 2. Web Server Mode
Launch the web interface to generate images interactively.

```bash
# Start server on default port (http://localhost:8000)
zimage serve

# Start on custom host/port
zimage serve --host 0.0.0.0 --port 9090
```

Once started, open your browser to the displayed URL.

## Command Line Arguments

### Generation Mode
| Argument | Short | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `prompt` | | `str` | Required | The text prompt for image generation. |
| `--output` | `-o` | `str` | `None` | Custom output filename. Defaults to `outputs/<prompt-slug>.png`. |
| `--steps` | | `int` | `9` | Number of inference steps. Higher usually means better quality. |
| `--width` | `-w` | `int` | `1280` | Image width (automatically adjusted to be a multiple of 8). |
| `--height` | `-H` | `int` | `720` | Image height (automatically adjusted to be a multiple of 8). |
| `--seed` | | `int` | `None` | Random seed for reproducible generation. |

### Server Mode (`serve`)
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host` | `str` | `0.0.0.0` | Host to bind the server to. |
| `--port` | `int` | `8000` | Port to bind the server to. |
| `--reload` | `bool` | `False` | Enable auto-reload (for development). |

## Development

To run the source code directly without installation:

1.  **Run CLI:**
    ```bash
    uv run src/zimage/cli.py "A prompt"
    ```

2.  **Run Server:**
    ```bash
    uv run src/zimage/cli.py serve --reload
    ```

3.  **Run tests:**
    ```bash
    uv run python -m unittest tests/manual_test_mps.py
    ```

## Notes

*   **Guidance Scale**: The script hardcodes `guidance_scale=0.0` as required by the Turbo model distillation process.
*   **Safety Checker**: Disabled by default to prevent false positives and potential black image outputs during local testing.