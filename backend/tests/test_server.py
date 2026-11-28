import json
import logging
import random
import threading
from collections.abc import Callable

import pytest

from server import Client, Matchmaker
from messages import MAX_MESSAGE_BYTES
from moves import MoveService

def test_client_with_on_send_forwards_instead_of_storing():
    client = Client("a", "Alice")
    seen = []
    client.on_send = seen.append
    client.send({"type": "ping"})
    assert seen == [{"type": "ping"}]
    assert client.inbox == []

CREATE = '{"type":"create_lobby","name":"Room"}'
LIST = '{"type":"list_lobbies"}'
LEAVE = '{"type":"leave_lobby"}'


def create(name: str = "Room", passcode: str | None = None) -> str:
    message = {"type": "create_lobby", "name": name}
    if passcode is not None:
        message["passcode"] = passcode
    return json.dumps(message)


def join(lobby_id: str, passcode: str | None = None) -> str:
    message = {"type": "join_lobby", "lobbyId": lobby_id}
    if passcode is not None:
        message["passcode"] = passcode
    return json.dumps(message)


class ScriptedRng:
    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)

    def random(self) -> float:
        return next(self._values)


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def of_type(client: Client, message_type: str) -> list[dict]:
    return [message for message in client.inbox if message["type"] == message_type]


def colors_for(rng) -> tuple[str, str]:
    mm = Matchmaker(rng=rng)
    host = mm.connect("a")
    guest = mm.connect("b")
    mm.handle_message(host, CREATE)
    mm.handle_message(guest, join("1"))
    return of_type(host, "match_started")[0]["color"], of_type(guest, "match_started")[0]["color"]


def run_together(calls: list[Callable[[], None]]) -> None:
    barrier = threading.Barrier(len(calls))
    errors: list[Exception] = []

    def invoke(call: Callable[[], None]) -> None:
        try:
            barrier.wait(timeout=5)
            call()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=invoke, args=(call,), daemon=True) for call in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()
    assert errors == []


def test_create_lobby_then_list():
    mm = Matchmaker()
    host = mm.connect("a")
    other = mm.connect("b")
    mm.handle_message(host, CREATE)
    assert host.inbox == [
        {"type": "lobby_created", "lobby": {"id": "1", "name": "Room", "locked": False}}
    ]

    mm.handle_message(other, LIST)
    assert other.inbox[-1] == {
        "type": "lobby_list",
        "lobbies": [{"id": "1", "name": "Room", "locked": False}],
    }


def test_locked_lobby_hides_passcode():
    mm = Matchmaker()
    host = mm.connect("a")
    other = mm.connect("b")
    mm.handle_message(host, create("Secret", "s3cret"))
    mm.handle_message(other, LIST)

    assert other.inbox[-1]["lobbies"] == [{"id": "1", "name": "Secret", "locked": True}]
    assert "s3cret" not in json.dumps(host.inbox)
    assert "s3cret" not in json.dumps(other.inbox)


def test_create_lobby_twice_is_rejected():
    mm = Matchmaker()
    host = mm.connect("a")
    mm.handle_message(host, CREATE)
    mm.handle_message(host, create("Again"))
    assert host.inbox[-1] == {
        "type": "error",
        "code": "ALREADY_IN_LOBBY",
        "message": "Already in lobby",
    }


def test_join_starts_game_with_opposite_colors():
    mm = Matchmaker(rng=ScriptedRng([0.0]))
    host = mm.connect("a", "Ada")
    guest = mm.connect("b", "Grace")
    watcher = mm.connect("c")
    mm.handle_message(host, CREATE)
    mm.handle_message(guest, join("1"))

    game = mm.game_of(host.id)
    assert game is not None
    assert mm.game_of(guest.id) is game
    assert game.white_id == host.id
    assert game.black_id == guest.id
    assert [message["type"] for message in host.inbox] == ["lobby_created", "match_started"]
    assert [message["type"] for message in guest.inbox] == ["match_started"]
    assert of_type(host, "match_started") == [
        {
            "type": "match_started",
            "gameId": game.id,
            "color": "white",
            "opponent": {"id": "b", "name": "Grace"},
        }
    ]
    assert of_type(guest, "match_started") == [
        {
            "type": "match_started",
            "gameId": game.id,
            "color": "black",
            "opponent": {"id": "a", "name": "Ada"},
        }
    ]

    mm.handle_message(watcher, LIST)
    assert watcher.inbox[-1] == {"type": "lobby_list", "lobbies": []}


