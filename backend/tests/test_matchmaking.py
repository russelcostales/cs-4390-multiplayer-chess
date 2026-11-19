import json
import logging
import random
import threading
from collections.abc import Callable

import pytest

from matchmaking import Client, Matchmaker
from messages import MAX_MESSAGE_BYTES


FIND = '{"type":"find_match"}'
CANCEL = '{"type":"cancel_match"}'


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
    first = mm.connect("a")
    second = mm.connect("b")
    mm.handle_message(first, FIND)
    mm.handle_message(second, FIND)
    return of_type(first, "match_found")[0]["color"], of_type(second, "match_found")[0]["color"]


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


def assert_consistent(mm: Matchmaker, clients: list[Client]) -> None:
    games = mm.games()
    seated: dict[str, object] = {}
    game_ids: set[str] = set()
    for game in games:
        assert game.white_id != game.black_id
        game_ids.add(game.id)
        for player_id in (game.white_id, game.black_id):
            assert player_id not in seated
            seated[player_id] = game
    assert len(game_ids) == len(games)

    waiting = mm.waiting_ids()
    assert len(waiting) == len(set(waiting))
    for player_id in waiting:
        assert player_id not in seated

    by_id = {client.id: client for client in clients}
    for player_id, game in seated.items():
        player = by_id[player_id]
        assert player.connected
        found = of_type(player, "match_found")
        assert len(found) == 1
        assert found[0]["gameId"] == game.id
        assert found[0]["color"] == game.color_of(player_id)
        assert found[0]["opponent"]["id"] == game.opponent_of(player_id)
        assert by_id[game.opponent_of(player_id)].connected
        assert mm.game_of(player_id) is game

    for client in clients:
        if not client.connected:
            assert client.id not in waiting
            assert mm.game_of(client.id) is None
        elif client.id in waiting:
            assert mm.game_of(client.id) is None
            assert of_type(client, "match_found") == []
        elif client.id not in seated:
            assert mm.game_of(client.id) is None


def test_two_clients_are_paired_with_opposite_colors():
    mm = Matchmaker(rng=ScriptedRng([0.0]))
    white = mm.connect("a", "Ada")
    black = mm.connect("b", "Grace")
    mm.handle_message(white, FIND)
    mm.handle_message(black, FIND.encode())

    game = mm.game_of(white.id)
    assert game is not None
    assert mm.game_of(black.id) is game
    assert game.white_id == white.id
    assert game.black_id == black.id
    assert game.white_id != game.black_id
    assert mm.waiting_ids() == []
    assert [message["type"] for message in white.inbox] == ["searching", "match_found"]
    assert [message["type"] for message in black.inbox] == ["match_found"]
    assert of_type(white, "match_found") == [
        {
            "type": "match_found",
            "gameId": game.id,
            "color": "white",
            "opponent": {"id": "b", "name": "Grace"},
        }
    ]
    assert of_type(black, "match_found") == [
        {
            "type": "match_found",
            "gameId": game.id,
            "color": "black",
            "opponent": {"id": "a", "name": "Ada"},
        }
    ]


def test_color_assignment_is_not_fixed():
    assert colors_for(ScriptedRng([0.0])) == ("white", "black")
    assert colors_for(ScriptedRng([0.5])) == ("black", "white")
    assert {colors_for(random.Random(seed))[0] for seed in range(40)} == {"white", "black"}


def test_odd_client_waits_for_the_next_player():
    mm = Matchmaker(rng=ScriptedRng([0.0, 0.0]))
    first = mm.connect("a")
    second = mm.connect("b")
    third = mm.connect("c")
    fourth = mm.connect("d")

    mm.handle_message(first, FIND)
    assert mm.games() == []
    assert mm.waiting_ids() == [first.id]

    mm.handle_message(second, FIND)
    assert mm.waiting_ids() == []
    assert mm.game_of(first.id) is mm.game_of(second.id)
    assert {of_type(first, "match_found")[0]["color"], of_type(second, "match_found")[0]["color"]} == {
        "white",
        "black",
    }

    mm.handle_message(third, FIND)
    assert mm.waiting_ids() == [third.id]
    assert of_type(third, "match_found") == []
    assert mm.game_of(third.id) is None

    mm.handle_message(fourth, FIND)
    assert mm.waiting_ids() == []
    game = mm.game_of(third.id)
    assert game is not None
    assert mm.game_of(fourth.id) is game
    assert first.id not in (game.white_id, game.black_id)
    assert of_type(third, "match_found")[0]["opponent"] == {"id": "d", "name": "d"}
    assert of_type(third, "match_found")[0]["gameId"] != of_type(first, "match_found")[0]["gameId"]


def test_duplicate_join_is_rejected():
    mm = Matchmaker(rng=ScriptedRng([0.0]))
    client = mm.connect("a")
    other = mm.connect("b")
    mm.handle_message(client, FIND)
    mm.handle_message(client, FIND)

    assert mm.waiting_ids() == [client.id]
    assert client.inbox[-1] == {
        "type": "error",
        "code": "ALREADY_QUEUED",
        "message": "Already queued for a match",
    }

    mm.handle_message(other, FIND)
    assert len(of_type(client, "match_found")) == 1
    assert mm.game_of(client.id) is mm.game_of(other.id)
    assert mm.waiting_ids() == []


