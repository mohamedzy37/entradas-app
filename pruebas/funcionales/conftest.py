"""Fixtures de las pruebas funcionales de la API (ver ayudas_api.py)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from ayudas_api import API_URL, auth, login, nuevo_cliente_http, refresh_de, email_aleatorio


@pytest.fixture(scope="session")
def api() -> httpx.Client:
    cliente = nuevo_cliente_http(API_URL)
    try:
        cliente.get("/health", timeout=90)  # en Render la primera peticion despierta la API
    except httpx.HTTPError as error:
        pytest.exit(f"No se puede conectar con la API en {API_URL}: {error}", returncode=2)
    yield cliente
    cliente.close()


def _token(api: httpx.Client, rol: str) -> str:
    respuesta = login(api, rol)
    assert respuesta.status_code == 200, f"Login de {rol} fallido: {respuesta.text}"
    return respuesta.json()["data"]["accessToken"]


@pytest.fixture(scope="session")
def token_admin(api) -> str:
    return _token(api, "ADMIN")


@pytest.fixture(scope="session")
def token_manager(api) -> str:
    return _token(api, "MANAGER")


@pytest.fixture(scope="session")
def token_cliente(api) -> str:
    return _token(api, "CLIENT")


@pytest.fixture
def usuario_nuevo(api) -> dict:
    """Registra un CLIENT nuevo y devuelve sus datos, token y refresh."""
    email = email_aleatorio()
    password = "Prueba1234"
    respuesta = api.post(
        "/api/auth/register",
        json={"name": "Usuario de prueba", "email": email, "password": password},
    )
    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()["data"]
    return {
        "id": datos["user"]["id"],
        "email": email,
        "password": password,
        "token": datos["accessToken"],
        "refresh": refresh_de(respuesta),
    }


@pytest.fixture(scope="session")
def crear_evento(api, token_admin):
    """Fabrica de eventos de prueba (un tipo de entrada con stock controlado).

    Al terminar la sesion los eventos creados se cancelan para que no aparezcan
    en el catalogo publico.
    """
    creados: list[str] = []

    def _crear(stock: int = 5, max_por_pedido: int = 4, precio_cents: int = 2500) -> dict:
        sufijo = uuid.uuid4().hex[:8]
        inicio = datetime.now(timezone.utc) + timedelta(days=30)
        respuesta = api.post(
            "/api/admin/events",
            headers=auth(token_admin),
            json={
                "title": f"Evento de prueba {sufijo}",
                "description": "Creado por las pruebas funcionales",
                "type": "CONCERT",
                "status": "PUBLISHED",
                "startAt": inicio.isoformat(),
                "endAt": (inicio + timedelta(hours=2)).isoformat(),
                "venueId": os.environ.get("VENUE_ID", "venue-prado"),
            },
        )
        assert respuesta.status_code == 201, respuesta.text
        evento = respuesta.json()["data"]
        creados.append(evento["id"])

        respuesta = api.post(
            f"/api/admin/events/{evento['id']}/ticket-types",
            headers=auth(token_admin),
            json={
                "name": "General",
                "priceCents": precio_cents,
                "currency": "EUR",
                "quantityTotal": stock,
                "maxPerOrder": max_por_pedido,
            },
        )
        assert respuesta.status_code == 201, respuesta.text
        evento = respuesta.json()["data"]
        evento["tipo"] = evento["ticketTypes"][0]
        return evento

    yield _crear

    for evento_id in creados:
        api.patch(
            f"/api/admin/events/{evento_id}",
            headers=auth(token_admin),
            json={"status": "CANCELLED"},
        )
