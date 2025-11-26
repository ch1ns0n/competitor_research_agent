import logging
import json
import time
import os
from functools import wraps
from logging.handlers import RotatingFileHandler
from contextvars import ContextVar
from datetime import datetime

# Context var to carry correlation ID (per request or per ASIN)
correlation_id_var = ContextVar("correlation_id", default=None)


# ------------------------------------------------------------
# FORMATTER: JSON structured logs
# ------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # correlation ID if exists
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        if hasattr(record, "extra"):
            log.update(record.extra)

        # exception stack trace
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)

        return json.dumps(log)


# ------------------------------------------------------------
# PUBLIC API
# ------------------------------------------------------------
def set_correlation_id(value: str):
    """
    Set a correlation_id for this request / pipeline (e.g., ASIN).
    """
    correlation_id_var.set(value)


def clear_correlation_id():
    correlation_id_var.set(None)


def get_correlation_id():
    return correlation_id_var.get()


# ------------------------------------------------------------
# LOGGER FACTORY
# ------------------------------------------------------------
_loggers_cache = {}

def get_logger(name: str):
    """
    Returns a structured JSON logger with console + rotating file output.
    Cached so all imports reuse the same logger.
    """
    if name in _loggers_cache:
        return _loggers_cache[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        # ---- Console handler ----
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(JsonFormatter())
        logger.addHandler(ch)

        # ---- File handler ----
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)

        log_path = os.path.join(log_dir, f"{name}.log")
        
        fh = RotatingFileHandler(
            log_path,
            maxBytes=5_000_000,
            backupCount=5,
            encoding="utf-8"
        )
        fh.setLevel(logging.INFO)
        fh.setFormatter(JsonFormatter())
        logger.addHandler(fh)

    _loggers_cache[name] = logger
    return logger


# ------------------------------------------------------------
# DECORATOR: trace a function with timing
# ------------------------------------------------------------
def with_trace(label: str = None):
    """
    Decorator to measure execution time of a function and log
    automatically using the active logger.
    
    Example:
    @with_trace("embedding_generation")
    def generate():
        ...
    """
    def decorator(func):
        traced_label = label or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            logger_name = func.__module__.split(".")[0]
            logger = get_logger(logger_name)

            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                ms = int((time.time() - start) * 1000)
                logger.info(
                    f"{traced_label} completed",
                    extra={"extra": {"trace": traced_label, "ms": ms}},
                )

        return wrapper
    return decorator


# ------------------------------------------------------------
# UTILITY: log info/error with extra metadata
# ------------------------------------------------------------
def log_info(logger, msg, **kwargs):
    logger.info(msg, extra={"extra": kwargs})


def log_error(logger, msg, **kwargs):
    logger.error(msg, extra={"extra": kwargs})