"""Ayudantes de las pruebas de extremo a extremo (Selenium) de EntradasYa.

Variables de entorno:

    WEB_URL     Web a probar (por defecto https://localhost).
    NAVEGADOR   firefox (por defecto), chrome o edge.
    HEADLESS    1 para no mostrar la ventana del navegador.
    LENTO       Segundos de pausa entre acciones, para verlo a ritmo humano
                (por defecto 0).
    ADMIN_EMAIL / ADMIN_PASSWORD, MANAGER_EMAIL / MANAGER_PASSWORD,
    CLIENT_EMAIL / CLIENT_PASSWORD: credenciales (por defecto, las de demo).

Selenium Manager (incluido en Selenium 4) descarga solo el driver del
navegador (geckodriver, chromedriver...) la primera vez.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

WEB_URL = os.environ.get("WEB_URL", "https://localhost").rstrip("/")
NAVEGADOR = os.environ.get("NAVEGADOR", "firefox").strip().lower()
HEADLESS = os.environ.get("HEADLESS", "0").strip().lower() in {"1", "true", "si", "sí"}
LENTO = float(os.environ.get("LENTO", "0") or 0)
ESPERA = 20  # segundos maximos para que aparezca algo en pantalla

CAPTURAS = Path(__file__).resolve().parent.parent / "resultados" / "capturas"

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


def _es_local(url: str) -> bool:
    return httpx.URL(url).host in {"localhost", "127.0.0.1", "::1"}


# --- Navegador -----------------------------------------------------------------


def crear_navegador() -> WebDriver:
    """Abre el navegador elegido. Acepta el certificado autofirmado de localhost."""
    if NAVEGADOR == "chrome":
        opciones = webdriver.ChromeOptions()
        if HEADLESS:
            opciones.add_argument("--headless=new")
        opciones.add_argument("--window-size=1400,1000")
        opciones.accept_insecure_certs = True
        driver = webdriver.Chrome(options=opciones)
    elif NAVEGADOR == "edge":
        opciones = webdriver.EdgeOptions()
        if HEADLESS:
            opciones.add_argument("--headless=new")
        opciones.add_argument("--window-size=1400,1000")
        opciones.accept_insecure_certs = True
        driver = webdriver.Edge(options=opciones)
    else:
        opciones = webdriver.FirefoxOptions()
        if HEADLESS:
            opciones.add_argument("-headless")
        opciones.accept_insecure_certs = True
        driver = webdriver.Firefox(options=opciones)
    # Ventana ancha: la cabecera muestra los textos completos (no la version movil).
    driver.set_window_size(1400, 1000)
    return driver


class Web:
    """Acciones de alto nivel sobre la web, como las haria un usuario."""

    def __init__(self, driver: WebDriver, nombre_prueba: str = "prueba"):
        self.driver = driver
        self.nombre_prueba = re.sub(r"[^\w.-]+", "_", nombre_prueba)[:80]
        self._capturas = 0

    # Navegacion -------------------------------------------------------------

    def abrir(self, ruta: str = "/") -> None:
        self.driver.get(WEB_URL + ruta)
        self._pausa()

    @property
    def ruta(self) -> str:
        url = httpx.URL(self.driver.current_url)
        return url.raw_path.decode()

    def esperar_ruta(self, prefijo: str) -> None:
        WebDriverWait(self.driver, ESPERA).until(
            lambda _: self.ruta.startswith(prefijo),
            message=f"La URL no llego a {prefijo} (esta en {self.ruta})",
        )

    # Lectura ----------------------------------------------------------------

    def texto(self) -> str:
        return self.driver.find_element(By.TAG_NAME, "body").text

    def esperar_texto(self, texto: str, espera: float = ESPERA) -> None:
        try:
            # Sin distinguir mayusculas: el CSS puede mostrar el texto en mayusculas
            # (text-transform) y Selenium lee el texto tal como se ve.
            buscado = texto.casefold()
            WebDriverWait(self.driver, espera).until(lambda _: buscado in self.texto().casefold())
        except TimeoutException as error:
            raise AssertionError(f"No aparece en pantalla: {texto!r}") from error

    def no_aparece(self, texto: str, espera: float = 2) -> bool:
        """Espera un poco y comprueba que el texto NO esta en pantalla."""
        time.sleep(espera)
        return texto not in self.texto()

    def elementos(self, css: str) -> list[WebElement]:
        return self.driver.find_elements(By.CSS_SELECTOR, css)

    # Escritura --------------------------------------------------------------

    def campo(self, etiqueta: str) -> WebElement:
        """Input cuya etiqueta <label> visible es `etiqueta`."""
        xpath = f"//label[.//span[normalize-space()={_xpath_literal(etiqueta)}]]//input"
        return WebDriverWait(self.driver, ESPERA).until(
            EC.visibility_of_element_located((By.XPATH, xpath)),
            message=f"No se encuentra el campo {etiqueta!r}",
        )

    def escribir(self, etiqueta: str, valor: str) -> None:
        elemento = self.campo(etiqueta)
        elemento.send_keys(Keys.CONTROL, "a")
        elemento.send_keys(Keys.DELETE)
        elemento.send_keys(valor)
        self._pausa()

    def escribir_por_placeholder(self, placeholder: str, valor: str, enter: bool = False) -> None:
        xpath = f"//input[@placeholder={_xpath_literal(placeholder)}]"
        elemento = WebDriverWait(self.driver, ESPERA).until(
            EC.visibility_of_element_located((By.XPATH, xpath))
        )
        elemento.clear()
        elemento.send_keys(valor)
        if enter:
            elemento.send_keys(Keys.ENTER)
        self._pausa()

    # Clics ------------------------------------------------------------------

    def pulsar(self, texto: str, *, dentro: str = "") -> None:
        """Pulsa el boton cuyo texto empieza por `texto`."""
        self._clic(f"{dentro}//button[starts-with(normalize-space(), {_xpath_literal(texto)})]", texto)

    def pulsar_etiqueta(self, aria_label: str) -> None:
        self._clic(f"//button[@aria-label={_xpath_literal(aria_label)}]", aria_label)

    def enlace(self, texto: str, *, dentro: str = "") -> None:
        """Pulsa el enlace que contiene `texto`."""
        self._clic(f"{dentro}//a[contains(normalize-space(), {_xpath_literal(texto)})]", texto)

    def hay_boton(self, texto: str) -> bool:
        xpath = f"//button[starts-with(normalize-space(), {_xpath_literal(texto)})]"
        return bool(self.driver.find_elements(By.XPATH, xpath))

    def hay_enlace(self, texto: str, *, dentro: str = "") -> bool:
        xpath = f"{dentro}//a[contains(normalize-space(), {_xpath_literal(texto)})]"
        return bool(self.driver.find_elements(By.XPATH, xpath))

    def _clic(self, xpath: str, descripcion: str) -> None:
        elemento = WebDriverWait(self.driver, ESPERA).until(
            EC.element_to_be_clickable((By.XPATH, xpath)),
            message=f"No se puede pulsar {descripcion!r}",
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
        elemento.click()
        self._pausa()

    # Sesion ------------------------------------------------------------------

    def iniciar_sesion(self, email: str, password: str) -> None:
        self.abrir("/acceder")
        self.escribir("Correo electrónico", email)
        self.escribir("Contraseña", password)
        self.pulsar("Entrar")
        self.esperar_sesion()

    def iniciar_sesion_como(self, rol: str) -> None:
        self.iniciar_sesion(*CREDENCIALES[rol])

    def esperar_sesion(self) -> None:
        self.esperar_texto("Salir")

    def cerrar_sesion(self) -> None:
        self.pulsar("Salir", dentro="//header")
        WebDriverWait(self.driver, ESPERA).until(
            lambda _: self.hay_enlace("Acceder", dentro="//header"),
            message="Tras cerrar sesion no aparece el enlace Acceder",
        )

    def registrarse(self, nombre: str, email: str, password: str, confirmacion: str | None = None) -> None:
        self.abrir("/registro")
        self.escribir("Nombre completo", nombre)
        self.escribir("Correo electrónico", email)
        self.escribir("Contraseña", password)
        self.escribir("Repite la contraseña", confirmacion if confirmacion is not None else password)
        self.pulsar("Crear cuenta", dentro="//form")

    # Varios ------------------------------------------------------------------

    def hay_alerta(self) -> bool:
        try:
            self.driver.switch_to.alert.dismiss()
            return True
        except NoAlertPresentException:
            return False

    def captura(self, descripcion: str) -> Path:
        """Guarda una captura de pantalla como evidencia de la prueba."""
        CAPTURAS.mkdir(parents=True, exist_ok=True)
        self._capturas += 1
        nombre = re.sub(r"[^\w-]+", "_", descripcion)
        ruta = CAPTURAS / f"{self.nombre_prueba}-{self._capturas:02d}-{nombre}.png"
        self.driver.save_screenshot(str(ruta))
        return ruta

    def _pausa(self) -> None:
        if LENTO:
            time.sleep(LENTO)


def _xpath_literal(texto: str) -> str:
    """Escapa un texto para usarlo como literal en XPath."""
    if "'" not in texto:
        return f"'{texto}'"
    if '"' not in texto:
        return f'"{texto}"'
    partes = texto.split("'")
    return "concat(" + ", \"'\", ".join(f"'{p}'" for p in partes) + ")"


# --- Preparacion de datos por la API -------------------------------------------
# Solo para preparar el escenario (crear un evento con stock, comprar entradas
# para la prueba del validador). Lo que se prueba se hace siempre en el navegador.


def email_aleatorio(prefijo: str = "e2e") -> str:
    return f"{prefijo}-{uuid.uuid4().hex[:10]}@ejemplo.com"


class ApiPreparacion:
    def __init__(self) -> None:
        self.http = httpx.Client(base_url=WEB_URL, timeout=90, verify=not _es_local(WEB_URL))
        self._token_admin: str | None = None
        self.eventos: list[str] = []

    def _login(self, email: str, password: str) -> str:
        respuesta = self.http.post("/api/auth/login", json={"email": email, "password": password})
        self.http.cookies.clear()
        respuesta.raise_for_status()
        return respuesta.json()["data"]["accessToken"]

    @property
    def admin(self) -> dict[str, str]:
        if self._token_admin is None:
            self._token_admin = self._login(*CREDENCIALES["ADMIN"])
        return {"Authorization": f"Bearer {self._token_admin}"}

    def crear_evento(self, stock: int = 50, max_por_pedido: int = 4) -> dict:
        inicio = datetime.now(timezone.utc) + timedelta(days=45)
        sufijo = uuid.uuid4().hex[:6]
        respuesta = self.http.post(
            "/api/admin/events",
            headers=self.admin,
            json={
                "title": f"Concierto E2E {sufijo}",
                "description": "Evento creado por las pruebas con Selenium",
                "type": "CONCERT",
                "status": "PUBLISHED",
                "startAt": inicio.isoformat(),
                "venueId": os.environ.get("VENUE_ID", "venue-prado"),
            },
        )
        respuesta.raise_for_status()
        evento = respuesta.json()["data"]
        self.eventos.append(evento["id"])
        respuesta = self.http.post(
            f"/api/admin/events/{evento['id']}/ticket-types",
            headers=self.admin,
            json={"name": "General", "priceCents": 2500, "quantityTotal": stock, "maxPerOrder": max_por_pedido},
        )
        respuesta.raise_for_status()
        return respuesta.json()["data"]

    def entradas_pagadas(self, evento: dict, cantidad: int = 1) -> list[str]:
        """Registra un cliente, compra y paga entradas. Devuelve los codigos."""
        email, password = email_aleatorio("e2e-comprador"), "Prueba1234"
        respuesta = self.http.post(
            "/api/auth/register", json={"name": "Comprador E2E", "email": email, "password": password}
        )
        self.http.cookies.clear()
        respuesta.raise_for_status()
        cabeceras = {"Authorization": f"Bearer {respuesta.json()['data']['accessToken']}"}
        respuesta = self.http.post(
            "/api/orders",
            headers=cabeceras,
            json={
                "buyer": {"name": "Comprador E2E", "email": email},
                "items": [{"ticketTypeId": evento["ticketTypes"][0]["id"], "quantity": cantidad}],
            },
        )
        respuesta.raise_for_status()
        referencia = respuesta.json()["data"]["reference"]
        respuesta = self.http.post(
            f"/api/orders/{referencia}/pay",
            headers=cabeceras,
            json={
                "cardNumber": "4242424242424242",
                "cardHolder": "COMPRADOR E2E",
                "expiryMonth": 12,
                "expiryYear": datetime.now().year + 2,
                "cvv": "123",
            },
        )
        respuesta.raise_for_status()
        return [t["code"] for t in respuesta.json()["data"]["order"]["tickets"]]

    def limpiar(self) -> None:
        for evento_id in self.eventos:
            try:
                self.http.patch(
                    f"/api/admin/events/{evento_id}", headers=self.admin, json={"status": "CANCELLED"}
                )
            except httpx.HTTPError:
                pass
        self.http.close()
