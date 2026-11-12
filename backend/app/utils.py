"""Utilidades de formato (dinero, fechas y paginacion)."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from .config import settings


def format_money(cents: int, currency: str | None = None) -> str:
    """Formatea centimos como moneda es-ES, p. ej. 3000 -> '30,00 EUR'."""
    currency = (currency or settings.DEFAULT_CURRENCY).upper()
    value = cents / 100
    text = f"{value:,.2f}"  # 1,234.56
    text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    symbol = "\u20ac" if currency == "EUR" else currency
    separator = "\u00a0" if currency == "EUR" else " "
    return f"{text}{separator}{symbol}"


def iso(value: datetime | None) -> str | None:
    """Serializa una fecha como ISO-8601 UTC con milisegundos y sufijo Z."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def pagination_meta(total: int, page: int, limit: int) -> dict:
    total_pages = math.ceil(total / limit) if limit > 0 else 0
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "totalPages": total_pages,
        "hasNext": page < total_pages,
        "hasPrev": page > 1,
    }


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
