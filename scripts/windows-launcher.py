"""
Windows launcher for Z-Image Studio Web UI.

This script starts the server and automatically opens the web browser.
It includes retry logic to wait for the server to be ready before opening.
"""

import subprocess
import sys
import time
import urllib.request
import urllib.error
import webbrowser
import os


def wait_for_server(url: str, timeout: float = 30.0, poll_interval: float = 0.5) -> bool:
    """Wait for the server to be ready by polling the URL."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError):
            pass
        time.sleep(poll_interval)
    return False


def main():
    server_url = "http://localhost:8000"

    print("Starting Z-Image Studio server...")

    # Start the server as a subprocess
    # Use sys.executable to run the bundled Python interpreter
    server_process = subprocess.Popen(
        [sys.executable, "-m", "zimage", "serve", "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    try:
        # Wait for server to be ready
        print(f"Waiting for server at {server_url}...")
        if wait_for_server(server_url):
            print(f"Server is ready! Opening {server_url} in your browser...")
            webbrowser.open(server_url)
            print("Press Ctrl+C to stop the server.")

            # Wait for server process
            server_process.wait()
        else:
            print("ERROR: Server failed to start within timeout.")
            server_process.terminate()
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server_process.terminate()
        server_process.wait()
        print("Server stopped.")


if __name__ == "__main__":
    main()
