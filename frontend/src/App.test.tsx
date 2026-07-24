import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import App from "./App";

vi.stubGlobal(
  "fetch",
  vi.fn(async (input: string) => {
    if (input.endsWith("/config")) {
      return new Response(
        JSON.stringify({
          csrf_token: "test",
          difficulties: { medium: { label: "Medium", skill: 7, move_time_ms: 250 } },
          time_controls: { "10+0": { label: "Rapid 10+0", initial_ms: 600000, increment_ms: 0 } },
          colors: ["white", "black", "random"],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    return new Response(JSON.stringify({ games: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }),
);

test("renders the game setup", async () => {
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Start a game" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Start game/ })).toBeInTheDocument();
});
