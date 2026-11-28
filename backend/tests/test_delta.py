from lib.delta import CursorDeltaEncoder, apply, diff, is_empty

def test_no_changes_gives_empty_delta():
    state = {"x": 1, "y": 2}
    delta = diff(state, dict(state))
    assert delta == {}
    assert is_empty(delta)


def test_only_changed_keys_are_sent():
    old = {"x": 1, "y": 2, "color": "white"}
    new = {"x": 5, "y": 2, "color": "white"}
    assert diff(old, new) == {"set": {"x": 5}}


def test_added_key_goes_in_set():
    assert diff({"x": 1}, {"x": 1, "y": 2}) == {"set": {"y": 2}}


def test_removed_key_goes_in_unset():
    assert diff({"x": 1, "y": 2}, {"x": 1}) == {"unset": ["y"]}


def test_round_trip_rebuilds_new_state():
    old = {"fen": "start", "turn": "white", "check": False}
    new = {"fen": "after e4", "turn": "black", "last_move": "e4"}
    assert apply(old, diff(old, new)) == new


def test_apply_does_not_modify_old():
    old = {"x": 1}
    apply(old, {"set": {"x": 2}})
    assert old == {"x": 1}


def test_apply_empty_delta_returns_same_state():
    old = {"x": 1, "y": 2}
    assert apply(old, {}) == old


def test_from_empty_state_sends_everything():
    new = {"x": 3, "y": 4}
    assert diff({}, new) == {"set": new}
    assert apply({}, diff({}, new)) == new

def test_cursor_encoder_starts_with_keyframe_then_deltas():
    enc = CursorDeltaEncoder()
    assert enc.encode(0.5, 0.5) == {"kx": 500, "ky": 500}
    assert enc.encode(0.504, 0.498) == {"dx": 4, "dy": -2}


def test_cursor_encoder_sends_keyframe_every_n():
    enc = CursorDeltaEncoder(keyframe_every=3)
    out = [enc.encode(i / 100, 0.5) for i in range(1, 7)]
    assert ["kx" in packet for packet in out] == [True, False, False, True, False, False]


def test_cursor_encoder_repeat_position_is_keyframe():
    enc = CursorDeltaEncoder()
    enc.encode(0.2, 0.2)
    enc.encode(0.3, 0.3)
    assert enc.encode(0.3, 0.3) == {"kx": 300, "ky": 300}


def test_cursor_encoder_reset_forces_keyframe():
    enc = CursorDeltaEncoder()
    enc.encode(0.2, 0.2)
    enc.reset()
    assert "kx" in enc.encode(0.3, 0.3)
    