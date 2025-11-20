import uuid, time, threading

class SessionService:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()

    def create_session(self, trace_id, meta):
        sid = str(uuid.uuid4())
        sess = {"id": sid, "trace": trace_id, "meta": meta, "events": [], "created": time.time()}
        with self.lock:
            self.sessions[sid] = sess
        return sess

    def append_event(self, sid, event):
        with self.lock:
            if sid in self.sessions:
                self.sessions[sid]["events"].append({"ts": time.time(), **event})
                return True
        return False

    def get_session(self, sid):
        with self.lock:
            return self.sessions.get(sid)