import logging
import math
import time
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import chess
import chess.engine
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import DIFFICULTIES, get_settings
from app.database import SessionLocal
from app.domain import (
    adjudicate_board,
    apply_elapsed,
    classify_loss,
    queue_review,
    rebuild_pgn,
    summarize_review,
)
from app.models import EngineJob, Game, Move, Review, utcnow

logger = logging.getLogger(__name__)
JOBS = Counter("chess_coach_engine_jobs_total", "Engine jobs", ["type", "result"])
ENGINE_SECONDS = Histogram(
    "chess_coach_engine_job_duration_seconds", "Engine job duration", ["type"]
)
FAILURES = Counter("chess_coach_engine_failures_total", "Engine job failures", ["type"])
QUEUE = Gauge("chess_coach_engine_queue_depth", "Queued engine jobs", ["type"])
REVIEW_PROGRESS = Gauge(
    "chess_coach_review_progress_percent", "Average progress of active reviews"
)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/health/live", "/health/ready"}:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        elif self.path == "/metrics":
            with SessionLocal() as db:
                for job_type in ("move", "review"):
                    count = db.scalar(
                        select(func.count(EngineJob.id)).where(
                            EngineJob.status == "queued",
                            EngineJob.job_type == job_type,
                        )
                    )
                    QUEUE.labels(job_type).set(count or 0)
                progress = db.scalar(
                    select(func.avg(Review.progress)).where(
                        Review.status.in_(["queued", "running"])
                    )
                )
                REVIEW_PROGRESS.set(float(progress or 0))
            body = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:
        return


def start_health_server() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8081), HealthHandler)
    Thread(target=server.serve_forever, daemon=True, name="health-server").start()


