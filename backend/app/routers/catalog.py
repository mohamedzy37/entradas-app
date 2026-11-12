"""Catalogo publico: categorias, recintos y eventos."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..database import get_db
from ..errors import ApiError
from ..models import Category, Event, EventStatus, EventType, TicketType, Venue
from ..serializers import present_category, present_event, present_venue
from ..utils import format_money, pagination_meta, utcnow

router = APIRouter(tags=["catalogo"])

VISIBLE_STATUSES = (EventStatus.PUBLISHED, EventStatus.SOLD_OUT)


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(Category, func.count(Event.id))
        .outerjoin(Event, Event.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.name.asc())
    ).all()
    return {"data": [present_category(category, count) for category, count in rows]}


@router.get("/venues")
def list_venues(
    q: str | None = Query(default=None, max_length=120),
    city: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    conditions = []
    if q:
        conditions.append(Venue.name.ilike(f"%{q.strip()}%"))
    if city:
        conditions.append(func.lower(Venue.city) == city.strip().lower())

    total = db.scalar(select(func.count(Venue.id)).where(*conditions)) or 0
    venues = db.scalars(
        select(Venue)
        .where(*conditions)
        .order_by(Venue.city.asc(), Venue.name.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "data": [present_venue(venue) for venue in venues],
        "pagination": pagination_meta(total, page, limit),
    }


@router.get("/venues/{venue_id}")
def get_venue(venue_id: str, db: Session = Depends(get_db)) -> dict:
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise ApiError.not_found("Recinto no encontrado")

    events = db.scalars(
        select(Event)
        .where(
            Event.venue_id == venue_id,
            Event.status.in_(VISIBLE_STATUSES),
            Event.start_at >= utcnow(),
        )
        .options(
            joinedload(Event.category),
            joinedload(Event.venue),
            selectinload(Event.ticket_types),
        )
        .order_by(Event.start_at.asc())
        .limit(20)
    ).all()

    upcoming = []
    for event in events:
        active = sorted(
            (tt for tt in event.ticket_types if tt.is_active),
            key=lambda tt: tt.price_cents,
        )
        cheapest = active[0] if active else None
        currency = cheapest.currency if cheapest else "EUR"
        min_price_cents = (
            event.min_price_cents
            if event.min_price_cents is not None
            else (cheapest.price_cents if cheapest else None)
        )
        upcoming.append(
            {
                "id": event.id,
                "title": event.title,
                "slug": event.slug,
                "type": event.type.value,
                "status": event.status.value,
                "startAt": event.start_at.isoformat(),
                "imageUrl": event.image_url,
                "category": present_category(event.category),
                "minPriceCents": min_price_cents,
                "minPrice": (
                    format_money(min_price_cents, currency)
                    if min_price_cents is not None
                    else None
                ),
            }
        )

    payload = present_venue(venue)
    payload["upcomingEvents"] = upcoming
    return {"data": payload}


def _parse_event_types(raw: str | None) -> list[EventType]:
    if not raw:
        return []
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    try:
        return [EventType(part) for part in parts]
    except ValueError as exc:
        raise ApiError.bad_request("Tipo de evento invalido") from exc


@router.get("/events")
def list_events(
    q: str | None = Query(default=None, max_length=120),
    event_type: str | None = Query(default=None, alias="type"),
    status: EventStatus | None = Query(default=None),
    category: str | None = Query(default=None, max_length=120),
    city: str | None = Query(default=None, max_length=120),
    venue_id: str | None = Query(default=None, alias="venueId", max_length=64),
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    include_past: bool = Query(default=False, alias="includePast"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=12, ge=1, le=50),
    sort: Literal["date_asc", "date_desc", "price_asc", "price_desc"] = Query(
        default="date_asc"
    ),
    db: Session = Depends(get_db),
) -> dict:
    conditions = []

    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(Event.title.ilike(like), Event.description.ilike(like)))

    types = _parse_event_types(event_type)
    if types:
        conditions.append(Event.type.in_(types))

    conditions.append(Event.status == status if status else Event.status.in_(VISIBLE_STATUSES))

    if category:
        conditions.append(Event.category.has(Category.slug == category.strip()))
    if city:
        conditions.append(
            Event.venue.has(func.lower(Venue.city) == city.strip().lower())
        )
    if venue_id:
        conditions.append(Event.venue_id == venue_id)

    if date_from is not None:
        if date_from.tzinfo is None:
            from datetime import timezone

            date_from = date_from.replace(tzinfo=timezone.utc)
        conditions.append(Event.start_at >= date_from)
    elif not include_past:
        conditions.append(Event.start_at >= utcnow())

    if date_to is not None:
        if date_to.tzinfo is None:
            from datetime import timezone

            date_to = date_to.replace(tzinfo=timezone.utc)
        conditions.append(Event.start_at <= date_to)

    if sort == "date_desc":
        order_by = Event.start_at.desc()
    elif sort == "price_asc":
        order_by = Event.min_price_cents.asc().nulls_last()
    elif sort == "price_desc":
        order_by = Event.min_price_cents.desc().nulls_last()
    else:
        order_by = Event.start_at.asc()

    total = db.scalar(select(func.count(Event.id)).where(*conditions)) or 0
    events = db.scalars(
        select(Event)
        .where(*conditions)
        .options(
            joinedload(Event.venue),
            joinedload(Event.category),
            selectinload(Event.ticket_types),
        )
        .order_by(order_by)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return {
        "data": [present_event(event, include_ticket_types=False) for event in events],
        "pagination": pagination_meta(total, page, limit),
    }


@router.get("/events/{id_or_slug}")
def get_event(id_or_slug: str, db: Session = Depends(get_db)) -> dict:
    event = db.scalar(
        select(Event)
        .where(or_(Event.id == id_or_slug, Event.slug == id_or_slug))
        .options(
            joinedload(Event.venue),
            joinedload(Event.category),
            selectinload(Event.ticket_types),
        )
    )
    if event is None:
        raise ApiError.not_found("Evento no encontrado")
    return {"data": present_event(event, include_ticket_types=True)}
