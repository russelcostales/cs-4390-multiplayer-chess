import threading

import chess
import pytest

from matchmaking import Game
from moves import MoveError, MoveService


WHITE = "white"
BLACK = "black"
START_FEN = chess.STARTING_FEN


def opened(game_id: str = "g1") -> MoveService:
    service = MoveService()
    service.open_game(Game(id=game_id, white_id=WHITE, black_id=BLACK))
    return service


def play(service: MoveService, moves: list[str], game_id: str = "g1") -> list:
    results = []
    for index, move in enumerate(moves):
        player = WHITE if index % 2 == 0 else BLACK
        results.append(service.submit_move(game_id, player, move))
    return results


def test_legal_opening_move_updates_fen():
    service = opened()
    before = service.state("g1")
    assert before is not None
    assert before.fen == START_FEN
    assert before.turn == "white"
    assert "e2e4" in before.legal_moves
    assert "e2e5" not in before.legal_moves
    assert before.moves == ()
    assert before.game_over is False

    result = service.submit_move("g1", WHITE, "e2e4")
    expected = chess.Board()
    expected.push_uci("e2e4")
    assert result.ok is True
    assert result.uci == "e2e4"
    assert result.san == "e4"
    assert result.fen == expected.fen()
    assert result.fen != START_FEN
    assert result.turn == "black"
    assert result.is_check is False
    assert result.game_over is False
    assert result.winner is None
    assert result.termination is None

    state = service.state("g1")
    assert state is not None
    assert state.fen == result.fen
    assert state.moves == ("e2e4",)
    assert state.turn == "black"

    reply = service.submit_move("g1", BLACK, "E7E5")
    assert reply.ok is True
    assert reply.uci == "e7e5"
    assert reply.turn == "white"


def test_illegal_move_leaves_the_board_unchanged():
    service = opened()
    result = service.submit_move("g1", WHITE, "e2e5")
    assert result.ok is False
    assert result.code == MoveError.ILLEGAL_MOVE
    assert result.message == "Illegal move"
    assert result.fen == START_FEN
    state = service.state("g1")
    assert state is not None
    assert state.fen == START_FEN
    assert state.moves == ()


def test_moving_out_of_turn_is_rejected():
    service = opened()
    result = service.submit_move("g1", BLACK, "e7e5")
    assert result.code == MoveError.NOT_YOUR_TURN
    assert result.fen == START_FEN
    assert service.state("g1").moves == ()

    assert service.submit_move("g1", WHITE, "e2e4").ok is True
    second = service.submit_move("g1", WHITE, "d2d4")
    assert second.code == MoveError.NOT_YOUR_TURN
    assert service.state("g1").moves == ("e2e4",)


def test_player_not_in_the_game_is_rejected():
    service = opened()
    result = service.submit_move("g1", "spectator", "e2e4")
    assert result.code == MoveError.NOT_IN_GAME
    assert result.message == "Player is not in this game"
    assert service.state("g1").fen == START_FEN
    assert service.state("g1").moves == ()


def test_unknown_game_is_rejected():
    service = opened()
    result = service.submit_move("missing", WHITE, "e2e4")
    assert result.ok is False
    assert result.code == MoveError.GAME_NOT_FOUND
    assert result.fen is None


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "zz99", "e2", "e4", "Nf3", None, 5, "e2e4" + ("x" * 40), "e2e4x"],
)
def test_malformed_moves_are_rejected_without_crashing(raw):
    service = opened()
    result = service.submit_move("g1", WHITE, raw)
    assert result.ok is False
    assert result.code == MoveError.INVALID_FORMAT
    assert result.message == "Invalid move format"
    assert result.uci is None
    state = service.state("g1")
    assert state.fen == START_FEN
    assert state.moves == ()
    assert service.submit_move("g1", WHITE, "e2e4").ok is True


def test_pinned_piece_and_ignoring_check_are_rejected():
    service = opened()
    assert all(result.ok for result in play(service, ["e2e4", "a7a6", "f1b5"]))
    fen = service.state("g1").fen
    pinned = service.submit_move("g1", BLACK, "d7d5")
    assert pinned.code == MoveError.ILLEGAL_MOVE
    assert service.state("g1").fen == fen
    assert service.submit_move("g1", BLACK, "a6a5").ok is True

    service = opened()
    assert all(result.ok for result in play(service, ["e2e4", "e7e5", "d1h5", "b8c6", "h5f7"]))
    assert service.state("g1").fen
    checked = service.state("g1")
    ignored = service.submit_move("g1", BLACK, "a7a6")
    assert ignored.code == MoveError.ILLEGAL_MOVE
    assert service.state("g1").fen == checked.fen
    assert service.submit_move("g1", BLACK, "e8f7").ok is True


