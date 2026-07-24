import { Chess, type Move, type Square } from "chess.js";
import { useMemo, useState } from "react";

const pieces: Record<string, string> = {
  wK: "♔",
  wQ: "♕",
  wR: "♖",
  wB: "♗",
  wN: "♘",
  wP: "♙",
  bK: "♚",
  bQ: "♛",
  bR: "♜",
  bB: "♝",
  bN: "♞",
  bP: "♟",
};

const fixedGrid = {
  gridTemplateColumns: "repeat(8, minmax(0, 1fr))",
  gridTemplateRows: "repeat(8, minmax(0, 1fr))",
};

type Props = {
  fen: string;
  orientation?: "white" | "black";
  disabled?: boolean;
  onMove?: (uci: string) => void;
};

export function ChessBoard({ fen, orientation = "white", disabled = false, onMove }: Props) {
  const chess = useMemo(() => new Chess(fen), [fen]);
  const [selected, setSelected] = useState<Square | null>(null);
  const [promotion, setPromotion] = useState<{ from: Square; to: Square } | null>(null);
  const ranks = orientation === "white" ? [8, 7, 6, 5, 4, 3, 2, 1] : [1, 2, 3, 4, 5, 6, 7, 8];
  const files = orientation === "white" ? "abcdefgh".split("") : "hgfedcba".split("");
  const legal = selected
    ? (chess.moves({ square: selected, verbose: true }) as Move[]).map((move) => move.to)
    : [];

  function choose(square: Square) {
    if (disabled || !onMove) return;
    if (selected) {
      const candidates = chess
        .moves({ square: selected, verbose: true })
        .filter((move) => move.to === square) as Move[];
      if (candidates.length) {
        if (candidates.some((move) => move.promotion)) {
          setPromotion({ from: selected, to: square });
        } else {
          onMove(`${selected}${square}`);
        }
        setSelected(null);
        return;
      }
    }
    const piece = chess.get(square);
    const currentTurn = chess.turn();
    setSelected(piece && piece.color === currentTurn ? square : null);
  }

  return (
    <div className="board-shell">
      <div className="chessboard" role="grid" aria-label="Chess board" style={fixedGrid}>
        {ranks.flatMap((rank) =>
          files.map((file) => {
            const square = `${file}${rank}` as Square;
            const piece = chess.get(square);
            const isLight = (file.charCodeAt(0) - 97 + rank) % 2 === 1;
            return (
              <button
                type="button"
                role="gridcell"
                aria-label={`${square}${piece ? ` ${piece.color === "w" ? "white" : "black"} ${piece.type}` : ""}`}
                className={[
                  "square",
                  isLight ? "light" : "dark",
                  selected === square ? "selected" : "",
                  legal.includes(square) ? "legal" : "",
                ].join(" ")}
                key={square}
                onClick={() => choose(square)}
                draggable={Boolean(piece) && !disabled}
                onDragStart={(event) => {
                  setSelected(square);
                  event.dataTransfer.setData("text/plain", square);
                }}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  const from = event.dataTransfer.getData("text/plain") as Square;
                  setSelected(from);
                  const candidates = chess
                    .moves({ square: from, verbose: true })
                    .filter((move) => move.to === square) as Move[];
                  if (candidates.some((move) => move.promotion)) {
                    setPromotion({ from, to: square });
                  } else if (candidates.length) {
                    onMove?.(`${from}${square}`);
                  }
                }}
              >
                {piece && (
                  <span className={`piece ${piece.color === "w" ? "white-piece" : "black-piece"}`}>
                    {pieces[`${piece.color}${piece.type.toUpperCase()}`]}
                  </span>
                )}
                <span className="coordinate">{square}</span>
              </button>
            );
          }),
        )}
      </div>
      {promotion && (
        <div className="promotion" role="dialog" aria-label="Choose promotion piece">
          {(["q", "r", "b", "n"] as const).map((kind) => (
            <button
              key={kind}
              onClick={() => {
                onMove?.(`${promotion.from}${promotion.to}${kind}`);
                setPromotion(null);
              }}
            >
              {pieces[`${chess.turn()}${kind.toUpperCase()}`]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
