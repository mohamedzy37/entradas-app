"""Pruebas de carga y estres de EntradasYa con Locust.

Simula dos tipos de usuario:

* Visitante (70 %): navega por el catalogo sin iniciar sesion.
* Comprador (30 %): se registra, navega, compra y paga entradas, consulta sus
  pedidos y refresca el token como hace el frontend.

Cada usuario espera entre 5 y 15 s entre acciones (~10 s de media), el mismo
supuesto que el estudio de costes: 420 usuarios ~= 42 peticiones/s.

Perfiles (variable de entorno PERFIL):

    (sin PERFIL)  Se usan -u / -r / -t de la linea de comandos o la interfaz web.
    carga         Sube a 420 usuarios en 2 min y los mantiene 5 min.
    pico          Llegan 420 usuarios de golpe (en ~10 s) y se mantienen 3 min.
    estres        Escalones de 100 en 100 usuarios cada minuto hasta 1200,
                  para encontrar el punto de rotura.
    produccion    Prueba moderada contra Render (produccion): escalones de
                  10, 25 y 50 usuarios de 1 min cada uno.

Antes de empezar, la prueba crea con el usuario ADMIN un evento propio con
mucho stock (para no agotar los eventos de demostracion) y lo cancela al
terminar.
"""

from __future__ import annotations

import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests
from locust import HttpUser, LoadTestShape, between, events, task

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@entradas.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin1234")
VENUE_ID = os.environ.get("VENUE_ID", "venue-prado")
PERFIL = os.environ.get("PERFIL", "").strip().lower()
REFRESH_COOKIE = "refresh_token"

TIPOS = ["MUSEUM", "FOOTBALL", "CINEMA", "FESTIVAL", "CONCERT", "THEATER"]
BUSQUEDAS = ["madrid", "concierto", "museo", "festival", "real", "noche"]

DATOS: dict = {"evento_id": None, "tipo_id": None, "slugs": []}
log = logging.getLogger("entradas-estres")


def _verificar_tls(host: str) -> bool:
    """El certificado de localhost es autofirmado: no se verifica en local."""
    return urlparse(host).hostname not in {"localhost", "127.0.0.1"}


def _refresh_de(respuesta) -> str | None:
    """Extrae la cookie del refresh de la respuesta (se gestiona a mano)."""
    cabecera = respuesta.headers.get("set-cookie", "")
    for trozo in cabecera.split(","):
        trozo = trozo.strip()
        if trozo.startswith(f"{REFRESH_COOKIE}="):
            return trozo.split(";", 1)[0].split("=", 1)[1]
    return None


# --- Preparacion y limpieza ---------------------------------------------------


