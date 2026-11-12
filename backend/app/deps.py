"""Dependencias de autenticacion y autorizacion por roles.

El access token viaja en la cabecera `Authorization: Bearer <jwt>` (nunca en
cookie). La unica cookie de la aplicacion es la del refresh token, que solo se
envia a /api/auth y no sirve para autenticar el resto de rutas.
"""

from __future__ import annotations

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .errors import ApiError
from .models import User, UserRole
from .security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False, description="JWT de acceso")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise ApiError.unauthorized("Inicia sesion para continuar")

    payload = decode_access_token(credentials.credentials)
    user = db.get(User, payload["sub"])
    if user is None:
        raise ApiError.unauthorized("La cuenta ya no existe")
    if not user.is_active:
        raise ApiError.forbidden("La cuenta esta desactivada")
    if payload.get("ver") != user.token_version:
        # Token anterior a un logout global, cambio de rol o desactivacion.
        raise ApiError.unauthorized("Sesion revocada, vuelve a iniciar sesion")

    # La autorizacion se basa en el rol actual de la BD, no en el del token:
    # un cambio de rol surte efecto de inmediato.
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None or not credentials.credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
    except ApiError:
        return None
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active or payload.get("ver") != user.token_version:
        return None
    return user


def require_roles(*roles: UserRole):
    """Fabrica de dependencias: exige uno de los roles indicados."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ApiError.forbidden("No tienes permisos para realizar esta accion")
        return user

    return dependency


require_admin = require_roles(UserRole.ADMIN)
require_manager = require_roles(UserRole.ADMIN, UserRole.MANAGER)
require_client = require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.CLIENT)
