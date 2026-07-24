import { useEffect, useState } from "react";
import { api, loadConfig } from "./api";
import { GameView } from "./GameView";
import { ReviewView } from "./ReviewView";
import type { Config, Game } from "./types";

type View = { name: "home" } | { name: "game"; game: Game } | { name: "review"; game: Game };

export default function App() {
  const [config, setConfig] = useState<Config | null>(null);
  const [games, setGames] = useState<Game[]>([]);
  const [view, setView] = useState<View>({ name: "home" });
  const [color, setColor] = useState("random");
  const [difficulty, setDifficulty] = useState("medium");
  const [timeControl, setTimeControl] = useState("10+0");
  const [error, setError] = useState("");

  async function refreshHome() {
    const result = await api.listGames();
    setGames(result.games);
  }

  useEffect(() => {
    loadConfig()
      .then((value) => {
        setConfig(value);
        return refreshHome();
      })
      .catch((cause) => setError((cause as Error).message));
  }, []);

  if (view.name === "game") {
    return (
      <GameView
        initial={view.game}
        onExit={() => {
          setView({ name: "home" });
          refreshHome();
        }}
        onReview={(game) => setView({ name: "review", game })}
      />
    );
  }
  if (view.name === "review") {
    return <ReviewView game={view.game} onExit={() => { setView({ name: "home" }); refreshHome(); }} />;
  }

  return (
    <>
      <header className="site-header">
        <a className="brand" href="/" aria-label="Chess Coach home">
          <span>♞</span> CHESS COACH
        </a>
        <span className="header-note">Play. Review. Improve.</span>
      </header>
      <main className="home">
        <section className="hero">
          <div>
            <span className="eyebrow">Your private training board</span>
            <h1>A sharper game starts with <em>one move.</em></h1>
            <p>Challenge Stockfish at your level, then turn every decision into a lesson.</p>
          </div>
          <div className="setup-card">
            <h2>Start a game</h2>
            <label>
              Play as
              <div className="segmented">
                {["white", "random", "black"].map((item) => (
                  <button className={color === item ? "active" : ""} key={item} onClick={() => setColor(item)}>
                    {item === "white" ? "♙" : item === "black" ? "♟" : "◐"} {item}
                  </button>
                ))}
              </div>
            </label>
            <label>
              Difficulty
              <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
                {config &&
                  Object.entries(config.difficulties).map(([key, value]) => (
                    <option key={key} value={key}>{value.label}</option>
                  ))}
              </select>
            </label>
            <label>
              Clock
              <div className="clock-options">
                {config &&
                  Object.entries(config.time_controls).map(([key, value]) => (
                    <button className={timeControl === key ? "active" : ""} key={key} onClick={() => setTimeControl(key)}>
                      <strong>{key}</strong><small>{value.label.split(" ")[0]}</small>
                    </button>
                  ))}
              </div>
            </label>
            <button
              className="primary start"
              disabled={!config}
              onClick={async () => {
                try {
                  const game = await api.createGame({ color, difficulty, time_control: timeControl });
                  setView({ name: "game", game });
                } catch (cause) {
                  setError((cause as Error).message);
                }
              }}
            >
              Start game <span>→</span>
            </button>
            {error && <p className="error">{error}</p>}
          </div>
        </section>

        <section className="history">
          <div className="section-heading">
            <div><span className="eyebrow">This browser</span><h2>Your games</h2></div>
            <span>{games.length} saved</span>
          </div>
          {!games.length ? (
            <div className="empty-state"><span>♟</span><p>Your completed games and reviews will appear here.</p></div>
          ) : (
            <div className="history-grid">
              {games.map((game) => (
                <article key={game.id}>
                  <div><span className={`status ${game.status}`} /> {game.status}</div>
                  <h3>{game.result ?? "In progress"} <small>vs Stockfish</small></h3>
                  <p>{game.time_control} · {game.difficulty} · playing {game.player_color}</p>
                  <button
                    className="secondary"
                    onClick={async () => {
                      const full = await api.getGame(game.id);
                      setView(full.status === "completed" && full.review_id ? { name: "review", game: full } : { name: "game", game: full });
                    }}
                  >
                    {game.status === "completed" ? "Open review" : "Resume"}
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
      <footer>Stockfish analysis · Games retained for 90 days · No account required</footer>
    </>
  );
}