def test_join_opens_a_board_for_the_game():
    moves = MoveService()
    mm = Matchmaker(moves=moves, rng=ScriptedRng([0.0]))
    host = mm.connect("a")
    guest = mm.connect("b")
    mm.handle_message(host, CREATE)
    assert moves.state("1") is None

    mm.handle_message(guest, join("1"))
    state = moves.state("1")
    assert state is not None
    assert state.turn == "white"
    assert moves.submit_move("1", host.id, "e2e4").ok is True


def test_color_assignment_is_not_fixed():
    assert colors_for(ScriptedRng([0.0])) == ("white", "black")
    assert colors_for(ScriptedRng([0.5])) == ("black", "white")
    assert {colors_for(random.Random(seed))[0] for seed in range(40)} == {"white", "black"}


def test_join_checks_the_passcode():
    mm = Matchmaker()
    host = mm.connect("a")
    guest = mm.connect("b")
    mm.handle_message(host, create("Secret", "pw"))

    mm.handle_message(guest, join("1"))
    assert guest.inbox[-1]["code"] == "WRONG_PASSCODE"
    mm.handle_message(guest, join("1", "bad"))
    assert guest.inbox[-1]["code"] == "WRONG_PASSCODE"
    assert mm.games() == []

    mm.handle_message(guest, join("1", "pw"))
    assert of_type(guest, "match_started") != []
    assert mm.game_of(guest.id) is not None


def test_join_unknown_or_full_lobby_is_rejected():
    mm = Matchmaker()
    host = mm.connect("a")
    guest = mm.connect("b")
    third = mm.connect("c")

    mm.handle_message(guest, join("99"))
    assert guest.inbox[-1] == {
        "type": "error",
        "code": "LOBBY_NOT_FOUND",
        "message": "Lobby not found",
    }

    mm.handle_message(host, CREATE)
    mm.handle_message(guest, join("1"))
    mm.handle_message(third, join("1"))
    assert third.inbox[-1]["code"] == "LOBBY_FULL"
    assert mm.game_of(third.id) is None


def test_cannot_join_while_already_in_a_lobby():
    mm = Matchmaker()
    host = mm.connect("a")
    mm.handle_message(host, CREATE)
    mm.handle_message(host, join("1"))
    assert host.inbox[-1]["code"] == "ALREADY_IN_LOBBY"
    assert mm.games() == []


def test_leave_waiting_lobby_removes_it():
    mm = Matchmaker()
    host = mm.connect("a")
    other = mm.connect("b")
    mm.handle_message(host, CREATE)
    mm.handle_message(host, LEAVE)
    assert host.inbox[-1] == {"type": "lobby_left"}

    mm.handle_message(other, LIST)
    assert other.inbox[-1] == {"type": "lobby_list", "lobbies": []}


def test_leave_when_not_in_a_lobby_is_rejected():
    mm = Matchmaker()
    client = mm.connect("a")
    mm.handle_message(client, LEAVE)
    assert client.inbox == [{"type": "lobby_left"}]
    
def test_resign_without_a_game_is_rejected():
    mm = Matchmaker()
    client = mm.connect("a")
    mm.handle_message(client, '{"type":"resign"}')
    assert client.inbox == [
        {"type": "error", "code": "NOT_IN_GAME", "message": "Not in a game"}
    ]


def test_leave_during_game_releases_opponent():
    moves = MoveService()
    mm = Matchmaker(moves=moves, rng=ScriptedRng([0.0]))
    host = mm.connect("a")
    guest = mm.connect("b")
    mm.handle_message(host, CREATE)
    mm.handle_message(guest, join("1"))

    mm.handle_message(guest, LEAVE)
    assert guest.inbox[-1] == {"type": "lobby_left"}
    assert of_type(host, "opponent_disconnected") == [
        {"type": "opponent_disconnected", "gameId": "1"}
    ]
    assert mm.game_of(host.id) is None
    assert mm.game_of(guest.id) is None
    assert moves.state("1") is None


