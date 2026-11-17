import json
import os
import signal
import threading
import time


class WorkerRuntime:
    """SIGTERM drains the current job. Forced stops remain recoverable by leases."""

    def __init__(self, path=None):
        self.stopping = threading.Event()
        self.path = path
        self.previous = None

    def __enter__(self):
        self.previous = signal.signal(signal.SIGTERM, lambda *_: self.stopping.set())
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.thread = threading.Thread(target=self.heartbeat, daemon=True)
            self.thread.start()
        return self

    def heartbeat(self):
        while not self.stopping.is_set():
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"pid": os.getpid(), "updated": time.time()}), encoding="utf-8"
            )
            temporary.replace(self.path)
            self.stopping.wait(5)

    def __exit__(self, *_):
        self.stopping.set()
        if self.path:
            self.thread.join(timeout=6)
        signal.signal(signal.SIGTERM, self.previous)
