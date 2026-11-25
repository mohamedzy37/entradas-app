"""Flujo de compra: reserva de stock, pago, entradas y control de acceso."""

from concurrent.futures import ThreadPoolExecutor

from ayudas_api import (
    TARJETA_RECHAZADA,
    auth,
    disponibles,
    nuevo_cliente_http,
    pago,
    pedido,
)


def test_comprar_sin_sesion_devuelve_401(api, crear_evento):
    evento = crear_evento()
    assert api.post("/api/orders", json=pedido(evento["tipo"]["id"])).status_code == 401


def test_flujo_completo_de_compra(api, crear_evento, usuario_nuevo, token_manager):
    evento = crear_evento(stock=5, precio_cents=2500)
    token = usuario_nuevo["token"]

    # 1. Reserva: el pedido queda PENDING y el stock se descuenta.
    respuesta = api.post("/api/orders", headers=auth(token), json=pedido(evento["tipo"]["id"], 2))
    assert respuesta.status_code == 201, respuesta.text
    orden = respuesta.json()["data"]
    assert orden["status"] == "PENDING"
    assert orden["totalCents"] == 2 * 2500
    assert orden["expiresAt"] is not None
    assert disponibles(api, evento) == 3

    # 2. Pago rechazado: el pedido sigue pendiente y no se emiten entradas.
    respuesta = api.post(
        f"/api/orders/{orden['reference']}/pay", headers=auth(token), json=pago(TARJETA_RECHAZADA)
    )
    assert respuesta.status_code == 402
    assert respuesta.json()["approved"] is False
    assert respuesta.json()["data"]["order"]["status"] == "PENDING"
    assert respuesta.json()["data"]["order"]["tickets"] == []

    # 3. Pago aprobado: PAID y una entrada por unidad comprada.
    respuesta = api.post(f"/api/orders/{orden['reference']}/pay", headers=auth(token), json=pago())
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["approved"] is True
    assert cuerpo["data"]["order"]["status"] == "PAID"
    assert cuerpo["data"]["payment"]["cardLast4"] == "4242"
    entradas = cuerpo["data"]["order"]["tickets"]
    assert len(entradas) == 2
    assert len({e["code"] for e in entradas}) == 2, "Los codigos de entrada deben ser unicos"

    # 4. No se puede pagar dos veces ni cancelar un pedido pagado.
    assert api.post(f"/api/orders/{orden['reference']}/pay", headers=auth(token), json=pago()).status_code == 409
    assert api.post(f"/api/orders/{orden['reference']}/cancel", headers=auth(token)).status_code == 409

    # 5. El pedido aparece en "mis pedidos".
    mis_pedidos = api.get("/api/orders", headers=auth(token)).json()["data"]
    assert orden["reference"] in {p["reference"] for p in mis_pedidos}

    # 6. Validacion en puerta: consulta publica y check-in solo para gestores.
    codigo = entradas[0]["code"]
    consulta = api.get(f"/api/tickets/{codigo}")
    assert consulta.status_code == 200
    assert consulta.json()["data"]["status"] == "VALID"

    assert api.post(f"/api/tickets/{codigo}/check-in", headers=auth(token)).status_code == 403
    check_in = api.post(f"/api/tickets/{codigo}/check-in", headers=auth(token_manager))
    assert check_in.status_code == 200, check_in.text
    assert check_in.json()["data"]["status"] == "USED"
    # La misma entrada no puede entrar dos veces.
    assert api.post(f"/api/tickets/{codigo}/check-in", headers=auth(token_manager)).status_code == 409


def test_cancelar_un_pedido_devuelve_el_stock(api, crear_evento, usuario_nuevo):
    evento = crear_evento(stock=5)
    token = usuario_nuevo["token"]
    orden = api.post("/api/orders", headers=auth(token), json=pedido(evento["tipo"]["id"], 3)).json()["data"]
    assert disponibles(api, evento) == 2

    respuesta = api.post(f"/api/orders/{orden['reference']}/cancel", headers=auth(token))
    assert respuesta.status_code == 200
    assert respuesta.json()["data"]["status"] == "CANCELLED"
    assert disponibles(api, evento) == 5

    # Un pedido cancelado no se puede pagar.
    assert api.post(f"/api/orders/{orden['reference']}/pay", headers=auth(token), json=pago()).status_code == 409


