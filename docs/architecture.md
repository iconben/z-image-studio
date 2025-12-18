# Z-Image Studio Architecture

This document provides an overview of the Z-Image Studio architecture, including project structure, key components, and development guidelines.

## Project Structure

```
z-image-studio/
├── src/zimage/           # Main source code
│   ├── cli.py           # Command-line interface
│   ├── server.py        # Web UI FastAPI server
│   ├── mcp_server.py    # MCP server (stdio + SSE)
│   ├── engine.py        # Image generation engine
│   ├── worker.py        # Async worker for generation tasks
│   ├── storage.py       # File storage and database operations
│   ├── hardware.py      # Hardware detection and optimization
│   └── ...              # Other core modules
├── tests/               # Test suite
├── docs/                # Documentation
├── pyproject.toml       # Project configuration and dependencies
└── README.md           # Quick start guide
```

## Modern Python Tooling

This project uses **uv** and **pyproject.toml** for modern Python development:

### What is uv?
`uv` is a modern Python package manager and tool installer that's significantly faster than pip and provides an all-in-one solution for Python projects.

### Key Benefits:
- **10-100x faster** than pip for package installation
- Integrated virtual environment management
- Single tool for dependency management, running scripts, and packaging
- Compatible with existing pip and conda workflows

### Project Configuration (pyproject.toml)
The entire project configuration is centralized in `pyproject.toml`:

```toml
[project]
name = "z-image-studio"
version = "0.1.0"
dependencies = [
    "fastapi>=0.123.0",
    "mcp>=1.23.2",
    # ... other dependencies
]

[project.scripts]
zimg = "zimage.cli:main"
zimg-mcp = "zimage.mcp_server:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.uv.sources]
diffusers = { git = "https://github.com/huggingface/diffusers" }
```

This replaces:
- `requirements.txt` → `[project.dependencies]`
- `setup.py` → `[project]` section
- `pytest.ini` → `[tool.pytest.ini_options]`
- Custom installation scripts → `[project.scripts]`

### Common uv Commands:
```bash
# Install dependencies
uv sync

# Run commands in the project environment
uv run pytest
uv run zimg generate "A prompt"
uv run python src/zimage/cli.py serve

# Install in development mode
uv pip install -e .
```

### Why This Modern Approach?
- **Single source of truth**: All configuration in one file
- **Faster development**: Quick dependency resolution and installation
- **Better caching**: Efficient package downloads and builds
- **Cross-platform**: Works consistently across operating systems
- **Future-proof**: Aligns with Python packaging standards

## Core Components

### 1. CLI Interface (`cli.py`)
- Entry point for command-line usage
- Supports image generation commands
- Can launch web server and MCP server
- Handles configuration and environment setup

### 2. Web UI Server (`server.py`)
- FastAPI-based web server
- Serves the web interface for interactive image generation
- Handles file uploads, history browsing, and model management
- Supports both local and remote access

### 3. MCP Server (`mcp_server.py`)
- Implements Model Context Protocol for AI agent integration
- Supports two transport modes:
  - **stdio**: Direct pipe communication with local agents
  - **SSE**: Server-Sent Events for web-based agent communication
- Provides tools: `generate`, `list_models`, `list_history`
- Transport-agnostic content structure

#### MCP Content Structure
The `generate` tool returns a consistent 3-element array:

1. **TextContent**: Metadata with generation info and access detail
   - SSE: includes an absolute `url` for remote access
   - stdio: includes a local `file_path` for local access
2. **ResourceLink**: Main image reference
   - SSE: absolute URL
   - stdio: `file://` URI
3. **ImageContent**: Base64-encoded thumbnail (256px max)

### 4. Generation Engine (`engine.py`)
- Handles the actual image generation using Diffusers
- Supports multiple model precisions (full, q8, q4)
- Optimized for different hardware (CUDA, MPS, CPU)
- Implements memory management and attention slicing

