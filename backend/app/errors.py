"""Errores de aplicacion y formato uniforme de respuesta de error."""

from __future__ import annotations

from typing import Any


def _default_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        402: "PAYMENT_REQUIRED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
    }.get(status_code, "INTERNAL_ERROR" if status_code >= 500 else "ERROR")


class ApiError(Exception):
    """Error de negocio con codigo HTTP y codigo estable."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        code: str | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.code = code or _default_code(status_code)
        self.details = details

    @staticmethod
    def bad_request(message: str = "Solicitud invalida", details: Any = None) -> "ApiError":
        return ApiError(400, message, details=details)

    @staticmethod
    def unauthorized(message: str = "No autorizado") -> "ApiError":
        return ApiError(401, message)

    @staticmethod
    def payment_required(message: str = "Pago requerido") -> "ApiError":
        return ApiError(402, message)

    @staticmethod
    def forbidden(message: str = "Acceso denegado") -> "ApiError":
        return ApiError(403, message)

    @staticmethod
    def not_found(message: str = "Recurso no encontrado") -> "ApiError":
        return ApiError(404, message)

    @staticmethod
    def conflict(message: str = "Conflicto con el estado actual del recurso") -> "ApiError":
        return ApiError(409, message)

    @staticmethod
    def too_many_requests(message: str = "Demasiadas peticiones") -> "ApiError":
        return ApiError(429, message)

    @staticmethod
    def internal(message: str = "Error interno del servidor") -> "ApiError":
        return ApiError(500, message)

    def body(self) -> dict:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        return {"error": error}
