"""Validate and apply moves for a matchmaking game.

The transport layer calls open_game with the Game from matchmaking, then
submit_move. Boards live in memory, one per game id. Each UCI move is stored
so the position can be rebuilt. A per-game lock makes two submissions for the
same game apply one at a time.
"""

import logging
import threading
from dataclasses import dataclass
from enum import Enum

import chess

from lobby import Color, Game


logger = logging.getLogger(__name__)

# UCI is 4 characters, or 5 when a pawn promotes ("e7e8q").
MAX_MOVE_LENGTH = 5

_PROMOTIONS = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)

_TERMINATION = {
    chess.Termination.CHECKMATE: "checkmate",
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
    chess.Termination.SEVENTYFIVE_MOVES: "seventyfive_moves",
    chess.Termination.FIVEFOLD_REPETITION: "fivefold_repetition",
}


class MoveError(str, Enum):
    INVALID_FORMAT = "INVALID_FORMAT"
    GAME_NOT_FOUND = "GAME_NOT_FOUND"
    GAME_OVER = "GAME_OVER"
    NOT_IN_GAME = "NOT_IN_GAME"
    NOT_YOUR_TURN = "NOT_YOUR_TURN"
    ILLEGAL_MOVE = "ILLEGAL_MOVE"
    PROMOTION_REQUIRED = "PROMOTION_REQUIRED"


@dataclass(frozen=True)
class MoveResult:
    ok: bool
    code: str | None = None
    message: str | None = None
    uci: str | None = None
    san: str | None = None
    fen: str | None = None
    turn: str | None = None
    is_check: bool | None = None
    game_over: bool = False
    result: str | None = None
    winner: str | None = None
    winner_id: str | None = None
    termination: str | None = None


@dataclass(frozen=True)
class GameState:
    game_id: str
    fen: str
    turn: str
    legal_moves: tuple[str, ...]
    moves: tuple[str, ...]
    game_over: bool
    result: str | None
    winner: str | None
    winner_id: str | None
    termination: str | None


class _Session:
    def __init__(self, game: Game) -> None:
        self.game = game
        self.board = chess.Board()
        self.moves: list[str] = []
        self.lock = threading.Lock()


class MoveService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, _Session] = {}

    def open_game(self, game: Game) -> None:
        """Start a standard board for a matchmaking game.

        Opening the same game again is ignored. Reusing the id for a different
        pairing raises ValueError.
        """
        if not isinstance(game, Game):
            raise TypeError("game must be a matchmaking Game")
        with self._lock:
            existing = self._sessions.get(game.id)
            if existing is not None:
                same = (
                    existing.game.white_id == game.white_id
                    and existing.game.black_id == game.black_id
                )
                if not same:
                    raise ValueError(f"game already open: {game.id}")
                return
            self._sessions[game.id] = _Session(game)

    def close_game(self, game_id: str) -> None:
        """Drop a board after matchmaking ends the session."""
        with self._lock:
            session = self._sessions.get(game_id)
        if session is None:
            return
        with session.lock:
            with self._lock:
                if self._sessions.get(game_id) is session:
                    del self._sessions[game_id]

    def state(self, game_id: str) -> GameState | None:
        session = self._session(game_id)
        if session is None:
            return None
        with session.lock:
            if self._session(game_id) is not session:
                return None
            return _state(session)

    def submit_move(self, game_id: str, player_id: str, move_str: object) -> MoveResult:
        """Apply one UCI move, or return an error without changing the board."""
        normalized = _normalize(move_str)
        if normalized is None:
            return _reject(MoveError.INVALID_FORMAT, "Invalid move format")

        session = self._session(game_id)
        if session is None:
            return _reject(MoveError.GAME_NOT_FOUND, "Game not found")

        with session.lock:
            if self._session(game_id) is not session:
                return _reject(MoveError.GAME_NOT_FOUND, "Game not found")
            return self._apply(session, player_id, normalized)

    def _session(self, game_id: str) -> _Session | None:
        with self._lock:
            return self._sessions.get(game_id)

    def _apply(self, session: _Session, player_id: str, text: str) -> MoveResult:
        board = session.board
        color = _player_color(session.game, player_id)
        if color is None:
            logger.warning(
                "rejected move game=%s code=%s",
                session.game.id,
                MoveError.NOT_IN_GAME.value,
            )
            return _snapshot(session, MoveError.NOT_IN_GAME, "Player is not in this game")

        if board.is_game_over():
            logger.warning(
                "rejected move game=%s code=%s",
                session.game.id,
                MoveError.GAME_OVER.value,
            )
            return _snapshot(session, MoveError.GAME_OVER, "Game is over")

        if board.turn != color:
            logger.warning(
                "rejected move game=%s code=%s",
                session.game.id,
                MoveError.NOT_YOUR_TURN.value,
            )
            return _snapshot(session, MoveError.NOT_YOUR_TURN, "Not your turn")

        move, bad_suffix = _parse_uci(text)
        if move is None:
            logger.warning(
                "rejected move game=%s code=%s",
                session.game.id,
                MoveError.INVALID_FORMAT.value,
            )
            return _snapshot(session, MoveError.INVALID_FORMAT, "Invalid move format")

        if bad_suffix:
            if _promotion_available(board, move):
                code = MoveError.PROMOTION_REQUIRED
                message = "Promotion piece required"
            else:
                code = MoveError.INVALID_FORMAT
                message = "Invalid move format"
            logger.warning("rejected move game=%s code=%s", session.game.id, code.value)
            return _snapshot(session, code, message)

        if _promotion_missing(board, move):
            logger.warning(
                "rejected move game=%s code=%s",
                session.game.id,
                MoveError.PROMOTION_REQUIRED.value,
            )
            return _snapshot(session, MoveError.PROMOTION_REQUIRED, "Promotion piece required")

        if move not in board.legal_moves:
            logger.warning(
                "rejected move game=%s code=%s",
                session.game.id,
                MoveError.ILLEGAL_MOVE.value,
            )
            return _snapshot(session, MoveError.ILLEGAL_MOVE, "Illegal move")

        san = board.san(move)
        uci = move.uci()
        board.push(move)
        session.moves.append(uci)
        return _snapshot(session, None, None, uci=uci, san=san)


