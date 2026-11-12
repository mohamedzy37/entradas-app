"""Esquemas de entrada (Pydantic v2)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from .models import EventStatus, EventType, UserRole

CURRENT_YEAR = datetime.now(timezone.utc).year


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _as_utc(value: object) -> object:
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# ---------------------------------------------------------------------------
# Autenticacion
# ---------------------------------------------------------------------------


class RegisterInput(BaseModel):
    name: Annotated[str, StringConstraints(min_length=2, max_length=120)]
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=8, max_length=100)]
    phone: Annotated[str | None, StringConstraints(min_length=6, max_length=30)] = None

    @field_validator("name", "phone", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        return _strip(value)

    @field_validator("email", mode="before")
    @classmethod
    def _lower_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def _email_length(cls, value: EmailStr) -> EmailStr:
        if len(str(value)) > 160:
            raise ValueError("Email invalido")
        return value

    @field_validator("password")
    @classmethod
    def _strong_password(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("La contrasena debe incluir al menos una letra")
        if not re.search(r"\d", value):
            raise ValueError("La contrasena debe incluir al menos un numero")
        return value


class LoginInput(BaseModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=1, max_length=100)]

    @field_validator("email", mode="before")
    @classmethod
    def _lower_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


# ---------------------------------------------------------------------------
# Pedidos
# ---------------------------------------------------------------------------


class BuyerInput(BaseModel):
    name: Annotated[str, StringConstraints(min_length=2, max_length=120)]
    email: EmailStr
    phone: Annotated[str | None, StringConstraints(min_length=6, max_length=30)] = None

    @field_validator("name", "phone", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        return _strip(value)

    @field_validator("email", mode="before")
    @classmethod
    def _lower_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class OrderItemInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticket_type_id: Annotated[str, StringConstraints(min_length=1, max_length=64)] = Field(
        alias="ticketTypeId"
    )
    quantity: int = Field(ge=1, le=50)


class CreateOrderInput(BaseModel):
    buyer: BuyerInput
    items: list[OrderItemInput] = Field(min_length=1, max_length=20)


class PayOrderInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    card_number: str = Field(alias="cardNumber")
    card_holder: Annotated[str, StringConstraints(min_length=3, max_length=120)] = Field(
        alias="cardHolder"
    )
    expiry_month: int = Field(alias="expiryMonth", ge=1, le=12)
    expiry_year: int = Field(alias="expiryYear", ge=CURRENT_YEAR, le=CURRENT_YEAR + 30)
    cvv: str

    @field_validator("card_number", "card_holder", "cvv", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        return _strip(value)

    @field_validator("card_number")
    @classmethod
    def _card_number(cls, value: str) -> str:
        digits = re.sub(r"\s+", "", value)
        if not re.fullmatch(r"\d{12,19}", digits):
            raise ValueError("Numero de tarjeta invalido (12-19 digitos)")
        return digits

    @field_validator("card_holder")
    @classmethod
    def _holder(cls, value: str) -> str:
        if len(value) < 3:
            raise ValueError("El titular es demasiado corto")
        return value

    @field_validator("cvv")
    @classmethod
    def _cvv(cls, value: str) -> str:
        if not re.fullmatch(r"\d{3,4}", value):
            raise ValueError("CVV invalido (3-4 digitos)")
        return value


# ---------------------------------------------------------------------------
# Administracion / gestion
# ---------------------------------------------------------------------------


class RoleUpdateInput(BaseModel):
    role: UserRole


class ActiveUpdateInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    is_active: bool = Field(alias="isActive")


class VenueCreateInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Annotated[str, StringConstraints(min_length=2, max_length=160)]
    address: Annotated[str, StringConstraints(min_length=2, max_length=200)]
    city: Annotated[str, StringConstraints(min_length=2, max_length=120)]
    country: Annotated[str, StringConstraints(min_length=2, max_length=80)] = "ES"
    capacity: int | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("name", "address", "city", "country", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        return _strip(value)


class VenueUpdateInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Annotated[str | None, StringConstraints(min_length=2, max_length=160)] = None
    address: Annotated[str | None, StringConstraints(min_length=2, max_length=200)] = None
    city: Annotated[str | None, StringConstraints(min_length=2, max_length=120)] = None
    country: Annotated[str | None, StringConstraints(min_length=2, max_length=80)] = None
    capacity: int | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("name", "address", "city", "country", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        return _strip(value)


class EventCreateInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: Annotated[str, StringConstraints(min_length=2, max_length=200)]
    description: str | None = None
    type: EventType
    status: EventStatus = EventStatus.PUBLISHED
    image_url: Annotated[str | None, StringConstraints(max_length=500)] = Field(
        default=None, alias="imageUrl"
    )
    start_at: datetime = Field(alias="startAt")
    end_at: datetime | None = Field(default=None, alias="endAt")
    doors_open_at: datetime | None = Field(default=None, alias="doorsOpenAt")
    category_id: str | None = Field(default=None, alias="categoryId", max_length=64)
    venue_id: str = Field(alias="venueId", min_length=1, max_length=64)

    @field_validator("title", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        return _strip(value)

    @field_validator("start_at", "end_at", "doors_open_at", mode="before")
    @classmethod
    def _utc(cls, value: object) -> object:
        return _as_utc(value)

    @model_validator(mode="after")
    def _dates(self) -> "EventCreateInput":
        if self.end_at and self.end_at < self.start_at:
            raise ValueError("La fecha de fin no puede ser anterior al inicio")
        return self


class EventUpdateInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: Annotated[str | None, StringConstraints(min_length=2, max_length=200)] = None
    description: str | None = None
    type: EventType | None = None
    status: EventStatus | None = None
    image_url: Annotated[str | None, StringConstraints(max_length=500)] = Field(
        default=None, alias="imageUrl"
    )
    start_at: datetime | None = Field(default=None, alias="startAt")
    end_at: datetime | None = Field(default=None, alias="endAt")
    doors_open_at: datetime | None = Field(default=None, alias="doorsOpenAt")
    category_id: str | None = Field(default=None, alias="categoryId", max_length=64)
    venue_id: str | None = Field(default=None, alias="venueId", max_length=64)
    min_price_cents: int | None = Field(default=None, alias="minPriceCents", ge=0)

    @field_validator("title", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        return _strip(value)

    @field_validator("start_at", "end_at", "doors_open_at", mode="before")
    @classmethod
    def _utc(cls, value: object) -> object:
        return _as_utc(value)


class TicketTypeCreateInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    description: str | None = None
    price_cents: int = Field(alias="priceCents", ge=0)
    currency: Annotated[str, StringConstraints(min_length=3, max_length=3)] = "EUR"
    quantity_total: int = Field(alias="quantityTotal", ge=1, le=1_000_000)
    max_per_order: int = Field(alias="maxPerOrder", default=10, ge=1, le=50)
    is_active: bool = Field(alias="isActive", default=True)

    @field_validator("name", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        return _strip(value)


class TicketTypeUpdateInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Annotated[str | None, StringConstraints(min_length=1, max_length=120)] = None
    description: str | None = None
    price_cents: int | None = Field(default=None, alias="priceCents", ge=0)
    quantity_total: int | None = Field(alias="quantityTotal", default=None, ge=1)
    max_per_order: int | None = Field(alias="maxPerOrder", default=None, ge=1, le=50)
    is_active: bool | None = Field(alias="isActive", default=None)

    @field_validator("name", mode="before")
    @classmethod
    def _clean(cls, value: object) -> object:
        return _strip(value)
