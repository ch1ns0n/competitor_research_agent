import logging
import os
import sys

LOG_PATH = "agent.log"

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Prevent adding handlers multiple times
    if logger.handlers:
        return logger

    # ---- Format ----
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )

    # ---- File handler (UTF-8 always safe) ----
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # ---- Stream handler (console) ----
    stream_handler = logging.StreamHandler()

    # Force UTF-8 on Windows terminals if possible
    try:
        stream = stream_handler.stream
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger