"""Primitivas de seguridad: hash de contrasenas y JWT (access + refresh).

Requisito del enunciado: la sesion NO se almacena en el backend. Por eso:

- Access token = JWT firmado (HS256), vida corta (15 min por defecto). Viaja en
  `Authorization: Bearer` y el navegador lo guarda SOLO en memoria.
- Refresh token = JWT firmado con OTRO secreto, vida larga (7 dias). Viaja en
  una cookie HttpOnly/Secure/SameSite=Strict limitada a /api/auth, de modo que
  JavaScript (y por tanto un XSS) no puede leerlo. El servidor no guarda nada.
- Ambos llevan `ver` = User.token_version. Incrementar ese contador invalida
  de golpe todos los tokens del usuario (logout global, cambio de rol,
  desactivacion) sin tabla de sesiones.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import settings
from .errors import ApiError
from .models import User

# Argon2id con parametros recomendados por OWASP (2024+).
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Hash de relleno para igualar tiempos de respuesta cuando el usuario no existe
# y evitar enumeracion de cuentas por temporizacion.
_DUMMY_HASH = _hasher.hash("timing-equalizer-not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def dummy_verify(password: str) -> None:
    """Consume tiempo similar a una verificacion real (anti-enumeracion)."""
    try:
        _hasher.verify(_DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        pass


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


# ---------------------------------------------------------------------------
# Access token (JWT)
# ---------------------------------------------------------------------------


def create_access_token(user: User) -> tuple[str, int]:
    """Devuelve (jwt, segundos_de_vida)."""
    now = datetime.now(timezone.utc)
    expires_in = settings.ACCESS_TOKEN_TTL_MINUTES * 60
    payload: dict[str, Any] = {
        "sub": user.id,
        "email": user.email,
        "role": user.role.value,
        "type": "access",
        "ver": user.token_version,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "type", "ver"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ApiError.unauthorized("Sesion expirada, vuelve a iniciar sesion") from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError.unauthorized("Token invalido") from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise ApiError.unauthorized("Token invalido")
    return payload


# ---------------------------------------------------------------------------
# Refresh token (JWT stateless)
# ---------------------------------------------------------------------------


def create_refresh_token(user: User, *, auth_time: int | None = None) -> tuple[str, int]:
    """Devuelve (jwt_refresh, segundos_de_vida).

    El refresh es un JWT firmado con un secreto DISTINTO al del access token y
    con `type=refresh`, de modo que uno nunca puede usarse en lugar del otro.
    No se guarda nada en el servidor.

    `auth_time` es el instante del login original. Al rotar se conserva, y la
    caducidad se calcula desde el: la sesion tiene una vida maxima absoluta y
    no puede alargarse indefinidamente refrescando.
    """
    now = int(datetime.now(timezone.utc).timestamp())
    auth_time = auth_time or now
    exp = auth_time + settings.refresh_ttl_seconds
    payload: dict[str, Any] = {
        "sub": user.id,
        "type": "refresh",
        "ver": user.token_version,
        "auth_time": auth_time,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "exp": exp,
        "jti": secrets.token_hex(16),
    }
    token = jwt.encode(
        payload, settings.JWT_REFRESH_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return token, max(exp - now, 0)


def decode_refresh_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_REFRESH_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "type", "ver", "auth_time"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ApiError.unauthorized("Sesion expirada, vuelve a iniciar sesion") from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError.unauthorized("Refresh token invalido") from exc

    if payload.get("type") != "refresh" or not payload.get("sub"):
        raise ApiError.unauthorized("Refresh token invalido")
    return payload
