from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CHESS_", extra="ignore")

    database_url: str = "sqlite:///./chess-coach.db"
    session_secret: str = Field(default="development-only-change-me", min_length=16)
    cookie_secure: bool = False
    cookie_name: str = "chess_coach_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 90
    retention_days: int = 90
    stockfish_path: str = "/usr/local/bin/stockfish"
    stockfish_hash_mb: int = 64
    analysis_time_ms: int = 150
    engine_version: str = "18"
    worker_poll_seconds: float = 0.25
    worker_lease_seconds: int = 30
    max_job_attempts: int = 3
    static_dir: str = "frontend/dist"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


DIFFICULTIES = {
    "beginner": {"label": "Beginner", "skill": 0, "move_time_ms": 50},
    "easy": {"label": "Easy", "skill": 3, "move_time_ms": 100},
    "medium": {"label": "Medium", "skill": 7, "move_time_ms": 250},
    "hard": {"label": "Hard", "skill": 12, "move_time_ms": 500},
    "expert": {"label": "Expert", "skill": 17, "move_time_ms": 1000},
    "maximum": {"label": "Maximum", "skill": 20, "move_time_ms": 2000},
}

TIME_CONTROLS = {
    "3+2": {"label": "Blitz 3+2", "initial_ms": 180_000, "increment_ms": 2_000},
    "5+0": {"label": "Blitz 5+0", "initial_ms": 300_000, "increment_ms": 0},
    "10+0": {"label": "Rapid 10+0", "initial_ms": 600_000, "increment_ms": 0},
    "15+10": {"label": "Rapid 15+10", "initial_ms": 900_000, "increment_ms": 10_000},
}

