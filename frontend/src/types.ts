export type Difficulty = {
  label: string;
  skill: number;
  move_time_ms: number;
};

export type TimeControl = {
  label: string;
  initial_ms: number;
  increment_ms: number;
};

export type Config = {
  csrf_token: string;
  difficulties: Record<string, Difficulty>;
  time_controls: Record<string, TimeControl>;
  colors: string[];
};

export type GameMove = {
  ply: number;
  color: "white" | "black";
  uci: string;
  san: string;
  fen_after: string;
  clock_ms_after: number;
};

export type Game = {
  id: string;
  player_color: "white" | "black";
  difficulty: string;
  time_control: string;
  status: "active" | "completed" | "error";
  fen: string;
  ply: number;
  version: number;
  white_clock_ms: number;
  black_clock_ms: number;
  turn_started_at: string;
  server_time: string;
  pending_ai: boolean;
  result: string | null;
  termination: string | null;
  review_id: string | null;
  created_at: string;
  moves?: GameMove[];
  pgn?: string;
};

export type ReviewMove = {
  ply: number;
  color: "white" | "black";
  uci: string;
  san: string;
  fen_after: string;
  classification: string;
  loss: number;
  eval_before_cp: number;
  eval_after_cp: number;
  white_expected_before: number;
  white_expected_after: number;
  best_move: string;
  pv: string[];
  coaching: string;
};

export type Review = {
  id: string;
  game_id: string;
  status: "queued" | "running" | "complete" | "failed";
  progress: number;
  engine_version: string;
  results: ReviewMove[];
  summary: {
    white?: { score: number; counts: Record<string, number> };
    black?: { score: number; counts: Record<string, number> };
    key_moments?: ReviewMove[];
  };
  error: string | null;
};
