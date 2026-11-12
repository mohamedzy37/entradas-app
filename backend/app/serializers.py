"""Serializadores: convierten modelos ORM en el contrato JSON de la API.

Mantienen los mismos nombres de campo (camelCase) que consumia el frontend
original para no romper la interfaz.
"""

from __future__ import annotations

from .models import (
    Category,
    Event,
    Order,
    OrderItem,
    Payment,
    Ticket,
    TicketType,
    User,
    Venue,
)
from .utils import format_money, iso


def present_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "phone": user.phone,
        "role": user.role.value,
        "isActive": user.is_active,
        "createdAt": iso(user.created_at),
    }


def present_category(category: Category | None, event_count: int = 0) -> dict | None:
    if category is None:
        return None
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "eventCount": event_count,
    }


def present_venue(venue: Venue) -> dict:
    return {
        "id": venue.id,
        "name": venue.name,
        "address": venue.address,
        "city": venue.city,
        "country": venue.country,
        "capacity": venue.capacity,
        "latitude": venue.latitude,
        "longitude": venue.longitude,
    }


def present_ticket_type(ticket_type: TicketType) -> dict:
    available = max(ticket_type.quantity_total - ticket_type.quantity_sold, 0)
    return {
        "id": ticket_type.id,
        "name": ticket_type.name,
        "description": ticket_type.description,
        "priceCents": ticket_type.price_cents,
        "price": format_money(ticket_type.price_cents, ticket_type.currency),
        "currency": ticket_type.currency,
        "quantityTotal": ticket_type.quantity_total,
        "quantitySold": ticket_type.quantity_sold,
        "available": available,
        "soldOut": available <= 0,
        "maxPerOrder": ticket_type.max_per_order,
        "isActive": ticket_type.is_active,
    }


def _active_ticket_types(event: Event) -> list[TicketType]:
    items = [tt for tt in event.ticket_types if tt.is_active]
    return sorted(items, key=lambda tt: tt.price_cents)


def present_event(event: Event, include_ticket_types: bool = False) -> dict:
    active = _active_ticket_types(event)
    cheapest = active[0] if active else None
    currency = cheapest.currency if cheapest else "EUR"
    min_price_cents = (
        event.min_price_cents
        if event.min_price_cents is not None
        else (cheapest.price_cents if cheapest else None)
    )

    payload = {
        "id": event.id,
        "title": event.title,
        "slug": event.slug,
        "description": event.description,
        "type": event.type.value,
        "status": event.status.value,
        "imageUrl": event.image_url,
        "startAt": iso(event.start_at),
        "endAt": iso(event.end_at),
        "doorsOpenAt": iso(event.doors_open_at),
        "currency": currency,
        "minPriceCents": min_price_cents,
        "minPrice": (
            format_money(min_price_cents, currency) if min_price_cents is not None else None
        ),
        "category": present_category(event.category),
        "venue": present_venue(event.venue),
        "isSoldOut": event.status.value == "SOLD_OUT",
    }
    if include_ticket_types:
        payload["ticketTypes"] = [present_ticket_type(tt) for tt in active]
    return payload


def present_payment(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "provider": payment.provider,
        "status": payment.status.value,
        "amountCents": payment.amount_cents,
        "amount": format_money(payment.amount_cents, payment.currency),
        "currency": payment.currency,
        "transactionId": payment.transaction_id,
        "cardLast4": payment.card_last4,
        "failureReason": payment.failure_reason,
        "createdAt": iso(payment.created_at),
    }


def present_order_ticket(ticket: Ticket) -> dict:
    return {
        "id": ticket.id,
        "code": ticket.code,
        "status": ticket.status.value,
        "holderName": ticket.holder_name,
        "usedAt": iso(ticket.used_at),
        "eventId": ticket.event_id,
        "eventTitle": ticket.event.title,
        "eventStartAt": iso(ticket.event.start_at),
        "ticketTypeName": ticket.ticket_type.name,
        "createdAt": iso(ticket.created_at),
    }


def present_order_item(item: OrderItem, currency: str) -> dict:
    return {
        "id": item.id,
        "ticketTypeId": item.ticket_type_id,
        "ticketTypeName": item.ticket_type.name,
        "eventId": item.ticket_type.event_id,
        "eventTitle": item.ticket_type.event.title,
        "eventStartAt": iso(item.ticket_type.event.start_at),
        "quantity": item.quantity,
        "unitPriceCents": item.unit_price_cents,
        "unitPrice": format_money(item.unit_price_cents, currency),
        "subtotalCents": item.subtotal_cents,
        "subtotal": format_money(item.subtotal_cents, currency),
    }


def present_order(order: Order) -> dict:
    return {
        "id": order.id,
        "reference": order.reference,
        "status": order.status.value,
        "buyer": {
            "name": order.buyer_name,
            "email": order.buyer_email,
            "phone": order.buyer_phone,
        },
        "currency": order.currency,
        "totalCents": order.total_cents,
        "total": format_money(order.total_cents, order.currency),
        "expiresAt": iso(order.expires_at),
        "paidAt": iso(order.paid_at),
        "createdAt": iso(order.created_at),
        "updatedAt": iso(order.updated_at),
        "items": [present_order_item(item, order.currency) for item in order.items],
        "tickets": [present_order_ticket(ticket) for ticket in order.tickets],
        "payments": [present_payment(payment) for payment in order.payments],
    }


def present_ticket_lookup(ticket: Ticket) -> dict:
    return {
        "id": ticket.id,
        "code": ticket.code,
        "status": ticket.status.value,
        "holderName": ticket.holder_name,
        "usedAt": iso(ticket.used_at),
        "event": {
            "id": ticket.event.id,
            "title": ticket.event.title,
            "slug": ticket.event.slug,
            "type": ticket.event.type.value,
            "status": ticket.event.status.value,
            "startAt": iso(ticket.event.start_at),
            "endAt": iso(ticket.event.end_at),
            "imageUrl": ticket.event.image_url,
            "venue": present_venue(ticket.event.venue),
        },
        "ticketType": {
            "id": ticket.ticket_type.id,
            "name": ticket.ticket_type.name,
            "priceCents": ticket.ticket_type.price_cents,
            "price": format_money(ticket.ticket_type.price_cents, ticket.ticket_type.currency),
            "currency": ticket.ticket_type.currency,
        },
        "orderReference": ticket.order.reference,
        "createdAt": iso(ticket.created_at),
    }