def test_cancel_removes_client_from_queue():
    mm = Matchmaker()
    client = mm.connect("a")
    other = mm.connect("b")
    mm.handle_message(client, FIND)
    mm.handle_message(client, CANCEL)

    assert mm.waiting_ids() == []
    assert of_type(client, "match_cancelled") == [{"type": "match_cancelled"}]

    mm.handle_message(other, FIND)
    assert mm.waiting_ids() == [other.id]
    assert mm.games() == []
    assert of_type(other, "match_found") == []


def test_cancel_when_not_queued_is_rejected():
    mm = Matchmaker()
    client = mm.connect("a")
    mm.handle_message(client, CANCEL)
    assert client.inbox == [
        {
            "type": "error",
            "code": "NOT_QUEUED",
            "message": "Not queued for a match",
        }
    ]
    assert mm.waiting_ids() == []


def test_cannot_queue_while_in_a_game():
    mm = Matchmaker(rng=ScriptedRng([0.0]))
    client = mm.connect("a")
    other = mm.connect("b")
    mm.handle_message(client, FIND)
    mm.handle_message(other, FIND)
    game = mm.game_of(client.id)

    mm.handle_message(client, FIND)
    assert client.inbox[-1] == {
        "type": "error",
        "code": "ALREADY_IN_GAME",
        "message": "Already in a game",
    }
    assert mm.game_of(client.id) is game
    assert mm.waiting_ids() == []

    mm.handle_message(client, CANCEL)
    assert client.inbox[-1]["code"] == "NOT_QUEUED"
    assert mm.game_of(client.id) is game


def test_disconnect_while_queued_removes_client():
    mm = Matchmaker()
    client = mm.connect("a")
    other = mm.connect("b")
    mm.handle_message(client, FIND)
    mm.disconnect(client)

    assert not client.connected
    assert mm.waiting_ids() == []
    mm.handle_message(client, FIND)
    mm.handle_message(other, FIND)
    assert mm.waiting_ids() == [other.id]
    assert mm.games() == []


def test_disconnect_during_game_releases_opponent():
    mm = Matchmaker(rng=ScriptedRng([0.0]))
    client = mm.connect("a")
    other = mm.connect("b")
    mm.handle_message(client, FIND)
    mm.handle_message(other, FIND)
    game_id = mm.game_of(client.id).id

    mm.disconnect(other)
    assert mm.game_of(client.id) is None
    assert mm.game_of(other.id) is None
    assert of_type(client, "opponent_disconnected") == [
        {"type": "opponent_disconnected", "gameId": game_id}
    ]

    mm.handle_message(client, FIND)
    assert mm.waiting_ids() == [client.id]
    assert mm.games() == []


def test_failed_delivery_requeues_partner_at_front():
    mm = Matchmaker(rng=ScriptedRng([0.0, 0.0]))
    survivor = mm.connect("a", "Ada")
    dropped = mm.connect("b", "Grace")
    nxt = mm.connect("c", "Lin")
    mm.handle_message(survivor, FIND)
    dropped.undeliverable.add("match_found")
    mm.handle_message(dropped, FIND)

    assert mm.games() == []
    assert mm.waiting_ids() == [survivor.id]
    assert not dropped.connected
    assert of_type(dropped, "match_found") == []
    assert dropped.id not in mm.waiting_ids()
    stale_game_id = of_type(survivor, "match_found")[0]["gameId"]
    assert of_type(survivor, "requeued") == [
        {"type": "requeued", "reason": "opponent_unavailable"}
    ]

    mm.handle_message(nxt, FIND)
    game = mm.game_of(survivor.id)
    assert game is not None
    assert mm.game_of(nxt.id) is game
    assert dropped.id not in (game.white_id, game.black_id)
    assert game.id != stale_game_id
    assert of_type(nxt, "match_found")[0]["opponent"]["id"] == survivor.id
    assert mm.waiting_ids() == []


def test_survivor_is_requeued_when_the_earlier_send_fails():
    mm = Matchmaker(rng=ScriptedRng([0.0, 0.0]))
    dropped = mm.connect("a")
    survivor = mm.connect("b")
    nxt = mm.connect("c")
    mm.handle_message(dropped, FIND)
    dropped.undeliverable.add("match_found")
    mm.handle_message(survivor, FIND)

    assert mm.waiting_ids() == [survivor.id]
    assert not dropped.connected
    assert mm.games() == []
    assert of_type(survivor, "requeued") == [
        {"type": "requeued", "reason": "opponent_unavailable"}
    ]

    mm.handle_message(nxt, FIND)
    game = mm.game_of(survivor.id)
    assert game is not None
    assert nxt.id in (game.white_id, game.black_id)
    assert dropped.id not in (game.white_id, game.black_id)


