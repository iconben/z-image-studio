import logging
import sys

_setup_done = False

def setup_logging():
    global _setup_done
    if _setup_done:
        return

    # Configure root logger to write to stderr
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr
    )
    _setup_done = True

def get_logger(name: str):
    if not _setup_done:
        setup_logging()
    return logging.getLogger(name)
