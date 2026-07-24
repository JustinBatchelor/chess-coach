import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text

from app import __version__
from app.api import router
from app.config import get_settings
from app.database import engine

REQUESTS = Counter("chess_coach_http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("chess_coach_http_duration_seconds", "HTTP latency", ["method", "path"])

app = FastAPI(title="Chess Coach API", version=__version__)
app.include_router(router)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        REQUESTS.labels(request.method, request.url.path, "500").inc()
        raise
    REQUESTS.labels(request.method, request.url.path, str(response.status_code)).inc()
    LATENCY.labels(request.method, request.url.path).observe(time.monotonic() - started)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.get("/health/live", include_in_schema=False)
def live() -> dict:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
def ready() -> dict:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


settings = get_settings()
static_dir = Path(settings.static_dir)
assets_dir = static_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith(("api/", "health/", "metrics")):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    candidate = static_dir / path
    if path and candidate.is_file() and static_dir in candidate.resolve().parents:
        return FileResponse(candidate)
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        {"message": "Chess Coach frontend has not been built.", "docs": "/docs"},
        status_code=200,
    )

