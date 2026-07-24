from app.domain import remaining_clock
from app.models import Game, Review, utcnow


def serialize_game(game: Game, include_moves: bool = True) -> dict:
    server_time = utcnow()
    white_ms, black_ms = remaining_clock(game, server_time)
    data = {
        "id": game.id,
        "player_color": game.player_color,
        "difficulty": game.difficulty,
        "time_control": game.time_control,
        "status": game.status,
        "fen": game.fen,
        "ply": game.ply,
        "version": game.version,
        "white_clock_ms": white_ms,
        "black_clock_ms": black_ms,
        "turn_started_at": game.turn_started_at.isoformat(),
        "server_time": server_time.isoformat(),
        "pending_ai": game.pending_ai,
        "result": game.result,
        "termination": game.termination,
        "review_id": game.review_id,
        "created_at": game.created_at.isoformat(),
    }
    if include_moves:
        data["moves"] = [
            {
                "ply": move.ply,
                "color": move.color,
                "uci": move.uci,
                "san": move.san,
                "fen_after": move.fen_after,
                "clock_ms_after": move.clock_ms_after,
            }
            for move in game.moves
        ]
        data["pgn"] = game.pgn
    return data


def serialize_review(review: Review) -> dict:
    return {
        "id": review.id,
        "game_id": review.game_id,
        "status": review.status,
        "progress": review.progress,
        "engine_version": review.engine_version,
        "results": review.results,
        "summary": review.summary,
        "error": review.error,
    }
