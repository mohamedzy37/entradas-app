"""Entradas: consulta por codigo y check-in en puerta.

La consulta es publica porque el codigo actua como capacidad secreta, pero el
check-in exige rol MANAGER o ADMIN (no cualquier cliente).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import require_manager
from ..errors import ApiError
from ..models import Event, Ticket, TicketStatus, User
from ..serializers import present_ticket_lookup
from ..utils import utcnow

router = APIRouter(prefix="/tickets", tags=["entradas"])


def _load_ticket(db: Session, code: str) -> Ticket:
    ticket = db.scalar(
        select(Ticket)
        .where(Ticket.code == code)
        .options(
            joinedload(Ticket.event).joinedload(Event.venue),
            joinedload(Ticket.ticket_type),
            joinedload(Ticket.order),
        )
    )
    if ticket is None:
        raise ApiError.not_found("Entrada no encontrada")
    return ticket


@router.get("/{code}")
def get_ticket(code: str, db: Session = Depends(get_db)) -> dict:
    return {"data": present_ticket_lookup(_load_ticket(db, code))}


@router.post("/{code}/check-in")
def check_in_ticket(
    code: str,
    user: User = Depends(require_manager),
    db: Session = Depends(get_db),
) -> dict:
    ticket = _load_ticket(db, code)

    if ticket.status == TicketStatus.USED:
        used_at = ticket.used_at.isoformat() if ticket.used_at else ""
        raise ApiError.conflict(f"La entrada ya fue utilizada el {used_at}")
    if ticket.status == TicketStatus.CANCELLED:
        raise ApiError.conflict("La entrada esta cancelada")

    ticket.status = TicketStatus.USED
    ticket.used_at = utcnow()
    db.commit()

    return {"data": present_ticket_lookup(ticket)}
