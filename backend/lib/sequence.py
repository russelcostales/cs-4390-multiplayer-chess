"""Sequence numbers for the unreliable channel.

The sender stamps each message with a number that goes up by one.
The receiver keeps the highest number it has seen and drops anything
older or repeated, so a late packet never moves state backwards.
"""


class SequenceCounter:
    """Hands out increasing sequence numbers, starting at 1."""

    def __init__(self) -> None:
        self._last = 0

    def next(self) -> int:
        self._last += 1
        return self._last

    def stamp(self, message: dict) -> dict:
        # copy so the caller's dict isn't changed
        return {**message, "seq": self.next()}


class StaleFilter:
    """Accepts a message only if its seq is newer than the last accepted one."""

    def __init__(self) -> None:
        self.last_seen = 0
        self.dropped = 0

    def accept(self, seq: int) -> bool:
        if seq <= self.last_seen:
            self.dropped += 1
            return False
        self.last_seen = seq
        return True

    def reset(self) -> None:
        # call when a new stream starts, like a reconnect
        self.last_seen = 0
        self.dropped = 0