def test_disconnect_while_waiting_removes_lobby():
    mm = Matchmaker()
    host = mm.connect("a")
    other = mm.connect("b")
    mm.handle_message(host, CREATE)
    mm.disconnect(host)

    assert not host.connected
    mm.handle_message(other, LIST)
    assert other.inbox[-1] == {"type": "lobby_list", "lobbies": []}
    mm.handle_message(host, CREATE)
    assert len(host.inbox) == 1


def test_disconnect_during_game_releases_opponent():
    moves = MoveService()
    mm = Matchmaker(moves=moves, rng=ScriptedRng([0.0]))
    host = mm.connect("a")
    guest = mm.connect("b")
    mm.handle_message(host, CREATE)
    mm.handle_message(guest, join("1"))

    mm.disconnect(guest)
    assert mm.game_of(host.id) is None
    assert mm.game_of(guest.id) is None
    assert moves.state("1") is None
    assert of_type(host, "opponent_disconnected") == [
        {"type": "opponent_disconnected", "gameId": "1"}
    ]

    mm.handle_message(host, CREATE)
    assert host.inbox[-1]["lobby"]["id"] == "2"


def test_failed_create_delivery_drops_the_lobby():
    mm = Matchmaker()
    host = mm.connect("a")
    other = mm.connect("b")
    host.undeliverable.add("lobby_created")
    mm.handle_message(host, CREATE)

    assert not host.connected
    mm.handle_message(other, LIST)
    assert other.inbox[-1] == {"type": "lobby_list", "lobbies": []}


def test_failed_match_delivery_leaves_no_game():
    moves = MoveService()
    mm = Matchmaker(moves=moves, rng=ScriptedRng([0.0]))
    host = mm.connect("a")
    guest = mm.connect("b")
    mm.handle_message(host, CREATE)
    guest.undeliverable.add("match_started")
    mm.handle_message(guest, join("1"))

    assert not guest.connected
    assert host.connected
    assert mm.games() == []
    assert moves.state("1") is None
    assert [message["type"] for message in host.inbox] == [
        "lobby_created",
        "match_started",
        "opponent_disconnected",
    ]


def test_both_match_notifications_failing_leaves_no_game():
    moves = MoveService()
    mm = Matchmaker(moves=moves, rng=ScriptedRng([0.0]))
    host = mm.connect("a")
    guest = mm.connect("b")
    mm.handle_message(host, CREATE)
    host.undeliverable.add("match_started")
    guest.undeliverable.add("match_started")
    mm.handle_message(guest, join("1"))

    assert mm.games() == []
    assert moves.state("1") is None
    assert not host.connected
    assert not guest.connected


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("{", "Malformed JSON"),
        ("", "Malformed JSON"),
        ('{"type":', "Malformed JSON"),
        (b"{", "Malformed JSON"),
        ("null", "Invalid message"),
        ("[]", "Invalid message"),
        ("123", "Invalid message"),
        (None, "Invalid message"),
        (5, "Invalid message"),
        (b"\xff", "Invalid message"),
        ('{"type":"find_match"}', "Unknown message type"),
        ('{"type":"match_started","gameId":"1","color":"white"}', "Unknown message type"),
        ('{"type":""}', "Unknown message type"),
        ('{"type":"create_lobby"}', "Invalid message"),
        ('{"type":"create_lobby","name":5}', "Invalid message"),
        ('{"type":"create_lobby","name":"x","playerId":"someone-else"}', "Invalid message"),
        ('{"type":"join_lobby"}', "Invalid message"),
        ('{"type":"join_lobby","lobbyId":"1","color":"white"}', "Invalid message"),
        ('{"type":"list_lobbies","id":"a"}', "Invalid message"),
        ('{"type":"leave_lobby","gameId":"x"}', "Invalid message"),
        ('{"type":1}', "Invalid message"),
        ("{}", "Invalid message"),
    ],
)
def test_invalid_messages_are_rejected(raw, message):
    mm = Matchmaker()
    client = mm.connect("a")
    mm.handle_message(client, raw)
    assert client.inbox == [
        {"type": "error", "code": "INVALID_MESSAGE", "message": message}
    ]
    assert mm.games() == []
    mm.handle_message(client, CREATE)
    assert client.inbox[-1]["type"] == "lobby_created"


