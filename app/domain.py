import math
from collections import Counter
from datetime import UTC, datetime

import chess
import chess.pgn
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EngineJob, Game, Move, Review, utcnow


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def remaining_clock(game: Game, now: datetime | None = None) -> tuple[int, int]:
    now = now or utcnow()
    white, black = game.white_clock_ms, game.black_clock_ms
    if game.status != "active":
        return white, black
    elapsed = max(0, int((aware(now) - aware(game.turn_started_at)).total_seconds() * 1000))
    board = chess.Board(game.fen)
    if board.turn == chess.WHITE:
        white = max(0, white - elapsed)
    else:
        black = max(0, black - elapsed)
    return white, black


def apply_elapsed(game: Game, now: datetime | None = None) -> bool:
    now = now or utcnow()
    game.white_clock_ms, game.black_clock_ms = remaining_clock(game, now)
    game.turn_started_at = now
    board = chess.Board(game.fen)
    expired = game.white_clock_ms == 0 if board.turn else game.black_clock_ms == 0
    if expired:
        opponent = not board.turn
        if board.has_insufficient_material(opponent):
            finish_game(game, "1/2-1/2", "timeout-insufficient-material")
        else:
            finish_game(game, "0-1" if board.turn else "1-0", "timeout")
        return True
    return False


def finish_game(game: Game, result: str, termination: str) -> None:
    game.status = "completed"
    game.result = result
    game.termination = termination
    game.pending_ai = False
    game.completed_at = utcnow()
    game.version += 1


def adjudicate_board(game: Game, board: chess.Board) -> bool:
    if not board.is_game_over(claim_draw=True):
        return False
    outcome = board.outcome(claim_draw=True)
    termination = outcome.termination.name.lower().replace("_", "-") if outcome else "unknown"
    finish_game(game, board.result(claim_draw=True), termination)
    return True


def rebuild_pgn(game: Game, moves: list[Move]) -> str:
    pgn = chess.pgn.Game()
    pgn.headers["Event"] = "Chess Coach"
    pgn.headers["White"] = "Player" if game.player_color == "white" else "Stockfish"
    pgn.headers["Black"] = "Player" if game.player_color == "black" else "Stockfish"
    pgn.headers["Result"] = game.result or "*"
    node = pgn
    board = pgn.board()
    for item in sorted(moves, key=lambda move: move.ply):
        move = chess.Move.from_uci(item.uci)
        node = node.add_variation(move)
        board.push(move)
    return str(pgn)


def queue_ai_move(db: Session, game: Game) -> None:
    key = f"move:{game.id}:{game.ply}"
    if db.scalar(select(EngineJob).where(EngineJob.dedupe_key == key)) is None:
        db.add(
            EngineJob(
                job_type="move",
                game_id=game.id,
                dedupe_key=key,
                priority=10,
                payload={"expected_ply": game.ply},
            )
        )
    game.pending_ai = True


def queue_review(db: Session, game: Game) -> Review:
    review = db.scalar(select(Review).where(Review.game_id == game.id))
    settings = get_settings()
    if review is None:
        review = Review(game_id=game.id, engine_version=settings.engine_version)
        db.add(review)
        db.flush()
        game.review_id = review.id
    key = f"review:{review.id}:{len(review.results or [])}"
    existing_job = db.scalar(select(EngineJob).where(EngineJob.dedupe_key == key))
    if existing_job is None:
        db.add(
            EngineJob(
                job_type="review",
                game_id=game.id,
                review_id=review.id,
                dedupe_key=key,
                priority=100,
                cursor=len(review.results or []),
            )
        )
    elif existing_job.status == "failed":
        existing_job.status = "queued"
        existing_job.attempts = 0
        existing_job.last_error = None
        existing_job.available_at = utcnow()
    review.status = "queued"
    return review


def classify_loss(loss: float) -> str:
    if loss <= 0.01:
        return "Best"
    if loss <= 0.03:
        return "Excellent"
    if loss <= 0.06:
        return "Good"
    if loss <= 0.12:
        return "Inaccuracy"
    if loss <= 0.25:
        return "Mistake"
    return "Blunder"


def review_score(losses: list[float]) -> int:
    if not losses:
        return 100
    return round(100 * sum(math.exp(-4 * loss) for loss in losses) / len(losses))


def summarize_review(results: list[dict]) -> dict:
    summary: dict = {"white": {}, "black": {}}
    for color in ("white", "black"):
        own = [row for row in results if row["color"] == color]
        losses = [float(row["loss"]) for row in own]
        counts = Counter(row["classification"] for row in own)
        summary[color] = {
            "score": review_score(losses),
            "counts": dict(counts),
        }
    summary["key_moments"] = sorted(results, key=lambda row: row["loss"], reverse=True)[:5]
    return summary
