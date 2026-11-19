"""FIFO matchmaking.

Identity comes from the server-side Client, never from the message body.
Queue changes and match notification share one lock so a player is paired at most once.
"""

import logging
import random
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from itertools import count
from typing import Protocol

from messages import (
    MAX_MESSAGE_BYTES,
    CancelMatchMessage,
    ClientMessage,
    ErrorCode,
    FindMatchMessage,
    MessageRejected,
    error_payload,
    parse_client_message,
)


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

    def send(self, message: dict) -> None:
        """Deliver one message. Must not call back into the Matchmaker."""
        if not self.connected or message.get("type") in self.undeliverable:
            raise DeliveryError(self.id)
        self.inbox.append(message)


class Color(str, Enum):
    WHITE = "white"
    BLACK = "black"


@dataclass(frozen=True)
class Game:
    id: str
    white_id: str
    black_id: str

    def __post_init__(self) -> None:
        if self.white_id == self.black_id:
            raise ValueError("a player cannot be paired with themselves")

    def color_of(self, player_id: str) -> str:
        if player_id == self.white_id:
            return Color.WHITE.value
        if player_id == self.black_id:
            return Color.BLACK.value
        raise KeyError(player_id)

    def opponent_of(self, player_id: str) -> str:
        if player_id == self.white_id:
            return self.black_id
        if player_id == self.black_id:
            return self.white_id
        raise KeyError(player_id)


