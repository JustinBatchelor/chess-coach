# Chess Coach

Chess Coach is a GPLv3 web application for playing timed standard chess against
Stockfish and reviewing every move after the game. The backend is FastAPI,
the browser interface is React, and PostgreSQL persists anonymous sessions,
games, engine jobs, and reviews.

## Features

- White, black, or random color selection
- 3+2, 5+0, 10+0, and 15+10 server-authoritative clocks
- Six Stockfish difficulty levels
- Resumable, idempotent computer-move jobs
- Interactive WDL-based post-game review
- Anonymous browser history with 90-day retention
- Rootless Podman workflow and OpenShift Helm chart

## Local development

Requirements are Podman 5+, a `podman compose` provider, Python 3.12 for
backend-only development, and Node.js 22 for frontend-only development.

Start the complete stack:

```sh
podman compose up --build
```

Open <http://localhost:8080>. Stop it without deleting the PostgreSQL volume:

```sh
podman compose down
```

For native development, install Python and frontend dependencies, run the
migration, and start the API and Vite development server in separate terminals:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
CHESS_DATABASE_URL=sqlite:///./chess-coach.db .venv/bin/python -m app.cli migrate
CHESS_DATABASE_URL=sqlite:///./chess-coach.db .venv/bin/python -m app.cli web
cd frontend
npm install
npm run dev
```

The Vite server proxies API calls to port 8080. A real Stockfish binary is
needed only when running the worker.

## Tests

```sh
.venv/bin/python -m pytest
cd frontend
npm test
npm run build
```

Validate the built image with an arbitrary OpenShift-like UID and read-only
root filesystem:

```sh
podman build -t localhost/chess-coach:0.1.0 -f Containerfile .
podman run --rm --user 1001230000 --read-only \
  --tmpfs /tmp:size=64m,mode=1777 \
  -e CHESS_DATABASE_URL=sqlite:////tmp/chess-coach.db \
  -e CHESS_SESSION_SECRET=container-validation-secret \
  -p 8080:8080 localhost/chess-coach:0.1.0 web
```

## Publishing to public Quay

Create a public repository named `chess-coach` in the intended Quay account or
organization. Do not put a Quay password in this repository.

```sh
podman login quay.io
export QUAY_NAMESPACE='jbatchel'
export VERSION='0.1.0'
export GIT_SHA="$(git rev-parse --short HEAD)"
podman build --platform linux/amd64 \
  --build-arg APP_VERSION="$VERSION" \
  --build-arg VCS_REF="$GIT_SHA" \
  -t "localhost/chess-coach:$VERSION" -f Containerfile .
podman tag "localhost/chess-coach:$VERSION" \
  "quay.io/$QUAY_NAMESPACE/chess-coach:$VERSION"
podman tag "localhost/chess-coach:$VERSION" \
  "quay.io/$QUAY_NAMESPACE/chess-coach:sha-$GIT_SHA"
podman push "quay.io/$QUAY_NAMESPACE/chess-coach:$VERSION"
podman push "quay.io/$QUAY_NAMESPACE/chess-coach:sha-$GIT_SHA"
```

Verify anonymous access and capture the immutable digest:

```sh
auth_file="$(mktemp)"
skopeo inspect --authfile "$auth_file" \
  "docker://quay.io/$QUAY_NAMESPACE/chess-coach:$VERSION"
```

Set `image.repository` and `image.digest` in the Helm values to deploy by
digest. Tags remain useful release labels but are not used as production
identity. Generate an SBOM with:

```sh
syft "localhost/chess-coach:$VERSION" \
  -o "spdx-json=build/sbom-$VERSION.spdx.json"
```

## OpenShift deployment

The chart defaults to an external PostgreSQL database. For the included
small-demo database, begin with `values-openshift.yaml`. Replace the image
digest and all example credentials.

```sh
helm lint charts/chess-coach
helm template chess-coach charts/chess-coach \
  -f charts/chess-coach/values-openshift.yaml >/tmp/chess-coach-rendered.yaml
oc apply --dry-run=server -f /tmp/chess-coach-rendered.yaml
helm upgrade --install chess-coach charts/chess-coach \
  --namespace chess-coach --create-namespace \
  -f charts/chess-coach/values-openshift.yaml \
  --wait --timeout 10m
oc rollout status deployment/chess-coach-web -n chess-coach
oc rollout status deployment/chess-coach-worker -n chess-coach
oc get route chess-coach -n chess-coach
```

For an external database, create a Secret with a SQLAlchemy-compatible URL:

```sh
oc create secret generic chess-coach-database -n chess-coach \
  --from-literal=database-url='postgresql+psycopg://USER:PASSWORD@HOST:5432/DB'
```

Set `postgresql.enabled=false` and
`database.existingSecret=chess-coach-database`. Back up PostgreSQL with the
database platform's native backup tooling before upgrades. Alembic migrations
are forward-only operationally; rollback means restoring the prior image and a
compatible database backup.

## Operations and security

- `/health/live`, `/health/ready`, and `/metrics` are available on the web pod.
- The image works with OpenShift's assigned UID and requires no SCC grants.
- Cookies are HTTP-only and SameSite=Lax; production values enable Secure.
- Mutations require a per-session CSRF token and game ownership is checked.
- The bundled PostgreSQL StatefulSet is for a small demo, not HA production.
- Scale workers only after increasing database and CPU capacity; job claiming
  uses PostgreSQL row locks and leases.
- Run `python -m app.cli cleanup` through the chart CronJob to enforce retention.

## Licensing

Chess Coach and `python-chess` are GPL-3.0-or-later. Stockfish 18 runs as a
separate UCI process and is GPLv3. The container includes the exact Stockfish
source and license material used to build the binary under `/usr/src/stockfish`
and `/usr/share/licenses/stockfish`.
