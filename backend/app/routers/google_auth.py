"""Rutas del login con Google (OpenID Connect). Ver app/google_oauth.py."""

from __future__ import annotations

import logging
import urllib.parse

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth_service import set_refresh_cookie
from ..config import settings
from ..database import get_db
from ..errors import ApiError
from ..google_oauth import (
    STATE_COOKIE_NAME,
    STATE_COOKIE_PATH,
    STATE_TTL_SECONDS,
    GoogleAuthError,
    check_state,
    exchange_code,
    read_state_cookie,
    safe_next,
    start_login,
    verify_id_token,
)
from ..models import UNUSABLE_PASSWORD, User, UserRole
from ..security import create_refresh_token

logger = logging.getLogger("entradas.google")

router = APIRouter(prefix="/auth", tags=["auth"])

# Pagina del frontend que recoge la sesion tras volver de Google.
FRONTEND_COMPLETE_PATH = "/acceder/google"
FRONTEND_ERROR_PATH = "/acceder"


def _clear_state_cookie(response: RedirectResponse) -> None:
    response.delete_cookie(
        key=STATE_COOKIE_NAME,
        path=STATE_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def _fail(reason: str, public_code: str = "google") -> RedirectResponse:
    # El detalle va al log; al usuario solo un codigo generico.
    logger.warning("Login con Google fallido: %s", reason)
    response = RedirectResponse(f"{FRONTEND_ERROR_PATH}?error={public_code}", status_code=303)
    _clear_state_cookie(response)
    return response


def _require_enabled() -> None:
    if not settings.google_enabled:
        raise ApiError.not_found("El login con Google no esta configurado")


@router.get("/providers")
def providers() -> dict:
    """Proveedores de login disponibles (el frontend muestra el boton si procede)."""
    return {"data": {"google": settings.google_enabled}}


@router.get("/google/login")
def google_login(next: str = "/") -> RedirectResponse:
    _require_enabled()
    url, state_cookie = start_login(safe_next(next))
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        key=STATE_COOKIE_NAME,
        value=state_cookie,
        max_age=STATE_TTL_SECONDS,
        path=STATE_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        # Lax (no Strict): la vuelta desde accounts.google.com es una navegacion
        # entre sitios y con Strict el navegador no enviaria la cookie.
        samesite="lax",
    )
    return response


def _find_or_create_user(db: Session, claims: dict) -> User:
    sub = str(claims["sub"])
    email = str(claims["email"]).strip().lower()

    user = db.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
        if user is not None:
            if user.google_sub and user.google_sub != sub:
                raise GoogleAuthError(
                    f"El email {email} ya esta vinculado a otra cuenta de Google"
                )
            # Vincula la cuenta existente: Google garantiza (email_verified)
            # que quien inicia sesion controla ese correo.
            user.google_sub = sub
        else:
            name = str(claims.get("name") or email.split("@")[0]).strip()[:120] or "Usuario"
            user = User(
                email=email,
                password_hash=UNUSABLE_PASSWORD,
                name=name,
                role=UserRole.CLIENT,  # como el registro publico: nunca otro rol
                is_active=True,
                token_version=0,
                google_sub=sub,
            )
            db.add(user)
    db.commit()
    return user


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_enabled()

    if error:
        # El usuario cancelo o Google denego el acceso.
        return _fail(f"Google devolvio error={error}", "google_cancelado")

    try:
        saved = read_state_cookie(request.cookies.get(STATE_COOKIE_NAME))
        check_state(saved["state"], state)
        if not code:
            raise GoogleAuthError("Falta el parametro code")
        tokens = exchange_code(code, saved["cv"])
        claims = verify_id_token(tokens["id_token"], saved["nonce"])
        user = _find_or_create_user(db, claims)
    except GoogleAuthError as exc:
        db.rollback()
        return _fail(exc.reason, exc.public_code)

    if not user.is_active:
        return _fail(f"Cuenta desactivada: {user.id}", "cuenta_desactivada")

    # Misma sesion stateless que el login con contrasena: refresh en cookie
    # HttpOnly. El frontend obtiene el access token llamando a /auth/refresh.
    refresh_token, refresh_ttl = create_refresh_token(user)
    target = f"{FRONTEND_COMPLETE_PATH}?next={urllib.parse.quote(safe_next(saved.get('next')))}"
    response = RedirectResponse(target, status_code=303)
    _clear_state_cookie(response)
    set_refresh_cookie(response, refresh_token, refresh_ttl)
    return response