class Matchmaker:
    def __init__(
        self,
        *,
        rng: RandomSource | None = None,
        max_message_bytes: int = MAX_MESSAGE_BYTES,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        rate_window_seconds: float = DEFAULT_RATE_WINDOW_SECONDS,
        clock: Callable[[], float] | None = None,
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
        self._ids = count(1)
        self._queue: deque[str] = deque()
        self._waiting: set[str] = set()
        self._games: dict[str, Game] = {}
        self._player_game: dict[str, str] = {}
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
                self._remove_waiting(client_id)
                self._hits.pop(client_id, None)
                self._release_game(existing)
            client = Client(client_id, _display_name(client_id, display_name))
            self._clients[client_id] = client
            return client

    def disconnect(self, client: Client) -> None:
        with self._lock:
            client.connected = False
            if self._clients.get(client.id) is not client:
                return
            self._remove_waiting(client.id)
            self._hits.pop(client.id, None)
            self._release_game(client)

    def handle_message(self, client: Client, raw: object) -> None:
        """Validate one payload, then run the matchmaking handler.

        ``client`` is the server-side connection. Fields in ``raw`` cannot set
        identity, color, or game id.
        """
        with self._lock:
            current = self._clients.get(client.id)
            if current is not client or not client.connected:
                logger.warning("message from inactive connection client=%s", client.id)
                return
            self._handle_locked(client, raw)

    def waiting_ids(self) -> list[str]:
        with self._lock:
            return list(self._queue)

    def game_of(self, client_id: str) -> Game | None:
        with self._lock:
            game_id = self._player_game.get(client_id)
            if game_id is None:
                return None
            return self._games.get(game_id)

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
        if isinstance(message, FindMatchMessage):
            self._find_match(client)
        elif isinstance(message, CancelMatchMessage):
            self._cancel(client)
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

    def _find_match(self, client: Client) -> None:
        if client.id in self._player_game:
            raise MessageRejected(ErrorCode.ALREADY_IN_GAME, "Already in a game")
        if client.id in self._waiting:
            raise MessageRejected(ErrorCode.ALREADY_QUEUED, "Already queued for a match")

        self._enqueue(client.id)
        requeued = self._drain()
        if client.id not in self._waiting or client.id in requeued:
            return
        try:
            client.send({"type": "searching"})
        except DeliveryError:
            self._remove_waiting(client.id)
            client.connected = False
            logger.warning("searching delivery failed client=%s", client.id)

    def _cancel(self, client: Client) -> None:
        if client.id not in self._waiting:
            raise MessageRejected(ErrorCode.NOT_QUEUED, "Not queued for a match")
        self._remove_waiting(client.id)
        try:
            client.send({"type": "match_cancelled"})
        except DeliveryError:
            client.connected = False

    def _drain(self) -> set[str]:
        requeued: set[str] = set()
        while len(self._queue) >= 2:
            requeued.update(self._attempt_pair())
        return requeued

    def _attempt_pair(self) -> set[str]:
        # Called with the matchmaker lock held. Notification finishes before
        # the lock is released, so a second join cannot pair either player again.
        earlier = self._pop_waiting()
        later = self._pop_waiting()
        ready = self._ready(earlier, later)
        if len(ready) < 2:
            return self._requeue_front_in_order(ready)
        if ready[0] == ready[1]:
            logger.error("skipped self-pair client=%s", ready[0])
            return self._requeue_front_in_order([ready[0]])

        white_id, black_id = self._assign_colors(ready[0], ready[1])
        try:
            game = Game(id=str(next(self._ids)), white_id=white_id, black_id=black_id)
        except ValueError:
            logger.error("skipped self-pair client=%s", ready[0])
            return self._requeue_front_in_order(ready)

        self._games[game.id] = game
        self._player_game[white_id] = game.id
        self._player_game[black_id] = game.id

        notified: list[str] = []
        failed = False
        for player_id in ready:
            player = self._clients[player_id]
            try:
                player.send(self._match_found_message(game, player_id))
            except DeliveryError:
                failed = True
                player.connected = False
                logger.warning("match delivery failed client=%s game=%s", player_id, game.id)
            else:
                notified.append(player_id)

        if not failed:
            return set()

        self._rollback(game)
        return self._requeue_front_in_order(notified)

    def _ready(self, first: str, second: str) -> list[str]:
        ready: list[str] = []
        for player_id in (first, second):
            if player_id in ready:
                continue
            player = self._clients.get(player_id)
            if player is None or not player.connected:
                continue
            if player_id in self._player_game:
                continue
            ready.append(player_id)
        return ready

    def _assign_colors(self, earlier: str, later: str) -> tuple[str, str]:
        if self._rng.random() < 0.5:
            return earlier, later
        return later, earlier

    def _match_found_message(self, game: Game, player_id: str) -> dict:
        opponent = self._clients[game.opponent_of(player_id)]
        return {
            "type": "match_found",
            "gameId": game.id,
            "color": game.color_of(player_id),
            "opponent": {"id": opponent.id, "name": opponent.display_name},
        }

    def _requeue_front_in_order(self, client_ids: list[str]) -> set[str]:
        requeued: set[str] = set()
        for client_id in reversed(client_ids):
            if self._requeue_front(client_id):
                requeued.add(client_id)
        return requeued

    def _requeue_front(self, client_id: str) -> bool:
        player = self._clients.get(client_id)
        if player is None or not player.connected:
            return False
        if client_id in self._player_game or client_id in self._waiting:
            return False
        self._queue.appendleft(client_id)
        self._waiting.add(client_id)
        try:
            player.send({"type": "requeued", "reason": "opponent_unavailable"})
        except DeliveryError:
            self._remove_waiting(client_id)
            player.connected = False
            logger.warning("requeue delivery failed client=%s", client_id)
            return False
        return True

    def _release_game(self, client: Client) -> None:
        game_id = self._player_game.get(client.id)
        if game_id is None:
            return
        game = self._games.get(game_id)
        if game is None:
            self._player_game.pop(client.id, None)
            return
        opponent_id = game.opponent_of(client.id)
        self._rollback(game)
        opponent = self._clients.get(opponent_id)
        if opponent is None or not opponent.connected:
            return
        try:
            opponent.send({"type": "opponent_disconnected", "gameId": game.id})
        except DeliveryError:
            opponent.connected = False
            self._remove_waiting(opponent.id)

    def _rollback(self, game: Game) -> None:
        self._games.pop(game.id, None)
        if self._player_game.get(game.white_id) == game.id:
            self._player_game.pop(game.white_id, None)
        if self._player_game.get(game.black_id) == game.id:
            self._player_game.pop(game.black_id, None)

    def _enqueue(self, client_id: str) -> None:
        if client_id in self._waiting:
            return
        self._queue.append(client_id)
        self._waiting.add(client_id)

    def _pop_waiting(self) -> str:
        client_id = self._queue.popleft()
        self._waiting.discard(client_id)
        return client_id

    def _remove_waiting(self, client_id: str) -> None:
        if client_id not in self._waiting:
            return
        self._waiting.remove(client_id)
        try:
            self._queue.remove(client_id)
        except ValueError:
            return

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
