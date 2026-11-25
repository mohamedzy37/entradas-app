"""Compra de entradas de principio a fin, como un usuario real."""

from ayudas_web import email_aleatorio


def _elegir_entradas(web, evento, cantidad):
    web.abrir(f"/eventos/{evento['slug']}")
    web.esperar_texto("Elige tus entradas")
    for _ in range(cantidad):
        web.pulsar_etiqueta("Añadir una entrada")
    web.esperar_texto("Entradas seleccionadas")


def test_compra_completa_con_pago_rechazado_y_reintento(web, evento):
    # 1. Un usuario nuevo se registra.
    web.registrarse("Carlos Comprador", email_aleatorio("e2e-compra"), "Selenium1234")
    web.esperar_sesion()

    # 2. Elige 2 entradas del evento y reserva.
    _elegir_entradas(web, evento, 2)
    web.esperar_texto("50,00")  # 2 x 25,00 EUR
    web.captura("entradas-elegidas")
    web.pulsar("Reservar entradas")

    # 3. Checkout: los datos del comprador vienen de su cuenta.
    web.esperar_ruta("/checkout")
    web.esperar_texto("Finaliza tu compra")
    assert web.campo("Nombre completo").get_attribute("value") == "Carlos Comprador"

    # 4. Paga con la tarjeta de prueba que el banco rechaza.
    web.pulsar("Probar tarjeta rechazada")
    web.captura("checkout-tarjeta-rechazada")
    web.pulsar("Pagar")

    # 5. El pedido queda pendiente de pago y se muestra el pago rechazado.
    web.esperar_ruta("/pedido/")
    web.esperar_texto("Pendiente de pago")
    web.esperar_texto("Rechazado")
    referencia = web.elementos("h1.font-mono")[0].text
    web.captura("pago-rechazado")

    # 6. Reintenta con una tarjeta valida desde la pagina del pedido.
    web.pulsar("Rellenar tarjeta de prueba válida")
    web.pulsar("Pagar")
    web.esperar_texto("¡Pago completado!")
    web.esperar_texto("Pagada")
    web.esperar_texto("Tus entradas (2)")
    codigos = [e.text for e in web.elementos("p.font-mono")]
    assert len(set(codigos)) == 2, f"Se esperaban 2 codigos de entrada distintos: {codigos}"
    web.captura("pago-completado")

    # 7. El pedido aparece en "Mis entradas".
    web.enlace("Mis entradas", dentro="//header")
    web.esperar_ruta("/cuenta")
    web.esperar_texto(referencia)
    web.captura("mis-entradas")


def test_el_checkout_valida_la_tarjeta(web, evento):
    web.iniciar_sesion_como("CLIENT")
    _elegir_entradas(web, evento, 1)
    web.pulsar("Reservar entradas")
    web.esperar_texto("Finaliza tu compra")

    # Sin datos de tarjeta no se crea el pedido.
    web.pulsar("Pagar")
    web.esperar_texto("Número de tarjeta inválido")
    assert web.ruta.startswith("/checkout")

    web.escribir("Número de tarjeta", "4242 4242 4242 4242")
    web.escribir("Titular de la tarjeta", "ANA GARCIA")
    web.escribir("Mes", "12")
    web.escribir("Año", "2001")
    web.escribir("CVV", "123")
    web.pulsar("Pagar")
    web.esperar_texto("Año de caducidad inválido")
    assert web.ruta.startswith("/checkout")


def test_no_se_pueden_elegir_mas_entradas_del_maximo_por_pedido(web, evento):
    web.abrir(f"/eventos/{evento['slug']}")
    web.esperar_texto("máx. 4")
    for _ in range(4):
        web.pulsar_etiqueta("Añadir una entrada")
    boton_mas = web.driver.find_element("xpath", "//button[@aria-label='Añadir una entrada']")
    assert not boton_mas.is_enabled(), "Con 4 entradas el boton + debe quedar desactivado"


def test_reservar_sin_sesion_pide_iniciar_sesion(web, evento):
    _elegir_entradas(web, evento, 1)
    web.pulsar("Reservar entradas")
    web.esperar_ruta("/acceder")
    web.esperar_texto("Inicia sesión")
