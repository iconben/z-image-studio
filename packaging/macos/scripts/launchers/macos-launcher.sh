#!/bin/bash
# macOS launcher script for Z-Image Studio
# Opens the web UI in the default browser

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

exec "./Z-Image Studio" serve --host 0.0.0.0 --port 8000