def test_no_se_puede_pagar_ni_cancelar_el_pedido_de_otro(api, crear_evento, usuario_nuevo, token_cliente):
    evento = crear_evento()
    orden = api.post(
        "/api/orders", headers=auth(usuario_nuevo["token"]), json=pedido(evento["tipo"]["id"])
    ).json()["data"]

    ajeno = auth(token_cliente)  # otro cliente distinto
    assert api.post(f"/api/orders/{orden['reference']}/pay", headers=ajeno, json=pago()).status_code == 403
    assert api.post(f"/api/orders/{orden['reference']}/cancel", headers=ajeno).status_code == 403
    # Tampoco aparece en sus pedidos.
    pedidos_ajenos = api.get("/api/orders", headers=ajeno).json()["data"]
    assert orden["reference"] not in {p["reference"] for p in pedidos_ajenos}


def test_no_se_puede_superar_el_maximo_por_pedido(api, crear_evento, token_cliente):
    evento = crear_evento(stock=20, max_por_pedido=4)
    respuesta = api.post("/api/orders", headers=auth(token_cliente), json=pedido(evento["tipo"]["id"], 5))
    assert respuesta.status_code == 400
    assert disponibles(api, evento) == 20


def test_no_se_venden_mas_entradas_de_las_que_hay(api, crear_evento, token_cliente):
    evento = crear_evento(stock=3, max_por_pedido=4)
    respuesta = api.post("/api/orders", headers=auth(token_cliente), json=pedido(evento["tipo"]["id"], 4))
    assert respuesta.status_code == 409
    assert disponibles(api, evento) == 3


def test_compras_simultaneas_no_provocan_sobreventa(api, crear_evento, token_cliente):
    """Condicion de carrera: 15 compras a la vez sobre 5 entradas.

    El backend bloquea la fila del tipo de entrada (SELECT ... FOR UPDATE), asi
    que exactamente 5 compras deben tener exito y el resto recibir 409.
    """
    evento = crear_evento(stock=5, max_por_pedido=1)
    tipo_id = evento["tipo"]["id"]

    def comprar(_: int) -> int:
        with nuevo_cliente_http() as cliente:
            return cliente.post("/api/orders", headers=auth(token_cliente), json=pedido(tipo_id)).status_code

    with ThreadPoolExecutor(max_workers=15) as hilos:
        codigos = list(hilos.map(comprar, range(15)))

    assert codigos.count(201) == 5, f"Respuestas: {codigos}"
    assert codigos.count(409) == 10, f"Respuestas: {codigos}"
    assert disponibles(api, evento) == 0


def test_tipo_de_entrada_inexistente(api, token_cliente):
    respuesta = api.post("/api/orders", headers=auth(token_cliente), json=pedido("no-existe"))
    assert respuesta.status_code == 400


def test_datos_de_pago_invalidos(api, crear_evento, token_cliente):
    evento = crear_evento()
    orden = api.post("/api/orders", headers=auth(token_cliente), json=pedido(evento["tipo"]["id"])).json()["data"]
    for campo, valor in [("cardNumber", "1234-abcd"), ("cvv", "12"), ("expiryMonth", 13), ("expiryYear", 2000)]:
        datos = pago() | {campo: valor}
        respuesta = api.post(f"/api/orders/{orden['reference']}/pay", headers=auth(token_cliente), json=datos)
        assert respuesta.status_code == 400, f"{campo}={valor!r}: {respuesta.text}"
    api.post(f"/api/orders/{orden['reference']}/cancel", headers=auth(token_cliente))


def test_entrada_inexistente_devuelve_404(api):
    assert api.get("/api/tickets/NO-EXISTE-123").status_code == 404