def _normalize(move_str: object) -> str | None:
    if not isinstance(move_str, str):
        return None
    text = move_str.strip().lower()
    if not text or len(text) > MAX_MOVE_LENGTH:
        return None
    return text


def _parse_uci(text: str) -> tuple[chess.Move | None, bool]:
    try:
        return chess.Move.from_uci(text), False
    except chess.InvalidMoveError:
        if len(text) == 5:
            try:
                return chess.Move.from_uci(text[:4]), True
            except chess.InvalidMoveError:
                return None, False
        return None, False


def _promotion_available(board: chess.Board, move: chess.Move) -> bool:
    piece = board.piece_at(move.from_square)
    if piece is None or piece.piece_type != chess.PAWN or piece.color != board.turn:
        return False
    last_rank = 7 if piece.color == chess.WHITE else 0
    if chess.square_rank(move.to_square) != last_rank:
        return False
    return any(
        chess.Move(move.from_square, move.to_square, promotion=promo) in board.legal_moves
        for promo in _PROMOTIONS
    )


def _promotion_missing(board: chess.Board, move: chess.Move) -> bool:
    if not _promotion_available(board, move):
        return False
    return move.promotion not in _PROMOTIONS


def _player_color(game: Game, player_id: str) -> chess.Color | None:
    if player_id == game.white_id:
        return chess.WHITE
    if player_id == game.black_id:
        return chess.BLACK
    return None


def _turn_name(turn: chess.Color) -> str:
    if turn == chess.WHITE:
        return Color.WHITE.value
    return Color.BLACK.value


def _outcome_fields(game: Game, board: chess.Board) -> tuple[bool, str | None, str | None, str | None, str | None]:
    outcome = board.outcome()
    if outcome is None:
        return False, None, None, None, None
    termination = _TERMINATION.get(outcome.termination, outcome.termination.name.lower())
    if outcome.winner is None:
        return True, outcome.result(), None, None, termination
    winner = _turn_name(outcome.winner)
    winner_id = game.white_id if outcome.winner == chess.WHITE else game.black_id
    return True, outcome.result(), winner, winner_id, termination


def _state(session: _Session) -> GameState:
    board = session.board
    game_over, result, winner, winner_id, termination = _outcome_fields(session.game, board)
    legal = () if game_over else tuple(sorted(move.uci() for move in board.legal_moves))
    return GameState(
        game_id=session.game.id,
        fen=board.fen(),
        turn=_turn_name(board.turn),
        legal_moves=legal,
        moves=tuple(session.moves),
        game_over=game_over,
        result=result,
        winner=winner,
        winner_id=winner_id,
        termination=termination,
    )


def _snapshot(
    session: _Session,
    code: MoveError | None,
    message: str | None,
    *,
    uci: str | None = None,
    san: str | None = None,
) -> MoveResult:
    view = _state(session)
    return MoveResult(
        ok=code is None,
        code=None if code is None else code.value,
        message=message,
        uci=uci,
        san=san,
        fen=view.fen,
        turn=view.turn,
        is_check=session.board.is_check(),
        game_over=view.game_over,
        result=view.result,
        winner=view.winner,
        winner_id=view.winner_id,
        termination=view.termination,
    )


def _reject(code: MoveError, message: str) -> MoveResult:
    logger.warning("rejected move code=%s", code.value)
    return MoveResult(ok=False, code=code.value, message=message)
