import argparse
import logging
from datetime import timedelta

import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select, text

from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import EngineJob, Game, Review, utcnow
from app.worker import run_worker


def migrate() -> None:
    # Every web/worker process runs this before startup. A PostgreSQL advisory
    # lock makes concurrent OpenShift rollouts safe; SQLite is single-process
    # in development and does not need the lock.
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(728194225)"))
            try:
                command.upgrade(Config("alembic.ini"), "head")
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(728194225)"))
    else:
        command.upgrade(Config("alembic.ini"), "head")


def cleanup() -> None:
    cutoff = utcnow() - timedelta(days=get_settings().retention_days)
    with SessionLocal() as db:
        ids = db.scalars(
            select(Game.id).where(
                Game.status.in_(["completed", "error"]), Game.completed_at < cutoff
            )
        ).all()
        if ids:
            db.execute(delete(EngineJob).where(EngineJob.game_id.in_(ids)))
            db.execute(delete(Review).where(Review.game_id.in_(ids)))
            db.execute(delete(Game).where(Game.id.in_(ids)))
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["web", "worker", "migrate", "cleanup", "worker-once"])
    args = parser.parse_args()
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.command == "web":
        migrate()
        uvicorn.run("app.main:app", host="0.0.0.0", port=8080, proxy_headers=True)
    elif args.command == "worker":
        migrate()
        run_worker()
    elif args.command == "worker-once":
        migrate()
        run_worker(once=True)
    elif args.command == "migrate":
        migrate()
    else:
        cleanup()


if __name__ == "__main__":
    main()
