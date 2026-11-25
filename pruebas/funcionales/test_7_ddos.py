"""Pruebas de proteccion frente a DoS/DDoS de capa 7 en el despliegue (Nginx).

Se lanzan contra WEB_URL (https://localhost) y se omiten contra Render: alli
no se usa el Nginx del proyecto (Render pone su propia proteccion delante) y
atacar la infraestructura de un tercero no es aceptable.

Proteccion configurada en frontend/nginx/default.conf.template:

* limit_req zona "api": API_RATE_LIMIT (20 r/s por IP) con rafaga de 40.
* limit_req zona "auth": AUTH_RATE_LIMIT (10/min por IP) en /api/auth/.
* limit_conn: 50 conexiones/peticiones simultaneas por IP.
* client_header_timeout / client_body_timeout de 10 s (Slowloris).
* client_max_body_size 1m y tamano maximo de cabeceras.
"""

from __future__ import annotations

import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from ayudas_api import WEB_URL, nuevo_cliente_http

pytestmark = pytest.mark.skipif(
    "onrender.com" in WEB_URL, reason="Las pruebas de DoS solo se hacen contra el despliegue propio"
)


@pytest.fixture(scope="module")
def web():
    cliente = nuevo_cliente_http(WEB_URL)
    try:
        cliente.get("/", timeout=30)
    except httpx.HTTPError as error:
        pytest.skip(f"No se puede conectar con {WEB_URL}: {error}")
    yield cliente
    cliente.close()


def _inundar(ruta: str, peticiones: int = 300, hilos: int = 50) -> list[int]:
    limites = httpx.Limits(max_connections=hilos, max_keepalive_connections=hilos)
    with httpx.Client(base_url=WEB_URL, verify=False, timeout=30, limits=limites) as cliente:

        def una(_: int) -> int:
            try:
                return cliente.get(ruta).status_code
            except httpx.HTTPError:
                return -1  # conexion rechazada o cortada

        with ThreadPoolExecutor(max_workers=hilos) as pool:
            return list(pool.map(una, range(peticiones)))


def test_inundacion_de_la_api_se_corta_con_429(web):
    """Un unico origen lanza 300 peticiones a la API lo mas rapido posible."""
    inicio = time.perf_counter()
    codigos = _inundar("/api/events?limit=1")
    duracion = time.perf_counter() - inicio

    atendidas = codigos.count(200)
    bloqueadas = codigos.count(429)
    print(f"\n300 peticiones en {duracion:.1f} s: {atendidas} atendidas, {bloqueadas} bloqueadas (429)")

    assert bloqueadas >= 150, f"Nginx deberia bloquear la mayoria: {bloqueadas} bloqueadas"
    # El limite deja pasar la rafaga (40) mas el ritmo permitido (20/s).
    assert atendidas <= 40 + 20 * (duracion + 1)
    assert not [c for c in codigos if c >= 500], "La inundacion no debe provocar errores 5xx"


def test_la_web_sigue_disponible_tras_la_inundacion(web):
    _inundar("/api/events?limit=1", peticiones=200)
    time.sleep(3)  # el cubo del limite se rellena a 20 peticiones/s

    inicio = time.perf_counter()
    respuesta = web.get("/api/events", params={"limit": 1})
    latencia = time.perf_counter() - inicio
    assert respuesta.status_code == 200
    assert latencia < 2, f"La API tarda {latencia:.2f} s en responder tras el ataque"
    assert web.get("/").status_code == 200


def test_los_ficheros_estaticos_no_cuentan_para_el_limite_de_la_api(web):
    _inundar("/api/events?limit=1", peticiones=150)
    # Aunque la API este limitada para esta IP, la web (SPA) se sigue sirviendo.
    assert web.get("/").status_code == 200


def test_slowloris_la_conexion_lenta_se_cierra(web):
    """Slowloris: abre una conexion y envia la peticion a medias, sin terminarla.

    Nginx debe cerrarla al vencer client_header_timeout (10 s) en lugar de
    dejarla abierta indefinidamente ocupando recursos.
    """
    url = httpx.URL(WEB_URL)
    puerto = url.port or 443
    contexto = ssl.create_default_context()
    contexto.check_hostname = False
    contexto.verify_mode = ssl.CERT_NONE

    with socket.create_connection((url.host, puerto), timeout=30) as crudo:
        with contexto.wrap_socket(crudo, server_hostname=url.host) as conexion:
            # TLS negocia HTTP/1.1 (sin ALPN), peticion incompleta: falta la linea en blanco final.
            conexion.sendall(f"GET / HTTP/1.1\r\nHost: {url.host}\r\nX-Lento: 1\r\n".encode())
            inicio = time.perf_counter()
            try:
                datos = conexion.recv(4096)
            except (ConnectionResetError, ssl.SSLError):
                datos = b""
            espera = time.perf_counter() - inicio

    print(f"\nConexion cerrada por el servidor tras {espera:.1f} s: {datos[:40]!r}")
    assert espera < 20, "Nginx no ha cerrado la conexion lenta"
    assert espera >= 5, "La conexion se cerro antes de tiempo (¿no es Nginx?)"
    assert datos == b"" or b"408" in datos


def test_cuerpo_demasiado_grande_se_rechaza(web):
    respuesta = web.post(
        "/api/orders",
        content=b"{" + b'"x":"' + b"A" * (2 * 1024 * 1024) + b'"}',
        headers={"Content-Type": "application/json"},
    )
    assert respuesta.status_code == 413


def test_cabeceras_enormes_se_rechazan(web):
    respuesta = web.get("/api/events", headers={"X-Relleno": "A" * 64 * 1024})
    assert respuesta.status_code in {400, 413, 431, 494}