def test_oversized_message_is_rejected():
    mm = Matchmaker()
    client = mm.connect("a")
    padded = '{"type":"create_lobby","name":"x","pad":"' + ("p" * MAX_MESSAGE_BYTES) + '"}'

    mm.handle_message(client, "x" * (MAX_MESSAGE_BYTES + 1))
    mm.handle_message(client, b"y" * (MAX_MESSAGE_BYTES + 1))
    mm.handle_message(client, padded)
    assert client.inbox == [
        {
            "type": "error",
            "code": "INVALID_MESSAGE",
            "message": "Message exceeds maximum size",
        }
    ] * 3

    mm.handle_message(client, "z" * MAX_MESSAGE_BYTES)
    assert client.inbox[-1]["message"] == "Malformed JSON"
    mm.handle_message(client, CREATE)
    assert client.inbox[-1]["type"] == "lobby_created"


def test_invalid_messages_do_not_change_lobby_state():
    mm = Matchmaker()
    host = mm.connect("a")
    other = mm.connect("b")
    mm.handle_message(host, CREATE)
    mm.handle_message(host, "{")
    mm.handle_message(host, '{"type":"create_lobby","name":"x","color":"white"}')
    mm.handle_message(host, "x" * (MAX_MESSAGE_BYTES + 1))

    assert [message["type"] for message in host.inbox] == ["lobby_created", "error", "error", "error"]
    mm.handle_message(other, LIST)
    assert other.inbox[-1]["lobbies"] == [{"id": "1", "name": "Room", "locked": False}]


def test_rejections_are_logged_without_echoing_input(caplog):
    mm = Matchmaker()
    client = mm.connect("a")
    secret = "SUPERSECRETTOKEN"
    raw = json.dumps({"type": "create_lobby", "name": "x", "token": secret})
    with caplog.at_level(logging.WARNING, logger="server"):
        mm.handle_message(client, raw)

    assert secret not in caplog.text
    assert secret not in json.dumps(client.inbox)
    assert client.inbox == [
        {"type": "error", "code": "INVALID_MESSAGE", "message": "Invalid message"}
    ]
    assert "rejected message" in caplog.text
    assert mm.games() == []


def test_lobby_messages_are_rate_limited():
    clock = ManualClock()
    mm = Matchmaker(rate_limit=3, rate_window_seconds=10, clock=clock)
    client = mm.connect("a")
    other = mm.connect("b")

    for _ in range(3):
        mm.handle_message(client, LEAVE)
    assert client.inbox == [{"type": "lobby_left"}] * 3

    mm.handle_message(client, CREATE)
    assert client.inbox[-1] == {
        "type": "error",
        "code": "RATE_LIMITED",
        "message": "Too many messages",
    }
    mm.handle_message(other, LIST)
    assert other.inbox[-1] == {"type": "lobby_list", "lobbies": []}

    clock.now = 10
    mm.handle_message(client, CREATE)
    assert client.inbox[-1]["type"] == "lobby_created"


def test_concurrent_joins_seat_one_guest():
    for _ in range(15):
        mm = Matchmaker()
        host = mm.connect("host")
        mm.handle_message(host, CREATE)
        guests = [mm.connect(f"g{i}") for i in range(6)]
        run_together([lambda c=guest: mm.handle_message(c, join("1")) for guest in guests])

        assert len(mm.games()) == 1
        game = mm.games()[0]
        seated = [guest for guest in guests if of_type(guest, "match_started")]
        assert len(seated) == 1
        assert seated[0].id in (game.white_id, game.black_id)
        for guest in guests:
            if guest is not seated[0]:
                assert guest.inbox[-1]["code"] == "LOBBY_FULL"


