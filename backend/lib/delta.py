"""Delta compression for flat state dicts.

Instead of sending the full state every time, send only what changed:
keys that were added or changed go in "set", keys that were removed go in "unset".
"""


def diff(old: dict, new: dict) -> dict:
    """Return the changes needed to turn old into new."""
    changed = {key: value for key, value in new.items() if key not in old or old[key] != value}
    removed = [key for key in old if key not in new]

    delta: dict = {}
    if changed:
        delta["set"] = changed
    if removed:
        delta["unset"] = removed
    return delta


def apply(old: dict, delta: dict) -> dict:
    """Rebuild the new state from old plus a delta. Does not modify old."""
    state = dict(old)
    state.update(delta.get("set", {}))
    for key in delta.get("unset", []):
        state.pop(key, None)
    return state


def is_empty(delta: dict) -> bool:
    # nothing changed, so there's nothing worth sending
    return not delta


# --- cursor stream ---------------------------------------------------------
# diff() above doesn't help the cursor since x and y both change on almost every
# packet. so the cursor gets rounded to ints and we send how far it moved instead.

CURSOR_SCALE = 1000  # 0-1 becomes 0-1000, still finer than a pixel on our board
KEYFRAME_EVERY = 10


class CursorDeltaEncoder:
    """Sender side of one cursor stream. Sends the full position (a keyframe) every
    KEYFRAME_EVERY packets and just dx/dy from the last packet in between."""

    def __init__(self, keyframe_every: int = KEYFRAME_EVERY) -> None:
        self._keyframe_every = keyframe_every
        self._last: tuple[int, int] | None = None
        self._since_keyframe = 0

    def encode(self, x: float, y: float) -> dict:
        qx, qy = round(x * CURSOR_SCALE), round(y * CURSOR_SCALE)
        # keyframe if nothing's been sent yet, it's been a while, or the client resent
        # the same spot (it stopped moving, and this fixes a lost last delta)
        if (
            self._last is None
            or self._since_keyframe >= self._keyframe_every - 1
            or (qx, qy) == self._last
        ):
            self._last = (qx, qy)
            self._since_keyframe = 0
            return {"kx": qx, "ky": qy}

        dx, dy = qx - self._last[0], qy - self._last[1]
        self._last = (qx, qy)
        self._since_keyframe += 1
        return {"dx": dx, "dy": dy}

    def reset(self) -> None:
        # next encode() will be a keyframe
        self._last = None
        self._since_keyframe = 0