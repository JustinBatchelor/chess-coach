import { Chess } from "chess.js";
import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { ChessBoard } from "./ChessBoard";
import type { Game } from "./types";

function formatClock(ms: number): string {
  const safe = Math.max(0, ms);
  const minutes = Math.floor(safe / 60_000);
  const seconds = Math.floor((safe % 60_000) / 1000);
  const tenths = Math.floor((safe % 1000) / 100);
  return safe < 10_000
    ? `${minutes}:${seconds.toString().padStart(2, "0")}.${tenths}`
    : `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

type Props = {
  initial: Game;
  onExit: () => void;
  onReview: (game: Game) => void;
};

export function GameView({ initial, onExit, onReview }: Props) {
  const [game, setGame] = useState(initial);
  const [error, setError] = useState("");
  const [now, setNow] = useState(Date.now());
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!game.pending_ai || game.status !== "active") return;
    const poll = window.setInterval(async () => {
      try {
        const next = await api.getGame(game.id);
        setGame(next);
      } catch (cause) {
        setError((cause as Error).message);
      }
    }, 500);
    return () => window.clearInterval(poll);
  }, [game.id, game.pending_ai, game.status]);

  useEffect(() => {
    if (game.status !== "active") return;
    const board = new Chess(game.fen);
    const activeMs = board.turn() === "w" ? game.white_clock_ms : game.black_clock_ms;
    if (activeMs <= 0) {
      api.sync(game.id).then(setGame).catch((cause) => setError((cause as Error).message));
    }
  }, [game, now]);

  const clocks = useMemo(() => {
    let white = game.white_clock_ms;
    let black = game.black_clock_ms;
    if (game.status === "active") {
      const board = new Chess(game.fen);
      const elapsed = Math.max(0, now - new Date(game.server_time).getTime());
      if (board.turn() === "w") white -= elapsed;
      else black -= elapsed;
    }
    return { white, black };
  }, [game, now]);

  const orientation =
    flipped ? (game.player_color === "white" ? "black" : "white") : game.player_color;
  const playerTurn =
    game.status === "active" &&
    !game.pending_ai &&
    new Chess(game.fen).turn() === (game.player_color === "white" ? "w" : "b");

  async function move(uci: string) {
    setError("");
    try {
      const next = await api.move(game.id, {
        uci,
        expected_ply: game.ply,
        expected_version: game.version,
        idempotency_key: crypto.randomUUID(),
      });
      setGame(next);
    } catch (cause) {
      setError((cause as Error).message);
      setGame(await api.getGame(game.id));
    }
  }

  return (
    <main className="game-layout">
      <section className="game-stage">
        <div className="opponent-row">
          <div>
            <span className="avatar">SF</span>
            <strong>Stockfish · {game.difficulty}</strong>
          </div>
          <time className="clock">{formatClock(game.player_color === "white" ? clocks.black : clocks.white)}</time>
        </div>
        <ChessBoard fen={game.fen} orientation={orientation} disabled={!playerTurn} onMove={move} />
        <div className="opponent-row">
          <div>
            <span className="avatar player">You</span>
            <strong>Your position</strong>
          </div>
          <time className="clock active">
            {formatClock(game.player_color === "white" ? clocks.white : clocks.black)}
          </time>
        </div>
      </section>

      <aside className="game-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">{game.time_control}</span>
            <h2>{game.status === "active" ? (game.pending_ai ? "Stockfish is thinking…" : "Your move") : "Game over"}</h2>
          </div>
          <button className="icon-button" onClick={() => setFlipped(!flipped)} aria-label="Flip board">
            ↻
          </button>
        </div>
        <div className="move-list" aria-label="Move history">
          {!game.moves?.length && <p className="muted">The board is set. Make your first move.</p>}
          {game.moves?.map((item, index) => (
            <span key={item.ply} className={index === game.moves!.length - 1 ? "last-move" : ""}>
              {item.color === "white" ? `${Math.ceil(item.ply / 2)}. ` : ""}
              {item.san}
            </span>
          ))}
        </div>
        {game.status !== "active" && (
          <div className="result-card">
            <span>{game.result}</span>
            <strong>{game.termination?.replaceAll("-", " ")}</strong>
            {game.review_id && (
              <button className="primary" onClick={() => onReview(game)}>
                Review this game
              </button>
            )}
          </div>
        )}
        {error && <p className="error">{error}</p>}
        <div className="panel-actions">
          {game.status === "active" && (
            <button
              className="danger"
              onClick={async () => {
                if (window.confirm("Resign this game?")) setGame(await api.resign(game.id));
              }}
            >
              Resign
            </button>
          )}
          <button className="secondary" onClick={onExit}>Back to home</button>
        </div>
      </aside>
    </main>
  );
}
