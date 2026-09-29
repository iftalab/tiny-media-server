# Mars Cam Streamer: testing exercise

## The story

A robot on Mars has a camera. The camera films and sends pictures to a
satellite. The satellite sends those pictures to phones on Earth. People watch
the video live.

One picture is called a **frame**.

```
  Mars camera  ---->  satellite  ---->  up to 5 phones on Earth
                    (the code you test)
```

## Your job

`mars_cam_streamer.py` is the satellite's code. Someone wrote it. **It has
bugs.**

Write tests that find the bugs. Do not fix the code. Do not change it.

You have about 1 hour.

## Rules the code must follow

| # | Rule |
| --- | --- |
| 1 | The camera sends 30 frames every second. |
| 2 | The satellite can hold 30 frames. No more. When it is full, it throws away the **oldest** frame. |
| 3 | Only 5 phones can be connected at the same time. |
| 4 | A phone can leave at any time. It can come back at any time. |
| 5 | Sending one frame to one phone is slow. It takes 30 to 500 ms. |
| 6 | Sending can fail. Then you get `ERR` instead of `OK`. |
| 7 | If a new frame arrives while the satellite is still busy with the last one, the new frame is thrown away. |
| 8 | People must see the video live. So: keep delay small, and lose as few frames as you can. |

## Why this is hard

Frames come in fast. They go out slow.

* In: one frame every 33 ms.
* Out: one frame takes up to 500 ms.

Frames arrive about 15 times faster than they can leave. The satellite holds
only 30. It will fill up.

When it is full it must throw a frame away. It should throw away the
**oldest** one, because this is live video and old frames are worth nothing.
Throwing away the newest instead is the classic mistake: the satellite stays
stuck on old frames and the viewer falls further behind every second.

Several of the bugs live near this idea.

## The code you are testing

The satellite calls these three methods:

```python
streamer.on_earth_client_connected(addr)      # a phone joins
streamer.on_earth_client_disconnected(addr)   # a phone leaves
streamer.on_frame_from_mars(frame)            # a new frame is ready
```

`addr` is just a string, like `"earth://alan"`. It says which phone.

You can also look inside with these two:

```python
streamer.connected_clients()      # which phones are connected -> list
streamer.buffered_frames(addr)    # frames the satellite is holding for that phone -> number
```

Those two are enough. You should not need to open up `MarsCamStreamer` and read
its private parts.

`buffered_frames` asks about one phone at a time. Rule 2 is about the satellite
as a whole, so if you want to check rule 2, add the phones up.

## How to run the tests

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pytest
pytest -q
```

Write your tests in `test_mars_cam_streamer.py`. It already has one empty test
to get you started.

## MockEarthClient: your fake phone

### What it is

* A **fake phone**. It stands where a real phone on Earth would stand.
* You need it because the satellite sends frames with `send_frame(addr, frame)`,
  and that function is empty here. It raises an error. Any test that lets the
  code send a frame will crash without a fake phone.
* It writes down every frame it is given. That list is how you check what the
  satellite did.
* You can make it slow, frozen, or broken, so you can test hard situations on
  purpose.

### Making one

```python
phone = MockEarthClient()                    # fast, always works
phone = MockEarthClient(delay=0.05)          # each send takes 50 ms
phone = MockEarthClient(gate=some_event)     # sends nothing until you say go
phone = MockEarthClient(result=Result.ERR)   # every send fails
```

| Setting | What it does | Use it when |
| --- | --- | --- |
| nothing | Sends are instant and always return `OK`. | Simple tests. |
| `delay=0.05` | Every send takes 50 ms. | You want a realistic slow phone. |
| `gate=event` | Every send waits. Nothing gets out until you call `event.set()`. | You want frames to pile up inside the satellite. |
| `result=Result.ERR` | Every send fails. | You want to test what happens after a failure. |

### What you can ask it

| Call | Gives you | Notes |
| --- | --- | --- |
| `phone.received` | A list of `(addr, frame)` pairs, oldest first. | Every send that happened. |
| `phone.frames()` | The same list, but only the frames. | Easier to read in asserts. |
| `phone.frames(addr)` | Only the frames sent to that one address. | Useful when one phone is catching all the addresses. |
| `phone.wait_for_frames(n)` | `True` if `n` frames arrived, `False` if they did not. | Sending happens on another thread, so you must wait. Gives up after 5 seconds. |

Two more helpers live in the same file:

| Call | What it does |
| --- | --- |
| `install(monkeypatch, phone)` | Puts one fake phone in place of the real `send_frame`. It gets the frames for *every* address. Call it before your test sends anything. |
| `install_many(monkeypatch, {addr: phone})` | Gives each address its own fake phone. Use it when the phones must act differently, like one slow and one fast. |
| `make_frame(7)` | Builds a frame labelled `"frame-7"`. |

### Examples

**One frame reaches one phone.**

```python
def test_frame_arrives(monkeypatch):
    phone = MockEarthClient()
    install(monkeypatch, phone)

    streamer = MarsCamStreamer()
    streamer.on_earth_client_connected("earth://alan")
    streamer.on_frame_from_mars(make_frame(1))

    assert phone.wait_for_frames(1)
    assert phone.frames()[0].data == "frame-1"
```

**Fill the satellite up, then look at what comes out.**

```python
def test_buffer_keeps_the_newest(monkeypatch):
    gate = threading.Event()
    phone = MockEarthClient(gate=gate)      # frozen: nothing can leave
    install(monkeypatch, phone)

    streamer = MarsCamStreamer()
    streamer.on_earth_client_connected("earth://alan")
    for ts in range(1, 41):                 # 40 frames, room for 30
        streamer.on_frame_from_mars(make_frame(ts))

    gate.set()                              # let them all out
    phone.wait_for_frames(30)

    labels = [f.data for f in phone.frames()]
    assert "frame-40" in labels             # the newest must survive
```

**A phone that always fails.**

```python
def test_failed_send(monkeypatch):
    phone = MockEarthClient(result=Result.ERR)
    install(monkeypatch, phone)
    ...
```

**Two phones, one of them slow.**

```python
def test_slow_phone_does_not_hurt_the_other(monkeypatch):
    fast = MockEarthClient()
    slow = MockEarthClient(delay=0.2)
    install_many(monkeypatch, {
        "earth://alan": fast,
        "earth://clive": slow,
    })

    streamer = MarsCamStreamer()
    streamer.on_earth_client_connected("earth://alan")
    streamer.on_earth_client_connected("earth://clive")
    ...
    # alan should still get his frames while clive crawls
```

## Why there is no fake camera

You need a fake phone because the satellite *calls* the phone.

You do not need a fake camera, because the camera does not work that way. The
camera calls the satellite. So in your test, **you are the camera**. Make a
frame and call the method:

```python
streamer.on_frame_from_mars(make_frame(1))
```

Do not build a helper that sends 30 frames a second in real time. Your tests
would get slow, and they would give a different answer each run. Send frames as
fast as you like, in the order you choose.

If you want frames arriving *while* phones join and leave, start a thread in
your test. That is not a mock.

## Two tips

* Tell frames apart by `frame.data` (like `"frame-7"`). Not by
  `frame.timestamp`. `make_frame(7)` sets both, but only `data` is safe to
  trust all the way through.
* `buffered_frames(addr)` will raise `KeyError` if that phone never connected.

## What we are looking for
- A list of test cases written in TESTS.md in the following format
- Case Id: For given situation, expected outcome. 
- Example: Frames must reach a earth client in the order Mars produced them
- Implementation of automated tests for your test cases in ```test_mars_cam_streamer.py```
- Write a BUGS.md with the bugs you have found with their severity