def test_castling_legal_and_illegal():
    service = opened()
    early = service.submit_move("g1", WHITE, "e1g1")
    assert early.code == MoveError.ILLEGAL_MOVE
    assert service.state("g1").fen == START_FEN

    assert all(
        result.ok
        for result in play(service, ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6"])
    )
    castle = service.submit_move("g1", WHITE, "e1g1")
    assert castle.ok is True
    assert castle.uci == "e1g1"
    assert castle.san == "O-O"

    walked = opened("kings")
    setup = ["e2e4", "e7e5", "e1e2", "e8e7", "e2e1", "e7e8", "g1f3", "b8c6", "f1c4", "g8f6"]
    assert all(result.ok for result in play(walked, setup, "kings"))
    fen = walked.state("kings").fen
    denied = walked.submit_move("kings", WHITE, "e1g1")
    assert denied.code == MoveError.ILLEGAL_MOVE
    assert walked.state("kings").fen == fen


def test_en_passant_legal_and_illegal():
    service = opened()
    assert all(result.ok for result in play(service, ["e2e4", "a7a6", "e4e5", "a6a5"]))
    fen = service.state("g1").fen
    missed = service.submit_move("g1", WHITE, "e5d6")
    assert missed.code == MoveError.ILLEGAL_MOVE
    assert service.state("g1").fen == fen

    captured = opened("ep")
    results = play(captured, ["e2e4", "a7a6", "e4e5", "d7d5", "e5d6"], "ep")
    assert all(result.ok for result in results)
    assert results[-1].uci == "e5d6"
    assert results[-1].san == "exd6"


def test_promotion_requires_a_piece_and_accepts_one():
    service = opened()
    setup = ["e2e4", "d7d5", "e4d5", "c7c6", "d5c6", "a7a6", "c6c7", "a6a5"]
    assert all(result.ok for result in play(service, setup))
    fen = service.state("g1").fen

    missing = service.submit_move("g1", WHITE, "c7d8")
    assert missing.code == MoveError.PROMOTION_REQUIRED
    assert missing.message == "Promotion piece required"
    assert service.state("g1").fen == fen

    invalid_piece = service.submit_move("g1", WHITE, "c7d8k")
    assert invalid_piece.code == MoveError.PROMOTION_REQUIRED
    assert service.state("g1").fen == fen

    promoted = service.submit_move("g1", WHITE, "c7d8q")
    assert promoted.ok is True
    assert promoted.uci == "c7d8q"
    assert promoted.san == "cxd8=Q+"
    assert service.state("g1").moves[-1] == "c7d8q"
    assert service.state("g1").fen == promoted.fen


def test_fools_mate_sets_the_winner_and_rejects_further_moves():
    service = opened()
    results = play(service, ["f2f3", "e7e5", "g2g4", "d8h4"])
    assert all(result.ok for result in results)
    mate = results[-1]
    assert mate.game_over is True
    assert mate.is_check is True
    assert mate.termination == "checkmate"
    assert mate.result == "0-1"
    assert mate.winner == "black"
    assert mate.winner_id == BLACK
    assert mate.san == "Qh4#"

    fen = service.state("g1").fen
    for player, move in ((WHITE, "a2a3"), (BLACK, "a7a6")):
        rejected = service.submit_move("g1", player, move)
        assert rejected.code == MoveError.GAME_OVER
        assert rejected.game_over is True
        assert rejected.winner == "black"
        assert service.state("g1").fen == fen
        assert service.state("g1").moves == ("f2f3", "e7e5", "g2g4", "d8h4")


def test_stalemate_is_detected():
    service = opened()
    moves = [
        "e2e3", "a7a5", "d1h5", "a8a6", "h5a5", "h7h5", "a5c7", "a6h6",
        "h2h4", "f7f6", "c7d7", "e8f7", "d7b7", "d8d3", "b7b8", "d3h7",
        "b8c8", "f7g6", "c8e6",
    ]
    results = play(service, moves)
    assert all(result.ok for result in results)
    draw = results[-1]
    assert draw.game_over is True
    assert draw.termination == "stalemate"
    assert draw.result == "1/2-1/2"
    assert draw.winner is None
    assert draw.winner_id is None
    assert service.state("g1").legal_moves == ()

    fen = service.state("g1").fen
    rejected = service.submit_move("g1", BLACK, "g6h6")
    assert rejected.code == MoveError.GAME_OVER
    assert service.state("g1").fen == fen


def test_fivefold_repetition_ends_the_game():
    service = opened()
    moves = []
    for _ in range(4):
        moves.extend(["b1c3", "b8c6", "c3b1", "c6b8"])
    results = play(service, moves)
    assert all(result.ok for result in results[:-1])
    assert results[-1].ok is True
    assert results[-1].game_over is True
    assert results[-1].termination == "fivefold_repetition"
    assert results[-1].result == "1/2-1/2"
    assert results[-1].winner is None


def test_move_history_rebuilds_the_board():
    service = opened()
    play(service, ["e2e4", "e7e5", "g1f3", "b8c6"])
    state = service.state("g1")
    board = chess.Board()
    for uci in state.moves:
        board.push_uci(uci)
    assert board.fen() == state.fen


def test_open_game_is_idempotent_and_close_drops_it():
    service = opened()
    game = Game(id="g1", white_id=WHITE, black_id=BLACK)
    service.submit_move("g1", WHITE, "e2e4")
    service.open_game(game)
    assert service.state("g1").moves == ("e2e4",)

    service.close_game("g1")
    assert service.state("g1") is None
    assert service.submit_move("g1", BLACK, "e7e5").code == MoveError.GAME_NOT_FOUND


def test_concurrent_moves_cannot_both_apply():
    for _ in range(20):
        service = opened()
        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()

        def submit(move: str) -> None:
            barrier.wait(timeout=5)
            result = service.submit_move("g1", WHITE, move)
            with lock:
                results.append(result)

        threads = [
            threading.Thread(target=submit, args=("e2e4",), daemon=True),
            threading.Thread(target=submit, args=("d2d4",), daemon=True),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            assert not thread.is_alive()

        applied = [result for result in results if result.ok]
        assert len(applied) == 1
        state = service.state("g1")
        assert state.moves == (applied[0].uci,)
        assert state.fen == applied[0].fen
        assert state.turn == "black"
