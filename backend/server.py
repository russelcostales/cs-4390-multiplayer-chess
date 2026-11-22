"""Lobby message handling.

Identity comes from the server-side Client, never from the message body.
State changes and notifications share one lock so a player is seated at most once.
"""

import logging
import random
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Protocol

from lobby import Game, LobbyError, LobbyManager
from messages import (
    MAX_MESSAGE_BYTES,
    ClientMessage,
    CreateLobbyMessage,
    ErrorCode,
    JoinLobbyMessage,
    LeaveLobbyMessage,
    ListLobbiesMessage,
    MessageRejected,
    MoveMessage,
    error_payload,
    parse_client_message,
)

from moves import MoveResult, MoveService

logger = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT = 10
DEFAULT_RATE_WINDOW_SECONDS = 10.0


class RandomSource(Protocol):
    def random(self) -> float: ...


class DeliveryError(Exception):
    def __init__(self, client_id: str) -> None:
        super().__init__(client_id)
        self.client_id = client_id


class Client:
    """A connected player. The server creates this; message bodies cannot."""

    def __init__(self, client_id: str, display_name: str) -> None:
        self.id = client_id
        self.display_name = display_name
        self.connected = True
        self.inbox: list[dict] = []
        # Message types whose send raises. Production leaves this empty so a
        # test can simulate a socket that dies while a notification is written.
        self.undeliverable: set[str] = set()
        self.on_send: Callable[[dict], None] | None = None

    def send(self, message: dict) -> None:
        """Deliver one message. Must not call back into the Matchmaker."""
        if not self.connected or message.get("type") in self.undeliverable:
            raise DeliveryError(self.id)
        if self.on_send is not None:
            self.on_send(message)
        else:
            self.inbox.append(message)


