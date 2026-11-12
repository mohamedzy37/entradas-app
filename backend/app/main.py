"""Aplicacion FastAPI de Entradas.

Seguridad de la puesta en produccion:
- Sesion stateless (no se guarda en el backend): access JWT en
  `Authorization: Bearer` y refresh JWT en cookie HttpOnly/Secure/SameSite.
- CORS restringido a una lista explicita de origenes del frontend.
- Cabeceras de seguridad y CSP estricta en las rutas de API.
- Rate limiting en login/registro/refresh.
- Errores uniformes sin filtrar detalles internos en produccion.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .database import Base, engine
from .migrations import apply_schema_updates
from .errors import ApiError
from .routers import admin, auth, catalog, orders, tickets

logger = logging.getLogger("entradas")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API REST de venta de entradas. Autenticacion JWT 100 % stateless: "
        "access token de vida corta en cabecera Bearer y refresh token JWT "
        "rotatorio en cookie HttpOnly. Roles: ADMIN, MANAGER y CLIENT."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.on_event("startup")
def on_startup() -> None:
    # En un despliegue real se usaria Alembic; aqui creamos el esquema si falta.
    try:
        Base.metadata.create_all(bind=engine)
        apply_schema_updates(engine)
    except Exception:  # pragma: no cover - solo para arranque sin BD
        logger.exception(
            "No se pudo crear el esquema. Ejecuta 'python scripts/init_db.py'."
        )


# ---------------------------------------------------------------------------
# Rate limiting en memoria (por IP y ruta)
# ---------------------------------------------------------------------------

RATE_LIMITED_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/refresh",
    "/api/auth/logout",
}
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if request.method == "POST" and path in RATE_LIMITED_PATHS:
        client = request.client.host if request.client else "desconocido"
        key = (client, path)
        now = time.monotonic()
        window = 60.0
        with_hits = _hits[key]
        while with_hits and now - with_hits[0] > window:
            with_hits.popleft()
        if len(with_hits) >= settings.AUTH_RATE_LIMIT_PER_MINUTE:
            retry_after = max(1, int(window - (now - with_hits[0])) + 1)
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "TOO_MANY_REQUESTS",
                        "message": "Demasiadas peticiones. Intentalo de nuevo en unos segundos.",
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )
        with_hits.append(now)
    return await call_next(request)


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    if request.url.path.startswith("/api") or request.url.path == "/health":
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains"
        )
    return response


app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)

# CORS se anade el ultimo para ser el middleware mas externo y aplicar tambien
# a las respuestas de error (incluido el 429).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Necesario solo si el frontend se sirve desde otro origen: permite que la
    # cookie del refresh viaje a /api/auth. Seguro porque la lista de origenes
    # es explicita (nunca "*").
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Retry-After"],
    max_age=600,
)


# ---------------------------------------------------------------------------
# Manejo uniforme de errores
# ---------------------------------------------------------------------------


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.body())


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    details = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", ())]
        if location and location[0] in {"body", "query", "path", "header"}:
            location = location[1:]
        details.append(
            {
                "path": ".".join(location),
                "message": error.get("msg", "Dato invalido"),
            }
        )
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Datos de entrada invalidos",
                "details": details,
            }
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("Conflicto de integridad: %s", exc)
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "CONFLICT",
                "message": "Ya existe un registro con esos datos",
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": "Ruta no encontrada"}},
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "ERROR", "message": str(exc.detail)}},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error no controlado: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Error interno del servidor",
            }
        },
    )


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------


@app.get("/health", tags=["salud"])
def health() -> JSONResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: base de datos no disponible")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unavailable"},
        )
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "database": "ok",
            "version": settings.APP_VERSION,
        },
    )


@app.get("/api", tags=["salud"])
def api_info() -> dict:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "auth": "JWT stateless: access en Authorization: Bearer, refresh en cookie HttpOnly",
        "roles": ["ADMIN", "MANAGER", "CLIENT"],
        "docs": "/docs",
        "endpoints": {
            "auth": [
                "POST /api/auth/register",
                "POST /api/auth/login",
                "POST /api/auth/refresh",
                "POST /api/auth/logout",
                "POST /api/auth/logout-all",
                "GET /api/auth/me",
            ],
            "catalogo": [
                "GET /api/categories",
                "GET /api/venues",
                "GET /api/venues/{id}",
                "GET /api/events",
                "GET /api/events/{idOrSlug}",
            ],
            "pedidos": [
                "GET /api/orders",
                "POST /api/orders",
                "GET /api/orders/{reference}",
                "POST /api/orders/{reference}/pay",
                "POST /api/orders/{reference}/cancel",
            ],
            "entradas": [
                "GET /api/tickets/{code}",
                "POST /api/tickets/{code}/check-in (MANAGER/ADMIN)",
            ],
            "administracion": [
                "GET /api/admin/users (ADMIN)",
                "PATCH /api/admin/users/{id}/role (ADMIN)",
                "PATCH /api/admin/users/{id}/active (ADMIN)",
                "GET /api/admin/orders (MANAGER/ADMIN)",
                "GET /api/admin/stats (MANAGER/ADMIN)",
                "POST/PATCH/DELETE /api/admin/events (MANAGER/ADMIN)",
                "POST/PATCH/DELETE /api/admin/ticket-types (MANAGER/ADMIN)",
                "POST/PATCH/DELETE /api/admin/venues (MANAGER/ADMIN)",
            ],
        },
    }


app.include_router(auth.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(tickets.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
