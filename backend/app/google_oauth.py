"""Login con Google mediante OpenID Connect.

Flujo "Authorization Code" con PKCE, `state` y `nonce`, ejecutado por el
BACKEND. El navegador solo hace redirecciones: no se carga ningun script de
Google en la pagina, asi que la CSP sigue siendo estricta.

1. GET /api/auth/google/login
   - Genera `state` (anti-CSRF), `nonce` (anti-replay del ID token) y un
     `code_verifier` PKCE.
   - Los guarda en una cookie FIRMADA, HttpOnly, de 10 minutos y limitada a
     /api/auth/google. Asi el flujo sigue siendo stateless: el servidor no
     guarda nada entre la ida y la vuelta.
   - Redirige a Google con el `code_challenge` (SHA-256 del verifier).
2. Google autentica al usuario y vuelve a GET /api/auth/google/callback con
   `code` y `state`.
   - Se comprueba que `state` coincide con el de la cookie.
   - El backend canjea el `code` por tokens en el endpoint de Google, de
     servidor a servidor, con el client secret y el `code_verifier`.
   - Se verifica el ID token: firma RS256 con las claves publicas de Google
     (JWKS), `iss`, `aud` = nuestro client id, `exp`, `nonce` y
     `email_verified`.
3. Se busca o crea el usuario (rol CLIENT) y se emite NUESTRA sesion: la cookie
   del refresh token, exactamente igual que en el login con contrasena.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

import jwt

from .config import settings

logger = logging.getLogger("entradas.google")

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

STATE_COOKIE_NAME = "google_oauth"
STATE_COOKIE_PATH = "/api/auth/google"
STATE_TTL_SECONDS = 600
_STATE_TYPE = "google_oauth_state"


class GoogleAuthError(Exception):
    """Fallo en el flujo de Google. `reason` solo se registra en el log."""

    def __init__(self, reason: str, *, public_code: str = "google") -> None:
        super().__init__(reason)
        self.reason = reason
        self.public_code = public_code


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def pkce_challenge(verifier: str) -> str:
    """code_challenge S256 = BASE64URL(SHA256(code_verifier))."""
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def safe_next(value: str | None) -> str:
    """Destino tras el login: SOLO rutas relativas de la propia web.

    Evita que el parametro `next` se use como redireccion abierta hacia otro
    dominio (p. ej. `//evil.com` o `https://evil.com`).
    """
    if not value or len(value) > 200:
        return "/"
    if not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        return "/"
    if any(ord(ch) < 32 or ch == "\\" for ch in value):
        return "/"
    return value


# ---------------------------------------------------------------------------
# Paso 1: inicio del login
# ---------------------------------------------------------------------------


def start_login(next_path: str) -> tuple[str, str]:
    """Devuelve (url_de_google, valor_de_la_cookie_de_estado)."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)  # 86 caracteres (RFC 7636: 43-128)
    now = int(time.time())

    state_cookie = jwt.encode(
        {
            "type": _STATE_TYPE,
            "state": state,
            "nonce": nonce,
            "cv": code_verifier,
            "next": safe_next(next_path),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "iat": now,
            "exp": now + STATE_TTL_SECONDS,
        },
        settings.JWT_REFRESH_SECRET,
        algorithm="HS256",
    )

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": pkce_challenge(code_verifier),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}", state_cookie


def read_state_cookie(value: str | None) -> dict[str, Any]:
    if not value:
        raise GoogleAuthError("Falta la cookie de estado (caducada o bloqueada)")
    try:
        data = jwt.decode(
            value,
            settings.JWT_REFRESH_SECRET,
            algorithms=["HS256"],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "state", "nonce", "cv", "type"]},
        )
    except jwt.InvalidTokenError as exc:
        raise GoogleAuthError(f"Cookie de estado invalida: {exc}") from exc
    if data.get("type") != _STATE_TYPE:
        raise GoogleAuthError("Cookie de estado de otro tipo")
    return data


def check_state(saved_state: str, received_state: str | None) -> None:
    if not received_state or not hmac.compare_digest(saved_state, received_state):
        raise GoogleAuthError("El parametro state no coincide (posible CSRF)")


# ---------------------------------------------------------------------------
# Paso 2: canje del code y verificacion del ID token
# ---------------------------------------------------------------------------


def exchange_code(code: str, code_verifier: str) -> dict[str, Any]:
    """Canjea el code por tokens (servidor a servidor, con client secret)."""
    body = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        }
    ).encode("ascii")
    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise GoogleAuthError(f"Google rechazo el code ({exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise GoogleAuthError(f"No se pudo contactar con Google: {exc}") from exc

    if "id_token" not in payload:
        raise GoogleAuthError("La respuesta de Google no incluye id_token")
    return payload


_jwks_client: jwt.PyJWKClient | None = None


def _google_signing_key(id_token: str) -> Any:
    """Clave publica de Google que firmo el token (JWKS con cache de 1 h)."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(JWKS_URI, cache_keys=True, lifespan=3600)
    try:
        return _jwks_client.get_signing_key_from_jwt(id_token).key
    except jwt.PyJWKClientError as exc:
        raise GoogleAuthError(f"No se pudo obtener la clave de Google: {exc}") from exc


def verify_id_token(
    id_token: str,
    expected_nonce: str,
    *,
    key_resolver: Callable[[str], Any] = _google_signing_key,
) -> dict[str, Any]:
    """Valida el ID token de Google y devuelve sus claims."""
    key = key_resolver(id_token)
    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],  # nunca "none" ni HS256 con la clave publica
            audience=settings.GOOGLE_CLIENT_ID,
            issuer=list(GOOGLE_ISSUERS),
            leeway=30,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.InvalidTokenError as exc:
        raise GoogleAuthError(f"ID token invalido: {exc}") from exc

    if not hmac.compare_digest(str(claims.get("nonce", "")), expected_nonce):
        raise GoogleAuthError("El nonce del ID token no coincide (posible replay)")
    if not claims.get("email"):
        raise GoogleAuthError("El ID token no incluye email")
    if claims.get("email_verified") is not True:
        raise GoogleAuthError("Email de Google no verificado", public_code="google_email")
    return claims
