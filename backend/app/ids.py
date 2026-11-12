"""Generadores de identificadores y codigos."""

import secrets
import time

# Alfabeto sin caracteres ambiguos (0/O, 1/I/L) para codigos legibles en puerta.
TICKET_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_id() -> str:
    """Identificador interno opaco de 24 caracteres hexadecimales."""
    return secrets.token_hex(12)


def order_reference() -> str:
    """Referencia publica de una orden, p. ej. ORD-9F3A21C4."""
    return f"ORD-{secrets.token_hex(4).upper()}"


def transaction_id() -> str:
    """Identificador de la pasarela de pago simulada."""
    stamped = _base36(int(time.time() * 1000)).upper()
    return f"SIM-{stamped}-{secrets.token_hex(4).upper()}"


def ticket_code() -> str:
    """Codigo de entrada en formato XXXX-XXXX-XXXX."""
    groups = [
        "".join(secrets.choice(TICKET_ALPHABET) for _ in range(4)) for _ in range(3)
    ]
    return "-".join(groups)


def _base36(number: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if number == 0:
        return "0"
    result = ""
    while number:
        number, remainder = divmod(number, 36)
        result = alphabet[remainder] + result
    return result
