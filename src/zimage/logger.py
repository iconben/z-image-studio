import logging
import sys

_setup_done = False

def setup_logging():
    global _setup_done
    if _setup_done:
        return

    # Configure root logger to write to stderr
    # basicConfig is idempotent if handlers exist, unless force=True
    # We want to ensure stderr logging for our app.
    # Check if handlers already exist to avoid overriding if embedded
    if logging.root.handlers:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr
    )
    _setup_done = True

def get_logger(name: str):
    # Do not auto-setup logging to allow embedding
    return logging.getLogger(name)
