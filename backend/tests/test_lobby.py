import pytest

from lobby import LobbyError, LobbyErrorReason, LobbyManager, LobbyStatus


@pytest.fixture
def manager() -> LobbyManager:
    return LobbyManager()


def reason_of(call) -> LobbyErrorReason:
    with pytest.raises(LobbyError) as exc:
        call()
    return exc.value.reason


def test_create_open_lobby_is_listed(manager):
    lobby = manager.create("a", "Friday blitz")
    assert not lobby.locked
    assert [l.id for l in manager.list_open()] == [lobby.id]


def test_create_with_passcode_is_locked_and_summary_hides_it(manager):
    lobby = manager.create("a", "CS 4390 lab", "secret")
    assert lobby.locked
    assert lobby.summary() == {"id": lobby.id, "name": "CS 4390 lab", "locked": True}


def test_empty_passcode_means_open(manager):
    assert not manager.create("a", "Room 214", "").locked


def test_blank_name_rejected(manager):
    assert reason_of(lambda: manager.create("a", "   ")) == LobbyErrorReason.INVALID_NAME


def test_join_open_lobby_starts_game_and_removes_from_list(manager):
    lobby = manager.create("a", "Friday blitz")
    joined = manager.join("b", lobby.id)
    assert joined.guest == "b"
    assert joined.status == LobbyStatus.IN_PROGRESS
    assert manager.list_open() == []


def test_join_wrong_passcode_rejected(manager):
    lobby = manager.create("a", "Lab", "secret")
    assert reason_of(lambda: manager.join("b", lobby.id, "nope")) == LobbyErrorReason.WRONG_PASSCODE
    assert reason_of(lambda: manager.join("b", lobby.id)) == LobbyErrorReason.WRONG_PASSCODE


def test_join_correct_passcode(manager):
    lobby = manager.create("a", "Lab", "secret")
    assert manager.join("b", lobby.id, "secret").guest == "b"


def test_join_full_lobby_rejected(manager):
    lobby = manager.create("a", "Lab")
    manager.join("b", lobby.id)
    assert reason_of(lambda: manager.join("c", lobby.id)) == LobbyErrorReason.FULL


def test_join_unknown_lobby(manager):
    assert reason_of(lambda: manager.join("a", "999")) == LobbyErrorReason.NOT_FOUND


def test_player_cannot_be_in_two_lobbies(manager):
    first = manager.create("a", "One")
    other = manager.create("b", "Two")
    assert reason_of(lambda: manager.create("a", "Three")) == LobbyErrorReason.ALREADY_IN_LOBBY
    assert reason_of(lambda: manager.join("a", other.id)) == LobbyErrorReason.ALREADY_IN_LOBBY
    assert manager.lobby_of("a") is first


def test_host_leaving_waiting_lobby_deletes_it(manager):
    lobby = manager.create("a", "Solo")
    result = manager.leave("a")
    assert result.opponent is None
    assert manager.get(lobby.id) is None
    assert manager.list_open() == []


def test_leaving_mid_game_reports_opponent_and_finishes(manager):
    lobby = manager.create("a", "Match")
    manager.join("b", lobby.id)
    result = manager.leave("b")
    assert result.opponent == "a"
    assert result.lobby.status == LobbyStatus.FINISHED
    assert manager.lobby_of("a") is None
    assert manager.lobby_of("b") is None


def test_leave_when_not_in_lobby(manager):
    assert manager.leave("ghost") is None