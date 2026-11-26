"""Ayudantes de las pruebas funcionales de la API de EntradasYa.

Las pruebas son de caja negra: hablan con la API por HTTP, igual que el
frontend. Variables de entorno:

    API_URL    URL de la API (por defecto http://127.0.0.1:3000, la API del
               docker compose de pruebas, sin pasar por Nginx).
    WEB_URL    URL publica del despliegue (por defecto https://localhost).
               Solo la usan las pruebas de test_6_despliegue.py.
    VERIFY_TLS "false" para aceptar el certificado autofirmado de localhost
               (por defecto se desactiva solo si la URL es de localhost).
    ADMIN_EMAIL / ADMIN_PASSWORD, MANAGER_EMAIL / MANAGER_PASSWORD,
    CLIENT_EMAIL / CLIENT_PASSWORD: credenciales (por defecto, las de demo).
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx

API_URL = os.environ.get("API_URL", "http://127.0.0.1:3000").rstrip("/")
WEB_URL = os.environ.get("WEB_URL", "https://localhost").rstrip("/")
REFRESH_COOKIE = "refresh_token"

CREDENCIALES = {
    "ADMIN": (
        os.environ.get("ADMIN_EMAIL", "admin@entradas.com"),
        os.environ.get("ADMIN_PASSWORD", "Admin1234"),
    ),
    "MANAGER": (
        os.environ.get("MANAGER_EMAIL", "gestor@entradas.com"),
        os.environ.get("MANAGER_PASSWORD", "Gestor1234"),
    ),
    "CLIENT": (
        os.environ.get("CLIENT_EMAIL", "ana.garcia@ejemplo.com"),
        os.environ.get("CLIENT_PASSWORD", "demo1234"),
    ),
}

TARJETA_OK = "4242424242424242"
TARJETA_RECHAZADA = "4000000000000002"  # el pago simulado rechaza las que acaban en 0002


def _es_local(url: str) -> bool:
    host = httpx.URL(url).host
    return host in {"localhost", "127.0.0.1", "::1"}


def _verify(url: str) -> bool:
    valor = os.environ.get("VERIFY_TLS")
    if valor is not None:
        return valor.strip().lower() not in {"0", "false", "no"}
    return not _es_local(url)


class _ReintentoSiLimite(httpx.HTTPTransport):
    """Si la API responde 429 con Retry-After (su limite de login/registro por
    IP), espera lo que indica y repite la peticion. Asi las pruebas tambien
    funcionan contra produccion, donde ese limite es de 20 por minuto.

    El 429 de Nginx no trae Retry-After, asi que las pruebas que comprueban
    ese limite siguen viendolo.
    """

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        for _ in range(3):
            respuesta = super().handle_request(request)
            espera = respuesta.headers.get("retry-after")
            if respuesta.status_code != 429 or not espera or not espera.isdigit():
                return respuesta
            respuesta.close()
            time.sleep(min(int(espera), 65))
        return super().handle_request(request)


def nuevo_cliente_http(base_url: str = API_URL) -> httpx.Client:
    """Cliente HTTP SIN memoria de cookies.

    Cada prueba envia la cookie del refresh de forma explicita, como haria el
    navegador, para controlar exactamente que se manda (y para que funcione
    tambien contra la API en HTTP, donde una cookie Secure no se reenviaria).
    """

    cliente: httpx.Client

    def _olvidar_cookies(_: httpx.Response) -> None:
        cliente.cookies.clear()

    verificar = _verify(base_url)
    cliente = httpx.Client(
        base_url=base_url,
        timeout=60,
        verify=verificar,
        follow_redirects=False,
        transport=_ReintentoSiLimite(verify=verificar),
        event_hooks={"response": [_olvidar_cookies]},
    )
    return cliente


def cookies_set(respuesta: httpx.Response) -> dict[str, dict[str, str]]:
    """Analiza las cabeceras Set-Cookie: {nombre: {"value": ..., atributos}}."""
    resultado: dict[str, dict[str, str]] = {}
    for crudo in respuesta.headers.get_list("set-cookie"):
        partes = [p.strip() for p in crudo.split(";")]
        nombre, _, valor = partes[0].partition("=")
        atributos = {"value": valor.strip('"')}
        for parte in partes[1:]:
            clave, _, val = parte.partition("=")
            atributos[clave.strip().lower()] = val.strip() or "true"
        resultado[nombre.strip()] = atributos
    return resultado


def refresh_de(respuesta: httpx.Response) -> str:
    cookie = cookies_set(respuesta).get(REFRESH_COOKIE)
    assert cookie is not None, "La respuesta no trae la cookie del refresh"
    return cookie["value"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def con_refresh(valor: str, origin: str | None = None) -> dict[str, str]:
    cabeceras = {"Cookie": f"{REFRESH_COOKIE}={valor}"}
    if origin:
        cabeceras["Origin"] = origin
    return cabeceras


def login(api: httpx.Client, rol_o_email: str, password: str | None = None) -> httpx.Response:
    if password is None:
        email, password = CREDENCIALES[rol_o_email]
    else:
        email = rol_o_email
    return api.post("/api/auth/login", json={"email": email, "password": password})


def email_aleatorio() -> str:
    return f"pf-{uuid.uuid4().hex[:12]}@ejemplo.com"


def disponibles(api: httpx.Client, evento: dict) -> int:
    respuesta = api.get(f"/api/events/{evento['slug']}")
    assert respuesta.status_code == 200, respuesta.text
    for tipo in respuesta.json()["data"]["ticketTypes"]:
        if tipo["id"] == evento["tipo"]["id"]:
            return tipo["available"]
    raise AssertionError("No se encontro el tipo de entrada del evento de prueba")


def pedido(tipo_id: str, cantidad: int = 1) -> dict:
    return {
        "buyer": {"name": "Comprador de prueba", "email": "comprador@ejemplo.com"},
        "items": [{"ticketTypeId": tipo_id, "quantity": cantidad}],
    }


def pago(tarjeta: str = TARJETA_OK) -> dict:
    return {
        "cardNumber": tarjeta,
        "cardHolder": "Comprador de prueba",
        "expiryMonth": 12,
        "expiryYear": datetime.now().year + 2,
        "cvv": "123",
    }
