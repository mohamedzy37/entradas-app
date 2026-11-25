"""Lo que ve y puede hacer cada rol: CLIENT, MANAGER y ADMIN."""


def test_un_cliente_no_entra_en_el_panel_de_gestion(web):
    web.iniciar_sesion_como("CLIENT")
    assert not web.hay_enlace("Gestión", dentro="//header")
    # Aunque escriba la URL a mano, la ruta esta protegida por rol.
    web.abrir("/gestion")
    web.esperar_texto("Acceso restringido")
    assert web.no_aparece("Panel de gestión", espera=1)
    web.captura("cliente-sin-acceso")


def test_un_visitante_sin_sesion_va_al_login_desde_gestion(web):
    web.abrir("/gestion")
    web.esperar_ruta("/acceder")


def test_el_gestor_ve_el_panel_sin_la_gestion_de_usuarios(web):
    web.iniciar_sesion_como("MANAGER")
    web.esperar_texto("MANAGER")  # insignia del rol en la cabecera
    web.enlace("Gestión", dentro="//header")
    web.esperar_texto("Panel de gestión")
    for pestana in ["Resumen", "Pedidos", "Eventos"]:
        assert web.hay_boton(pestana), f"Falta la pestaña {pestana}"
    assert not web.hay_boton("Usuarios"), "Un MANAGER no debe gestionar usuarios"
    web.pulsar("Pedidos")
    web.esperar_texto("Referencia")
    web.captura("panel-gestor")


def test_el_admin_gestiona_usuarios(web):
    web.iniciar_sesion_como("ADMIN")
    web.esperar_texto("ADMIN")
    web.enlace("Gestión", dentro="//header")
    web.esperar_texto("Panel de gestión")
    web.pulsar("Usuarios")
    web.escribir_por_placeholder("Buscar por nombre o email", "gestor@entradas.com")
    web.esperar_texto("gestor@entradas.com")
    web.captura("panel-admin-usuarios")


def test_el_gestor_registra_el_acceso_de_una_entrada(web, preparacion, evento):
    codigo = preparacion.entradas_pagadas(evento, cantidad=1)[0]

    web.iniciar_sesion_como("MANAGER")
    web.enlace("Validar entrada", dentro="//header")
    web.esperar_texto("Validar una entrada")

    # Consulta: la entrada es valida.
    web.escribir("Código de la entrada", codigo.lower())  # el validador normaliza a mayusculas
    web.pulsar("Consultar estado")
    web.esperar_texto(codigo)
    web.esperar_texto("Válida")
    web.captura("entrada-valida")

    # Check-in en la puerta.
    web.pulsar("Registrar acceso")
    web.esperar_texto("Acceso registrado correctamente.")
    web.esperar_texto("Usada")
    web.captura("acceso-registrado")

    # La misma entrada no puede entrar dos veces.
    web.pulsar("Registrar acceso")
    web.esperar_texto("ya fue utilizada")
    web.captura("entrada-repetida")


def test_un_cliente_puede_consultar_pero_no_registrar_accesos(web, preparacion, evento):
    codigo = preparacion.entradas_pagadas(evento, cantidad=1)[0]
    web.iniciar_sesion_como("CLIENT")
    web.abrir("/validar")
    web.escribir("Código de la entrada", codigo)
    web.pulsar("Consultar estado")
    web.esperar_texto("Válida")
    assert not web.hay_boton("Registrar acceso")


def test_codigo_de_entrada_inexistente(web):
    web.abrir("/validar")
    web.escribir("Código de la entrada", "NO-EXISTE-0000")
    web.pulsar("Consultar estado")
    web.esperar_texto("Entrada no encontrada")
