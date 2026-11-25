"""Registro de usuarios e inicio de sesion."""

import pytest

from ayudas_api import REFRESH_COOKIE, auth, cookies_set, email_aleatorio, login


def test_registro_crea_un_cliente_y_abre_sesion(api):
    email = email_aleatorio()
    respuesta = api.post(
        "/api/auth/register",
        json={"name": "Nuevo Usuario", "email": email, "password": "Segura1234"},
    )
    assert respuesta.status_code == 201, respuesta.text
    datos = respuesta.json()["data"]
    assert datos["user"]["email"] == email
    assert datos["user"]["role"] == "CLIENT"
    assert datos["tokenType"] == "Bearer"
    assert datos["accessToken"]
    assert datos["expiresIn"] == 15 * 60


def test_el_refresh_va_en_cookie_segura_y_no_en_el_cuerpo(api):
    respuesta = api.post(
        "/api/auth/register",
        json={"name": "Nuevo Usuario", "email": email_aleatorio(), "password": "Segura1234"},
    )
    assert respuesta.status_code == 201
    assert "refreshToken" not in respuesta.json()["data"]

    cookie = cookies_set(respuesta)[REFRESH_COOKIE]
    assert cookie["value"]
    assert cookie.get("httponly") == "true", "La cookie del refresh debe ser HttpOnly"
    assert cookie.get("secure") == "true", "La cookie del refresh debe ser Secure"
    assert cookie.get("samesite", "").lower() == "strict"
    assert cookie.get("path") == "/api/auth"


def test_el_registro_publico_no_permite_elegir_rol(api):
    respuesta = api.post(
        "/api/auth/register",
        json={
            "name": "Intento de escalada",
            "email": email_aleatorio(),
            "password": "Segura1234",
            "role": "ADMIN",
        },
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["data"]["user"]["role"] == "CLIENT"


def test_no_se_puede_registrar_dos_veces_el_mismo_email(api, usuario_nuevo):
    respuesta = api.post(
        "/api/auth/register",
        json={"name": "Duplicado", "email": usuario_nuevo["email"], "password": "Segura1234"},
    )
    assert respuesta.status_code == 409


@pytest.mark.parametrize(
    "datos, campo",
    [
        ({"name": "Ana", "email": "no-es-un-email", "password": "Segura1234"}, "email"),
        ({"name": "Ana", "email": "a@ejemplo.com", "password": "corta1"}, "password"),
        ({"name": "Ana", "email": "a@ejemplo.com", "password": "sinnumeros"}, "password"),
        ({"name": "Ana", "email": "a@ejemplo.com", "password": "12345678"}, "password"),
        ({"name": "A", "email": "a@ejemplo.com", "password": "Segura1234"}, "name"),
    ],
)
def test_registro_valida_los_datos(api, datos, campo):
    respuesta = api.post("/api/auth/register", json=datos)
    assert respuesta.status_code == 400
    error = respuesta.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(detalle["path"] == campo for detalle in error["details"])


@pytest.mark.parametrize("rol", ["ADMIN", "MANAGER", "CLIENT"])
def test_login_de_los_tres_roles(api, rol):
    respuesta = login(api, rol)
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()["data"]
    assert datos["user"]["role"] == rol
    assert REFRESH_COOKIE in cookies_set(respuesta)


def test_login_es_insensible_a_mayusculas_en_el_email(api, usuario_nuevo):
    respuesta = login(api, usuario_nuevo["email"].upper(), usuario_nuevo["password"])
    assert respuesta.status_code == 200


def test_login_con_contrasena_incorrecta(api, usuario_nuevo):
    respuesta = login(api, usuario_nuevo["email"], "Incorrecta123")
    assert respuesta.status_code == 401
    assert REFRESH_COOKIE not in cookies_set(respuesta)


def test_login_no_revela_si_el_usuario_existe(api, usuario_nuevo):
    existe = login(api, usuario_nuevo["email"], "Incorrecta123")
    no_existe = login(api, email_aleatorio(), "Incorrecta123")
    assert existe.status_code == no_existe.status_code == 401
    assert existe.json()["error"]["message"] == no_existe.json()["error"]["message"]


def test_me_devuelve_el_usuario_del_token(api, usuario_nuevo):
    respuesta = api.get("/api/auth/me", headers=auth(usuario_nuevo["token"]))
    assert respuesta.status_code == 200
    assert respuesta.json()["data"]["user"]["email"] == usuario_nuevo["email"]


def test_me_sin_token_devuelve_401(api):
    assert api.get("/api/auth/me").status_code == 401
