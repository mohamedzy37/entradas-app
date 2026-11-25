"""Pruebas del despliegue publico (Nginx con HTTPS o Render), contra WEB_URL.

Comprueban la configuracion de produccion segura: redireccion a HTTPS,
cabeceras de seguridad, que solo se publica lo necesario y el limite de
peticiones del login. Se ejecutan las ultimas porque la prueba del rate limit
bloquea el login desde esta IP durante alrededor de un minuto.
"""

from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from ayudas_api import WEB_URL, nuevo_cliente_http

ES_RENDER = "onrender.com" in WEB_URL


@pytest.fixture(scope="module")
def web():
    cliente = nuevo_cliente_http(WEB_URL)
    try:
        cliente.get("/", timeout=90)
    except httpx.HTTPError as error:
        pytest.skip(f"No se puede conectar con {WEB_URL}: {error}")
    yield cliente
    cliente.close()


def test_http_redirige_a_https(web):
    url_http = httpx.URL(WEB_URL).copy_with(scheme="http", port=None)
    try:
        respuesta = httpx.get(str(url_http), follow_redirects=False, timeout=30)
    except httpx.HTTPError as error:
        pytest.skip(f"El puerto HTTP no esta publicado: {error}")
    assert respuesta.status_code in {301, 302, 307, 308}
    assert respuesta.headers["location"].startswith("https://")


def test_la_web_se_sirve_por_https(web):
    respuesta = web.get("/")
    assert respuesta.status_code == 200
    assert respuesta.url.scheme == "https"
    assert "text/html" in respuesta.headers.get("content-type", "")


@pytest.mark.parametrize(
    "cabecera, contiene",
    [
        ("strict-transport-security", "max-age="),
        ("x-content-type-options", "nosniff"),
        ("x-frame-options", "DENY"),
        ("referrer-policy", "strict-origin-when-cross-origin"),
        ("content-security-policy", "default-src 'self'"),
        ("content-security-policy", "frame-ancestors 'none'"),
    ],
)
def test_cabeceras_de_seguridad_en_la_web(web, cabecera, contiene):
    valor = web.get("/").headers.get(cabecera)
    assert valor is not None, f"Falta la cabecera {cabecera}"
    assert contiene.lower() in valor.lower()


def test_no_se_revela_la_version_del_servidor(web):
    servidor = web.get("/").headers.get("server", "")
    assert not any(c.isdigit() for c in servidor), f"Cabecera Server con version: {servidor}"


def test_las_rutas_de_la_spa_devuelven_la_aplicacion(web):
    respuesta = web.get("/eventos/cualquier-cosa")
    assert respuesta.status_code == 200
    assert "text/html" in respuesta.headers.get("content-type", "")


def test_la_api_es_accesible_por_el_mismo_origen(web):
    respuesta = web.get("/api/events", params={"limit": 1})
    assert respuesta.status_code == 200
    assert "data" in respuesta.json()


@pytest.mark.parametrize("ruta", ["/.env", "/.git/config"])
def test_no_se_exponen_ficheros_ocultos(web, ruta):
    respuesta = web.get(ruta)
    # 404 en Nginx; en Render la SPA responde con index.html, nunca con el fichero.
    assert respuesta.status_code == 404 or "text/html" in respuesta.headers.get("content-type", "")
    assert "POSTGRES_PASSWORD" not in respuesta.text
    assert "[core]" not in respuesta.text


@pytest.mark.skipif(ES_RENDER, reason="En Render no se usa el Nginx del proyecto (no hay limit_req)")
def test_el_login_tiene_limite_de_peticiones():
    """Fuerza bruta: 40 intentos de login a la vez desde la misma IP.

    Nginx deja pasar una rafaga de 10 y responde 429 al resto, tanto con el
    limite normal (10/min) como con el de pruebas (AUTH_RATE_LIMIT=120r/m).
    """

    def intento(_: int) -> int:
        with nuevo_cliente_http(WEB_URL) as cliente:
            return cliente.post(
                "/api/auth/login",
                json={"email": "fuerza.bruta@ejemplo.com", "password": "NoEsLaClave1"},
            ).status_code

    with ThreadPoolExecutor(max_workers=20) as hilos:
        codigos = list(hilos.map(intento, range(40)))

    assert codigos.count(429) >= 20, f"No se ha aplicado el limite: {codigos}"
    assert set(codigos) <= {401, 429}, f"Respuestas inesperadas: {codigos}"
