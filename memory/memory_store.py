import time, threading

class MemoryStore:
    def __init__(self):
        # simple dict store, thread-safe operations
        self.store = {}
        self.lock = threading.Lock()

    def add_document(self, key, doc):
        with self.lock:
            self.store[key] = {"doc": doc, "ts": time.time()}

    def get(self, key):
        with self.lock:
            return self.store.get(key)

    def search_keys(self, prefix):
        with self.lock:
            return [k for k in self.store if k.startswith(prefix)]

    def all(self):
        with self.lock:
            return dict(self.store)