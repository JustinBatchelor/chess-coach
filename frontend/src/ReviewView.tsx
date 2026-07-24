import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { ChessBoard } from "./ChessBoard";
import type { Game, Review } from "./types";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

export function ReviewView({ game, onExit }: { game: Game; onExit: () => void }) {
  const [review, setReview] = useState<Review | null>(null);
  const [selected, setSelected] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!game.review_id) return;
    let active = true;
    async function poll() {
      try {
        const next = await api.review(game.review_id!);
        if (active) setReview(next);
        if (active && ["queued", "running"].includes(next.status)) {
          window.setTimeout(poll, 1000);
        }
      } catch (cause) {
        if (active) setError((cause as Error).message);
      }
    }
    poll();
    return () => {
      active = false;
    };
  }, [game.review_id]);

  const fen = selected === 0 ? START : review?.results[selected - 1]?.fen_after ?? START;
  const current = selected > 0 ? review?.results[selected - 1] : undefined;
  const graph = useMemo(() => {
    if (!review?.results.length) return "";
    return review.results
      .map((row, index) => {
        const x = review.results.length === 1 ? 0 : (index / (review.results.length - 1)) * 100;
        const y = 100 - row.white_expected_after * 100;
        return `${x},${y}`;
      })
      .join(" ");
  }, [review]);

  if (!review || review.status !== "complete") {
    return (
      <main className="center-card">
        <span className="analysis-mark">◎</span>
        <h1>Analyzing your game</h1>
        <p>Stockfish is checking every position. You can safely leave and return later.</p>
        <div className="progress"><span style={{ width: `${review?.progress ?? 0}%` }} /></div>
        <strong>{review?.progress ?? 0}%</strong>
        {review?.status === "failed" && (
          <button className="primary" onClick={() => api.retryReview(review.id).then(setReview)}>
            Retry analysis
          </button>
        )}
        {error && <p className="error">{error}</p>}
        <button className="secondary" onClick={onExit}>Back to home</button>
      </main>
    );
  }

  return (
    <main className="review-page">
      <header className="review-header">
        <div>
          <span className="eyebrow">Stockfish {review.engine_version} review</span>
          <h1>Game review</h1>
        </div>
        <button className="secondary" onClick={onExit}>Done</button>
      </header>
      <section className="score-strip">
        {(["white", "black"] as const).map((color) => (
          <div key={color}>
            <span>{color === game.player_color ? "You" : "Stockfish"} · {color}</span>
            <strong>{review.summary[color]?.score ?? 100}</strong>
            <small>review score</small>
          </div>
        ))}
      </section>
      <div className="review-grid">
        <section>
          <ChessBoard fen={fen} orientation={game.player_color} disabled />
          <div className="review-nav">
            <button onClick={() => setSelected(0)}>⏮</button>
            <button onClick={() => setSelected(Math.max(0, selected - 1))}>←</button>
            <span>{selected} / {review.results.length}</span>
            <button onClick={() => setSelected(Math.min(review.results.length, selected + 1))}>→</button>
            <button onClick={() => setSelected(review.results.length)}>⏭</button>
          </div>
        </section>
        <aside className="review-panel">
          <div className="eval-graph">
            <span>White</span>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Expected score graph">
              <line x1="0" y1="50" x2="100" y2="50" />
              <polyline points={graph} />
            </svg>
            <span>Black</span>
          </div>
          {current ? (
            <div className={`move-insight ${current.classification.toLowerCase()}`}>
              <span className="classification">{current.classification}</span>
              <h2>{Math.ceil(current.ply / 2)}{current.color === "black" ? "…" : "."} {current.san}</h2>
              <p>{current.coaching}</p>
              <dl>
                <div><dt>Best move</dt><dd>{current.best_move}</dd></div>
                <div><dt>Engine line</dt><dd>{current.pv.join(" ") || "—"}</dd></div>
              </dl>
            </div>
          ) : (
            <div className="move-insight"><h2>Starting position</h2><p>Step forward to review each move.</p></div>
          )}
          <div className="review-moves">
            {review.results.map((row) => (
              <button
                key={row.ply}
                className={selected === row.ply ? "active" : ""}
                onClick={() => setSelected(row.ply)}
                title={row.classification}
              >
                {row.color === "white" && `${Math.ceil(row.ply / 2)}. `}
                {row.san}
                <i className={row.classification.toLowerCase()} />
              </button>
            ))}
          </div>
        </aside>
      </div>
    </main>
  );
}

