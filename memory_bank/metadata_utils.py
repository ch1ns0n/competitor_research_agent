import os
import json
import tempfile
import threading
import sys

# Platform-specific file locks
if os.name == "nt":
    import msvcrt
else:
    import fcntl

_lock = threading.Lock()

def _acquire_file_lock(f):
    if os.name == "nt":
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
    else:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

def _release_file_lock(f):
    if os.name == "nt":
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
    else:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def ensure_metadata_file(path: str):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def load_metadata(path: str):
    ensure_metadata_file(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def append_metadata(path: str, record: dict) -> int:
    """
    Append record into JSON metadata file in a safe, atomic manner.
    Returns the assigned integer id (0-based).
    """
    ensure_metadata_file(path)
    # process-level lock for speed
    with _lock:
        # read-modify-write with OS file lock
        with open(path, "r+", encoding="utf-8") as f:
            _acquire_file_lock(f)
            try:
                try:
                    data = json.load(f)
                except Exception:
                    data = []
                assigned_id = len(data)
                data.append(record)
                # atomic write via tempfile in same dir
                dirpath = os.path.dirname(path) or "."
                fd, tmp_path = tempfile.mkstemp(dir=dirpath)
                with os.fdopen(fd, "w", encoding="utf-8") as tmpf:
                    json.dump(data, tmpf, indent=2)
                    tmpf.flush()
                    os.fsync(tmpf.fileno())
                # replace original file atomically
                os.replace(tmp_path, path)
                return assigned_id
            finally:
                _release_file_lock(f)

def get_multiple_metadata(path: str, ids):
    items = load_metadata(path)
    result = []
    for i in ids:
        if 0 <= i < len(items):
            result.append(items[i])
        else:
            result.append(None)
    return result