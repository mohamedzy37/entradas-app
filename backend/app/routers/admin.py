"""Panel de gestion y administracion, protegido por roles.

- MANAGER/ADMIN: gestion de eventos, recintos, tipos de entrada, pedidos y
  estadisticas.
- ADMIN: ademas, gestion de usuarios y roles.
"""

from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..database import get_db
from ..deps import require_admin, require_manager
from ..errors import ApiError
from ..models import (
    Category,
    Event,
    EventStatus,
    Order,
    OrderItem,
    OrderStatus,
    Ticket,
    TicketStatus,
    TicketType,
    User,
    UserRole,
    Venue,
)
from ..schemas import (
    ActiveUpdateInput,
    EventCreateInput,
    EventUpdateInput,
    RoleUpdateInput,
    TicketTypeCreateInput,
    TicketTypeUpdateInput,
    VenueCreateInput,
    VenueUpdateInput,
)
from ..serializers import present_event, present_order, present_user
from ..utils import pagination_meta
from .orders import ORDER_LOAD_OPTIONS

router = APIRouter(prefix="/admin", tags=["administracion"])


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or "evento"


def _unique_slug(db: Session, title: str, current_id: str | None = None) -> str:
    base = _slugify(title)
    candidate = base
    suffix = 2
    while True:
        stmt = select(Event.id).where(Event.slug == candidate)
        if current_id:
            stmt = stmt.where(Event.id != current_id)
        if db.scalar(stmt) is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def _load_event(db: Session, event_id: str) -> Event:
    event = db.scalar(
        select(Event)
        .where(Event.id == event_id)
        .options(
            joinedload(Event.venue),
            joinedload(Event.category),
            selectinload(Event.ticket_types),
        )
    )
    if event is None:
        raise ApiError.not_found("Evento no encontrado")
    return event


def _recompute_min_price(db: Session, event_id: str) -> None:
    event = db.get(Event, event_id)
    if event is None:
        return
    prices = db.scalars(
        select(TicketType.price_cents).where(
            TicketType.event_id == event_id, TicketType.is_active.is_(True)
        )
    ).all()
    event.min_price_cents = min(prices) if prices else None


# ---------------------------------------------------------------------------
# Usuarios (solo ADMIN)
# ---------------------------------------------------------------------------


@router.get("/users")
def list_users(
    q: str | None = Query(default=None, max_length=120),
    role: UserRole | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    conditions = []
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(User.name.ilike(like), User.email.ilike(like)))
    if role:
        conditions.append(User.role == role)

    total = db.scalar(select(func.count(User.id)).where(*conditions)) or 0
    users = db.scalars(
        select(User)
        .where(*conditions)
        .order_by(User.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "data": [present_user(user) for user in users],
        "pagination": pagination_meta(total, page, limit),
    }


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    payload: RoleUpdateInput,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    target = db.get(User, user_id)
    if target is None:
        raise ApiError.not_found("Usuario no encontrado")

    if target.role == UserRole.ADMIN and payload.role != UserRole.ADMIN:
        admins = db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.ADMIN, User.is_active.is_(True)
            )
        )
        if (admins or 0) <= 1:
            raise ApiError.conflict("No puedes degradar al ultimo administrador")

    if target.role != payload.role:
        target.role = payload.role
        # Invalida sus tokens: el JWT ya no reflejaria el rol real.
        target.token_version += 1
    db.commit()
    return {"data": present_user(target)}


