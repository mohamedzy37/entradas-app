"""Fixtures de las pruebas de extremo a extremo con Selenium (ver ayudas_web.py)."""

from __future__ import annotations

import base64

import httpx
import pytest

from ayudas_web import WEB_URL, ApiPreparacion, Web, crear_navegador


@pytest.fixture(scope="session", autouse=True)
def web_disponible():
    try:
        httpx.get(WEB_URL, verify=False, timeout=90)
    except httpx.HTTPError as error:
        pytest.exit(f"No se puede abrir {WEB_URL}: {error}", returncode=2)


@pytest.fixture(scope="session")
def preparacion():
    api = ApiPreparacion()
    yield api
    api.limpiar()


@pytest.fixture(scope="session")
def evento(preparacion) -> dict:
    """Evento propio con stock suficiente para todas las pruebas de compra."""
    return preparacion.crear_evento(stock=50, max_por_pedido=4)


@pytest.fixture
def web(request):
    """Navegador nuevo y limpio (sin sesion ni datos guardados) para cada prueba."""
    driver = crear_navegador()
    pagina = Web(driver, request.node.name)
    yield pagina
    driver.quit()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Si una prueba falla, guarda una captura de pantalla del navegador."""
    resultado = yield
    informe = resultado.get_result()
    if informe.when != "call" or not informe.failed:
        return
    pagina = item.funcargs.get("web")
    if pagina is None:
        return
    try:
        ruta = pagina.captura("FALLO")
    except Exception:  # noqa: BLE001 - el navegador puede estar cerrado
        return
    informe.sections.append(("Captura del fallo", str(ruta)))
    # Si pytest-html esta instalado, la captura se incrusta en el informe HTML.
    plugin_html = item.config.pluginmanager.getplugin("html")
    if plugin_html is not None:
        imagen = base64.b64encode(ruta.read_bytes()).decode()
        extras = getattr(informe, "extras", [])
        extras.append(plugin_html.extras.png(imagen))
        informe.extras = extras
