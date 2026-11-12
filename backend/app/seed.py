"""Carga inicial de datos: catalogo, usuarios demo y pedidos de ejemplo.

El catalogo se lee de `app/data/seed.json`, exportado del proyecto original.
Las fechas del JSON son desplazamientos en dias, de modo que al re-sembrar en
cualquier fecha los eventos siguen quedando en el futuro.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ids import new_id
from .models import (
    Category,
    Event,
    EventStatus,
    EventType,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
    Ticket,
    TicketStatus,
    TicketType,
    User,
    UserRole,
    Venue,
)
from .security import hash_password, verify_password
from .utils import utcnow

logger = logging.getLogger("entradas.seed")

SEED_FILE = Path(__file__).parent / "data" / "seed.json"

DEMO_USERS = (
    {
        "id": "user-demo",
        "email": "ana.garcia@ejemplo.com",
        "name": "Ana Garcia",
        "phone": "+34 600 111 222",
        "password": "demo1234",
        "role": UserRole.CLIENT,
    },
    {
        "id": "user-manager",
        "email": "gestor@entradas.com",
        "name": "Gestor de eventos",
        "phone": "+34 600 222 333",
        "password": "Gestor1234",
        "role": UserRole.MANAGER,
    },
    {
        "id": "user-admin",
        "email": "admin@entradas.com",
        "name": "Administrador",
        "phone": "+34 600 333 444",
        "password": "Admin1234",
        "role": UserRole.ADMIN,
    },
)


def _load_json() -> dict:
    if not SEED_FILE.exists():
        raise RuntimeError(
            f"No se encuentra {SEED_FILE}. Ejecuta el exportador del proyecto original."
        )
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def _upsert_categories(db: Session, rows: list[dict]) -> None:
    for row in rows:
        category = db.get(Category, row["id"])
        if category is None:
            db.add(Category(id=row["id"], name=row["name"], slug=row["slug"]))
        else:
            category.name = row["name"]
            category.slug = row["slug"]


def _upsert_venues(db: Session, rows: list[dict]) -> None:
    for row in rows:
        venue = db.get(Venue, row["id"])
        values = {
            "name": row["name"],
            "address": row["address"],
            "city": row["city"],
            "country": row["country"],
            "capacity": row.get("capacity"),
            "latitude": row.get("latitude"),
            "longitude": row.get("longitude"),
        }
        if venue is None:
            db.add(Venue(id=row["id"], **values))
        else:
            for key, value in values.items():
                setattr(venue, key, value)


def _event_dates(row: dict) -> dict:
    now = utcnow()

    def at(offset: int | None):
        return now + timedelta(days=offset) if offset is not None else None

    return {
        "start_at": at(row.get("startOffsetDays")),
        "end_at": at(row.get("endOffsetDays")),
        "doors_open_at": at(row.get("doorsOpenOffsetDays")),
    }


def _upsert_events(db: Session, rows: list[dict]) -> None:
    for row in rows:
        dates = _event_dates(row)
        event = db.get(Event, row["id"])
        values = {
            "title": row["title"],
            "slug": row["slug"],
            "description": row.get("description"),
            "type": EventType(row["type"]),
            "status": EventStatus(row["status"]),
            "image_url": row.get("imageUrl"),
            "start_at": dates["start_at"],
            "end_at": dates["end_at"],
            "doors_open_at": dates["doors_open_at"],
            "category_id": row.get("categoryId"),
            "venue_id": row["venueId"],
        }
        if event is None:
            event = Event(id=row["id"], **values)
            db.add(event)
        else:
            for key, value in values.items():
                setattr(event, key, value)

        for tt in row.get("ticketTypes", []):
            ticket_type = db.get(TicketType, tt["id"])
            tt_values = {
                "event_id": row["id"],
                "name": tt["name"],
                "description": tt.get("description"),
                "price_cents": tt["priceCents"],
                "currency": tt.get("currency") or "EUR",
                "quantity_total": tt["quantityTotal"],
                "max_per_order": tt.get("maxPerOrder") or 10,
                "is_active": tt.get("isActive", True),
            }
            if ticket_type is None:
                db.add(TicketType(id=tt["id"], quantity_sold=0, **tt_values))
            else:
                for key, value in tt_values.items():
                    setattr(ticket_type, key, value)
                if ticket_type.quantity_total < ticket_type.quantity_sold:
                    ticket_type.quantity_total = ticket_type.quantity_sold

    db.flush()

    # Precio minimo por evento a partir de sus tipos de entrada activos.
    for row in rows:
        prices = db.scalars(
            select(TicketType.price_cents).where(
                TicketType.event_id == row["id"], TicketType.is_active.is_(True)
            )
        ).all()
        event = db.get(Event, row["id"])
        if event is not None:
            event.min_price_cents = min(prices) if prices else None


def _upsert_demo_users(db: Session) -> dict[str, User]:
    users: dict[str, User] = {}
    for spec in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == spec["email"]))
        if user is None:
            user = User(
                id=spec["id"],
                email=spec["email"],
                name=spec["name"],
                phone=spec["phone"],
                password_hash=hash_password(spec["password"]),
                role=spec["role"],
                is_active=True,
            )
            db.add(user)
        else:
            user.name = spec["name"]
            user.phone = spec["phone"]
            user.role = spec["role"]
            user.is_active = True
            if not verify_password(user.password_hash, spec["password"]):
                user.password_hash = hash_password(spec["password"])
        users[spec["role"].value] = user
    db.flush()
    return users


def _create_demo_orders(db: Session, demo_user: User) -> None:
    now = utcnow()

    paid = db.scalar(select(Order).where(Order.reference == "ORD-DEMO0001"))
    if paid is None:
        prado_type = db.get(TicketType, "tt-prado-general")
        if prado_type is not None:
            prado_type.quantity_sold += 2
            paid = Order(
                id="order-demo-1",
                reference="ORD-DEMO0001",
                buyer_name="Ana Garcia",
                buyer_email="ana.garcia@ejemplo.com",
                buyer_phone="+34 600 111 222",
                user_id=demo_user.id,
                status=OrderStatus.PAID,
                total_cents=3000,
                currency="EUR",
                created_at=now - timedelta(days=2),
                paid_at=now - timedelta(days=2),
                items=[
                    OrderItem(
                        id="oi-demo-1",
                        ticket_type_id="tt-prado-general",
                        quantity=2,
                        unit_price_cents=1500,
                        subtotal_cents=3000,
                    )
                ],
                tickets=[
                    Ticket(
                        id="ticket-demo-1",
                        code="DEMO-PAID-0001",
                        event_id="evt-prado",
                        ticket_type_id="tt-prado-general",
                        holder_name="Ana Garcia",
                        status=TicketStatus.VALID,
                    ),
                    Ticket(
                        id="ticket-demo-2",
                        code="DEMO-PAID-0002",
                        event_id="evt-prado",
                        ticket_type_id="tt-prado-general",
                        holder_name="Carlos Garcia",
                        status=TicketStatus.VALID,
                    ),
                ],
                payments=[
                    Payment(
                        id="payment-demo-1",
                        provider="SIMULATED",
                        status=PaymentStatus.APPROVED,
                        amount_cents=3000,
                        currency="EUR",
                        transaction_id="TXN-DEMO-0001",
                        card_last4="4242",
                    )
                ],
            )
            db.add(paid)
    else:
        paid.user_id = demo_user.id

    # Reserva pendiente sin propietario: sirve para probar el pago como demo.
    pending = db.scalar(select(Order).where(Order.reference == "ORD-DEMO0002"))
    if pending is None:
        aitana_type = db.get(TicketType, "tt-aitana-general")
        if aitana_type is not None:
            aitana_type.quantity_sold += 1
            pending = Order(
                id="order-demo-2",
                reference="ORD-DEMO0002",
                buyer_name="Luis Perez",
                buyer_email="luis.perez@ejemplo.com",
                user_id=None,
                status=OrderStatus.PENDING,
                total_cents=4500,
                currency="EUR",
                expires_at=now + timedelta(days=1, hours=23, minutes=59),
                items=[
                    OrderItem(
                        id="oi-demo-2",
                        ticket_type_id="tt-aitana-general",
                        quantity=1,
                        unit_price_cents=4500,
                        subtotal_cents=4500,
                    )
                ],
                payments=[
                    Payment(
                        id="payment-demo-2",
                        provider="SIMULATED",
                        status=PaymentStatus.REJECTED,
                        amount_cents=4500,
                        currency="EUR",
                        transaction_id="TXN-DEMO-0002",
                        card_last4="0002",
                        failure_reason=(
                            "Pago rechazado (simulado: tarjeta terminada en 0002)"
                        ),
                    )
                ],
            )
            db.add(pending)
    else:
        pending.status = OrderStatus.PENDING
        pending.expires_at = now + timedelta(days=1, hours=23, minutes=59)
        pending.paid_at = None
        pending.user_id = None

    db.flush()


def run_seed(db: Session) -> dict:
    payload = _load_json()

    _upsert_categories(db, payload["categories"])
    _upsert_venues(db, payload["venues"])
    _upsert_events(db, payload["events"])

    users = _upsert_demo_users(db)
    _create_demo_orders(db, users[UserRole.CLIENT.value])

    db.commit()

    summary = {
        "categories": len(payload["categories"]),
        "venues": len(payload["venues"]),
        "events": len(payload["events"]),
        "ticketTypes": sum(len(e.get("ticketTypes", [])) for e in payload["events"]),
        "users": len(DEMO_USERS),
        "orders": 2,
    }
    logger.info("Seed completado: %s", summary)
    print(f"Seed completado: {summary}")
    return summary
