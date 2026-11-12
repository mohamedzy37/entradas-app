"""Rutas de autenticacion: JWT stateless (access en cabecera, refresh en cookie)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth_service import (
    clear_refresh_cookie,
    issue_tokens,
    revoke_all_for_user,
    rotate_refresh_token,
)
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..errors import ApiError
from ..models import User, UserRole
from ..schemas import LoginInput, RegisterInput
from ..security import (
    dummy_verify,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from ..serializers import present_user

router = APIRouter(prefix="/auth", tags=["auth"])


def require_trusted_origin(request: Request) -> None:
    """Defensa anti-CSRF adicional a SameSite=Strict.

    Las rutas que leen la cookie del refresh solo aceptan peticiones cuyo
    `Origin` sea el del frontend. Los navegadores siempre envian `Origin` en un
    POST con fetch; los clientes sin navegador (curl, pruebas) no lo envian y
    no pueden ser victimas de CSRF, asi que se permiten.
    """
    origin = request.headers.get("Origin")
    if origin is not None and origin not in settings.cors_origins:
        raise ApiError.forbidden("Origen no permitido")


def _refresh_cookie(request: Request) -> str | None:
    return request.cookies.get(settings.REFRESH_COOKIE_NAME)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterInput,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    existing = db.scalar(select(User).where(User.email == str(payload.email)))
    if existing is not None:
        raise ApiError.conflict("Ya existe una cuenta con ese correo electronico")

    user = User(
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        name=payload.name,
        phone=payload.phone,
        role=UserRole.CLIENT,  # el registro publico nunca concede otro rol
        is_active=True,
        token_version=0,
    )
    db.add(user)
    db.commit()

    return {"data": issue_tokens(user, response)}


@router.post("/login")
def login(
    payload: LoginInput,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    user = db.scalar(select(User).where(User.email == str(payload.email)))
    if user is None:
        # Mismo coste temporal que una verificacion real (anti-enumeracion).
        dummy_verify(payload.password)
        raise ApiError.unauthorized("Credenciales invalidas")

    if not verify_password(user.password_hash, payload.password):
        raise ApiError.unauthorized("Credenciales invalidas")

    if not user.is_active:
        raise ApiError.forbidden("La cuenta esta desactivada")

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        db.commit()

    return {"data": issue_tokens(user, response)}


@router.post(
    "/refresh",
    dependencies=[Depends(require_trusted_origin)],
    response_model=None,
)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    try:
        return {"data": rotate_refresh_token(db, _refresh_cookie(request), response)}
    except ApiError as error:
        # Si el refresh no sirve, se borra la cookie para no reintentar en bucle.
        # Se devuelve el error como respuesta propia para conservar el
        # Set-Cookie de borrado (una excepcion descartaria `response`).
        failed = JSONResponse(status_code=error.status_code, content=error.body())
        clear_refresh_cookie(failed)
        return failed


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def logout() -> Response:
    """Cierra la sesion en ESTE navegador borrando la cookie del refresh.

    Como el refresh es HttpOnly, ningun script lo ha podido leer: al borrar la
    cookie el token desaparece. El access en memoria caduca en <= 15 min.
    Para invalidar tambien otros dispositivos se usa /logout-all.
    """
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response


@router.post("/logout-all", dependencies=[Depends(require_trusted_origin)])
def logout_all(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Invalida todos los tokens del usuario en todos sus dispositivos."""
    revoke_all_for_user(db, user)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {"data": {"user": present_user(user)}}
