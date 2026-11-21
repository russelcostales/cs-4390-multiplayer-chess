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