def test_concurrent_disconnect_and_leave_close_the_game():
    for _ in range(20):
        moves = MoveService()
        mm = Matchmaker(moves=moves)
        host = mm.connect("a")
        guest = mm.connect("b")
        mm.handle_message(host, CREATE)
        mm.handle_message(guest, join("1"))
        run_together([lambda: mm.disconnect(host), lambda: mm.handle_message(guest, LEAVE)])

        assert mm.games() == []
        assert moves.state("1") is None
        assert mm.game_of(host.id) is None
        assert mm.game_of(guest.id) is None

def move(uci: str) -> str:
    return json.dumps({"type": "move", "move": uci})


def started_game() -> tuple[Matchmaker, Client, Client]:
    mm = Matchmaker(rng=ScriptedRng([0.0]))
    host = mm.connect("a")
    guest = mm.connect("b")
    mm.handle_message(host, CREATE)
    mm.handle_message(guest, join("1"))
    return mm, host, guest


def test_move_is_sent_to_both_players():
    mm, host, guest = started_game()
    mm.handle_message(host, move("e2e4"))
    for player in (host, guest):
        update = of_type(player, "move_made")[0]
        assert update["uci"] == "e2e4"
        assert update["san"] == "e4"
        assert update["turn"] == "black"
        assert update["gameOver"] is False


def test_move_out_of_turn_is_rejected_and_not_broadcast():
    mm, host, guest = started_game()
    mm.handle_message(guest, move("e7e5"))
    assert of_type(guest, "error")[0]["code"] == "NOT_YOUR_TURN"
    assert of_type(host, "move_made") == []


def test_illegal_move_is_rejected():
    mm, host, guest = started_game()
    mm.handle_message(host, move("e2e5"))
    assert of_type(host, "error")[0]["code"] == "ILLEGAL_MOVE"
    assert of_type(guest, "move_made") == []


def test_move_without_a_game_is_rejected():
    mm = Matchmaker()
    client = mm.connect("a")
    mm.handle_message(client, move("e2e4"))
    assert of_type(client, "error")[0]["code"] == "NOT_IN_GAME"

def cursor(x: float, y: float) -> str:
    return json.dumps({"type": "cursor", "x": x, "y": y})


def test_cursor_is_relayed_to_opponent_only():
    mm, host, guest = started_game()
    mm.handle_message(host, cursor(0.25, 0.75))
    assert of_type(guest, "cursor") == [{"type": "cursor", "kx": 250, "ky": 750, "seq": 1}]
    assert of_type(host, "cursor") == []


def test_cursor_without_a_game_is_dropped_silently():
    mm = Matchmaker()
    client = mm.connect("a")
    mm.handle_message(client, cursor(0.5, 0.5))
    assert client.inbox == []


def test_cursor_out_of_range_is_rejected():
    mm, host, guest = started_game()
    mm.handle_message(host, cursor(1.5, 0.5))
    assert host.inbox[-1]["code"] == "INVALID_MESSAGE"
    assert of_type(guest, "cursor") == []


def test_cursor_has_its_own_rate_limit():
    clock = ManualClock()
    mm = Matchmaker(
        rng=ScriptedRng([0.0]),
        rate_limit=3,
        rate_window_seconds=10,
        cursor_rate_limit=5,
        cursor_rate_window_seconds=1,
        clock=clock,
    )
    host = mm.connect("a")
    guest = mm.connect("b")
    mm.handle_message(host, CREATE)
    mm.handle_message(guest, join("1"))

    for _ in range(8):
        mm.handle_message(host, cursor(0.5, 0.5))
    assert len(of_type(guest, "cursor")) == 5
    assert of_type(host, "error") == []

    # cursor spam didn't eat into the normal limit
    mm.handle_message(host, move("e2e4"))
    assert of_type(host, "move_made")

    clock.now = 1
    mm.handle_message(host, cursor(0.1, 0.1))
    assert len(of_type(guest, "cursor")) == 6

