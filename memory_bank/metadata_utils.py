import os, json, tempfile, threading
from typing import List, Dict, Any

_lock = threading.Lock()

def ensure_folder(path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def append_jsonl(path: str, record: Dict[str, Any]) -> int:
    ensure_folder(path)
    with _lock:
        # append line, return assigned id (0-based)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("")  # create
        # read length then append
        with open(path, "r+", encoding="utf-8") as f:
            lines = f.readlines()
            assigned_id = len(lines)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
        return assigned_id

def load_all(path: str) -> List[Dict[str, Any]]:
    ensure_folder(path)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def get_by_indices(path: str, indices: List[int]):
    items = load_all(path)
    out = []
    for i in indices:
        out.append(items[i] if 0 <= i < len(items) else None)
    return out