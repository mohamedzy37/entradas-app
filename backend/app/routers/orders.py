"""Pedidos: reserva de stock, pago simulado, cancelacion y consulta."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_client
from ..errors import ApiError
from ..ids import order_reference, ticket_code, transaction_id
from ..models import (
    EventStatus,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
    Ticket,
    TicketType,
    User,
    UserRole,
)
from ..schemas import CreateOrderInput, PayOrderInput
from ..serializers import present_order, present_payment
from ..utils import utcnow

router = APIRouter(prefix="/orders", tags=["pedidos"])

ORDER_LOAD_OPTIONS = (
    selectinload(Order.items)
    .joinedload(OrderItem.ticket_type)
    .joinedload(TicketType.event),
    selectinload(Order.tickets).joinedload(Ticket.event),
    selectinload(Order.tickets).joinedload(Ticket.ticket_type),
    selectinload(Order.payments),
)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def load_order_full(db: Session, reference: str) -> Order:
    order = db.scalar(
        select(Order).where(Order.reference == reference).options(*ORDER_LOAD_OPTIONS)
    )
    if order is None:
        raise ApiError.not_found("Orden no encontrada")
    return order


def _assert_can_manage(order: Order, user: User) -> None:
    if order.user_id and order.user_id != user.id and user.role != UserRole.ADMIN:
        raise ApiError.forbidden("Esta reserva pertenece a otra cuenta")


def _release_reserved_stock(db: Session, items: list[OrderItem]) -> None:
    for item in items:
        db.execute(
            update(TicketType)
            .where(
                TicketType.id == item.ticket_type_id,
                TicketType.quantity_sold >= item.quantity,
            )
            .values(quantity_sold=TicketType.quantity_sold - item.quantity)
        )


def _expire_if_needed(db: Session, order: Order) -> bool:
    if order.status != OrderStatus.PENDING:
        return False
    expires_at = _aware(order.expires_at)
    if expires_at is None or expires_at > utcnow():
        return False

    _release_reserved_stock(db, list(order.items))
    order.status = OrderStatus.EXPIRED
    db.commit()
    return True


def _unique_ticket_code(db: Session, used: set[str]) -> str:
    for _ in range(20):
        code = ticket_code()
        if code in used:
            continue
        exists = db.scalar(select(Ticket.id).where(Ticket.code == code))
        if exists is None:
            used.add(code)
            return code
    raise ApiError.internal("No se pudo generar un codigo de entrada unico")


def _unique_reference(db: Session) -> str:
    for _ in range(10):
        reference = order_reference()
        if db.scalar(select(Order.id).where(Order.reference == reference)) is None:
            return reference
    raise ApiError.internal("No se pudo generar una referencia de orden unica")


@router.get("")
def list_my_orders(
    user: User = Depends(require_client),
    db: Session = Depends(get_db),
) -> dict:
    # Marca como EXPIRED las reservas vencidas y libera su stock.
    stale = db.scalars(
        select(Order)
        .where(
            Order.user_id == user.id,
            Order.status == OrderStatus.PENDING,
            Order.expires_at < utcnow(),
        )
        .options(selectinload(Order.items))
    ).all()
    for order in stale:
        _release_reserved_stock(db, list(order.items))
        order.status = OrderStatus.EXPIRED
    if stale:
        db.commit()

    orders = db.scalars(
        select(Order)
        .where(Order.user_id == user.id)
        .options(*ORDER_LOAD_OPTIONS)
        .order_by(Order.created_at.desc())
        .limit(50)
    ).all()

    return {"data": [present_order(order) for order in orders]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(
    payload: CreateOrderInput,
    user: User = Depends(require_client),
    db: Session = Depends(get_db),
) -> dict:
    grouped: dict[str, int] = {}
    for item in payload.items:
        grouped[item.ticket_type_id] = grouped.get(item.ticket_type_id, 0) + item.quantity

    ticket_types = db.scalars(
        select(TicketType)
        .where(TicketType.id.in_(list(grouped.keys())))
        .options(selectinload(TicketType.event))
        .with_for_update()
    ).all()

    if len(ticket_types) != len(grouped):
        raise ApiError.bad_request("Uno o mas tipos de entrada no existen")

    now = utcnow()
    total_cents = 0
    currency = settings.DEFAULT_CURRENCY
    order_items: list[OrderItem] = []

    for ticket_type in ticket_types:
        quantity = grouped.get(ticket_type.id, 0)
        if quantity <= 0:
            continue

        if not ticket_type.is_active:
            raise ApiError.conflict(
                f'El tipo de entrada "{ticket_type.name}" no esta disponible'
            )

        event = ticket_type.event
        if event.status not in (EventStatus.PUBLISHED, EventStatus.SOLD_OUT):
            raise ApiError.conflict(
                f'El evento "{event.title}" no esta disponible para la venta'
            )
        if _aware(event.start_at) is not None and _aware(event.start_at) <= now:
            raise ApiError.conflict(f'El evento "{event.title}" ya ha comenzado')

        if quantity > ticket_type.max_per_order:
            raise ApiError.bad_request(
                f'Maximo {ticket_type.max_per_order} entradas por tipo ("{ticket_type.name}")'
            )

        available = ticket_type.quantity_total - ticket_type.quantity_sold
        if quantity > available:
            raise ApiError.conflict(
                f'No hay suficientes entradas para "{ticket_type.name}". '
                f"Disponibles: {available}"
            )

        ticket_type.quantity_sold += quantity
        subtotal_cents = ticket_type.price_cents * quantity
        total_cents += subtotal_cents
        currency = ticket_type.currency
        order_items.append(
            OrderItem(
                ticket_type_id=ticket_type.id,
                quantity=quantity,
                unit_price_cents=ticket_type.price_cents,
                subtotal_cents=subtotal_cents,
            )
        )

    if not order_items:
        raise ApiError.bad_request("La orden debe incluir al menos una entrada valida")

    order = Order(
        reference=_unique_reference(db),
        buyer_name=payload.buyer.name,
        buyer_email=str(payload.buyer.email),
        buyer_phone=payload.buyer.phone,
        user_id=user.id,
        status=OrderStatus.PENDING,
        total_cents=total_cents,
        currency=currency,
        expires_at=now + timedelta(minutes=settings.ORDER_RESERVATION_MINUTES),
        items=order_items,
    )
    db.add(order)
    db.commit()

    return {"data": present_order(load_order_full(db, order.reference))}


@router.get("/{reference}")
def get_order(reference: str, db: Session = Depends(get_db)) -> dict:
    order = load_order_full(db, reference)
    _expire_if_needed(db, order)
    return {"data": present_order(order)}


@router.post("/{reference}/pay")
def pay_order(
    reference: str,
    payload: PayOrderInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    order = db.scalar(
        select(Order).where(Order.reference == reference).with_for_update()
    )
    if order is None:
        raise ApiError.not_found("Orden no encontrada")

    _assert_can_manage(order, user)

    if order.status == OrderStatus.PAID:
        raise ApiError.conflict("La orden ya esta pagada")
    if order.status == OrderStatus.CANCELLED:
        raise ApiError.conflict("La orden esta cancelada")
    if order.status == OrderStatus.REFUNDED:
        raise ApiError.conflict("La orden fue reembolsada")
    if order.status == OrderStatus.EXPIRED:
        raise ApiError.conflict("La orden ha expirado. Crea una nueva orden.")

    if _expire_if_needed(db, order):
        raise ApiError.conflict(
            "La reserva ha expirado. Crea una nueva orden para continuar."
        )

    last4 = payload.card_number[-4:]
    declined = payload.card_number.endswith("0002")

    if declined:
        payment = Payment(
            order_id=order.id,
            status=PaymentStatus.REJECTED,
            amount_cents=order.total_cents,
            currency=order.currency,
            transaction_id=transaction_id(),
            card_last4=last4,
            failure_reason="Pago rechazado (simulado: tarjeta terminada en 0002)",
        )
        db.add(payment)
        db.commit()

        return JSONResponse(
            status_code=402,
            content={
                "approved": False,
                "data": {
                    "order": present_order(load_order_full(db, reference)),
                    "payment": present_payment(payment),
                },
            },
        )

    now = utcnow()
    payment = Payment(
        order_id=order.id,
        status=PaymentStatus.APPROVED,
        amount_cents=order.total_cents,
        currency=order.currency,
        transaction_id=transaction_id(),
        card_last4=last4,
    )
    db.add(payment)

    order.status = OrderStatus.PAID
    order.paid_at = now
    order.expires_at = None

    # Una entrada por unidad comprada.
    used_codes: set[str] = set()
    items = db.scalars(
        select(OrderItem).where(OrderItem.order_id == order.id)
    ).all()
    for item in items:
        for _ in range(item.quantity):
            db.add(
                Ticket(
                    code=_unique_ticket_code(db, used_codes),
                    order_id=order.id,
                    event_id=item.ticket_type.event_id,
                    ticket_type_id=item.ticket_type_id,
                    holder_name=order.buyer_name,
                )
            )
    db.commit()

    paid_order = load_order_full(db, reference)
    approved_payment = next(
        (p for p in paid_order.payments if p.status == PaymentStatus.APPROVED), payment
    )

    return JSONResponse(
        status_code=200,
        content={
            "approved": True,
            "data": {
                "order": present_order(paid_order),
                "payment": present_payment(approved_payment),
            },
        },
    )


@router.post("/{reference}/cancel")
def cancel_order(
    reference: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    order = db.scalar(
        select(Order).where(Order.reference == reference).with_for_update()
    )
    if order is None:
        raise ApiError.not_found("Orden no encontrada")

    _assert_can_manage(order, user)

    if order.status == OrderStatus.PAID:
        raise ApiError.conflict(
            "Una orden pagada no se puede cancelar. Solicita un reembolso."
        )
    if order.status == OrderStatus.CANCELLED:
        raise ApiError.conflict("La orden ya esta cancelada")
    if order.status == OrderStatus.REFUNDED:
        raise ApiError.conflict("La orden fue reembolsada")

    if order.status == OrderStatus.PENDING:
        _release_reserved_stock(db, list(order.items))

    order.status = OrderStatus.CANCELLED
    order.expires_at = None
    db.commit()

    return {"data": present_order(load_order_full(db, reference))}
