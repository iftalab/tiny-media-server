"""Test suite for MarsCamStreamer.

Starting point only - add your own cases.

Run with:  pytest -q
"""

import threading
import time

import mars_cam_streamer
from mars_cam_streamer import MarsCamStreamer
from satellite_api import Frame, Result


def make_frame(ts: int) -> Frame:
    return Frame(data=f"frame-{ts}", timestamp=ts)


class MockEarthClient:
    """A fake phone on Earth.

    The streamer sends frames with send_frame(addr, frame). The real one raises
    NotImplementedError, so every test needs a stand-in. This is it. It records
    every frame it is handed, and it can be made slow, frozen, or broken.

        phone = MockEarthClient()                   # instant, always OK
        phone = MockEarthClient(delay=0.05)         # 50 ms per send
        phone = MockEarthClient(result=Result.ERR)  # every send fails
        phone = MockEarthClient(gate=some_event)    # frozen until gate.set()

    A closed gate is how you make frames pile up inside the satellite, which is
    when the buffer rules start to matter.

    install(monkeypatch, phone) sends every address to one phone.
    install_many(monkeypatch, {addr: phone}) gives each address its own.
    """

    def __init__(self, result=Result.OK, delay=0.0, gate=None):
        self.result = result
        self.delay = delay
        self.gate = gate
        self.received = []      # list of (addr, frame), in arrival order

    def send_frame(self, addr: str, f: Frame) -> Result:
        if self.gate is not None:
            self.gate.wait(timeout=5.0)
        if self.delay:
            time.sleep(self.delay)
        self.received.append((addr, f))
        return self.result

    def frames(self, addr=None):
        """Just the frames, dropping the addr. Pass addr to filter to one phone."""
        return [f for a, f in self.received if addr is None or a == addr]

    def wait_for_frames(self, count: int, timeout: float = 5.0) -> bool:
        """Wait until `count` frames have arrived. True if they did, False if
        they did not turn up before the timeout.

        Sending happens on another thread, so a test must wait before it can
        assert on what arrived:  assert phone.wait_for_frames(6)
        """
        deadline = time.monotonic() + timeout
        while len(self.received) < count and time.monotonic() < deadline:
            time.sleep(0.005)
        return len(self.received) >= count


def install(monkeypatch, phone: MockEarthClient) -> None:
    """Send every frame, for every address, to this one fake phone."""
    monkeypatch.setattr(mars_cam_streamer, "send_frame", phone.send_frame)


def install_many(monkeypatch, phones: dict) -> None:
    """Give each address its own fake phone: {"earth://alan": phone, ...}.

    Use this when the phones must behave differently, e.g. one slow and one
    fast. Every address you connect needs an entry, or the send raises KeyError.
    """
    def route(addr: str, f: Frame) -> Result:
        return phones[addr].send_frame(addr, f)

    monkeypatch.setattr(mars_cam_streamer, "send_frame", route)


# --------------------------------------------------------------------- tests


def test_starting_point():
    streamer = MarsCamStreamer()
    assert True


def test_buffered_frames_are_delivered_in_capture_order(monkeypatch):
    """TC01 frames must reach a client in the order Mars produced them.

    The client is held behind a closed gate so frames accumulate in the
    satellite's buffer - the condition under which ordering actually matters.
    """
    addr = "earth://alan"
    gate = threading.Event()
    phone = MockEarthClient(gate=gate)
    install(monkeypatch, phone)

    streamer = MarsCamStreamer()
    streamer.on_earth_client_connected(addr)

    frame_count = 6
    for ts in range(1, frame_count + 1):
        streamer.on_frame_from_mars(make_frame(ts))
        time.sleep(0.002)   # 33 ms apart in reality; enough here to separate frames

    gate.set()
    arrived = phone.wait_for_frames(frame_count)
    streamer.on_earth_client_disconnected(addr)

    assert arrived, f"expected {frame_count} frames, got {len(phone.received)}"

    timestamps = [f.timestamp for f in phone.frames()]
    assert timestamps == sorted(timestamps), (
        f"frames delivered out of order: {timestamps}"
    )
