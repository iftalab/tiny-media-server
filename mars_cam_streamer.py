"""Satellite middleware: streams Mars camera frames to Earth clients.

Requirements it is supposed to meet:
  * Camera sends 30 fps; a frame arriving while the previous one is still being
    processed must be discarded.
  * The satellite can buffer at most 30 frames.
  * At most 5 clients may be connected concurrently.
  * send_frame() is blocking (30-500 ms) and may return ERR.
  * Goal: minimise latency and frame loss for every connected client.
"""

import threading
import time

from satellite_api import Frame, Result, send_frame

MAX_CLIENTS = 5
MAX_BUFFER = 30


class MarsCamStreamer:

    def __init__(self):
        self._clients = {}      # addr -> client state
        self._busy = False

    # ------------------------------------------------------------------ API

    def on_earth_client_connected(self, addr: str) -> None:
        if len(self._clients) > MAX_CLIENTS:
            return

        client = {"queue": [], "running": True}
        self._clients[addr] = client

        t = threading.Thread(target=self._pump, args=(addr,), daemon=True)
        client["thread"] = t
        t.start()

    def on_earth_client_disconnected(self, addr: str) -> None:
        client = self._clients.get(addr)
        if client is None:
            return
        client["running"] = False

    def on_frame_from_mars(self, f: Frame) -> None:
        if self._busy:
            return
        self._busy = True

        for addr, client in self._clients.items():
            queue = client["queue"]
            if len(queue) > MAX_BUFFER:
                queue.pop()
            queue.append(f)

        self._process(f)
        self._busy = False

    # -------------------------------------------------------------- helpers

    def _process(self, f: Frame) -> None:
        """Correction algorithms run here."""
        f.timestamp = int(time.time() * 1000)

    def _pump(self, addr: str) -> None:
        client = self._clients[addr]
        while client["running"]:
            queue = client["queue"]
            if not queue:
                time.sleep(0.001)
                continue
            frame = queue.pop()
            send_frame(addr, frame)

    # --------------------------------------------------------- introspection

    def connected_clients(self):
        return list(self._clients.keys())

    def buffered_frames(self, addr: str) -> int:
        return len(self._clients[addr]["queue"])
