"""Navegacion por la web sin iniciar sesion."""

from ayudas_web import WEB_URL


def test_la_portada_carga_por_https(web):
    web.abrir("/")
    web.esperar_texto("Explorar eventos")
    assert "EntradasYa" in web.driver.title
    if WEB_URL.startswith("https://"):
        assert web.driver.current_url.startswith("https://")
    # Sin sesion la cabecera ofrece entrar o registrarse.
    assert web.hay_enlace("Acceder", dentro="//header")
    assert web.hay_enlace("Crear cuenta", dentro="//header")
    web.captura("portada")


def test_ver_el_listado_de_eventos(web):
    web.abrir("/")
    web.enlace("Explorar eventos")
    web.esperar_ruta("/eventos")
    web.esperar_texto("Todos los eventos")
    assert web.elementos("a[href^='/eventos/']"), "No se muestra ningun evento"
    web.captura("listado")


def test_filtrar_por_tipo_desde_la_cabecera(web):
    web.abrir("/eventos")
    web.enlace("Concierto", dentro="//header")
    web.esperar_ruta("/eventos?type=CONCERT")
    web.esperar_texto("Todos los eventos")


def test_buscar_un_evento(web, evento):
    web.abrir("/")
    web.escribir_por_placeholder(
        "¿Qué quieres ver? Museo, partido, concierto...", evento["title"], enter=True
    )
    web.esperar_ruta("/eventos")
    web.esperar_texto("Resultados para")
    web.esperar_texto(evento["title"])
    web.captura("busqueda")


def test_abrir_el_detalle_de_un_evento(web, evento):
    web.abrir(f"/eventos/{evento['slug']}")
    web.esperar_texto(evento["title"])
    web.esperar_texto("Elige tus entradas")
    web.esperar_texto("General")
    # Sin elegir entradas no se puede reservar.
    boton = web.driver.find_element("xpath", "//button[normalize-space()='Reservar entradas']")
    assert not boton.is_enabled()
    web.captura("detalle")


def test_pagina_no_encontrada(web):
    web.abrir("/esta-pagina-no-existe")
    web.esperar_texto("Página no encontrada")


def test_validador_de_entradas_sin_sesion_solo_consulta(web):
    web.abrir("/validar")
    web.esperar_texto("Validar una entrada")
    assert web.hay_boton("Consultar estado")
    assert not web.hay_boton("Registrar acceso"), "Un visitante no debe poder registrar accesos"
