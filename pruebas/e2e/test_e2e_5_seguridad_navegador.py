"""Seguridad observable desde el navegador."""

from ayudas_web import email_aleatorio


def test_los_tokens_no_son_accesibles_desde_javascript(web):
    """Un XSS no podria robar la sesion: el access token esta solo en memoria
    y el refresh en una cookie HttpOnly que JavaScript no puede leer."""
    web.iniciar_sesion_como("CLIENT")

    cookies_js = web.driver.execute_script("return document.cookie")
    assert "refresh_token" not in cookies_js

    almacenado = web.driver.execute_script(
        "const t = {};"
        "for (const s of [localStorage, sessionStorage])"
        "  for (let i = 0; i < s.length; i++) t[s.key(i)] = s.getItem(s.key(i));"
        "return t;"
    )
    for clave, valor in almacenado.items():
        assert not str(valor).startswith("eyJ"), f"Hay un JWT guardado en el navegador ({clave})"


def test_la_cookie_del_refresh_es_httponly_secure_y_strict(web):
    web.iniciar_sesion_como("CLIENT")
    # Selenium (no JavaScript) si puede ver las cookies HttpOnly.
    cookie = next((c for c in web.driver.get_cookies() if c["name"] == "refresh_token"), None)
    if cookie is None:
        # La cookie tiene Path=/api/auth: solo se ve estando en esa ruta.
        web.abrir("/api/auth/providers")
        cookie = next((c for c in web.driver.get_cookies() if c["name"] == "refresh_token"), None)
    assert cookie is not None, "No se encuentra la cookie del refresh"
    assert cookie["httpOnly"] is True
    assert cookie["secure"] is True
    assert cookie.get("sameSite") == "Strict"
    assert cookie["path"] == "/api/auth"


def test_un_nombre_con_html_no_se_ejecuta_xss(web):
    """React escapa el contenido: un nombre con HTML se muestra como texto."""
    carga = "<img src=x onerror=alert('xss')>"
    web.registrarse(f"{carga} Atacante", email_aleatorio("e2e-xss"), "Selenium1234")
    web.esperar_sesion()
    assert not web.hay_alerta(), "Se ha ejecutado JavaScript inyectado (XSS)"
    # El HTML aparece como texto literal en la cabecera, no como una imagen.
    web.esperar_texto("<img")
    assert not web.elementos("header img[src='x']")
    web.captura("xss-escapado")


def test_la_politica_csp_bloquea_scripts_en_linea(web):
    web.abrir("/")
    web.esperar_texto("Explorar eventos")
    ejecutado = web.driver.execute_script(
        "window.__csp = false;"
        "const s = document.createElement('script');"
        "s.textContent = 'window.__csp = true';"
        "document.head.appendChild(s);"
        "return window.__csp;"
    )
    assert ejecutado is False, "La CSP deberia bloquear scripts en linea"
