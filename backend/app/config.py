"""Configuracion central de la API (12-factor: todo por variables de entorno)."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Aplicacion ---
    APP_NAME: str = "Entradas API"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"  # development | production
    PORT: int = Field(default=3000, ge=1, le=65535)
    # Documentacion interactiva (/docs, /redoc, /openapi.json).
    # Sin definir = automatico: activa en desarrollo, desactivada en produccion
    # para no publicar el mapa completo de la API.
    ENABLE_DOCS: bool | None = None

    # --- Base de datos ---
    DATABASE_URL: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/entradas_py"
    )

    # --- Negocio ---
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    ORDER_RESERVATION_MINUTES: int = Field(default=15, ge=1, le=120)
    DEFAULT_CURRENCY: str = Field(default="EUR", min_length=3, max_length=3)

    # --- Seguridad / JWT ---
    # Sesion 100 % stateless: access y refresh son JWT firmados con secretos
    # distintos. El servidor no guarda ningun token ni sesion.
    JWT_SECRET: str = "dev-secret-cambiar-en-produccion-0123456789abcdef"
    JWT_REFRESH_SECRET: str = "dev-secret-refresh-cambiar-en-produccion-fedcba9876"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "entradas-api"
    JWT_AUDIENCE: str = "entradas-web"
    ACCESS_TOKEN_TTL_MINUTES: int = Field(default=15, ge=1, le=120)
    REFRESH_TOKEN_TTL_DAYS: int = Field(default=7, ge=1, le=30)

    # --- Cookie del refresh token ---
    # HttpOnly (inaccesible para JS), SameSite=Strict (no viaja en peticiones
    # de otros sitios: anti-CSRF) y Path limitado a /api/auth.
    # COOKIE_SECURE vacio = automatico: Secure en produccion.
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_PATH: str = "/api/auth"
    COOKIE_SECURE: bool | None = None

    # --- Login con Google (OpenID Connect) ---
    # Credenciales de un "ID de cliente de OAuth" (tipo aplicacion web) de
    # Google Cloud. Si GOOGLE_CLIENT_ID esta vacio, el login con Google se
    # desactiva. GOOGLE_REDIRECT_URI debe coincidir EXACTAMENTE con la URI
    # autorizada en Google Cloud, p. ej. https://localhost/api/auth/google/callback
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # --- Limitacion de peticiones (auth) ---
    AUTH_RATE_LIMIT_PER_MINUTE: int = Field(default=20, ge=1, le=1000)

    @field_validator("ENVIRONMENT")
    @classmethod
    def _valid_environment(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"development", "production", "test"}:
            raise ValueError("ENVIRONMENT debe ser development, test o production")
        return value

    @field_validator("JWT_SECRET", "JWT_REFRESH_SECRET")
    @classmethod
    def _strong_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("Los secretos JWT deben tener al menos 32 caracteres")
        return value

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.CORS_ORIGINS.split(",") if item.strip()]

    @property
    def google_enabled(self) -> bool:
        return bool(
            self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET and self.GOOGLE_REDIRECT_URI
        )

    @property
    def docs_enabled(self) -> bool:
        if self.ENABLE_DOCS is None:
            return not self.is_production
        return self.ENABLE_DOCS

    @property
    def cookie_secure(self) -> bool:
        if self.COOKIE_SECURE is None:
            return self.is_production
        return self.COOKIE_SECURE

    @property
    def refresh_ttl_seconds(self) -> int:
        return self.REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production:
        if settings.JWT_SECRET.startswith("dev-secret") or settings.JWT_REFRESH_SECRET.startswith(
            "dev-secret"
        ):
            raise RuntimeError(
                "Secretos JWT inseguros: cambia los de desarrollo antes de produccion"
            )
        if settings.JWT_SECRET == settings.JWT_REFRESH_SECRET:
            raise RuntimeError("JWT_SECRET y JWT_REFRESH_SECRET deben ser distintos")
        if not settings.cookie_secure:
            raise RuntimeError("En produccion la cookie del refresh debe ser Secure")
    return settings


settings = get_settings()
