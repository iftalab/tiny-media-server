"""Satellite runtime stub.

In production this is provided by the satellite firmware. For the exercise it is
a module-level function so tests can patch it:

    monkeypatch.setattr(mars_cam_streamer, "send_frame", fake_send)
"""

from enum import Enum


class Frame:
    def __init__(self, data: str, timestamp: int):
        self.data = data
        self.timestamp = timestamp

    def __repr__(self) -> str:
        return f"Frame(ts={self.timestamp})"


class Result(Enum):
    OK = 0
    ERR = 1


def send_frame(addr: str, f: Frame) -> Result:
    """Blocking. Takes 30-500 ms. Returns Result.OK or Result.ERR."""
    raise NotImplementedError("Provided by the satellite runtime")