@router.patch("/users/{user_id}/active")
def update_user_active(
    user_id: str,
    payload: ActiveUpdateInput,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    target = db.get(User, user_id)
    if target is None:
        raise ApiError.not_found("Usuario no encontrado")

    if target.id == current.id and not payload.is_active:
        raise ApiError.conflict("No puedes desactivar tu propia cuenta")

    if target.role == UserRole.ADMIN and not payload.is_active:
        admins = db.scalar(
            select(func.count(User.id)).where(
                User.role == UserRole.ADMIN, User.is_active.is_(True)
            )
        )
        if (admins or 0) <= 1:
            raise ApiError.conflict("No puedes desactivar al ultimo administrador")

    if target.is_active != payload.is_active:
        target.is_active = payload.is_active
        # Al desactivar (o reactivar) se invalidan todas sus sesiones.
        target.token_version += 1
    db.commit()
    return {"data": present_user(target)}


# ---------------------------------------------------------------------------
# Pedidos y estadisticas (MANAGER/ADMIN)
# ---------------------------------------------------------------------------


@router.get("/orders")
def list_all_orders(
    q: str | None = Query(default=None, max_length=120),
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> dict:
    conditions = []
    if q:
        like = f"%{q.strip()}%"
        conditions.append(
            or_(Order.reference.ilike(like), Order.buyer_email.ilike(like))
        )
    if order_status:
        conditions.append(Order.status == order_status)

    total = db.scalar(select(func.count(Order.id)).where(*conditions)) or 0
    orders = db.scalars(
        select(Order)
        .where(*conditions)
        .options(*ORDER_LOAD_OPTIONS)
        .order_by(Order.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "data": [present_order(order) for order in orders],
        "pagination": pagination_meta(total, page, limit),
    }


@router.get("/stats")
def stats(
    _: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> dict:
    revenue = db.scalar(
        select(func.coalesce(func.sum(Order.total_cents), 0)).where(
            Order.status == OrderStatus.PAID
        )
    ) or 0
    data = {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "events": db.scalar(select(func.count(Event.id))) or 0,
        "publishedEvents": db.scalar(
            select(func.count(Event.id)).where(
                Event.status.in_([EventStatus.PUBLISHED, EventStatus.SOLD_OUT])
            )
        )
        or 0,
        "orders": db.scalar(select(func.count(Order.id))) or 0,
        "paidOrders": db.scalar(
            select(func.count(Order.id)).where(Order.status == OrderStatus.PAID)
        )
        or 0,
        "pendingOrders": db.scalar(
            select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING)
        )
        or 0,
        "revenueCents": int(revenue),
        "tickets": db.scalar(select(func.count(Ticket.id))) or 0,
        "ticketsUsed": db.scalar(
            select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.USED)
        )
        or 0,
    }
    return {"data": data}


# ---------------------------------------------------------------------------
# Eventos (MANAGER/ADMIN)
# ---------------------------------------------------------------------------


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreateInput,
    _: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> dict:
    venue = db.get(Venue, payload.venue_id)
    if venue is None:
        raise ApiError.bad_request("El recinto indicado no existe")
    if payload.category_id:
        category = db.get(Category, payload.category_id)
        if category is None:
            raise ApiError.bad_request("La categoria indicada no existe")

    event = Event(
        title=payload.title,
        slug=_unique_slug(db, payload.title),
        description=payload.description,
        type=payload.type,
        status=payload.status,
        image_url=payload.image_url,
        start_at=payload.start_at,
        end_at=payload.end_at,
        doors_open_at=payload.doors_open_at,
        category_id=payload.category_id,
        venue_id=payload.venue_id,
    )
    db.add(event)
    db.commit()

    return {"data": present_event(_load_event(db, event.id), include_ticket_types=True)}


@router.patch("/events/{event_id}")
def update_event(
    event_id: str,
    payload: EventUpdateInput,
    _: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> dict:
    event = db.get(Event, event_id)
    if event is None:
        raise ApiError.not_found("Evento no encontrado")

    data = payload.model_dump(exclude_unset=True)
    data.pop("min_price_cents", None)

    if "venue_id" in data and data["venue_id"]:
        if db.get(Venue, data["venue_id"]) is None:
            raise ApiError.bad_request("El recinto indicado no existe")
    if "category_id" in data and data["category_id"]:
        if db.get(Category, data["category_id"]) is None:
            raise ApiError.bad_request("La categoria indicada no existe")

    if "title" in data and data["title"]:
        data["slug"] = _unique_slug(db, data["title"], current_id=event.id)

    for key, value in data.items():
        setattr(event, key, value)

    db.commit()
    return {"data": present_event(_load_event(db, event.id), include_ticket_types=True)}


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: str,
    _: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> Response:
    event = db.get(Event, event_id)
    if event is None:
        raise ApiError.not_found("Evento no encontrado")

    ticket_count = db.scalar(
        select(func.count(Ticket.id)).where(Ticket.event_id == event_id)
    )
    item_count = db.scalar(
        select(func.count(OrderItem.id))
        .join(TicketType, TicketType.id == OrderItem.ticket_type_id)
        .where(TicketType.event_id == event_id)
    )
    if (ticket_count or 0) > 0 or (item_count or 0) > 0:
        raise ApiError.conflict(
            "No se puede eliminar un evento con entradas vendidas. Cancelalo en su lugar."
        )

    db.delete(event)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Tipos de entrada (MANAGER/ADMIN)
# ---------------------------------------------------------------------------


@router.post("/events/{event_id}/ticket-types", status_code=status.HTTP_201_CREATED)
def create_ticket_type(
    event_id: str,
    payload: TicketTypeCreateInput,
    _: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> dict:
    event = db.get(Event, event_id)
    if event is None:
        raise ApiError.not_found("Evento no encontrado")

    existing = db.scalar(
        select(TicketType.id).where(
            TicketType.event_id == event_id, TicketType.name == payload.name
        )
    )
    if existing is not None:
        raise ApiError.conflict("Ya existe un tipo de entrada con ese nombre en el evento")

    ticket_type = TicketType(
        event_id=event_id,
        name=payload.name,
        description=payload.description,
        price_cents=payload.price_cents,
        currency=payload.currency,
        quantity_total=payload.quantity_total,
        max_per_order=payload.max_per_order,
        is_active=payload.is_active,
    )
    db.add(ticket_type)
    db.flush()
    _recompute_min_price(db, event_id)
    db.commit()

    return {"data": present_event(_load_event(db, event_id), include_ticket_types=True)}


@router.patch("/ticket-types/{ticket_type_id}")
def update_ticket_type(
    ticket_type_id: str,
    payload: TicketTypeUpdateInput,
    _: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> dict:
    ticket_type = db.get(TicketType, ticket_type_id)
    if ticket_type is None:
        raise ApiError.not_found("Tipo de entrada no encontrado")

    data = payload.model_dump(exclude_unset=True)

    new_total = data.get("quantity_total")
    if new_total is not None and new_total < ticket_type.quantity_sold:
        raise ApiError.conflict(
            f"No puedes reducir el aforo por debajo de las entradas ya vendidas "
            f"({ticket_type.quantity_sold})"
        )

    for key, value in data.items():
        setattr(ticket_type, key, value)

    db.flush()
    _recompute_min_price(db, ticket_type.event_id)
    db.commit()

    return {
        "data": present_event(_load_event(db, ticket_type.event_id), include_ticket_types=True)
    }


@router.delete("/ticket-types/{ticket_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket_type(
    ticket_type_id: str,
    _: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> Response:
    ticket_type = db.get(TicketType, ticket_type_id)
    if ticket_type is None:
        raise ApiError.not_found("Tipo de entrada no encontrado")

    items = db.scalar(
        select(func.count(OrderItem.id)).where(
            OrderItem.ticket_type_id == ticket_type_id
        )
    )
    if ticket_type.quantity_sold > 0 or (items or 0) > 0:
        raise ApiError.conflict(
            "No puedes eliminar un tipo de entrada con ventas. Desactivalo en su lugar."
        )

    event_id = ticket_type.event_id
    db.delete(ticket_type)
    db.flush()
    _recompute_min_price(db, event_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Recintos (MANAGER/ADMIN)
# ---------------------------------------------------------------------------


@router.post("/venues", status_code=status.HTTP_201_CREATED)
def create_venue(
    payload: VenueCreateInput,
    _: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> dict:
    venue = Venue(**payload.model_dump())
    db.add(venue)
    db.commit()
    from ..serializers import present_venue

    return {"data": present_venue(venue)}


@router.patch("/venues/{venue_id}")
def update_venue(
    venue_id: str,
    payload: VenueUpdateInput,
    _: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> dict:
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise ApiError.not_found("Recinto no encontrado")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(venue, key, value)

    db.commit()
    from ..serializers import present_venue

    return {"data": present_venue(venue)}


@router.delete("/venues/{venue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_venue(
    venue_id: str,
    _: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> Response:
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise ApiError.not_found("Recinto no encontrado")

    events = db.scalar(select(func.count(Event.id)).where(Event.venue_id == venue_id))
    if (events or 0) > 0:
        raise ApiError.conflict("No puedes eliminar un recinto con eventos asociados")

    db.delete(venue)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
