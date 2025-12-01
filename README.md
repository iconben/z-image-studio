# Z-Image CLI

A command-line interface for the **Z-Image-Turbo** text-to-image generation model (`Tongyi-MAI/Z-Image-Turbo`).

This tool is designed to run efficiently on local machines, with specific optimizations for **Apple Silicon (MPS)**, falling back to CPU if unavailable.

## Features

*   **Z-Image-Turbo Model**: Utilizes the high-quality `Tongyi-MAI/Z-Image-Turbo` model via `diffusers`.
*   **Hybrid Interface**: 
    *   **CLI**: Fast, direct image generation from the terminal.
    *   **Web UI**: Modern web interface for interactive generation.
*   **MPS Acceleration**: Optimized for Mac users with Apple Silicon.
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

2.  **Install dependencies:**
    Using `uv` (recommended):
    ```bash
    uv sync
    ```

## Usage

Run the script using `uv run` or directly with python if your environment is active.

### 1. CLI Generation (Default Mode)
Generate images directly from the command line.

```bash
# Basic generation
uv run main.py "A futuristic city with neon lights"

# Custom output path
uv run main.py "A cute cat" --output "my_cat.png"

# High quality settings
uv run main.py "Landscape view" --width 1920 --height 1080 --steps 20
```

### 2. Web Server Mode
Launch the web interface to generate images interactively.

```bash
# Start server on default port (http://localhost:8000)
uv run main.py serve

# Start on custom host/port
uv run main.py serve --host 0.0.0.0 --port 9090
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

### Server Mode (`serve`)
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host` | `str` | `0.0.0.0` | Host to bind the server to. |
| `--port` | `int` | `8000` | Port to bind the server to. |
| `--reload` | `bool` | `False` | Enable auto-reload (for development). |

## Notes

*   **Guidance Scale**: The script hardcodes `guidance_scale=0.0` as required by the Turbo model distillation process.
*   **Safety Checker**: Disabled by default to prevent false positives and potential black image outputs during local testing.