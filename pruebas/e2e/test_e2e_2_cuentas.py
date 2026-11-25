"""Registro, inicio y cierre de sesion, y persistencia de la sesion (refresh JWT)."""

import pytest

from ayudas_web import CREDENCIALES, email_aleatorio


def test_registro_de_un_usuario_nuevo(web):
    email = email_aleatorio()
    web.registrarse("Lucía Prueba", email, "Selenium1234")
    web.esperar_sesion()
    # Ya ha iniciado sesion: la cabecera muestra su nombre y "Mis entradas".
    web.esperar_texto("Lucía")
    assert web.hay_enlace("Mis entradas", dentro="//header")
    # Es un CLIENT: no ve el panel de gestion.
    assert not web.hay_enlace("Gestión", dentro="//header")
    web.captura("registrado")


@pytest.mark.parametrize(
    "password, confirmacion, mensaje",
    [
        ("corta1", None, "al menos 8 caracteres"),
        ("sinnumeros", None, "letras y números"),
        ("Selenium1234", "Distinta1234", "no coinciden"),
    ],
)
def test_el_registro_valida_la_contrasena(web, password, confirmacion, mensaje):
    web.registrarse("Usuario Prueba", email_aleatorio(), password, confirmacion)
    web.esperar_texto(mensaje)
    assert web.ruta.startswith("/registro")


def test_no_se_puede_registrar_un_email_existente(web):
    web.registrarse("Ana Repetida", CREDENCIALES["CLIENT"][0], "Selenium1234")
    web.esperar_texto("Ya existe una cuenta")
    assert web.ruta.startswith("/registro")


def test_login_con_contrasena_incorrecta_muestra_error(web):
    web.abrir("/acceder")
    web.escribir("Correo electrónico", CREDENCIALES["CLIENT"][0])
    web.escribir("Contraseña", "NoEsLaClave99")
    web.pulsar("Entrar")
    web.esperar_texto("Credenciales invalidas")
    assert web.hay_enlace("Acceder", dentro="//header")
    web.captura("login-incorrecto")


def test_login_y_logout(web):
    web.iniciar_sesion_como("CLIENT")
    web.esperar_ruta("/")
    web.captura("sesion-iniciada")
    web.cerrar_sesion()
    assert not web.hay_enlace("Mis entradas", dentro="//header")


def test_la_sesion_sobrevive_a_recargar_la_pagina(web):
    """El access token vive en memoria: al recargar se pierde y el frontend
    pide uno nuevo con la cookie HttpOnly del refresh (sesion sin estado)."""
    web.iniciar_sesion_como("CLIENT")
    web.driver.refresh()
    web.esperar_sesion()
    web.abrir("/cuenta")  # ruta protegida, carga completa de la pagina
    web.esperar_texto("Salir")
    assert web.ruta.startswith("/cuenta")


def test_tras_cerrar_sesion_no_se_recupera_al_recargar(web):
    web.iniciar_sesion_como("CLIENT")
    web.cerrar_sesion()
    web.driver.refresh()
    web.esperar_texto("Acceder")
    assert web.no_aparece("Salir")
    # Las rutas protegidas vuelven a pedir inicio de sesion.
    web.abrir("/cuenta")
    web.esperar_ruta("/acceder")


def test_ruta_protegida_redirige_al_login_y_vuelve_tras_entrar(web):
    web.abrir("/cuenta")
    web.esperar_ruta("/acceder")
    web.escribir("Correo electrónico", CREDENCIALES["CLIENT"][0])
    web.escribir("Contraseña", CREDENCIALES["CLIENT"][1])
    web.pulsar("Entrar")
    web.esperar_ruta("/cuenta")
    web.esperar_sesion()
