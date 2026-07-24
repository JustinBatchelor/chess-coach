import hashlib
import hmac
import secrets
from dataclasses import dataclass

from fastapi import Cookie, Depends, Header, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import AnonymousSession, utcnow


@dataclass
class SessionContext:
    record: AnonymousSession
    raw_token: str
    csrf_token: str


def token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def csrf_for(raw: str, secret: str) -> str:
    return hmac.new(secret.encode(), f"csrf:{raw}".encode(), hashlib.sha256).hexdigest()


def get_session_context(
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    cookie_value: str | None = Cookie(default=None, alias="chess_coach_session"),
) -> SessionContext:
    signer = TimestampSigner(settings.session_secret)
    raw: str | None = None
    if cookie_value:
        try:
            raw = signer.unsign(
                cookie_value, max_age=settings.session_max_age_seconds
            ).decode()
        except (BadSignature, SignatureExpired):
            raw = None

    record = None
    if raw:
        record = db.scalar(
            select(AnonymousSession).where(AnonymousSession.token_hash == token_hash(raw))
        )
    if record is None:
        raw = secrets.token_urlsafe(32)
        record = AnonymousSession(token_hash=token_hash(raw))
        db.add(record)
        db.commit()
        db.refresh(record)
        signed = signer.sign(raw).decode()
        response.set_cookie(
            settings.cookie_name,
            signed,
            max_age=settings.session_max_age_seconds,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
        )
    else:
        record.last_seen_at = utcnow()
        db.commit()
    return SessionContext(
        record=record,
        raw_token=raw,
        csrf_token=csrf_for(raw, settings.session_secret),
    )


def require_csrf(
    context: SessionContext = Depends(get_session_context),
    supplied: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> SessionContext:
    if supplied is None or not hmac.compare_digest(context.csrf_token, supplied):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    return context