def net_config(loss: float = 0, delay: float = 0, delta: bool = True) -> str:
    return json.dumps({
        "type": "net_config",
        "config": {"lossPercent": loss, "delayMs": delay, "deltaCompression": delta, "huffmanCoding": True},
    })


def game_with_net_rng(net_rng) -> tuple[Matchmaker, Client, Client]:
    mm = Matchmaker(rng=ScriptedRng([0.0]), net_rng=net_rng)
    host = mm.connect("a")
    guest = mm.connect("b")
    mm.handle_message(host, CREATE)
    mm.handle_message(guest, join("1"))
    return mm, host, guest


def test_cursor_can_be_lost_by_the_simulator():
    mm, host, guest = game_with_net_rng(ScriptedRng([0.1]))
    mm.handle_message(guest, net_config(loss=20))
    mm.handle_message(host, cursor(0.5, 0.5))
    assert of_type(guest, "cursor") == []

    mm.send_net_stats()
    stats = of_type(guest, "net_stats")[-1]["stats"]
    assert stats["packetsSent"] == 1
    assert stats["packetsDropped"] == 1


def test_delayed_cursor_goes_through_send_later():
    mm, host, guest = game_with_net_rng(ScriptedRng([0.5]))
    mm.handle_message(guest, net_config(delay=200))
    later = []
    guest.on_send_later = lambda message, delay: later.append((message, delay))

    mm.handle_message(host, cursor(0.5, 0.5))
    assert later[0][0] == {"type": "cursor", "kx": 500, "ky": 500, "seq": 1}
    assert later[0][1] == pytest.approx(0.2)
    assert of_type(guest, "cursor") == []


def test_net_config_out_of_range_is_rejected():
    mm = Matchmaker()
    client = mm.connect("a")
    mm.handle_message(client, net_config(loss=80))
    assert client.inbox[-1]["code"] == "INVALID_MESSAGE"


def test_net_stats_are_sent_outside_a_game():
    mm = Matchmaker()
    client = mm.connect("a")
    mm.send_net_stats()
    assert of_type(client, "net_stats")[0]["stats"]["packetsSent"] == 0


def test_net_reset_stats_clears_counters():
    mm, host, guest = started_game()
    mm.handle_message(host, cursor(0.5, 0.5))
    mm.handle_message(guest, '{"type":"net_reset_stats"}')
    mm.send_net_stats()
    assert of_type(guest, "net_stats")[-1]["stats"]["packetsSent"] == 0

def test_cursor_seq_counts_up_per_receiver():
    mm, host, guest = started_game()
    for _ in range(3):
        mm.handle_message(host, cursor(0.5, 0.5))
    mm.handle_message(guest, cursor(0.1, 0.1))

    assert [m["seq"] for m in of_type(guest, "cursor")] == [1, 2, 3]
    # host's stream has its own counter, so it starts at 1 too
    assert [m["seq"] for m in of_type(host, "cursor")] == [1]


def test_cursor_sends_deltas_after_first_keyframe():
    mm, host, guest = started_game()
    mm.handle_message(host, cursor(0.5, 0.5))
    mm.handle_message(host, cursor(0.51, 0.5))
    assert of_type(guest, "cursor") == [
        {"type": "cursor", "kx": 500, "ky": 500, "seq": 1},
        {"type": "cursor", "dx": 10, "dy": 0, "seq": 2},
    ]


def test_cursor_with_delta_off_sends_plain_floats():
    mm, host, guest = started_game()
    mm.handle_message(guest, net_config(delta=False))
    mm.handle_message(host, cursor(0.25, 0.75))
    assert of_type(guest, "cursor") == [{"type": "cursor", "x": 0.25, "y": 0.75, "seq": 1}]


def test_delta_shrinks_bytes_sent():
    mm, host, guest = started_game()
    for i in range(5):
        mm.handle_message(host, cursor(0.123456789 + i / 1000, 0.987654321))
    mm.send_net_stats()
    stats = of_type(guest, "net_stats")[-1]["stats"]
    assert stats["bytesSent"] < stats["bytesRaw"]