@events.test_start.add_listener
def preparar(environment, **_):
    host = environment.host.rstrip("/")
    sesion = requests.Session()
    sesion.verify = _verificar_tls(host)

    r = sesion.post(f"{host}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=90)
    r.raise_for_status()
    cabeceras = {"Authorization": f"Bearer {r.json()['data']['accessToken']}"}
    DATOS["admin"] = cabeceras

    inicio = datetime.now(timezone.utc) + timedelta(days=60)
    r = sesion.post(
        f"{host}/api/admin/events",
        headers=cabeceras,
        json={
            "title": f"Prueba de estres {uuid.uuid4().hex[:6]}",
            "description": "Evento creado por Locust",
            "type": "CONCERT",
            "status": "PUBLISHED",
            "startAt": inicio.isoformat(),
            "venueId": VENUE_ID,
        },
        timeout=30,
    )
    r.raise_for_status()
    evento = r.json()["data"]
    r = sesion.post(
        f"{host}/api/admin/events/{evento['id']}/ticket-types",
        headers=cabeceras,
        json={"name": "General", "priceCents": 3000, "quantityTotal": 1_000_000, "maxPerOrder": 4},
        timeout=30,
    )
    r.raise_for_status()
    evento = r.json()["data"]
    DATOS["evento_id"] = evento["id"]
    DATOS["tipo_id"] = evento["ticketTypes"][0]["id"]

    r = sesion.get(f"{host}/api/events", params={"limit": 50}, timeout=30)
    DATOS["slugs"] = [e["slug"] for e in r.json()["data"]] or [evento["slug"]]
    log.info("Evento de estres %s preparado; %d eventos en el catalogo", evento["id"], len(DATOS["slugs"]))


@events.test_stop.add_listener
def limpiar(environment, **_):
    if not DATOS.get("evento_id"):
        return
    host = environment.host.rstrip("/")
    try:
        # El token del admin puede haber caducado: se vuelve a iniciar sesion.
        r = requests.post(
            f"{host}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            verify=_verificar_tls(host),
            timeout=60,
        )
        token = r.json()["data"]["accessToken"]
        requests.patch(
            f"{host}/api/admin/events/{DATOS['evento_id']}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "CANCELLED"},
            verify=_verificar_tls(host),
            timeout=60,
        )
    except Exception as error:  # noqa: BLE001 - la limpieza no debe romper el informe
        log.warning("No se pudo cancelar el evento de estres: %s", error)


# --- Usuarios simulados -------------------------------------------------------


class UsuarioBase(HttpUser):
    abstract = True
    wait_time = between(5, 15)

    def on_start(self):
        self.client.verify = _verificar_tls(self.host)

    def ver_portada(self):
        self.client.get("/api/events", params={"page": 1, "limit": 12}, name="/api/events (portada)")

    def filtrar(self):
        params = {"type": random.choice(TIPOS), "sort": random.choice(["date_asc", "price_asc"])}
        if random.random() < 0.5:
            params["q"] = random.choice(BUSQUEDAS)
        self.client.get("/api/events", params=params, name="/api/events (filtros)")

    def ver_evento(self):
        slug = random.choice(DATOS["slugs"])
        self.client.get(f"/api/events/{slug}", name="/api/events/[slug]")


class Visitante(UsuarioBase):
    weight = 7

    @task(4)
    def portada(self):
        self.ver_portada()

    @task(2)
    def busqueda(self):
        self.filtrar()

    @task(3)
    def detalle(self):
        self.ver_evento()

    @task(1)
    def categorias(self):
        self.client.get("/api/categories")


class Comprador(UsuarioBase):
    weight = 3

    def on_start(self):
        super().on_start()
        self.email = f"estres-{uuid.uuid4().hex[:12]}@ejemplo.com"
        self.password = "Estres1234"
        self.token = None
        self.refresh = None
        r = self.client.post(
            "/api/auth/register",
            json={"name": "Usuario de estres", "email": self.email, "password": self.password},
            name="/api/auth/register",
        )
        self._guardar_sesion(r)

    def _guardar_sesion(self, respuesta):
        # El cliente no guarda cookies: el refresh se envia a mano, como el navegador.
        self.client.cookies.clear()
        if respuesta.status_code in (200, 201):
            self.token = respuesta.json()["data"]["accessToken"]
            self.refresh = _refresh_de(respuesta) or self.refresh

    @property
    def auth(self):
        return {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def navegar(self):
        self.ver_portada()

    @task(2)
    def detalle(self):
        self.ver_evento()

    @task(2)
    def comprar(self):
        if not self.token:
            return self.iniciar_sesion()
        r = self.client.post(
            "/api/orders",
            headers=self.auth,
            json={
                "buyer": {"name": "Usuario de estres", "email": self.email},
                "items": [{"ticketTypeId": DATOS["tipo_id"], "quantity": random.randint(1, 2)}],
            },
            name="/api/orders (reservar)",
        )
        if r.status_code == 401:  # access caducado: se vuelve a entrar
            self.token = None
            return
        if r.status_code != 201:
            return
        referencia = r.json()["data"]["reference"]
        if random.random() < 0.9:
            self.client.post(
                f"/api/orders/{referencia}/pay",
                headers=self.auth,
                json={
                    "cardNumber": "4242424242424242",
                    "cardHolder": "Usuario de estres",
                    "expiryMonth": 12,
                    "expiryYear": datetime.now().year + 2,
                    "cvv": "123",
                },
                name="/api/orders/[ref]/pay",
            )
        else:
            self.client.post(f"/api/orders/{referencia}/cancel", headers=self.auth, name="/api/orders/[ref]/cancel")

    @task(1)
    def mis_pedidos(self):
        if self.token:
            self.client.get("/api/orders", headers=self.auth, name="/api/orders (mis pedidos)")

    @task(1)
    def refrescar_token(self):
        if not self.refresh:
            return
        r = self.client.post(
            "/api/auth/refresh",
            headers={"Cookie": f"{REFRESH_COOKIE}={self.refresh}"},
            name="/api/auth/refresh",
        )
        self._guardar_sesion(r)

    @task(1)
    def iniciar_sesion(self):
        # Login real con Argon2id: es la operacion mas costosa de la API.
        r = self.client.post(
            "/api/auth/login",
            json={"email": self.email, "password": self.password},
            name="/api/auth/login",
        )
        self._guardar_sesion(r)


# --- Perfiles de carga ---------------------------------------------------------

if PERFIL == "carga":

    class Carga(LoadTestShape):
        """Rampa de 2 min hasta 420 usuarios y 5 min estable."""

        def tick(self):
            t = self.get_run_time()
            if t < 120:
                return max(int(420 * t / 120), 1), 10
            if t < 420:
                return 420, 10
            return None

elif PERFIL == "pico":

    class Pico(LoadTestShape):
        """420 usuarios en ~10 s (apertura de una venta) y 3 min estable."""

        def tick(self):
            return (420, 50) if self.get_run_time() < 190 else None

elif PERFIL == "estres":

    class Estres(LoadTestShape):
        """Escalones de 100 usuarios por minuto hasta 1200."""

        escalon = 100
        duracion = 60
        maximo = 1200

        def tick(self):
            n = int(self.get_run_time() // self.duracion) + 1
            usuarios = n * self.escalon
            if usuarios > self.maximo:
                return None
            return usuarios, 20

elif PERFIL == "produccion":

    class Produccion(LoadTestShape):
        """Carga moderada para el despliegue de produccion en Render (plan gratuito)."""

        escalones = [(60, 10), (120, 25), (180, 50)]

        def tick(self):
            t = self.get_run_time()
            for fin, usuarios in self.escalones:
                if t < fin:
                    return usuarios, 5
            return None