class Matchmaker:
    def __init__(
        self,
        *,
        rng: RandomSource | None = None,
        max_message_bytes: int = MAX_MESSAGE_BYTES,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        rate_window_seconds: float = DEFAULT_RATE_WINDOW_SECONDS,
        clock: Callable[[], float] | None = None,
        moves: MoveService | None = None,
    ) -> None:
        if max_message_bytes < 1:
            raise ValueError("max_message_bytes must be positive")
        if rate_limit < 1:
            raise ValueError("rate_limit must be positive")
        if rate_window_seconds <= 0:
            raise ValueError("rate_window_seconds must be positive")

        self._rng = rng if rng is not None else random.Random()
        self._max_message_bytes = max_message_bytes
        self._rate_limit = rate_limit
        self._rate_window = rate_window_seconds
        self._clock = clock if clock is not None else time.monotonic
        self._lock = threading.Lock()
        self._lobbies = LobbyManager()
        self._moves = moves if moves is not None else MoveService()
        self._games: dict[str, Game] = {}
        self._clients: dict[str, Client] = {}
        self._hits: dict[str, deque[float]] = {}

    def connect(self, client_id: str, display_name: str | None = None) -> Client:
        if not isinstance(client_id, str) or client_id == "":
            raise ValueError("client id is required")
        with self._lock:
            existing = self._clients.get(client_id)
            if existing is not None:
                if existing.connected:
                    raise ValueError(f"client already connected: {client_id}")
                self._hits.pop(client_id, None)
                self._leave(client_id)
            client = Client(client_id, _display_name(client_id, display_name))
            self._clients[client_id] = client
            return client

    def disconnect(self, client: Client) -> None:
        with self._lock:
            client.connected = False
            if self._clients.get(client.id) is not client:
                return
            self._hits.pop(client.id, None)
            self._leave(client.id)

    def handle_message(self, client: Client, raw: object) -> None:
        """Validate one payload, then run the lobby handler.

        ``client`` is the server-side connection. Fields in ``raw`` cannot set
        identity, color, or game id.
        """
        with self._lock:
            current = self._clients.get(client.id)
            if current is not client or not client.connected:
                logger.warning("message from inactive connection client=%s", client.id)
                return
            self._handle_locked(client, raw)

    def game_of(self, client_id: str) -> Game | None:
        with self._lock:
            lobby = self._lobbies.lobby_of(client_id)
            return self._games.get(lobby.id) if lobby else None

    def games(self) -> list[Game]:
        with self._lock:
            return list(self._games.values())

    def _handle_locked(self, client: Client, raw: object) -> None:
        if not self._consume_rate(client.id):
            self._reject(client, ErrorCode.RATE_LIMITED, "Too many messages")
            return
        try:
            message = parse_client_message(raw, max_bytes=self._max_message_bytes)
            self._dispatch(client, message)
        except MessageRejected as rejected:
            self._reject(client, rejected.code, rejected.public_message)

    def _dispatch(self, client: Client, message: ClientMessage) -> None:
        if isinstance(message, CreateLobbyMessage):
            self._create_lobby(client, message)
        elif isinstance(message, ListLobbiesMessage):
            self._list_lobbies(client)
        elif isinstance(message, JoinLobbyMessage):
            self._join_lobby(client, message)
        elif isinstance(message, LeaveLobbyMessage):
            self._leave_lobby(client)
        elif isinstance(message, MoveMessage):
            self._move(client, message)
        else:
            raise MessageRejected(ErrorCode.INVALID_MESSAGE, "Unknown message type")

    def _reject(self, client: Client, code: ErrorCode, message: str) -> None:
        logger.warning(
            "rejected message client=%s code=%s message=%s",
            client.id,
            code.value,
            message,
        )
        try:
            client.send(error_payload(code, message))
        except DeliveryError:
            logger.warning("undeliverable error client=%s code=%s", client.id, code.value)

    def _create_lobby(self, client: Client, message: CreateLobbyMessage) -> None:
        try:
            lobby = self._lobbies.create(client.id, message.name, message.passcode)
        except LobbyError as error:
            raise _lobby_rejection(error) from error
        self._send_or_drop(client, {"type": "lobby_created", "lobby": lobby.summary()})

    def _list_lobbies(self, client: Client) -> None:
        lobbies = [lobby.summary() for lobby in self._lobbies.list_open()]
        self._send_or_drop(client, {"type": "lobby_list", "lobbies": lobbies})

    def _join_lobby(self, client: Client, message: JoinLobbyMessage) -> None:
        try:
            lobby = self._lobbies.join(client.id, message.lobbyId, message.passcode)
        except LobbyError as error:
            raise _lobby_rejection(error) from error

        white_id, black_id = self._assign_colors(lobby.host, client.id)
        game = Game(id=lobby.id, white_id=white_id, black_id=black_id)
        self._games[game.id] = game
        self._moves.open_game(game)

        failed: list[str] = []
        for player_id in (lobby.host, client.id):
            player = self._clients[player_id]
            try:
                player.send(self._match_started_message(game, player_id))
            except DeliveryError:
                player.connected = False
                failed.append(player_id)
                logger.warning("match delivery failed client=%s game=%s", player_id, game.id)
        for player_id in failed:
            self._leave(player_id)

    def _leave_lobby(self, client: Client) -> None:
        if self._lobbies.lobby_of(client.id) is None:
            raise MessageRejected(ErrorCode.NOT_IN_LOBBY, "Not in a lobby")
        self._leave(client.id)
        self._send_or_drop(client, {"type": "lobby_left"})

    def _move(self, client: Client, message: MoveMessage) -> None:
        lobby = self._lobbies.lobby_of(client.id)
        game = self._games.get(lobby.id) if lobby else None
        if game is None:
            raise MessageRejected(ErrorCode.NOT_IN_GAME, "Not in a game")
        result = self._moves.submit_move(game.id, client.id, message.move)
        if not result.ok:
            raise MessageRejected(ErrorCode(result.code), result.message)
        update = _move_message(game.id, result)
        for player_id in (game.white_id, game.black_id):
            if game.id not in self._games:
                break
            self._send_or_drop(self._clients[player_id], update)

    def _leave(self, client_id: str) -> None:
        result = self._lobbies.leave(client_id)
        if result is None:
            return
        game = self._games.pop(result.lobby.id, None)
        if game is None:
            return
        self._moves.close_game(game.id)
        opponent = self._clients.get(result.opponent) if result.opponent else None
        if opponent is None or not opponent.connected:
            return
        try:
            opponent.send({"type": "opponent_disconnected", "gameId": game.id})
        except DeliveryError:
            opponent.connected = False

    def _send_or_drop(self, client: Client, message: dict) -> None:
        try:
            client.send(message)
        except DeliveryError:
            client.connected = False
            self._leave(client.id)
            logger.warning("delivery failed client=%s type=%s", client.id, message["type"])

    def _assign_colors(self, host: str, guest: str) -> tuple[str, str]:
        if self._rng.random() < 0.5:
            return host, guest
        return guest, host

    def _match_started_message(self, game: Game, player_id: str) -> dict:
        opponent = self._clients[game.opponent_of(player_id)]
        return {
            "type": "match_started",
            "gameId": game.id,
            "color": game.color_of(player_id),
            "opponent": {"id": opponent.id, "name": opponent.display_name},
        }

    def _consume_rate(self, client_id: str) -> bool:
        now = self._clock()
        hits = self._hits.setdefault(client_id, deque())
        while hits and now - hits[0] >= self._rate_window:
            hits.popleft()
        if len(hits) >= self._rate_limit:
            return False
        hits.append(now)
        return True


def _display_name(client_id: str, display_name: str | None) -> str:
    if display_name is None:
        return client_id
    cleaned = display_name.strip()
    if not cleaned:
        return client_id
    return cleaned[:64]


def _lobby_rejection(error: LobbyError) -> MessageRejected:
    code = ErrorCode(error.reason.value.upper())
    text = error.reason.value.replace("_", " ").capitalize()
    return MessageRejected(code, text)

def _move_message(game_id: str, result: MoveResult) -> dict:
    return {
        "type": "move_made",
        "gameId": game_id,
        "uci": result.uci,
        "san": result.san,
        "fen": result.fen,
        "turn": result.turn,
        "isCheck": result.is_check,
        "gameOver": result.game_over,
        "result": result.result,
        "winner": result.winner,
        "termination": result.termination,
    }