def test_both_notifications_failing_leaves_no_game():
    mm = Matchmaker(rng=ScriptedRng([0.0]))
    first = mm.connect("a")
    second = mm.connect("b")
    mm.handle_message(first, FIND)
    first.undeliverable.add("match_found")
    second.undeliverable.add("match_found")
    mm.handle_message(second, FIND)

    assert first.inbox == [{"type": "searching"}]
    assert second.inbox == []
    assert mm.waiting_ids() == []
    assert mm.games() == []
    assert not first.connected
    assert not second.connected


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
        ('{"type":"resign"}', "Unknown message type"),
        ('{"type":"match_found","gameId":"1","color":"white"}', "Unknown message type"),
        ('{"type":""}', "Unknown message type"),
        ('{"type":"find_match","color":"white"}', "Invalid message"),
        ('{"type":"find_match","gameId":"x"}', "Invalid message"),
        ('{"type":"find_match","playerId":"someone-else"}', "Invalid message"),
        ('{"type":"cancel_match","id":"a"}', "Invalid message"),
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
    assert mm.waiting_ids() == []
    assert mm.games() == []
    mm.handle_message(client, FIND)
    assert mm.waiting_ids() == [client.id]
    assert mm.games() == []


def test_oversized_message_is_rejected():
    mm = Matchmaker()
    client = mm.connect("a")
    padded = '{"type":"find_match","color":"white","pad":"' + ("p" * MAX_MESSAGE_BYTES) + '"}'

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
    assert mm.waiting_ids() == []
    mm.handle_message(client, FIND)
    assert mm.waiting_ids() == [client.id]


def test_invalid_messages_do_not_change_queue_state():
    mm = Matchmaker()
    client = mm.connect("a")
    mm.handle_message(client, FIND)
    mm.handle_message(client, "{")
    mm.handle_message(client, '{"type":"find_match","color":"white"}')
    mm.handle_message(client, "x" * (MAX_MESSAGE_BYTES + 1))

    assert mm.waiting_ids() == [client.id]
    assert mm.games() == []
    assert [message["type"] for message in client.inbox] == ["searching", "error", "error", "error"]


def test_rejections_are_logged_without_echoing_input(caplog):
    mm = Matchmaker()
    client = mm.connect("a")
    secret = "SUPERSECRETTOKEN"
    raw = json.dumps({"type": "find_match", "token": secret, "color": "white"})
    with caplog.at_level(logging.WARNING, logger="matchmaking"):
        mm.handle_message(client, raw)

    assert secret not in caplog.text
    assert secret not in json.dumps(client.inbox)
    assert client.inbox == [
        {"type": "error", "code": "INVALID_MESSAGE", "message": "Invalid message"}
    ]
    assert "rejected message" in caplog.text
    assert mm.waiting_ids() == []


def test_matchmaking_messages_are_rate_limited():
    clock = ManualClock()
    mm = Matchmaker(rate_limit=3, rate_window_seconds=10, clock=clock, rng=ScriptedRng([0.0]))
    client = mm.connect("a")
    other = mm.connect("b")

    for _ in range(3):
        mm.handle_message(client, CANCEL)
    assert [message["code"] for message in client.inbox] == ["NOT_QUEUED"] * 3

    mm.handle_message(client, FIND)
    assert mm.waiting_ids() == []
    assert client.inbox[-1] == {
        "type": "error",
        "code": "RATE_LIMITED",
        "message": "Too many messages",
    }

    mm.handle_message(other, FIND)
    assert mm.waiting_ids() == [other.id]

    clock.now = 10
    mm.handle_message(client, FIND)
    assert mm.waiting_ids() == []
    game = mm.game_of(client.id)
    assert game is not None
    assert mm.game_of(other.id) is game
    assert {of_type(client, "match_found")[0]["color"], of_type(other, "match_found")[0]["color"]} == {
        "white",
        "black",
    }


@pytest.mark.parametrize("population", [7, 8])
def test_concurrent_joins_do_not_double_pair(population):
    for _ in range(15):
        mm = Matchmaker()
        clients = [mm.connect(f"p{i}", f"Player {i}") for i in range(population)]
        run_together([lambda c=client: mm.handle_message(c, FIND) for client in clients])

        assert_consistent(mm, clients)
        games = mm.games()
        assert len(games) == population // 2
        assert len(mm.waiting_ids()) == population % 2
        seated = {player_id for game in games for player_id in (game.white_id, game.black_id)}
        assert len(seated) == population // 2 * 2
        for client in clients:
            if client.id in seated:
                assert len(of_type(client, "match_found")) == 1
            else:
                assert of_type(client, "match_found") == []
                assert mm.waiting_ids() == [client.id]


def test_concurrent_disconnect_does_not_double_book():
    for _ in range(20):
        mm = Matchmaker()
        clients = [mm.connect(str(i)) for i in range(6)]
        calls = []
        for client in clients:
            calls.append(lambda c=client: mm.handle_message(c, FIND))
            calls.append(lambda c=client: mm.disconnect(c))
        run_together(calls)
        assert_consistent(mm, clients)
