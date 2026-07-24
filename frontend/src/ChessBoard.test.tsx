import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { ChessBoard } from "./ChessBoard";

test("uses a fixed eight-by-eight board grid", () => {
  render(<ChessBoard fen="8/8/8/3k4/8/4K3/8/8 w - - 0 1" />);

  const board = screen.getByRole("grid", { name: "Chess board" });

  expect(screen.getAllByRole("gridcell")).toHaveLength(64);
  expect(board.style.gridTemplateColumns).toBe("repeat(8, minmax(0, 1fr))");
  expect(board.style.gridTemplateRows).toBe("repeat(8, minmax(0, 1fr))");
});
