---
name: chess-coach
description: Implement, review, or troubleshoot JustinBatchelor/chess-coach, the FastAPI and React chess application with Stockfish workers and an OpenShift Helm chart. Use for this repository's gameplay, reviews, tests, and releases.
---

# Chess Coach

Work in the active checkout of `JustinBatchelor/chess-coach`. Paths below are
relative to its root. Read `README.md` and the relevant source before editing.

## Implementation map

- `app/api.py`, `security.py`, and `schemas.py`: session ownership, CSRF,
  request validation, and game/review endpoints.
- `app/domain.py`: authoritative clocks, adjudication, PGN, job deduplication,
  and review classification. `app/models.py` and `migrations/`: SQLAlchemy
  persistence and Alembic schema changes.
- `app/worker.py`: leased database jobs, Stockfish UCI execution, resumable
  reviews, and worker metrics. `app/config.py`: settings and difficulty levels.
- `frontend/src/GameView.tsx`, `ChessBoard.tsx`, and `ReviewView.tsx`: play,
  board interaction, and review UI. Keep `api.ts` and `types.ts` aligned with
  backend response schemas.
- `Containerfile`, `compose.yaml`, and `charts/chess-coach/`: container,
  local stack, migrations, cleanup, web/worker, and database deployment.

## Behavior to preserve

The server determines legal moves, elapsed time, and game results; browser
clocks are a display. Preserve session ownership checks and per-session CSRF
on mutations. Anonymous sessions and game history are retained for 90 days
by the cleanup command, not through a login/account system.

Computer moves must remain idempotent under retries and stale jobs. Preserve
expected-ply checks, unique job keys, leases, and PostgreSQL row locking.
Reviews resume from saved progress and use expected WDL outcome loss; do not
silently replace that scoring with centipawn loss. SQLite is useful locally
but does not establish PostgreSQL concurrency behavior.

## Development and checks

Use Python 3.12+ and the dependencies declared in `pyproject.toml`; the frontend
uses Node 22 in the documented workflow. `podman compose up --build` starts the
full stack. Native API setup and migration commands are in `README.md`; a real
Stockfish binary is required for worker execution.

Select relevant checks from the repository root:

```sh
python -m pytest
ruff check app tests
cd frontend && npm test && npm run build
```

`tests/test_domain.py` covers rules and review scoring; `tests/test_api.py`
covers workflows and ownership. Frontend tests cover board interaction and the
app. Inspect `tests/e2e_smoke.py` before running its browser workflow. For chart
changes, run `helm lint charts/chess-coach` and render with the intended values.
Documentation-only changes need no container build or deployment.

## Releases and operations

Keep the image compatible with an arbitrary OpenShift UID and a read-only root
filesystem; the app needs no additional SCC grants. Keep Stockfish source and
license material in the image as specified in `Containerfile`.

Production image identity is the digest; the README and Makefile describe Quay
publishing and SBOM generation. Use existing Secrets for real session/database
credentials and keep `.env`, databases, and authentication files out of Git.
Before an authorized schema upgrade, retain a compatible database backup:
operational rollback restores a compatible image and database rather than
assuming migrations can be reversed. Source publication does not imply cluster
deployment or image publication.
