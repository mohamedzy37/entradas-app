"""Modelos de datos (SQLAlchemy 2.0).

Diseno alineado con el dominio de venta de entradas y con los requisitos de
seguridad del enunciado:

- `User.role` implementa el sistema de roles (ADMIN, MANAGER, CLIENT).
- No hay tabla de sesiones ni de tokens: la sesion es 100 % stateless.
  `User.token_version` es un contador que viaja dentro de los JWT; al
  incrementarlo se invalidan todos los tokens emitidos para ese usuario.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .ids import new_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sa_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Enum almacenado como VARCHAR (sin tipos nativos de PostgreSQL)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


# Marcador de "sin contrasena": no es un hash Argon2 valido, asi que
# verify_password() siempre devuelve False y no se puede entrar con contrasena.
UNUSABLE_PASSWORD = "!sin-contrasena"


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    CLIENT = "CLIENT"


class EventType(str, enum.Enum):
    MUSEUM = "MUSEUM"
    FOOTBALL = "FOOTBALL"
    CINEMA = "CINEMA"
    FESTIVAL = "FESTIVAL"
    CONCERT = "CONCERT"
    THEATER = "THEATER"
    OTHER = "OTHER"


class EventStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    SOLD_OUT = "SOLD_OUT"
    CANCELLED = "CANCELLED"
    FINISHED = "FINISHED"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    EXPIRED = "EXPIRED"


class TicketStatus(str, enum.Enum):
    VALID = "VALID"
    USED = "USED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REFUNDED = "REFUNDED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    role: Mapped[UserRole] = mapped_column(
        sa_enum(UserRole, "user_role"), default=UserRole.CLIENT, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Version de credenciales: se incrementa para invalidar todos los JWT del
    # usuario (logout global, cambio de rol o desactivacion). No es una sesion:
    # es un unico entero por usuario, no un registro por login.
    token_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    # Identificador estable de la cuenta de Google ("sub" del ID token) si el
    # usuario ha iniciado sesion con Google. Las cuentas creadas solo con
    # Google no tienen contrasena utilizable (password_hash = UNUSABLE_PASSWORD).
    google_sub: Mapped[str | None] = mapped_column(String(255))
    orders: Mapped[list["Order"]] = relationship(back_populates="user")

    __table_args__ = (Index("uq_users_google_sub", "google_sub", unique=True),)


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)

    events: Mapped[list["Event"]] = relationship(back_populates="category")


class Venue(Base, TimestampMixin):
    __tablename__ = "venues"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    country: Mapped[str] = mapped_column(String(80), default="ES", nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    events: Mapped[list["Event"]] = relationship(back_populates="venue")


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[EventType] = mapped_column(sa_enum(EventType, "event_type"), nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        sa_enum(EventStatus, "event_status"),
        default=EventStatus.PUBLISHED,
        index=True,
        nullable=False,
    )
    image_url: Mapped[str | None] = mapped_column(String(500))
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    doors_open_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    min_price_cents: Mapped[int | None] = mapped_column(Integer)
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    venue_id: Mapped[str] = mapped_column(
        ForeignKey("venues.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    category: Mapped[Category | None] = relationship(back_populates="events")
    venue: Mapped[Venue] = relationship(back_populates="events")
    ticket_types: Mapped[list["TicketType"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TicketType.price_cents",
    )
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="event")


class TicketType(Base, TimestampMixin):
    __tablename__ = "ticket_types"
    __table_args__ = (
        UniqueConstraint("event_id", "name", name="uq_ticket_type_event_name"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    quantity_total: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_sold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_per_order: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    event: Mapped[Event] = relationship(back_populates="ticket_types")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="ticket_type")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="ticket_type")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    reference: Mapped[str] = mapped_column(
        String(40), unique=True, index=True, nullable=False
    )
    buyer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    buyer_email: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    buyer_phone: Mapped[str | None] = mapped_column(String(30))
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        sa_enum(OrderStatus, "order_status"),
        default=OrderStatus.PENDING,
        index=True,
        nullable=False,
    )
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User | None] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OrderItem.created_at",
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Ticket.created_at",
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Payment.created_at",
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticket_type_id: Mapped[str] = mapped_column(
        ForeignKey("ticket_types.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="items")
    ticket_type: Mapped[TicketType] = relationship(back_populates="order_items")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ticket_type_id: Mapped[str] = mapped_column(
        ForeignKey("ticket_types.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    holder_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[TicketStatus] = mapped_column(
        sa_enum(TicketStatus, "ticket_status"),
        default=TicketStatus.VALID,
        index=True,
        nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="tickets")
    event: Mapped[Event] = relationship(back_populates="tickets")
    ticket_type: Mapped[TicketType] = relationship(back_populates="tickets")

    __table_args__ = (Index("ix_tickets_event_status", "event_id", "status"),)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(40), default="SIMULATED", nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        sa_enum(PaymentStatus, "payment_status"),
        default=PaymentStatus.PENDING,
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    card_last4: Mapped[str | None] = mapped_column(String(4))
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    order: Mapped[Order] = relationship(back_populates="payments")
