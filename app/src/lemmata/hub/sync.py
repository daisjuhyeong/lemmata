"""Background loop: sync every project (code from GitHub, paper from Overleaf) (default every 5 minutes)."""
from __future__ import annotations

import threading


class SyncLoop(threading.Thread):
    def __init__(self, mgr, interval=300):
        super().__init__(name="lemmata-hub-sync", daemon=True)
        self.mgr, self.interval = mgr, interval
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.wait(self.interval):
            if self.mgr.gh.token():
                self.mgr.sync_all()

    def stop(self):
        self.stop_event.set()