def claim_job(db: Session) -> EngineJob | None:
    now = utcnow()
    job = db.scalar(
        select(EngineJob)
        .where(
            or_(
                EngineJob.status == "queued",
                (EngineJob.status == "running") & (EngineJob.lease_until < now),
            ),
            EngineJob.available_at <= now,
        )
        .order_by(EngineJob.priority.asc(), EngineJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    settings = get_settings()
    job.status = "running"
    job.lease_until = now + timedelta(seconds=settings.worker_lease_seconds)
    db.commit()
    db.refresh(job)
    return job


def analysis_state(info: dict) -> dict:
    score = info["score"].pov(chess.WHITE).score(mate_score=100_000) or 0
    wdl = info.get("wdl")
    if wdl is not None:
        white_wdl = wdl.pov(chess.WHITE)
        expected = (white_wdl.wins + white_wdl.draws * 0.5) / 1000
        wdl_values = [white_wdl.wins, white_wdl.draws, white_wdl.losses]
    else:
        expected = 1 / (1 + math.exp(-score / 400))
        wdl_values = []
    return {
        "cp": score,
        "white_expected": round(expected, 6),
        "wdl": wdl_values,
        "pv": [move.uci() for move in info.get("pv", [])[:6]],
    }


def analyse(engine: chess.engine.SimpleEngine, board: chess.Board) -> dict:
    settings = get_settings()
    info = engine.analyse(
        board,
        chess.engine.Limit(time=settings.analysis_time_ms / 1000),
        info=chess.engine.INFO_SCORE | chess.engine.INFO_PV,
    )
    return analysis_state(info)


def pv_to_san(board: chess.Board, pv: list[str]) -> list[str]:
    work = board.copy()
    result: list[str] = []
    for uci in pv:
        try:
            move = chess.Move.from_uci(uci)
            if move not in work.legal_moves:
                break
            result.append(work.san(move))
            work.push(move)
        except ValueError:
            break
    return result


def handle_move(db: Session, job: EngineJob, engine: chess.engine.SimpleEngine) -> None:
    game = db.scalar(select(Game).where(Game.id == job.game_id).with_for_update())
    expected_ply = int(job.payload["expected_ply"])
    if (
        game is None
        or game.status != "active"
        or not game.pending_ai
        or game.ply != expected_ply
    ):
        job.status = "done"
        job.lease_until = None
        db.commit()
        return
    if apply_elapsed(game):
        queue_review(db, game)
        job.status = "done"
        job.lease_until = None
        db.commit()
        return

    board = chess.Board(game.fen)
    ai_is_white = game.player_color == "black"
    if board.turn != ai_is_white:
        job.status = "done"
        game.pending_ai = False
        db.commit()
        return

    level = DIFFICULTIES[game.difficulty]
    engine.configure({"Skill Level": level["skill"], "Threads": 1})
    result = engine.play(board, chess.engine.Limit(time=level["move_time_ms"] / 1000))
    if apply_elapsed(game):
        queue_review(db, game)
        job.status = "done"
        job.lease_until = None
        db.commit()
        return
    move = result.move
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
    game.pending_ai = False
    db.add(
        Move(
            game=game,
            ply=game.ply,
            color="white" if mover else "black",
            uci=move.uci(),
            san=san,
            fen_after=game.fen,
            clock_ms_after=mover_clock,
            idempotency_key=f"engine:{job.id}",
        )
    )
    db.flush()
    if adjudicate_board(game, board):
        queue_review(db, game)
    game.pgn = rebuild_pgn(game, list(game.moves))
    job.status = "done"
    job.lease_until = None
    db.commit()


def handle_review(db: Session, job: EngineJob, engine: chess.engine.SimpleEngine) -> None:
    review = db.scalar(select(Review).where(Review.id == job.review_id).with_for_update())
    game = db.get(Game, job.game_id)
    if review is None or game is None:
        job.status = "done"
        db.commit()
        return
    moves = db.scalars(select(Move).where(Move.game_id == game.id).order_by(Move.ply)).all()
    cursor = len(review.results or [])
    if cursor >= len(moves):
        review.summary = summarize_review(review.results or [])
        review.status = "complete"
        review.progress = 100
        review.completed_at = utcnow()
        job.status = "done"
        job.lease_until = None
        db.commit()
        return

    board = chess.Board()
    for prior in moves[:cursor]:
        board.push_uci(prior.uci)
    state = dict(review.engine_state or {})
    before = state.get("current") or analyse(engine, board)
    item = moves[cursor]
    actual = chess.Move.from_uci(item.uci)
    mover = board.turn
    best_line = pv_to_san(board, before["pv"])
    best_move = best_line[0] if best_line else item.san
    board.push(actual)
    after = analyse(engine, board)
    before_expected = before["white_expected"] if mover else 1 - before["white_expected"]
    after_expected = after["white_expected"] if mover else 1 - after["white_expected"]
    loss = round(max(0.0, before_expected - after_expected), 6)
    classification = classify_loss(loss)
    if classification in {"Best", "Excellent"}:
        coaching = f"{item.san} was a strong choice."
    else:
        coaching = f"{item.san} reduced your chances; {best_move} was the engine's preference."
    row = {
        "ply": item.ply,
        "color": "white" if mover else "black",
        "uci": item.uci,
        "san": item.san,
        "fen_after": item.fen_after,
        "classification": classification,
        "loss": loss,
        "eval_before_cp": before["cp"],
        "eval_after_cp": after["cp"],
        "white_expected_before": before["white_expected"],
        "white_expected_after": after["white_expected"],
        "best_move": best_move,
        "pv": best_line,
        "coaching": coaching,
    }
    results = list(review.results or [])
    results.append(row)
    review.results = results
    review.engine_state = {"current": after}
    review.status = "running"
    review.progress = round(len(results) * 100 / len(moves))
    job.cursor = len(results)
    job.status = "queued"
    job.lease_until = None
    job.available_at = utcnow()
    db.commit()


def fail_job(db: Session, job_id: str, error: Exception) -> None:
    settings = get_settings()
    job = db.get(EngineJob, job_id)
    if job is None:
        return
    job.attempts += 1
    job.last_error = str(error)[:2000]
    job.lease_until = None
    if job.attempts >= settings.max_job_attempts:
        job.status = "failed"
        if job.review_id:
            review = db.get(Review, job.review_id)
            if review:
                review.status = "failed"
                review.error = "Engine analysis failed after three attempts."
        elif job.job_type == "move":
            game = db.get(Game, job.game_id)
            if game:
                game.status = "error"
                game.pending_ai = False
                game.termination = "engine-error"
    else:
        job.status = "queued"
        job.available_at = utcnow() + timedelta(seconds=2**job.attempts)
    db.commit()


def run_worker(once: bool = False) -> None:
    settings = get_settings()
    engine = chess.engine.SimpleEngine.popen_uci(settings.stockfish_path)
    engine.configure({"Hash": settings.stockfish_hash_mb, "Threads": 1, "UCI_ShowWDL": True})
    start_health_server()
    logger.info("engine worker started")
    try:
        while True:
            with SessionLocal() as db:
                job = claim_job(db)
            if job is None:
                if once:
                    return
                time.sleep(settings.worker_poll_seconds)
                continue
            try:
                with SessionLocal() as db:
                    current = db.get(EngineJob, job.id)
                    with ENGINE_SECONDS.labels(current.job_type).time():
                        if current.job_type == "move":
                            handle_move(db, current, engine)
                        else:
                            handle_review(db, current, engine)
                    JOBS.labels(current.job_type, "success").inc()
            except Exception as exc:
                logger.exception("engine job failed", extra={"job_id": job.id})
                JOBS.labels(job.job_type, "failure").inc()
                FAILURES.labels(job.job_type).inc()
                with SessionLocal() as db:
                    fail_job(db, job.id, exc)
            if once:
                return
    finally:
        engine.quit()
