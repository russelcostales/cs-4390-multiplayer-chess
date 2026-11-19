from dataclasses import dataclass
from enum import Enum
from itertools import count


class LobbyStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


class LobbyErrorReason(str, Enum):
    NOT_FOUND = "lobby_not_found"
    FULL = "lobby_full"
    WRONG_PASSCODE = "wrong_passcode"
    ALREADY_IN_LOBBY = "already_in_lobby"
    INVALID_NAME = "invalid_name"


class LobbyError(Exception):
    def __init__(self, reason: LobbyErrorReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass
class Lobby:
    id: str
    name: str
    host: str
    passcode: str | None = None
    guest: str | None = None
    status: LobbyStatus = LobbyStatus.WAITING

    @property
    def locked(self) -> bool:
        return self.passcode is not None

    @property
    def is_full(self) -> bool:
        return self.guest is not None

    # passcode is never included
    def summary(self) -> dict:
        return {"id": self.id, "name": self.name, "locked": self.locked}


@dataclass
class LeaveResult:
    lobby: Lobby
    opponent: str | None


class LobbyManager:
    def __init__(self) -> None:
        self._lobbies: dict[str, Lobby] = {}
        self._player_lobby: dict[str, str] = {}
        self._ids = count(1)

    def create(self, host: str, name: str, passcode: str | None = None) -> Lobby:
        if host in self._player_lobby:
            raise LobbyError(LobbyErrorReason.ALREADY_IN_LOBBY)
        name = name.strip()
        if not name:
            raise LobbyError(LobbyErrorReason.INVALID_NAME)

        lobby = Lobby(
            id=str(next(self._ids)),
            name=name,
            host=host,
            passcode=passcode or None,
        )
        self._lobbies[lobby.id] = lobby
        self._player_lobby[host] = lobby.id
        return lobby

    def get(self, lobby_id: str) -> Lobby | None:
        return self._lobbies.get(lobby_id)

    def lobby_of(self, player: str) -> Lobby | None:
        lobby_id = self._player_lobby.get(player)
        return self._lobbies.get(lobby_id) if lobby_id else None

    def list_open(self) -> list[Lobby]:
        return [
            lobby
            for lobby in self._lobbies.values()
            if lobby.status == LobbyStatus.WAITING and not lobby.is_full
        ]

    def join(self, player: str, lobby_id: str, passcode: str | None = None) -> Lobby:
        if player in self._player_lobby:
            raise LobbyError(LobbyErrorReason.ALREADY_IN_LOBBY)

        lobby = self._lobbies.get(lobby_id)
        if lobby is None:
            raise LobbyError(LobbyErrorReason.NOT_FOUND)
        if lobby.is_full or lobby.status != LobbyStatus.WAITING:
            raise LobbyError(LobbyErrorReason.FULL)
        if lobby.locked and lobby.passcode != passcode:
            raise LobbyError(LobbyErrorReason.WRONG_PASSCODE)

        lobby.guest = player
        lobby.status = LobbyStatus.IN_PROGRESS
        self._player_lobby[player] = lobby.id
        return lobby

    # also used for disconnects: the caller notifies result.opponent
    def leave(self, player: str) -> LeaveResult | None:
        lobby = self.lobby_of(player)
        if lobby is None:
            return None

        opponent = lobby.guest if player == lobby.host else lobby.host
        if lobby.status == LobbyStatus.IN_PROGRESS:
            lobby.status = LobbyStatus.FINISHED

        del self._lobbies[lobby.id]
        self._player_lobby.pop(lobby.host, None)
        if lobby.guest:
            self._player_lobby.pop(lobby.guest, None)
            
        return LeaveResult(lobby=lobby, opponent=opponent)