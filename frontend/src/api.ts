import type { Config, Game, Review } from "./types";

let csrf = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body) headers.set("Content-Type", "application/json");
  if (init?.method && init.method !== "GET") headers.set("X-CSRF-Token", csrf);
  const response = await fetch(path, { credentials: "same-origin", ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? "Request failed");
  }
  return response.json() as Promise<T>;
}

export async function loadConfig(): Promise<Config> {
  const config = await request<Config>("/api/v1/config");
  csrf = config.csrf_token;
  return config;
}

export const api = {
  listGames: () => request<{ games: Game[] }>("/api/v1/games"),
  getGame: (id: string) => request<Game>(`/api/v1/games/${id}`),
  createGame: (body: { color: string; difficulty: string; time_control: string }) =>
    request<Game>("/api/v1/games", { method: "POST", body: JSON.stringify(body) }),
  move: (
    id: string,
    body: { uci: string; expected_ply: number; expected_version: number; idempotency_key: string },
  ) =>
    request<Game>(`/api/v1/games/${id}/moves`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  resign: (id: string) => request<Game>(`/api/v1/games/${id}/resign`, { method: "POST" }),
  sync: (id: string) => request<Game>(`/api/v1/games/${id}/sync`, { method: "POST" }),
  review: (id: string) => request<Review>(`/api/v1/reviews/${id}`),
  retryReview: (id: string) =>
    request<Review>(`/api/v1/reviews/${id}/retry`, { method: "POST" }),
};