### 5. Worker System (`worker.py`)
- Async task management for long-running operations
- Prevents blocking during image generation
- Handles cleanup and memory management

### 6. Hardware Layer (`hardware.py`)
- Automatic hardware detection (CUDA, MPS, CPU)
- Performance recommendations based on available resources
- Model precision optimization

## Transport Modes

### MCP stdio Transport
- Uses standard input/output for communication
- Ideal for local AI agents and CLI tools
- Returns local file paths in content

### MCP SSE Transport
- HTTP-based Server-Sent Events
- Supports web-based AI agents and remote access
- Builds absolute URLs for client access
- Includes progress reporting via `ctx.report_progress()`
- Handles client disconnections gracefully
- Mounted under `/mcp`, with:
  - `GET /mcp/sse` for the SSE stream
  - `POST /mcp/messages/` for client JSON-RPC messages
- `/mcp` is reserved for future Streamable HTTP transport

## Configuration Management

### Pytest Configuration
The project uses modern pytest configuration centralized in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = ["-v", "--tb=short", "--strict-markers", "--strict-config"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
]
```

Key features:
- **Auto asyncio mode**: Automatically detects and runs async test functions
- **Strict markers**: Ensures all pytest.mark.* decorators are properly declared
- **Test discovery**: Automatically finds tests in the `tests/` directory
- **Selective testing**: Use `-m "not slow"` to skip time-intensive tests

### Environment Variables
- `Z_IMAGE_STUDIO_DATA_DIR`: Override data directory location
- `Z_IMAGE_STUDIO_OUTPUT_DIR`: Override output directory location
- `ZIMAGE_BASE_URL`: Base URL for building absolute links in SSE mode
- `ZIMAGE_DISABLE_MCP_SSE`: Set to "1" to disable mounting `/mcp/sse` and `/mcp/messages/`

## Testing Strategy

### Test Organization
- Unit tests focus on individual components
- Integration tests verify component interactions
- Mock-based testing to avoid heavy model loading during development
- SSE tests use comprehensive mocking to prevent real generation

### Key Test Patterns
```python
# Mock heavy dependencies
with patch('zimage.mcp_server._get_engine') as mock_get_engine, \
     patch('zimage.mcp_server.save_image') as mock_save:

    # Setup mock returns
    mock_get_engine.return_value = (mock_generate_func, mock_cleanup_func)

    # Test the functionality
    result = await some_function()
```

## Memory and Performance Optimization

### Automatic Optimizations
- **Attention Slicing**: Automatically enabled for systems with limited RAM/VRAM
- **Precision Selection**: Hardware-aware model precision recommendations
- **Memory Cleanup**: Automatic cleanup after generation tasks

### Hardware Support
- **NVIDIA CUDA**: Primary acceleration platform
- **Apple Silicon (MPS)**: Native support for M1/M2/M3 chips
- **CPU Fallback**: Software-based generation when GPU unavailable

## Security Considerations

### MCP Security
- Input validation for all user prompts
- Safe file handling with sandboxed output directories
- Resource limits to prevent abuse

### Web Security
- CORS configuration for cross-origin requests
- File upload restrictions
- XSS prevention in web interface

## Development Guidelines

### Code Style
- Follow PEP 8 formatting
- Use type hints where appropriate
- Comprehensive docstrings for public APIs

### Adding New Features
1. Implement feature in appropriate module
2. Add unit tests with mocking for heavy dependencies
3. Update documentation if user-facing
4. Test both stdio and SSE modes for MCP changes

### Performance Considerations
- Profile memory usage for new features
- Consider impact on different hardware configurations
- Use async patterns for I/O-bound operations

## Future Considerations

### Scalability
- Multi-GPU support for parallel generation
- Distributed processing for high-volume scenarios
- Caching layer for common generations

### Extensibility
- Plugin system for custom models
- Additional transport modes for MCP
- Enhanced web UI features
