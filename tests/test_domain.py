from datetime import timedelta

import chess

from app.domain import (
    adjudicate_board,
    apply_elapsed,
    classify_loss,
    review_score,
)
from app.models import Game, utcnow


def make_game(**overrides):
    values = {
        "session_id": "session",
        "player_color": "white",
        "difficulty": "medium",
        "time_control": "3+2",
        "initial_ms": 180_000,
        "increment_ms": 2_000,
        "status": "active",
        "version": 1,
        "fen": chess.STARTING_FEN,
        "white_clock_ms": 180_000,
        "black_clock_ms": 180_000,
        "turn_started_at": utcnow(),
    }
    values.update(overrides)
    return Game(**values)


def test_review_classifications_and_score():
    assert classify_loss(0.0) == "Best"
    assert classify_loss(0.02) == "Excellent"
    assert classify_loss(0.05) == "Good"
    assert classify_loss(0.10) == "Inaccuracy"
    assert classify_loss(0.20) == "Mistake"
    assert classify_loss(0.30) == "Blunder"
    assert review_score([]) == 100
    assert review_score([0.0, 0.0]) == 100
    assert review_score([0.25]) == 37


def test_clock_timeout_is_server_authoritative():
    game = make_game(white_clock_ms=500, turn_started_at=utcnow() - timedelta(seconds=1))
    assert apply_elapsed(game) is True
    assert game.status == "completed"
    assert game.result == "0-1"
    assert game.termination == "timeout"


def test_checkmate_adjudication():
    board = chess.Board()
    for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
        board.push_uci(uci)
    game = make_game(fen=board.fen())
    assert adjudicate_board(game, board) is True
    assert game.result == "0-1"
    assert game.termination == "checkmate"
