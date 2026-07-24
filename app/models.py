import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def uuid4() -> str:
    return str(uuid.uuid4())


class AnonymousSession(Base):
    __tablename__ = "anonymous_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    games: Mapped[list["Game"]] = relationship(back_populates="session", cascade="all, delete")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    session_id: Mapped[str] = mapped_column(ForeignKey("anonymous_sessions.id"), index=True)
    player_color: Mapped[str] = mapped_column(String(8))
    difficulty: Mapped[str] = mapped_column(String(16))
    time_control: Mapped[str] = mapped_column(String(16))
    initial_ms: Mapped[int] = mapped_column(Integer)
    increment_ms: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    fen: Mapped[str] = mapped_column(Text)
    pgn: Mapped[str] = mapped_column(Text, default="")
    ply: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    white_clock_ms: Mapped[int] = mapped_column(Integer)
    black_clock_ms: Mapped[int] = mapped_column(Integer)
    turn_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pending_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    termination: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[AnonymousSession] = relationship(back_populates="games")
    moves: Mapped[list["Move"]] = relationship(
        back_populates="game", cascade="all, delete", order_by="Move.ply"
    )


class Move(Base):
    __tablename__ = "moves"
    __table_args__ = (
        UniqueConstraint("game_id", "ply", name="uq_move_game_ply"),
        UniqueConstraint("game_id", "idempotency_key", name="uq_move_game_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    ply: Mapped[int] = mapped_column(Integer)
    color: Mapped[str] = mapped_column(String(8))
    uci: Mapped[str] = mapped_column(String(8))
    san: Mapped[str] = mapped_column(String(24))
    fen_after: Mapped[str] = mapped_column(Text)
    clock_ms_after: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    game: Mapped[Game] = relationship(back_populates="moves")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    engine_version: Mapped[str] = mapped_column(String(32))
    results: Mapped[list] = mapped_column(JSON, default=list)
    engine_state: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EngineJob(Base):
    __tablename__ = "engine_jobs"
    __table_args__ = (
        Index("ix_engine_jobs_claim", "status", "priority", "available_at"),
        UniqueConstraint("dedupe_key", name="uq_engine_job_dedupe"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(String(24))
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"), index=True)
    review_id: Mapped[str | None] = mapped_column(ForeignKey("reviews.id"), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    cursor: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

