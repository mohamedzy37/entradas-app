"""Emision, rotacion y revocacion de tokens SIN estado en el servidor.

Requisito del enunciado: la sesion no se almacena en el backend.

- Access token: JWT de vida corta (15 min). Viaja en la cabecera
  `Authorization: Bearer` y el frontend lo guarda solo en memoria.
- Refresh token: JWT de vida larga (7 dias), firmado con otro secreto. Viaja en
  una cookie HttpOnly + Secure + SameSite=Strict limitada a /api/auth.
- Rotacion: cada /refresh devuelve un access nuevo y sustituye la cookie por un
  refresh nuevo, conservando la caducidad absoluta del login original.
- Revocacion: `User.token_version` va dentro de ambos tokens. Si no coincide
  con el valor actual en BD, el token se rechaza. Incrementarlo invalida todas
  las sesiones del usuario sin necesidad de guardar ninguna.
"""

from __future__ import annotations

from fastapi import Response
from sqlalchemy.orm import Session

from .config import settings
from .errors import ApiError
from .models import User
from .security import create_access_token, create_refresh_token, decode_refresh_token
from .serializers import present_user


# ---------------------------------------------------------------------------
# Cookie del refresh token
# ---------------------------------------------------------------------------


def set_refresh_cookie(response: Response, refresh_token: str, max_age: int) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=max_age,
        path=settings.REFRESH_COOKIE_PATH,
        httponly=True,  # inaccesible desde JavaScript (mitiga robo por XSS)
        secure=settings.cookie_secure,  # solo por HTTPS en produccion
        samesite="strict",  # no se envia desde otros sitios (mitiga CSRF)
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


# ---------------------------------------------------------------------------
# Emision y rotacion
# ---------------------------------------------------------------------------


def issue_tokens(user: User, response: Response, *, auth_time: int | None = None) -> dict:
    """Emite un par access+refresh. El refresh va en cookie, NO en el cuerpo."""
    access_token, expires_in = create_access_token(user)
    refresh_token, refresh_expires_in = create_refresh_token(user, auth_time=auth_time)
    set_refresh_cookie(response, refresh_token, refresh_expires_in)
    return {
        "user": present_user(user),
        "accessToken": access_token,
        "tokenType": "Bearer",
        "expiresIn": expires_in,
        "refreshExpiresIn": refresh_expires_in,
    }


def rotate_refresh_token(db: Session, refresh_token: str | None, response: Response) -> dict:
    """Valida el refresh de la cookie y emite un par nuevo (rotacion)."""
    if not refresh_token:
        raise ApiError.unauthorized("No hay sesion activa")

    payload = decode_refresh_token(refresh_token)

    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise ApiError.unauthorized("La cuenta ya no esta disponible")

    if payload["ver"] != user.token_version:
        # Token emitido antes de un logout global, cambio de rol o desactivacion.
        raise ApiError.unauthorized("Sesion revocada, vuelve a iniciar sesion")

    return issue_tokens(user, response, auth_time=int(payload["auth_time"]))


def revoke_all_for_user(db: Session, user: User) -> None:
    """Invalida todos los JWT (access y refresh) emitidos para el usuario."""
    user.token_version += 1
    db.commit()
