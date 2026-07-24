import random

import chess
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DIFFICULTIES, TIME_CONTROLS
from app.database import get_db
from app.domain import (
    adjudicate_board,
    apply_elapsed,
    queue_ai_move,
    queue_review,
    rebuild_pgn,
)
from app.models import Game, Move, Review, utcnow
from app.schemas import GameCreate, MoveCreate
from app.security import SessionContext, get_session_context, require_csrf
from app.serializers import serialize_game, serialize_review

router = APIRouter(prefix="/api/v1")


def owned_game(db: Session, game_id: str, context: SessionContext, lock: bool = False) -> Game:
    query = select(Game).where(Game.id == game_id, Game.session_id == context.record.id)
    if lock:
        query = query.with_for_update()
    game = db.scalar(query)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@router.get("/config")
def config(context: SessionContext = Depends(get_session_context)) -> dict:
    return {
        "csrf_token": context.csrf_token,
        "difficulties": DIFFICULTIES,
        "time_controls": TIME_CONTROLS,
        "colors": ["white", "black", "random"],
    }


@router.post("/games", status_code=status.HTTP_201_CREATED)
def create_game(
    payload: GameCreate,
    db: Session = Depends(get_db),
    context: SessionContext = Depends(require_csrf),
) -> dict:
    color = random.choice(("white", "black")) if payload.color == "random" else payload.color
    control = TIME_CONTROLS[payload.time_control]
    board = chess.Board()
    now = utcnow()
    game = Game(
        session_id=context.record.id,
        player_color=color,
        difficulty=payload.difficulty,
        time_control=payload.time_control,
        initial_ms=control["initial_ms"],
        increment_ms=control["increment_ms"],
        fen=board.fen(),
        white_clock_ms=control["initial_ms"],
        black_clock_ms=control["initial_ms"],
        turn_started_at=now,
    )
    db.add(game)
    db.flush()
    if color == "black":
        queue_ai_move(db, game)
    db.commit()
    db.refresh(game)
    return serialize_game(game)


@router.get("/games")
def list_games(
    db: Session = Depends(get_db),
    context: SessionContext = Depends(get_session_context),
) -> dict:
    games = db.scalars(
        select(Game)
        .where(Game.session_id == context.record.id)
        .order_by(Game.created_at.desc())
        .limit(50)
    ).all()
    return {"games": [serialize_game(game, include_moves=False) for game in games]}


@router.get("/games/{game_id}")
def get_game(
    game_id: str,
    db: Session = Depends(get_db),
    context: SessionContext = Depends(get_session_context),
) -> dict:
    return serialize_game(owned_game(db, game_id, context))


@router.post("/games/{game_id}/moves", status_code=status.HTTP_202_ACCEPTED)
def submit_move(
    game_id: str,
    payload: MoveCreate,
    db: Session = Depends(get_db),
    context: SessionContext = Depends(require_csrf),
) -> dict:
    game = owned_game(db, game_id, context, lock=True)
    prior = db.scalar(
        select(Move).where(
            Move.game_id == game.id, Move.idempotency_key == payload.idempotency_key
        )
    )
    if prior is not None:
        return serialize_game(game)
    if game.status != "active":
        raise HTTPException(status_code=409, detail="Game is not active")
    if game.pending_ai:
        raise HTTPException(status_code=409, detail="Computer move is pending")
    if payload.expected_ply != game.ply or payload.expected_version != game.version:
        raise HTTPException(status_code=409, detail="Game state is stale")

    board = chess.Board(game.fen)
    player_is_white = game.player_color == "white"
    if board.turn != player_is_white:
        raise HTTPException(status_code=409, detail="It is not the player's turn")
    if apply_elapsed(game):
        queue_review(db, game)
        db.commit()
        return serialize_game(game)

    move = chess.Move.from_uci(payload.uci)
    if move not in board.legal_moves:
        raise HTTPException(status_code=422, detail="Illegal move")
    san = board.san(move)
    mover = board.turn
    board.push(move)
    if mover == chess.WHITE:
        game.white_clock_ms += game.increment_ms
        mover_clock = game.white_clock_ms
    else:
        game.black_clock_ms += game.increment_ms
        mover_clock = game.black_clock_ms

    game.ply += 1
    game.version += 1
    game.fen = board.fen()
    game.turn_started_at = utcnow()
    move_row = Move(
        game=game,
        ply=game.ply,
        color="white" if mover else "black",
        uci=move.uci(),
        san=san,
        fen_after=game.fen,
        clock_ms_after=mover_clock,
        idempotency_key=payload.idempotency_key,
    )
    db.add(move_row)
    db.flush()

    if adjudicate_board(game, board):
        queue_review(db, game)
    else:
        queue_ai_move(db, game)
    game.pgn = rebuild_pgn(game, list(game.moves))
    db.commit()
    db.refresh(game)
    return serialize_game(game)


@router.post("/games/{game_id}/resign")
def resign(
    game_id: str,
    db: Session = Depends(get_db),
    context: SessionContext = Depends(require_csrf),
) -> dict:
    game = owned_game(db, game_id, context, lock=True)
    if game.status != "active":
        raise HTTPException(status_code=409, detail="Game is not active")
    game.status = "completed"
    game.result = "0-1" if game.player_color == "white" else "1-0"
    game.termination = "resignation"
    game.completed_at = utcnow()
    game.pending_ai = False
    game.version += 1
    queue_review(db, game)
    game.pgn = rebuild_pgn(game, list(game.moves))
    db.commit()
    return serialize_game(game)


@router.post("/games/{game_id}/sync")
def sync_game(
    game_id: str,
    db: Session = Depends(get_db),
    context: SessionContext = Depends(require_csrf),
) -> dict:
    game = owned_game(db, game_id, context, lock=True)
    if game.status == "active" and apply_elapsed(game):
        queue_review(db, game)
        db.commit()
    return serialize_game(game)


@router.get("/reviews/{review_id}")
def get_review(
    review_id: str,
    db: Session = Depends(get_db),
    context: SessionContext = Depends(get_session_context),
) -> dict:
    review = db.scalar(
        select(Review)
        .join(Game, Game.id == Review.game_id)
        .where(Review.id == review_id, Game.session_id == context.record.id)
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return serialize_review(review)


@router.post("/reviews/{review_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_review(
    review_id: str,
    db: Session = Depends(get_db),
    context: SessionContext = Depends(require_csrf),
) -> dict:
    review = db.scalar(
        select(Review)
        .join(Game, Game.id == Review.game_id)
        .where(Review.id == review_id, Game.session_id == context.record.id)
        .with_for_update()
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.status not in {"failed", "queued"}:
        raise HTTPException(status_code=409, detail="Review cannot be retried")
    game = db.get(Game, review.game_id)
    review.error = None
    queue_review(db, game)
    db.commit()
    return serialize_review(review)
